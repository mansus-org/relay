"""The events repositories: SQLAlchemy statements over the events and rsvps tables."""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relay.contexts.events.domain.event import Event
from relay.contexts.events.domain.ports import EventRepository, RsvpRepository
from relay.contexts.events.domain.rsvp import AlreadyRsvpedError, Rsvp
from relay.contexts.events.infrastructure.models import EventModel, RsvpModel


def upcoming_statement(cells: list[str], after: datetime | None, limit: int) -> Select:
    """One page of what is on, soonest first.

    `IN` leaves out the events that named no locality at all, which is what keeps them
    out of every locality's list. With `after` None the page has no floor and the past
    is on it. Built here rather than inline so the query the repository runs is the
    query a test can put under EXPLAIN.
    """
    statement = select(EventModel).where(EventModel.location_cell.in_(cells))
    if after is not None:
        statement = statement.where(EventModel.starts_at > after.astimezone(UTC))
    return statement.order_by(EventModel.starts_at.asc()).limit(limit)


class SqlAlchemyEventRepository(EventRepository):
    """Events in the same session as the unit of work that handed it over."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> Event | None:
        row = await self._session.get(EventModel, id)
        return row.to_domain() if row is not None else None

    async def add(self, entity: Event) -> None:
        self._session.add(EventModel.from_domain(entity))

    async def page_upcoming(
        self, *, cells: Iterable[str], after: datetime | None, limit: int
    ) -> list[Event]:
        statement = upcoming_statement(list(cells), after, limit)
        rows = (await self._session.execute(statement)).scalars()
        return [row.to_domain() for row in rows]


class SqlAlchemyRsvpRepository(RsvpRepository):
    """Who is going to what, in the same session as the event it is going to."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> Rsvp | None:
        row = await self._session.get(RsvpModel, id)
        return row.to_domain() if row is not None else None

    async def add(self, entity: Rsvp) -> None:
        """Takes the place, or says it was already taken.

        The unique pair is what makes that true even when two requests arrive at the
        same moment: one of them is held back by the database rather than by a read
        that happened a moment too early.
        """
        try:
            self._session.add(RsvpModel.from_domain(entity))
            await self._session.flush()
        except IntegrityError as error:
            raise AlreadyRsvpedError(
                f"{entity.member_id} is already going to {entity.event_id}."
            ) from error

    async def by_member(self, *, event_id: UUID, member_id: UUID) -> Rsvp | None:
        row = (
            await self._session.execute(
                select(RsvpModel)
                .where(RsvpModel.event_id == event_id, RsvpModel.member_id == member_id)
                .limit(1)
            )
        ).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def delete(self, rsvp: Rsvp) -> None:
        """Gives the place back. The row is this session's or the delete is a no-op."""
        await self._session.execute(
            delete(RsvpModel).where(
                RsvpModel.event_id == rsvp.event_id, RsvpModel.member_id == rsvp.member_id
            )
        )

    async def count_for(self, event_id: UUID) -> int:
        return (
            await self._session.execute(
                select(func.count()).select_from(RsvpModel).where(RsvpModel.event_id == event_id)
            )
        ).scalar_one()

    async def counts_for(self, event_ids: Sequence[UUID]) -> dict[UUID, int]:
        if not event_ids:
            return {}
        rows = await self._session.execute(
            select(RsvpModel.event_id, func.count())
            .where(RsvpModel.event_id.in_(event_ids))
            .group_by(RsvpModel.event_id)
        )
        return {event_id: count for event_id, count in rows}
