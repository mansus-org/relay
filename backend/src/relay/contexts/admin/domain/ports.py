"""What moderation asks of the database, without saying what it is made of."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from relay.contexts.admin.domain.members import MemberSummary
from relay.contexts.admin.domain.moderation_log import ModerationLog
from relay.contexts.auth.domain.invite import Invite
from relay.contexts.posts.domain.post import ModerationStatus, Post
from relay.shared.domain import Repository


class ModerationLogRepository(Repository[ModerationLog, int]):
    """The audit trail: rows are added and read, and nothing else ever happens to them."""

    @abstractmethod
    async def page(
        self,
        *,
        post_id: UUID | None = None,
        community_id: UUID | None = None,
        target_user_id: int | None = None,
        actor_id: int | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[ModerationLog], int]:
        """Newest first, narrowed by whatever was asked for, with the total behind the filter."""

    @abstractmethod
    async def ai_decisions(self, post_ids: Sequence[UUID]) -> dict[UUID, dict]:
        """The newest machine decision for each of these posts, for the queue to show beside them.

        A post nobody has run past a model is simply absent from the answer. That matters:
        an empty answer is not a decision to approve, and a queue that invented one would
        have an admin nodding along to an opinion nobody held.
        """


class ModeratedPostRepository(ABC):
    """Posts, as moderation sees them: every one of them, whatever its status.

    Deliberately not the posts context's repository, which only ever hands back posts
    that are still up. That is exactly wrong for a queue whose whole job begins where a
    reader's feed stops. It reads the same table the posts context owns, the way the
    communities context already reads it for a feed.
    """

    @abstractmethod
    async def page(
        self, *, status: ModerationStatus | None, limit: int, offset: int
    ) -> tuple[list[Post], int]:
        """Newest first, and the total under the same filter."""

    @abstractmethod
    async def get(self, post_id: UUID) -> Post:
        """One post, whatever its status. Raises PostNotFoundError when there is none."""

    @abstractmethod
    async def set_status(self, post: Post, *, to: ModerationStatus, was: ModerationStatus) -> bool:
        """Move a post to `to`, only if it is still `was`, and say whether it moved.

        The second condition is the lock. Two admins who open the same card and both
        click remove get one True and one False, and the one who gets False is told the
        state instead of going away believing a decision that was already made.
        """


class MemberRepository(ABC):
    """Accounts, for the people who run a Relay."""

    @abstractmethod
    async def page(
        self,
        *,
        search: str | None,
        is_admin: bool | None,
        deactivated: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MemberSummary], int]:
        """Accounts, newest first, with the total under the same filter."""

    @abstractmethod
    async def get(self, member_id: int) -> MemberSummary | None:
        """One account, or nothing when there is no such id."""

    @abstractmethod
    async def set_deactivated(self, member_id: int, *, at: datetime, on: bool) -> bool:
        """Switch one account off, or back on, and say whether it was there to switch.

        One column and one timestamp, written as a compare-and-set on the state it is
        supposed to be in, so doing it twice cannot write a second timestamp over the
        first and lose the moment it actually happened.
        """

    @abstractmethod
    async def end_sessions(self, member_id: int, *, at: datetime) -> int:
        """Cut off every session that account has running, and say how many there were."""


class InvitationRepository(ABC):
    """Invites, made and pulled back by whoever runs the place."""

    @abstractmethod
    async def add(self, invite: Invite) -> None:
        """Write a new invite. Afterwards it has the id the database gave it."""

    @abstractmethod
    async def get(self, invite_id: int) -> Invite | None:
        """One invite by row number, not by token: this is the list, not the link."""

    @abstractmethod
    async def page(self, *, state: str | None, limit: int, offset: int) -> tuple[list[Invite], int]:
        """Newest first, and the total under the same filter.

        `state` is one of the three words `Invite.state` answers with, and nothing else:
        the filter and the field in the response are the same question asked the same way.
        """

    @abstractmethod
    async def revoke(self, invite: Invite, *, at: datetime) -> bool:
        """Close an invite that is still open, and say whether it was still open."""
