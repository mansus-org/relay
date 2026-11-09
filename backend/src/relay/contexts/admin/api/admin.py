"""The admin API: the moderation queue, the members, the invites.

Every route here sits behind `AdminUser`, so the two refusals are always the same pair:
401 when nobody is signed in and 403 when somebody who is not in charge tried it anyway.
Nothing under this path hands out admin - `users.is_admin` is set by whoever runs the
database, and there is no route anywhere that writes it.

The shapes are flat and every list carries `total`, because the screen on the other side
of this is a table with a page count under it.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from relay.container import Container
from relay.contexts.admin.application import (
    DeactivateMember,
    Deactivation,
    GetMember,
    IssueInvite,
    ListInvites,
    ListMembers,
    MemberDetail,
    ModerationQueue,
    ReadModerationLog,
    ReadPost,
    RestoreMember,
    ReviewPost,
    RevokeInvite,
)
from relay.contexts.admin.domain.errors import (
    AlreadyInThatStateError,
    InviteNotFoundError,
    MemberCannotBeDeactivatedError,
    MemberNotFoundError,
)
from relay.contexts.admin.domain.members import MemberSummary
from relay.contexts.admin.domain.moderation_log import ModerationLog
from relay.contexts.admin.domain.review import ReviewAction
from relay.contexts.auth.api.dependencies import AdminUser
from relay.contexts.auth.domain.errors import InviteNoteTooLongError
from relay.contexts.auth.domain.invite import Invite
from relay.contexts.posts.domain.post import ModerationStatus, Post, PostNotFoundError
from relay.shared.api.dependencies import get_container
from relay.shared.domain import ValidationError

router = APIRouter(tags=["admin"])

# A page of a table an admin reads. The default is generous enough that the first screen
# is the whole queue for a small Relay, and the ceiling keeps one request from being a
# dump of the database.
DEFAULT_PAGE = 50
MAX_PAGE = 200

Limit = Annotated[int, Query(ge=1, le=MAX_PAGE, description="How many to take.")]
Offset = Annotated[int, Query(ge=0, description="How many to skip.")]


# --- the shapes -----------------------------------------------------------------------


class ModeratedPostResponse(BaseModel):
    """One post as moderation sees it: the whole thing, plus where it stands.

    `author_id` is an id and not a name, because the queue is an admin's working list and
    the name is one lookup away on the members screen. The body comes whole: nobody can
    decide about a post from its first line.

    `ai_decision` is what a model said about this post, if anything ever did, in the
    machine's own shape - this API passes it through rather than explaining it. Null means
    no machine has looked, which is not the same as one that found nothing.
    """

    id: str
    author_id: str
    body: str
    created_at: datetime
    moderation_status: str
    community_id: str | None = None
    location_cell: str | None = None
    parent_id: str | None = None
    ai_decision: dict | None = None

    @classmethod
    def from_domain(cls, post: Post, *, ai_decision: dict | None = None) -> "ModeratedPostResponse":
        return cls(
            id=str(post.id),
            author_id=str(post.author_id),
            body=post.body,
            created_at=post.created_at,
            moderation_status=post.moderation_status.value,
            community_id=str(post.community_id) if post.community_id else None,
            location_cell=post.location_cell,
            parent_id=str(post.parent_id) if post.parent_id else None,
            ai_decision=ai_decision,
        )


class QueuePageResponse(BaseModel):
    posts: list[ModeratedPostResponse]
    total: int


class ReviewRequest(BaseModel):
    """Why, on the occasions a decision needs a why.

    Removing needs a reason and approving does not: a removal takes something away from a
    person who will ask for it, an approval is a mark that somebody looked. The rule is the
    domain's and not this schema's, so the refusal is a sentence about the decision instead
    of a complaint about a missing key.
    """

    reason: str = ""


class LogEntryResponse(BaseModel):
    """One line of the trail. Read-only, everywhere, forever.

    `trigger` says who made the call. `actor_id` is null when it was not a person: a model
    has no account, and inventing one to fill the column would be the first lie in a table
    whose whole job is telling the truth.
    """

    id: int
    actor_id: int | None
    action: str
    trigger: str
    post_id: str | None = None
    community_id: str | None = None
    target_user_id: int | None = None
    reason: str
    ai_decision: dict | None = None
    created_at: datetime

    @classmethod
    def from_domain(cls, entry: ModerationLog) -> "LogEntryResponse":
        return cls(
            id=entry.require_id(),
            actor_id=entry.actor_id,
            action=entry.action.value,
            trigger=entry.trigger.value,
            post_id=str(entry.post_id) if entry.post_id else None,
            community_id=str(entry.community_id) if entry.community_id else None,
            target_user_id=entry.target_user_id,
            reason=entry.reason,
            ai_decision=entry.ai_decision,
            created_at=entry.created_at,
        )


class LogPageResponse(BaseModel):
    entries: list[LogEntryResponse]
    total: int


class MemberResponse(BaseModel):
    """One account, and whether it is still allowed to be one."""

    id: int
    username: str
    display_name: str
    is_admin: bool
    created_at: datetime
    deactivated_at: datetime | None = None
    is_deactivated: bool

    @classmethod
    def from_domain(cls, member: MemberSummary) -> "MemberResponse":
        return cls(
            id=member.id,
            username=member.username,
            display_name=member.display_name,
            is_admin=member.is_admin,
            created_at=member.created_at,
            deactivated_at=member.deactivated_at,
            is_deactivated=member.is_deactivated,
        )


class MemberPageResponse(BaseModel):
    members: list[MemberResponse]
    total: int


class MemberDetailResponse(BaseModel):
    """One account and everything moderation already did to it."""

    member: MemberResponse
    history: list[LogEntryResponse]


class MemberActionResponse(BaseModel):
    """The account after the change, and how many sessions it cost.

    The count is in the answer because it is the part an admin cannot see from the
    account itself: switching someone off is also throwing out every device they are
    signed in on, right now.
    """

    member: MemberResponse
    sessions_ended: int


class InviteResponse(BaseModel):
    """One invite, token included.

    The token is the whole secret and the reason an admin asked for the invite, so it
    comes back in the answer rather than being written down somewhere else. Anyone who
    holds it can join with it, once.

    `url` is the same thing already in `token`, already assembled into the link you would
    actually send somebody, so no client has to know how a URL is put together. It is null
    when the deployment never said what host it is on (`BASE_URL`), because a link to a
    guessed host is worse than no link at all.
    """

    id: int
    token: str
    url: str | None = None
    note: str | None = None
    state: str
    created_at: datetime | None = None
    used_at: datetime | None = None
    used_by_id: int | None = None
    revoked_at: datetime | None = None

    @classmethod
    def from_domain(cls, invite: Invite, *, base_url: str | None = None) -> "InviteResponse":
        token = str(invite.token)
        return cls(
            id=invite.require_id(),
            token=token,
            url=join_invite_link(base_url, token),
            note=invite.note,
            state=invite.state,
            created_at=invite.created_at,
            used_at=invite.used_at,
            used_by_id=invite.used_by_id,
            revoked_at=invite.revoked_at,
        )


class InvitePageResponse(BaseModel):
    invites: list[InviteResponse]
    total: int


class IssueInviteRequest(BaseModel):
    """Who this invite is for. A line of text, and nothing else."""

    note: str | None = None


# --- the dependencies -----------------------------------------------------------------


def get_moderation_queue(
    container: Annotated[Container, Depends(get_container)],
) -> ModerationQueue:
    return container.get_moderation_queue()


def get_read_post(container: Annotated[Container, Depends(get_container)]) -> ReadPost:
    return container.get_moderated_post()


def get_review_post(
    container: Annotated[Container, Depends(get_container)],
) -> ReviewPost:
    return container.get_review_post()


def get_moderation_log(
    container: Annotated[Container, Depends(get_container)],
) -> ReadModerationLog:
    return container.get_moderation_log()


def get_list_members(
    container: Annotated[Container, Depends(get_container)],
) -> ListMembers:
    return container.get_list_members()


def get_get_member(container: Annotated[Container, Depends(get_container)]) -> GetMember:
    return container.get_get_member()


def get_deactivate_member(
    container: Annotated[Container, Depends(get_container)],
) -> DeactivateMember:
    return container.get_deactivate_member()


def get_restore_member(
    container: Annotated[Container, Depends(get_container)],
) -> RestoreMember:
    return container.get_restore_member()


def get_list_invites(
    container: Annotated[Container, Depends(get_container)],
) -> ListInvites:
    return container.get_list_invites()


def get_issue_invite(
    container: Annotated[Container, Depends(get_container)],
) -> IssueInvite:
    return container.get_issue_invite()


def get_revoke_invite(
    container: Annotated[Container, Depends(get_container)],
) -> RevokeInvite:
    return container.get_revoke_invite()


# --- the refusals ---------------------------------------------------------------------


def _gone(error: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


def _conflict(error: Exception) -> HTTPException:
    return HTTPException(status_code=409, detail=str(error))


def join_invite_link(base_url: str | None, token: str) -> str | None:
    """The link to send somebody: `<BASE_URL>/join?token=<token>`.

    `BASE_URL` is written either way - a bare host, or one with its scheme already on it -
    because whoever sets it is copy-pasting from a browser bar and will not think about the
    difference. With nothing configured there is no answer, and `None` is the honest one:
    the token on its own still works, and a link to a host somebody guessed at gets an
    invite sent to a server that is not this one.
    """
    if not base_url:
        return None
    root = base_url.strip().rstrip("/")
    if not root:
        return None
    if "://" not in root:
        root = f"https://{root}"
    return f"{root}/join?token={quote(token, safe='')}"


# --- the queue ------------------------------------------------------------------------


@router.get(
    "/admin/queue",
    response_model=QueuePageResponse,
    summary="What needs looking at",
    description=(
        "Posts newest first, by default the ones nobody has decided about yet. Pass "
        "`status` to see the approved ones or the removed ones instead; leave it out "
        "for the pending queue. `total` counts everything under the filter, not the "
        "page. Admin only."
    ),
    responses={401: {"description": "No access token."}, 403: {"description": "Not an admin."}},
)
async def read_queue(
    _: AdminUser,
    use_case: Annotated[ModerationQueue, Depends(get_moderation_queue)],
    status: Annotated[
        ModerationStatus | None,
        Query(description="Only posts in this state. Omit it for the pending queue."),
    ] = None,
    limit: Limit = DEFAULT_PAGE,
    offset: Offset = 0,
) -> QueuePageResponse:
    wanted = ModerationStatus.PENDING if status is None else status
    page = await use_case.execute(status=wanted, limit=limit, offset=offset)
    return QueuePageResponse(
        posts=[
            ModeratedPostResponse.from_domain(post, ai_decision=page.ai_decisions.get(post.id))
            for post in page.posts
        ],
        total=page.total,
    )


@router.get(
    "/admin/queue/{post_id}",
    response_model=ModeratedPostResponse,
    summary="One post, whatever its state",
    description=("The whole post, including the ones a reader can no longer see. Admin only."),
    responses={401: {"description": "No access token."}, 403: {"description": "Not an admin."}},
)
async def read_one(
    post_id: UUID,
    _: AdminUser,
    use_case: Annotated[ReadPost, Depends(get_read_post)],
) -> ModeratedPostResponse:
    try:
        found = await use_case.execute(post_id=post_id)
    except PostNotFoundError as error:
        raise _gone(error) from error
    return ModeratedPostResponse.from_domain(found.post, ai_decision=found.ai_decision)


async def _review(
    use_case: ReviewPost,
    *,
    post_id: UUID,
    action: ReviewAction,
    reason: str,
    admin_id: int,
) -> ModeratedPostResponse:
    """Run one decision, and turn the refusals into the codes this API already uses."""
    try:
        post = await use_case.execute(
            post_id=post_id,
            action=action,
            reason=reason,
            admin_id=admin_id,
        )
    except PostNotFoundError as error:
        raise _gone(error) from error
    except AlreadyInThatStateError as error:
        raise _conflict(error) from error
    except ValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ModeratedPostResponse.from_domain(post)


def _refusals(bad_request: str) -> dict[int | str, dict[str, Any]]:
    """What a decision route turns down, written once because all three say the same.

    The 400 is the one that differs, so it is the one handed in.
    """
    return {
        400: {"description": bad_request},
        401: {"description": "No access token."},
        403: {"description": "Not an admin."},
        404: {"description": "No post with that id."},
        409: {"description": "That is already what the post is."},
    }


@router.post(
    "/admin/queue/{post_id}/approve",
    response_model=ModeratedPostResponse,
    summary="Approve a post",
    description=(
        "Puts a post nobody has decided about up for everyone. A `reason` is welcome and "
        "not needed: an approval is the mark that somebody looked. It writes a line to the "
        "moderation log with who did it, and approving something already approved is a 409, "
        "so two admins on the same card cannot decide it twice. Admin only."
    ),
    responses=_refusals("A reason too long to be one."),
)
async def approve_post(
    post_id: UUID,
    admin: AdminUser,
    use_case: Annotated[ReviewPost, Depends(get_review_post)],
    payload: ReviewRequest | None = None,
) -> ModeratedPostResponse:
    return await _review(
        use_case,
        post_id=post_id,
        action=ReviewAction.APPROVE,
        reason=payload.reason if payload else "",
        admin_id=admin.require_id(),
    )


@router.post(
    "/admin/queue/{post_id}/remove",
    response_model=ModeratedPostResponse,
    summary="Remove a post",
    description=(
        "Takes a post down: it stops reaching readers, and it stays in the database, because "
        "the record of what was said is worth more than the silence that follows. `reason` "
        "is required - the person whose post it was will ask, and the log is where the "
        "answer lives. Removing something already removed is a 409. Admin only."
    ),
    responses=_refusals("A removal with no reason, or a reason too long to be one."),
)
async def remove_post(
    post_id: UUID,
    admin: AdminUser,
    use_case: Annotated[ReviewPost, Depends(get_review_post)],
    payload: ReviewRequest | None = None,
) -> ModeratedPostResponse:
    return await _review(
        use_case,
        post_id=post_id,
        action=ReviewAction.REMOVE,
        reason=payload.reason if payload else "",
        admin_id=admin.require_id(),
    )


@router.post(
    "/admin/queue/{post_id}/restore",
    response_model=ModeratedPostResponse,
    summary="Put a removed post back",
    description=(
        "The way back from a removal, and it only works on one: the post comes back as "
        "approved rather than straight into the queue, because it has already been looked at "
        "once. Admin only."
    ),
    responses=_refusals("A reason too long to be one."),
)
async def restore_post(
    post_id: UUID,
    admin: AdminUser,
    use_case: Annotated[ReviewPost, Depends(get_review_post)],
    payload: ReviewRequest | None = None,
) -> ModeratedPostResponse:
    return await _review(
        use_case,
        post_id=post_id,
        action=ReviewAction.RESTORE,
        reason=payload.reason if payload else "",
        admin_id=admin.require_id(),
    )


@router.get(
    "/admin/log",
    response_model=LogPageResponse,
    summary="What moderation did",
    description=(
        "The trail, newest first. Narrow it to one post, one community, one account, or "
        "one admin. Nothing here is ever edited or deleted, so this is also the answer to "
        "`who removed this, and when`. Admin only."
    ),
    responses={401: {"description": "No access token."}, 403: {"description": "Not an admin."}},
)
async def read_log(
    _: AdminUser,
    use_case: Annotated[ReadModerationLog, Depends(get_moderation_log)],
    post_id: Annotated[UUID | None, Query(description="Only decisions about this post.")] = None,
    community_id: Annotated[
        UUID | None, Query(description="Only decisions about posts in this community.")
    ] = None,
    target_user_id: Annotated[
        int | None, Query(description="Only decisions about this account.")
    ] = None,
    actor_id: Annotated[int | None, Query(description="Only decisions this admin made.")] = None,
    limit: Limit = DEFAULT_PAGE,
    offset: Offset = 0,
) -> LogPageResponse:
    entries, total = await use_case.execute(
        post_id=post_id,
        community_id=community_id,
        target_user_id=target_user_id,
        actor_id=actor_id,
        limit=limit,
        offset=offset,
    )
    return LogPageResponse(entries=[LogEntryResponse.from_domain(e) for e in entries], total=total)


# --- the members ----------------------------------------------------------------------


@router.get(
    "/admin/members",
    response_model=MemberPageResponse,
    summary="Everyone with an account",
    description=(
        "Newest accounts first. `search` matches a part of the username or the display "
        "name, case does not matter. `admin` and `deactivated` narrow it to the people who "
        "run this Relay, or to the ones that are switched off. Admin only."
    ),
    responses={401: {"description": "No access token."}, 403: {"description": "Not an admin."}},
)
async def read_members(
    _: AdminUser,
    use_case: Annotated[ListMembers, Depends(get_list_members)],
    search: Annotated[
        str | None, Query(description="A part of a username or a display name.")
    ] = None,
    admin: Annotated[bool | None, Query(description="Only admins, or only everybody else.")] = None,
    deactivated: Annotated[
        bool | None, Query(description="Only switched-off accounts, or only live ones.")
    ] = None,
    limit: Limit = DEFAULT_PAGE,
    offset: Offset = 0,
) -> MemberPageResponse:
    members, total = await use_case.execute(
        search=search, is_admin=admin, deactivated=deactivated, limit=limit, offset=offset
    )
    return MemberPageResponse(
        members=[MemberResponse.from_domain(member) for member in members], total=total
    )


@router.get(
    "/admin/members/{member_id}",
    response_model=MemberDetailResponse,
    summary="One account, and what moderation did to it",
    description=("The account, and every line of the trail that names it. Admin only."),
    responses={401: {"description": "No access token."}, 403: {"description": "Not an admin."}},
)
async def read_member(
    member_id: int,
    _: AdminUser,
    use_case: Annotated[GetMember, Depends(get_get_member)],
) -> MemberDetailResponse:
    try:
        detail: MemberDetail = await use_case.execute(member_id=member_id)
    except MemberNotFoundError as error:
        raise _gone(error) from error
    return MemberDetailResponse(
        member=MemberResponse.from_domain(detail.member),
        history=[LogEntryResponse.from_domain(entry) for entry in detail.history],
    )


@router.delete(
    "/admin/members/{member_id}",
    response_model=MemberActionResponse,
    summary="Switch an account off",
    description=(
        "The account stops signing in and every session it had running is thrown out, so "
        "the devices holding them are signed out at their next request. Their posts stay "
        "up and their username stays taken: this is a pause with a timestamp on it, and "
        "`POST /admin/members/{member_id}/restore` undoes it exactly. `reason` goes in the "
        "query, because a delete carries no body to explain itself in; it is required, and "
        "it is logged next to your name. Neither your own account nor another "
        "admin's can be switched off. Admin only."
    ),
    responses={
        401: {"description": "No access token."},
        403: {"description": "Not an admin."},
        404: {"description": "No account with that id."},
        409: {
            "description": "Already off, or it is your own account, or it belongs to another admin."
        },
    },
)
async def deactivate_member(
    member_id: int,
    admin: AdminUser,
    use_case: Annotated[DeactivateMember, Depends(get_deactivate_member)],
    reason: Annotated[
        str | None, Query(description="Why. It goes in the log next to your name.")
    ] = None,
) -> MemberActionResponse:
    try:
        done: Deactivation = await use_case.execute(
            admin=admin, member_id=member_id, reason=reason or ""
        )
    except MemberNotFoundError as error:
        raise _gone(error) from error
    except (AlreadyInThatStateError, MemberCannotBeDeactivatedError) as error:
        raise _conflict(error) from error
    except ValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return MemberActionResponse(
        member=MemberResponse.from_domain(done.member), sessions_ended=done.sessions_ended
    )


@router.post(
    "/admin/members/{member_id}/restore",
    response_model=MemberResponse,
    summary="Put an account back",
    description=(
        "Clears the switch again. They can sign in with the same credentials; the sessions "
        "that were thrown out do not come back, because they were thrown out for a reason. "
        "Admin only."
    ),
    responses={
        401: {"description": "No access token."},
        403: {"description": "Not an admin."},
        404: {"description": "No account with that id."},
        409: {"description": "It was not switched off."},
    },
)
async def restore_member(
    member_id: int,
    admin: AdminUser,
    use_case: Annotated[RestoreMember, Depends(get_restore_member)],
    payload: ReviewRequest | None = None,
) -> MemberResponse:
    try:
        member = await use_case.execute(
            admin=admin, member_id=member_id, reason=payload.reason if payload else ""
        )
    except MemberNotFoundError as error:
        raise _gone(error) from error
    except AlreadyInThatStateError as error:
        raise _conflict(error) from error
    return MemberResponse.from_domain(member)


# --- the invites ----------------------------------------------------------------------


@router.get(
    "/admin/invites",
    response_model=InvitePageResponse,
    summary="Every invite handed out",
    description=(
        "Newest first. `state` is `open`, `used` or `revoked`; leave it out for all three. "
        "An open invite is one still waiting to be redeemed, and its token is here so the "
        "person who made it can still send it. Admin only."
    ),
    responses={401: {"description": "No access token."}, 403: {"description": "Not an admin."}},
)
async def read_invites(
    _: AdminUser,
    container: Annotated[Container, Depends(get_container)],
    use_case: Annotated[ListInvites, Depends(get_list_invites)],
    state: Annotated[
        Literal["open", "used", "revoked"] | None,
        Query(description="Only invites in this state."),
    ] = None,
    limit: Limit = DEFAULT_PAGE,
    offset: Offset = 0,
) -> InvitePageResponse:
    invites, total = await use_case.execute(state=state, limit=limit, offset=offset)
    return InvitePageResponse(
        invites=[
            InviteResponse.from_domain(invite, base_url=container.settings.invite_base_url)
            for invite in invites
        ],
        total=total,
    )


@router.post(
    "/admin/invites",
    response_model=InviteResponse,
    status_code=201,
    summary="Make an invite",
    description=(
        "One invite, redeemable by the first person who registers with it and by nobody "
        "else. `note` is who it is set aside for, so the list is not a row of anonymous "
        "strings. The answer carries the token and the link to send, already put together. "
        "Relay is invite-only: this is the only way in. Admin only."
    ),
    responses={
        400: {"description": "The note was too long to be a note."},
        401: {"description": "No access token."},
        403: {"description": "Not an admin."},
    },
)
async def issue_invite(
    admin: AdminUser,
    container: Annotated[Container, Depends(get_container)],
    use_case: Annotated[IssueInvite, Depends(get_issue_invite)],
    payload: IssueInviteRequest | None = None,
) -> InviteResponse:
    try:
        invite = await use_case.execute(admin=admin, note=payload.note if payload else None)
    except (InviteNoteTooLongError, ValidationError) as error:
        # The length rule lives with the invite, because it is the invite's rule; this is
        # where it turns into a 400 rather than a stack trace.
        raise HTTPException(status_code=400, detail=str(error)) from error
    return InviteResponse.from_domain(invite, base_url=container.settings.invite_base_url)


@router.delete(
    "/admin/invites/{invite_id}",
    response_model=InviteResponse,
    summary="Take an invite back",
    description=(
        "Closes an invite nobody has used yet, so the link stops working. An invite that "
        "was already spent cannot be taken back - the person it let in is already in. "
        "Admin only."
    ),
    responses={
        401: {"description": "No access token."},
        403: {"description": "Not an admin."},
        404: {"description": "No invite with that id."},
        409: {"description": "It was already used or already revoked."},
    },
)
async def revoke_invite(
    invite_id: int,
    container: Annotated[Container, Depends(get_container)],
    _: AdminUser,
    use_case: Annotated[RevokeInvite, Depends(get_revoke_invite)],
) -> InviteResponse:
    try:
        invite = await use_case.execute(invite_id=invite_id)
    except InviteNotFoundError as error:
        raise _gone(error) from error
    except AlreadyInThatStateError as error:
        raise _conflict(error) from error
    return InviteResponse.from_domain(invite, base_url=container.settings.invite_base_url)
