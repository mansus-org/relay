"""The HTTP edge of the communities context: found one, find one, join one, read its feed.

The shapes here are the ones the mobile screens already expect, field for field:
`mobile/src/infrastructure/http/community-repository.ts` reads `id`, `name`,
`description`, `member_count`, `location_cell`, `radius_km`, `allow_pseudonyms`,
`is_member`, `created_by` and `created_at`, sends `cell` on the nearby list and on a
join, and reads a feed as `posts` and `next_cursor`.

The feed also carries the community's events, in `events`. That is the one place in this
column where a communities route borrows a use case from the events context, and it is a
door on purpose: the events context publishes "what has this community lately filed", and
this route asks it, because the rules about which events a reader is allowed to see — the
locality ring, what membership does and does not open — belong to events and are not
something to write out twice here. The events array is paged by nothing: it is the newest
ten filings, and the calendar is the surface that pages.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from relay.container import Container
from relay.contexts.communities.application import (
    CreateCommunity,
    GetCommunity,
    GetCommunityFeed,
    JoinCommunity,
    ListCommunities,
)
from relay.contexts.communities.domain import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PSEUDONYM_LENGTH,
    Community,
    CommunityFeedPage,
    CommunityNotFoundError,
    CommunityPost,
    NotAMemberError,
    OutOfRangeError,
)
from relay.contexts.events.api.events import EventResponse
from relay.contexts.events.application import GetCommunityAnnouncements
from relay.contexts.events.domain.cells import CellError as EventCellError
from relay.contexts.events.domain.community import CommunityNotFoundError as NoCommunity
from relay.contexts.events.domain.listing import EventDetails
from relay.contexts.posts.domain.cells import CellError
from relay.contexts.posts.domain.feed import Cursor, InvalidCursorError
from relay.contexts.posts.domain.post import Post
from relay.shared.api.dependencies import get_container
from relay.shared.domain import ConflictError, ValidationError

router = APIRouter(tags=["communities"])


def _bearer(authorization: str | None) -> UUID | None:
    """The id sent as a bearer token, or None when nothing usable was sent."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return UUID(token)
    except ValueError:
        return None


async def get_author_id(authorization: Annotated[str | None, Header()] = None) -> UUID:
    """Who is writing. The one place this context insists on being told.

    PLACEHOLDER UNTIL RELY-87 LANDS, in exactly the way
    `relay.contexts.posts.api.posts.get_author_id` is one: there are no accounts yet,
    so the bearer value is taken to be the reader's id. At rebase time this and
    `get_reader_id` are deleted and the endpoints' `Depends` point at RELY-87's auth
    dependency instead. Nothing else in this file changes.
    """
    reader = _bearer(authorization)
    if reader is None:
        raise HTTPException(
            status_code=401, detail="Relay has no accounts yet: send your id as a bearer token."
        )
    return reader


async def get_reader_id(authorization: Annotated[str | None, Header()] = None) -> UUID | None:
    """Who is reading, if they chose to say. Every read here works without it.

    A token that is not an id is treated as no token rather than a 401: `is_member` is
    a nicety, and a nearby list that refused to load because a stale token was still in
    the app would be a worse answer than one that says "not a member of these".
    """
    return _bearer(authorization)


def display_name(person_id: UUID) -> str:
    """The name shown for a person until RELY-87's user records replace it."""
    return f"Member {str(person_id)[:8]}"


class PersonResponse(BaseModel):
    """Somebody, by id and by the name to print beside it."""

    id: str
    name: str


class CommunityResponse(BaseModel):
    """One community, as the list and the detail screen both draw it."""

    id: str
    name: str
    description: str
    member_count: int
    location_cell: str | None = None
    radius_km: float | None = None
    allow_pseudonyms: bool
    is_member: bool
    created_by: PersonResponse
    created_at: datetime

    @classmethod
    def from_domain(cls, community: Community) -> "CommunityResponse":
        return cls(
            id=str(community.id),
            name=community.name,
            description=community.description,
            member_count=community.member_count,
            location_cell=community.location_cell,
            radius_km=community.radius_km,
            allow_pseudonyms=community.allow_pseudonyms,
            is_member=community.is_member,
            created_by=PersonResponse(
                id=str(community.created_by), name=display_name(community.created_by)
            ),
            created_at=community.created_at,
        )


class CommunityPostResponse(BaseModel):
    """One post in a community, shaped like a post anywhere else on Relay.

    The author's name is what this community calls them, which is the whole reason a
    community's feed is a different endpoint from the locality one: the same post says
    "Member 3f2a" in the street and "the baker" in the community.
    """

    id: str
    author: PersonResponse
    body: str
    created_at: datetime
    location_cell: str | None = None

    @classmethod
    def from_domain(cls, entry: CommunityPost) -> "CommunityPostResponse":
        post: Post = entry.post
        return cls(
            id=str(post.id),
            author=PersonResponse(
                id=str(post.author_id),
                name=entry.pseudonym or display_name(post.author_id),
            ),
            body=post.body,
            created_at=post.created_at,
            location_cell=post.location_cell,
        )


class CommunityFeedResponse(BaseModel):
    """Newest first. `next_cursor` is null once there is nothing older to ask for.

    `events` is what the community has lately filed, newest filed first — a plan is an
    announcement, so it is here beside the posts that announced it and stays until
    something newer pushes it off. It is its own list and not posts with a flag on them,
    because a plan is paged by when it happens and a post by when it was written, and
    two things with two clocks cannot share one cursor. Empty when no `cell` was sent:
    a plan nobody can reach is not something to show them.
    """

    posts: list[CommunityPostResponse]
    next_cursor: str | None = None
    events: list[EventResponse] = []

    @classmethod
    def from_domain(
        cls, page: CommunityFeedPage, events: Sequence[EventDetails] = ()
    ) -> "CommunityFeedResponse":
        return cls(
            posts=[CommunityPostResponse.from_domain(entry) for entry in page.posts],
            next_cursor=str(page.next_cursor) if page.next_cursor is not None else None,
            events=[EventResponse.from_domain(details) for details in events],
        )


class NewCommunityRequest(BaseModel):
    """`location_cell` is the cell the community is anchored at, not the founder's.

    Leaving it out is allowed and founds a community about a subject instead of a
    place: it exists and is joinable, and it is in nobody's nearby list. `radius_km`
    is read with it and ignored without it, and a cell that is not a cell is refused
    rather than stored, because an anchor no reach test can measure from anchors
    nothing.
    """

    name: str
    description: str = ""
    location_cell: str | None = None
    radius_km: float | None = None
    allow_pseudonyms: bool = False


class JoinCommunityRequest(BaseModel):
    """`cell` is where the reader is standing, and the only proof a local community wants.

    A pseudonym is refused for a community that does not allow them rather than quietly
    dropped: someone who asked not to be named and was named anyway is worse off than
    one who got an error.
    """

    cell: str | None = None
    pseudonym: str | None = None


def get_create_community(
    container: Annotated[Container, Depends(get_container)],
) -> CreateCommunity:
    return container.get_create_community()


def get_list_communities(
    container: Annotated[Container, Depends(get_container)],
) -> ListCommunities:
    return container.get_list_communities()


def get_community_use_case(
    container: Annotated[Container, Depends(get_container)],
) -> GetCommunity:
    return container.get_community()


def get_community_feed_use_case(
    container: Annotated[Container, Depends(get_container)],
) -> GetCommunityFeed:
    return container.get_community_feed()


def get_join_community(
    container: Annotated[Container, Depends(get_container)],
) -> JoinCommunity:
    return container.get_join_community()


def get_community_announcements(
    container: Annotated[Container, Depends(get_container)],
) -> GetCommunityAnnouncements:
    """The events half of the feed, borrowed from the context that owns events."""
    return container.get_community_announcements()


def community_id_of(raw: str) -> UUID:
    """The id in the path, or a 404 for anything that is not one.

    Refusing a malformed id with a 404 rather than a 422 is deliberate:
    `/communities/joined` is the mobile app's next endpoint and is not built yet, and
    the app reads a 404 there as "no communities yet" and carries on. Answering 422
    instead would turn a route that does not exist into an error on someone's screen.
    """
    try:
        return UUID(raw)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="No community with that id.") from error


@router.get(
    "/communities",
    response_model=list[CommunityResponse],
    summary="The communities whose locality you are standing in",
    description=(
        "Every community anchored within its own radius of `cell`, which is the reader's "
        "current H3 resolution-8 cell. A community with no locality is not here: it is "
        "about a subject, and the way into one of those is a link someone shared. Send "
        "your id as a bearer token and each one says whether you are already a member."
    ),
    responses={400: {"description": "That is not a cell a feed reads at."}},
)
async def list_communities(
    cell: Annotated[str, Query(description="Your current H3 resolution-8 cell.")],
    use_case: Annotated[ListCommunities, Depends(get_list_communities)],
    reader: Annotated[UUID | None, Depends(get_reader_id)],
) -> list[CommunityResponse]:
    try:
        found = await use_case.execute(cell=cell, viewer=reader)
    except CellError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return [CommunityResponse.from_domain(community) for community in found]


@router.post(
    "/communities",
    response_model=CommunityResponse,
    status_code=201,
    summary="Found a community",
    description=(
        "Saves a community and returns it. At most "
        f"{MAX_NAME_LENGTH} characters of name and {MAX_DESCRIPTION_LENGTH} of "
        "description. The founder is not joined to it: they asked for it to exist, and "
        "joining is a separate press of a button."
    ),
    responses={
        400: {
            "description": f"The name was empty or over {MAX_NAME_LENGTH} characters, "
            "the radius was outside 1 to 50 km, or `location_cell` was not a cell."
        },
        401: {"description": "No bearer token to found it as."},
    },
)
async def create_community(
    payload: NewCommunityRequest,
    author_id: Annotated[UUID, Depends(get_author_id)],
    use_case: Annotated[CreateCommunity, Depends(get_create_community)],
) -> CommunityResponse:
    try:
        community = await use_case.execute(
            created_by=author_id,
            name=payload.name,
            description=payload.description,
            location_cell=payload.location_cell,
            radius_km=payload.radius_km,
            allow_pseudonyms=payload.allow_pseudonyms,
        )
    except (ValidationError, CellError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return CommunityResponse.from_domain(community)


@router.get(
    "/communities/{community_id}",
    response_model=CommunityResponse,
    summary="One community",
    description=(
        "A community by id, with its member count. Public whether or not you are a "
        "member: a community you cannot read before joining is one you cannot decide "
        "whether to join."
    ),
    responses={404: {"description": "No community with that id."}},
)
async def read_community(
    community_id: str,
    use_case: Annotated[GetCommunity, Depends(get_community_use_case)],
    reader: Annotated[UUID | None, Depends(get_reader_id)],
) -> CommunityResponse:
    try:
        community = await use_case.execute(community_id_of(community_id), viewer=reader)
    except CommunityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return CommunityResponse.from_domain(community)


@router.get(
    "/communities/{community_id}/feed",
    response_model=CommunityFeedResponse,
    summary="A community's posts, newest first",
    description=(
        "Posts its members filed into it, and the events it has lately filed beside "
        "them. For its members only: send your id as a "
        "bearer token and you get the feed, and without one you get a 403 telling you "
        "to join. Paged by `created_at`: pass `next_cursor` back as `cursor` for the "
        "older pages. An author who joined under a pseudonym is named by it here and "
        f"nowhere else; a pseudonym is at most {MAX_PSEUDONYM_LENGTH} characters. "
        "Send `cell` to be told which events you can actually get to: without it the "
        "events list comes back empty."
    ),
    responses={
        400: {"description": "That cursor or that cell was not something this feed takes."},
        401: {"description": "No bearer token to read as."},
        403: {"description": "You are not a member of this community."},
        404: {"description": "No community with that id."},
    },
)
async def read_community_feed(
    community_id: str,
    use_case: Annotated[GetCommunityFeed, Depends(get_community_feed_use_case)],
    announcements: Annotated[GetCommunityAnnouncements, Depends(get_community_announcements)],
    reader: Annotated[UUID | None, Depends(get_reader_id)],
    cursor: Annotated[
        str | None, Query(description="The next_cursor from the page before this one.")
    ] = None,
    cell: Annotated[
        str | None,
        Query(description="Where the reader is standing, for the events beside the posts."),
    ] = None,
    radius_km: Annotated[
        float | None, Query(description="How far that reader reaches. Ten kilometres by default.")
    ] = None,
) -> CommunityFeedResponse:
    id = community_id_of(community_id)
    try:
        page = await use_case.execute(
            community_id=id,
            viewer=reader,
            cursor=Cursor.parse(cursor) if cursor is not None else None,
        )
    except InvalidCursorError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except CommunityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except NotAMemberError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    # The events are read after the posts on purpose: the posts are what settle whether
    # this reader may be here at all, and a community only announces its plans to people
    # who are allowed to read what it wrote. They fail on their own terms too — a cell
    # that is not a cell is a 400 about the cell, and not about the cursor.
    filed: Sequence[EventDetails] = ()
    if cell is not None:
        try:
            filed = await announcements.execute(community_id=id, cell=cell, radius_km=radius_km)
        except EventCellError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except NoCommunity as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
    return CommunityFeedResponse.from_domain(page, filed)


@router.post(
    "/communities/{community_id}/join",
    response_model=CommunityResponse,
    summary="Join a community",
    description=(
        "Adds you to the community's member list and returns it, counted. A community "
        "anchored to a place wants `cell`: if your cell is outside its radius you get a "
        "403 and no membership, because a locality community of people who cannot walk "
        "to it is not one. Joining one you are already in is not an error and changes "
        "nothing, not your pseudonym. A pseudonym is what you are called in this "
        "community and nowhere else."
    ),
    responses={
        400: {
            "description": "The cell was not one a feed reads at, or the pseudonym was "
            f"over {MAX_PSEUDONYM_LENGTH} characters or not allowed here."
        },
        401: {"description": "No bearer token to join as."},
        403: {
            "description": "You are too far from this community to join it, or it needs "
            "a cell to tell."
        },
        404: {"description": "No community with that id."},
        409: {"description": "Another join for you got there first."},
    },
)
async def join_community(
    community_id: str,
    use_case: Annotated[JoinCommunity, Depends(get_join_community)],
    author_id: Annotated[UUID, Depends(get_author_id)],
    payload: JoinCommunityRequest | None = None,
) -> CommunityResponse:
    try:
        community = await use_case.execute(
            community_id=community_id_of(community_id),
            user_id=author_id,
            cell=payload.cell if payload else None,
            pseudonym=payload.pseudonym if payload else None,
        )
    except CommunityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except OutOfRangeError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (ValidationError, CellError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return CommunityResponse.from_domain(community)
