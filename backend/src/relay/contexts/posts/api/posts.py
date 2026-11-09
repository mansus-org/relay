"""The HTTP edge of the posts context: say something, read your locality, look one up.

The shapes here are the ones the mobile screens already expect, field for field:
`mobile/src/infrastructure/http/post-dto.ts` reads `author` as an object and tolerates
`reactions` and `reply_count` being absent, and `feed-repository.ts` sends
`cell`, `radius` and `cursor` and reads `posts` and `next_cursor`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from relay.container import Container
from relay.contexts.posts.application import CreatePost, GetFeed, GetPost
from relay.contexts.posts.domain.cells import DEFAULT_RADIUS_KM, CellError
from relay.contexts.posts.domain.feed import Cursor, FeedPage, InvalidCursorError
from relay.contexts.posts.domain.post import MAX_BODY_LENGTH, Post, PostNotFoundError
from relay.shared.api.dependencies import get_container
from relay.shared.domain import ValidationError

router = APIRouter(tags=["posts"])


async def get_author_id(authorization: Annotated[str | None, Header()] = None) -> UUID:
    """Who is writing. The one place this context asks for identity.

    PLACEHOLDER UNTIL RELY-87 LANDS. There are no accounts yet, so there is no token
    to verify: the bearer value is taken to be the author's id and anything that is
    not an id is refused. At rebase time this function is deleted and the two
    endpoints' `Depends(get_author_id)` points at RELY-87's auth dependency instead.
    Nothing else in this file changes, and `GET /feed` and `GET /posts/{id}` stay
    public either way.
    """
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401, detail="Relay has no accounts yet: send your id as a bearer token."
        )
    try:
        return UUID(token)
    except ValueError as error:
        raise HTTPException(
            status_code=401, detail="That bearer token is not a user id yet."
        ) from error


def display_name(author_id: UUID) -> str:
    """The name shown for an author until RELY-87's user records replace it."""
    return f"Member {str(author_id)[:8]}"


class AuthorResponse(BaseModel):
    """Who wrote it. Mobile renders `author.name` and keeps the id for its cache."""

    id: str
    name: str


class ReactionResponse(BaseModel):
    """One reaction tally. Reactions are RELY-90's; the shape is here so the client
    has something real to read once they exist."""

    emoji: str
    count: int
    mine: bool = False


class PostResponse(BaseModel):
    id: str
    author: AuthorResponse
    body: str
    created_at: datetime
    location_cell: str | None = None
    reactions: list[ReactionResponse] = []
    reply_count: int = 0

    @classmethod
    def from_domain(cls, post: Post) -> "PostResponse":
        return cls(
            id=str(post.id),
            author=AuthorResponse(id=str(post.author_id), name=display_name(post.author_id)),
            body=post.body,
            created_at=post.created_at,
            location_cell=post.location_cell,
        )


class FeedResponse(BaseModel):
    """Newest first. `next_cursor` is null once there is nothing older to ask for."""

    posts: list[PostResponse]
    next_cursor: str | None = None

    @classmethod
    def from_domain(cls, page: FeedPage) -> "FeedResponse":
        return cls(
            posts=[PostResponse.from_domain(post) for post in page.posts],
            next_cursor=str(page.next_cursor) if page.next_cursor is not None else None,
        )


class NewPostRequest(BaseModel):
    """`location_cell` is the writer's own cell, so a post lands in their locality.

    Leaving it out is allowed and means the post reaches no locality feed; Relay does
    not guess a locality from anything else. Sending one that is not a cell is refused
    rather than stored, for the same reason.
    """

    body: str
    location_cell: str | None = None
    community_id: UUID | None = None


def get_create_post(
    container: Annotated[Container, Depends(get_container)],
) -> CreatePost:
    return container.get_create_post()


def get_feed_use_case(
    container: Annotated[Container, Depends(get_container)],
) -> GetFeed:
    return container.get_feed()


def get_post_use_case(
    container: Annotated[Container, Depends(get_container)],
) -> GetPost:
    return container.get_post()


@router.post(
    "/posts",
    response_model=PostResponse,
    status_code=201,
    summary="Say something",
    description=(
        "Saves a post and returns it. At most 500 characters of text. "
        "`location_cell` has to be a real resolution-8 H3 cell, because a post filed "
        "anywhere else is a post no locality feed will ever read."
    ),
    responses={
        400: {
            "description": f"The body was empty or over {MAX_BODY_LENGTH} characters, "
            "or `location_cell` was not a resolution-8 H3 cell."
        },
        401: {"description": "No bearer token to write as."},
    },
)
async def create_post(
    payload: NewPostRequest,
    author_id: Annotated[UUID, Depends(get_author_id)],
    use_case: Annotated[CreatePost, Depends(get_create_post)],
) -> PostResponse:
    try:
        post = await use_case.execute(
            author_id=author_id,
            body=payload.body,
            location_cell=payload.location_cell,
            community_id=payload.community_id,
        )
    except (ValidationError, CellError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return PostResponse.from_domain(post)


@router.get(
    "/feed",
    response_model=FeedResponse,
    summary="This locality's posts, newest first",
    description=(
        "Posts said within `radius` km of `cell`, which is the reader's current H3 "
        "resolution-8 cell. Paged by `created_at`: pass `next_cursor` back as `cursor` "
        "for the older pages. Public, like every read in Relay."
    ),
    responses={400: {"description": "The cell or the radius was not usable."}},
)
async def read_feed(
    cell: Annotated[str, Query(description="Your current H3 resolution-8 cell.")],
    use_case: Annotated[GetFeed, Depends(get_feed_use_case)],
    radius: Annotated[
        float,
        Query(description="How far out to read, in km: between 0 and 25."),
    ] = DEFAULT_RADIUS_KM,
    cursor: Annotated[
        str | None, Query(description="The next_cursor from the page before this one.")
    ] = None,
) -> FeedResponse:
    try:
        page = await use_case.execute(
            cell=cell,
            radius_km=radius,
            cursor=Cursor.parse(cursor) if cursor is not None else None,
        )
    except (CellError, InvalidCursorError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return FeedResponse.from_domain(page)


@router.get(
    "/posts/{post_id}",
    response_model=PostResponse,
    summary="One post",
    description="A post by id. A removed one is reported as gone, the way a feed treats it.",
    responses={404: {"description": "No post with that id."}},
)
async def read_post(
    post_id: UUID,
    use_case: Annotated[GetPost, Depends(get_post_use_case)],
) -> PostResponse:
    try:
        post = await use_case.execute(post_id)
    except PostNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return PostResponse.from_domain(post)
