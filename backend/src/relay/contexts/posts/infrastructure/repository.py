"""The posts and reactions repositories: SQLAlchemy statements over their tables."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, case, delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relay.contexts.posts.domain.ports import PostRepository, ReactionRepository
from relay.contexts.posts.domain.post import ModerationStatus, Post
from relay.contexts.posts.domain.reaction import AlreadyReactedError, Reaction, ReactionTally
from relay.contexts.posts.infrastructure.models import PostModel, ReactionModel


def feed_statement(cells: list[str], before: datetime | None, limit: int) -> Select:
    """One page of a locality feed, newest first.

    `IN` leaves out the posts that named no locality at all, which is what keeps them
    out of every locality feed. Answers are left out too: a reply carries its parent's
    locality so a thread stays in one place, but the feed is a list of things people
    said, not of everything said. Built here rather than inline so the query the
    repository runs is the query a test can put under EXPLAIN.
    """
    statement = (
        select(PostModel)
        .where(PostModel.location_cell.in_(cells))
        .where(PostModel.moderation_status != ModerationStatus.REMOVED.value)
        .where(PostModel.parent_id.is_(None))
        .order_by(PostModel.created_at.desc())
        .limit(limit)
    )
    if before is not None:
        # Compared in UTC, the one zone the column is written in. SQLite keeps no offset
        # of its own, so a page asked for from another zone would otherwise be read as
        # that zone's wall clock and start at the wrong instant.
        statement = statement.where(PostModel.created_at < before.astimezone(UTC))
    return statement


def replies_statement(post_id: UUID) -> Select:
    """The one query that opens a thread: one post's replies, in the order they were
    said, so a client reads a conversation the way it happened.

    Built here for the same reason as the feed's: so a test can put it under EXPLAIN.
    """
    return (
        select(PostModel)
        .where(PostModel.parent_id == post_id)
        .where(PostModel.moderation_status != ModerationStatus.REMOVED.value)
        .order_by(PostModel.created_at)
    )


def reply_counts_statement(post_ids: list[UUID]) -> Select:
    """How many replies each of these posts has, in one pass instead of one per post."""
    return (
        select(PostModel.parent_id, func.count().label("replies"))
        .where(PostModel.parent_id.in_(post_ids))
        .where(PostModel.moderation_status != ModerationStatus.REMOVED.value)
        .group_by(PostModel.parent_id)
    )


def reaction_tallies_statement(post_ids: list[UUID], viewer: UUID | None) -> Select:
    """Every emoji on each of these posts, counted, and whether `viewer` left one.

    One grouped query for a whole feed, because the alternative is a query per post.
    """
    left_by_viewer = func.sum(case((ReactionModel.user_id == viewer, 1), else_=0))
    return (
        select(
            ReactionModel.post_id,
            ReactionModel.emoji,
            func.count().label("total"),
            left_by_viewer.label("by_viewer"),
        )
        .where(ReactionModel.post_id.in_(post_ids))
        .group_by(ReactionModel.post_id, ReactionModel.emoji)
    )


class SqlAlchemyPostRepository(PostRepository):
    """Posts in the same session as the unit of work that handed it over."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> Post | None:
        row = await self._session.get(PostModel, id)
        return row.to_domain() if row is not None else None

    async def add(self, entity: Post) -> None:
        self._session.add(PostModel.from_domain(entity))

    async def page_neighbouring(
        self, *, cells: Iterable[str], before: datetime | None, limit: int
    ) -> list[Post]:
        statement = feed_statement(list(cells), before, limit)
        rows = (await self._session.execute(statement)).scalars()
        return [row.to_domain() for row in rows]

    async def replies_to(self, post_id: UUID) -> list[Post]:
        rows = (await self._session.execute(replies_statement(post_id))).scalars()
        return [row.to_domain() for row in rows]

    async def count_replies(self, post_ids: Iterable[UUID]) -> dict[UUID, int]:
        asked = list(post_ids)
        if not asked:
            return {}
        rows = (await self._session.execute(reply_counts_statement(asked))).all()
        counted = dict(rows)
        return {post_id: counted.get(post_id, 0) for post_id in asked}


def _is_one_reaction_already(error: IntegrityError) -> bool:
    """Whether a broken constraint is the one that says one person, one emoji, once.

    Only that one is translated: any other integrity error is a bug and has to stay
    one. The two databases name it differently - Postgres names the constraint, SQLite
    lists the columns - so both spellings are checked.
    """
    said = str(error.orig)
    return "uq_post_reactions_post_user_emoji" in said or (
        "post_reactions.post_id, post_reactions.user_id, post_reactions.emoji" in said
    )


class SqlAlchemyReactionRepository(ReactionRepository):
    """Reactions in the same session as the unit of work that handed it over."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, reaction: Reaction) -> None:
        self._session.add(ReactionModel.from_domain(reaction))
        try:
            # Written now rather than at commit, so the unique key gets the chance to
            # say what it knows. A use case checks for the reaction first and then
            # writes, and two taps of the same emoji a heartbeat apart both pass that
            # check; the one that arrives second has to be told it already happened,
            # not error out on a constraint nobody translated.
            await self._session.flush()
        except IntegrityError as error:
            if not _is_one_reaction_already(error):
                raise
            raise AlreadyReactedError(
                f"{reaction.user_id} has already reacted with {reaction.emoji}."
            ) from error

    async def get(self, *, post_id: UUID, user_id: UUID, emoji: str) -> Reaction | None:
        statement = select(ReactionModel).where(
            ReactionModel.post_id == post_id,
            ReactionModel.user_id == user_id,
            ReactionModel.emoji == emoji,
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def remove(self, *, post_id: UUID, user_id: UUID, emoji: str) -> bool:
        statement = delete(ReactionModel).where(
            ReactionModel.post_id == post_id,
            ReactionModel.user_id == user_id,
            ReactionModel.emoji == emoji,
        )
        # How many rows the delete took is the answer; the session types it as a Result.
        gone = cast("CursorResult[Any]", await self._session.execute(statement))
        return bool(gone.rowcount)

    async def tallies(
        self, post_ids: Iterable[UUID], *, viewer: UUID | None = None
    ) -> dict[UUID, tuple[ReactionTally, ...]]:
        asked = list(post_ids)
        if not asked:
            return {}
        rows = (await self._session.execute(reaction_tallies_statement(asked, viewer))).all()
        on_post: dict[UUID, list[ReactionTally]] = {post_id: [] for post_id in asked}
        for row in rows:
            on_post[row.post_id].append(
                ReactionTally(emoji=row.emoji, count=row.total, user_reacted=bool(row.by_viewer))
            )
        return {
            post_id: tuple(sorted(tallies, key=lambda tally: (-tally.count, tally.emoji)))
            for post_id, tallies in on_post.items()
        }
