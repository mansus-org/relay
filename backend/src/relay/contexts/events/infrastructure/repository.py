"""The events repositories: SQLAlchemy statements over the events and rsvps tables."""

from collections.abc import Iterable, Sequence
from datetime import UTC
from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relay.contexts.events.domain.event import Event
from relay.contexts.events.domain.listing import ListingStart
from relay.contexts.events.domain.ports import EventRepository, RsvpRepository
from relay.contexts.events.domain.rsvp import AlreadyRsvpedError, Rsvp
from relay.contexts.events.infrastructure.models import EventModel, RsvpModel


def listing_statement(cells: list[str], start: ListingStart, limit: int) -> Select:
    """One page of the listing, in the direction it was asked to be read.

    `IN` leaves out the events that named no locality at all, which is what keeps them
    out of every locality's list. The page is cut at a row and not at an instant, because
    hosts pick start times and a town's events all start at seven: a cut at "after
    seven" would drop every other event at seven that did not fit on the page.

    That cut is written as a range over the time with a tie-break at its edge, and not as
    `(starts_at, id) > (:wall, :seen)`. Both databases flatten the row pair into that
    range today, but the flattening is the planner's doing and not something to build
    on: a database that read a row pair as one value would have no range to use the index
    for, and would read the whole locality again for every page. Built here rather than
    inline so the query the repository runs is the query a test can put under EXPLAIN.
    """
    statement = select(EventModel).where(EventModel.location_cell.in_(cells))
    # The wall is bound in UTC however it arrived. `ListingStart` already keeps it there;
    # this is the second line, because on SQLite the column holds UTC text and a wall in
    # another zone would be compared as the words for that other clock.
    wall = start.at.astimezone(UTC)
    if start.seen_id is None:
        # A wall with no row yet, so what starts exactly at it belongs on the page.
        # Read backwards it does not: an event starting at the wall is starting now,
        # which is nobody's past. The two directions split time at the wall, and the
        # row sitting on it is on exactly one of them.
        statement = statement.where(
            EventModel.starts_at < wall if start.backwards else EventModel.starts_at >= wall
        )
    else:
        # A marker names a row already read, so this page is strictly past it either way:
        # everything on the far side of the wall, or at it and further along than that row.
        at_the_wall = (EventModel.starts_at == wall) & (
            EventModel.id < start.seen_id if start.backwards else EventModel.id > start.seen_id
        )
        # The wall is named twice on purpose. The tie-break already implies which side of
        # it the page is on, but a range said on its own is something a database can use
        # the index for, rather than reading the locality and filtering afterwards.
        up_to = EventModel.starts_at <= wall if start.backwards else EventModel.starts_at >= wall
        clear = EventModel.starts_at < wall if start.backwards else EventModel.starts_at > wall
        statement = statement.where(up_to, clear | at_the_wall)
    order = (
        (EventModel.starts_at.desc(), EventModel.id.desc())
        if start.backwards
        else (EventModel.starts_at.asc(), EventModel.id.asc())
    )
    return statement.order_by(*order).limit(limit)


class SqlAlchemyEventRepository(EventRepository):
    """Events in the same session as the unit of work that handed it over."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> Event | None:
        row = await self._session.get(EventModel, id)
        return row.to_domain() if row is not None else None

    async def add(self, entity: Event) -> None:
        self._session.add(EventModel.from_domain(entity))

    async def page_listing(
        self, *, cells: Iterable[str], start: ListingStart, limit: int
    ) -> list[Event]:
        statement = listing_statement(list(cells), start, limit)
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
