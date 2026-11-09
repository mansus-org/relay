"""The events and rsvps tables: what was planned comes back, and the listing filters."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import h3
import pytest
from sqlalchemy import Select, func, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.events.application.rsvp_event import RsvpEvent
from relay.contexts.events.domain.event import Event
from relay.contexts.events.domain.listing import ListingStart
from relay.contexts.events.domain.rsvp import AlreadyRsvpedError, Rsvp
from relay.contexts.events.infrastructure.h3_cells import rings_for
from relay.contexts.events.infrastructure.models import EventModel
from relay.contexts.events.infrastructure.repository import upcoming_statement
from relay.contexts.events.infrastructure.unit_of_work import SqlAlchemyEventsUnitOfWork
from relay.shared.application import Clock
from relay.shared.infrastructure.database import create_session_factory

VIGO = "883920cd1bfffff"
#: A real cell next door to Vigo's, taken from the ring a listing would read.
NEXT_DOOR = next(cell for cell in h3.grid_disk(VIGO, 1) if cell != VIGO)
A_CORUNA = "883925cf43fffff"
STARTS = datetime(2026, 3, 4, 18, tzinfo=UTC)
PLANNED = datetime(2026, 3, 1, tzinfo=UTC)
TOKYO = timezone(timedelta(hours=9))
HOST = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
async def uow(migrated_engine: AsyncEngine) -> AsyncIterator[SqlAlchemyEventsUnitOfWork]:
    unit = SqlAlchemyEventsUnitOfWork(create_session_factory(migrated_engine))
    async with unit:
        yield unit


def planned(
    title: str,
    *,
    cell: str | None = VIGO,
    hours: float = 0,
    ends_in: float | None = None,
) -> Event:
    return Event.plan(
        host_id=HOST,
        title=title,
        starts_at=STARTS + timedelta(hours=hours),
        ends_at=None if ends_in is None else STARTS + timedelta(hours=ends_in),
        venue_name="The corner bar" if cell else None,
        details="Bring yourself." if cell else None,
        created_at=PLANNED,
        location_cell=cell,
    )


def going_to(event: Event, member: UUID | None = None) -> Rsvp:
    return Rsvp.go(event_id=event.id, member_id=member or uuid4(), at=PLANNED)


async def seed(uow: SqlAlchemyEventsUnitOfWork, *events: Event) -> None:
    for event in events:
        await uow.events.add(event)
    await uow.commit()


async def listing(
    uow: SqlAlchemyEventsUnitOfWork, cells: list[str], start: ListingStart | None = None
):
    return await uow.events.page_upcoming(
        cells=cells, start=start or ListingStart(at=STARTS), limit=20
    )


async def test_an_event_comes_back_as_it_was_planned(uow: SqlAlchemyEventsUnitOfWork) -> None:
    event = Event.plan(
        host_id=HOST,
        title="Book swap",
        starts_at=STARTS,
        ends_at=STARTS + timedelta(hours=2),
        venue_name="The corner bar",
        details="Bring one book.",
        created_at=PLANNED,
        location_cell=VIGO,
    )
    await seed(uow, event)

    back = await uow.events.get(event.id)

    assert back is not None
    assert back.id == event.id
    assert (back.host_id, back.title, back.venue_name, back.details) == (
        HOST,
        "Book swap",
        "The corner bar",
        "Bring one book.",
    )
    # A start time that came in as one instant comes back as that instant, with a zone on it.
    assert (back.starts_at, back.ends_at, back.created_at) == (
        event.starts_at,
        event.ends_at,
        event.created_at,
    )
    assert back.location_cell == VIGO


async def test_an_event_that_named_no_place_comes_back_without_one(
    uow: SqlAlchemyEventsUnitOfWork,
) -> None:
    event = planned("Somewhere, maybe", cell=None)
    await seed(uow, event)

    back = await uow.events.get(event.id)
    assert back is not None
    assert back.location_cell is None


async def test_an_event_that_was_never_planned_comes_back_as_nothing(
    uow: SqlAlchemyEventsUnitOfWork,
) -> None:
    assert await uow.events.get(uuid4()) is None


async def test_the_listing_reads_the_cells_it_is_given_and_no_others(
    uow: SqlAlchemyEventsUnitOfWork,
) -> None:
    await seed(
        uow,
        planned("here", hours=1),
        planned("next door", cell=NEXT_DOOR, hours=2),
        planned("across the region", cell=A_CORUNA, hours=3),
    )

    assert [event.title for event in await listing(uow, [VIGO, NEXT_DOOR])] == [
        "here",
        "next door",
    ]


async def test_an_event_that_named_no_place_is_in_no_localitys_listing(
    uow: SqlAlchemyEventsUnitOfWork,
) -> None:
    await seed(
        uow,
        planned("here", hours=1),
        planned("nowhere in particular", cell=None, hours=2),
    )

    assert [event.title for event in await listing(uow, [VIGO])] == ["here"]


async def test_an_event_that_already_started_is_not_coming_up(
    uow: SqlAlchemyEventsUnitOfWork,
) -> None:
    await seed(uow, planned("underway", hours=-1), planned("later", hours=1))

    assert [event.title for event in await listing(uow, [VIGO])] == ["later"]


async def test_a_page_of_nothing_asks_for_no_counts(uow: SqlAlchemyEventsUnitOfWork) -> None:
    """An empty locality reads as empty, and the counts are never asked for nothing.

    A `where ... in ()` over no ids is a syntax error in some databases, so the read that
    tallies a page has to notice an empty page before it writes the query.
    """
    assert await listing(uow, [VIGO]) == []
    assert await uow.rsvps.counts_for([]) == {}


async def test_a_page_read_backwards_reads_the_recent_past_first(
    uow: SqlAlchemyEventsUnitOfWork,
) -> None:
    """The other direction, from a wall past everything: most recent first."""
    await seed(uow, planned("last week", hours=-24 * 7), planned("later", hours=1))

    back = await listing(
        uow, [VIGO], start=ListingStart(at=STARTS + timedelta(days=1), backwards=True)
    )

    assert [event.title for event in back] == ["later", "last week"]


async def test_a_page_stops_where_it_was_told_to(uow: SqlAlchemyEventsUnitOfWork) -> None:
    await seed(uow, *[planned(f"event {n}", hours=n) for n in range(5)])

    found = await uow.events.page_upcoming(cells=[VIGO], start=ListingStart(at=STARTS), limit=2)

    assert [event.title for event in found] == ["event 1", "event 2"]


async def test_a_page_starts_at_the_same_instant_when_the_time_comes_in_another_zone(
    uow: SqlAlchemyEventsUnitOfWork,
) -> None:
    """A page marker is an instant, not a reading of one wall clock."""
    await seed(uow, *[planned(f"event {n}", hours=n) for n in range(5)])

    in_tokyo = (STARTS + timedelta(hours=3)).astimezone(TOKYO)

    assert [
        event.title for event in await listing(uow, [VIGO], start=ListingStart(at=in_tokyo))
    ] == [
        "event 4",
    ]


async def test_events_sharing_a_start_time_still_come_out_a_page_at_a_time(
    uow: SqlAlchemyEventsUnitOfWork,
) -> None:
    """Twenty suppers at seven is an ordinary Saturday, and the table has to page it.

    The marker names a row and not an instant, so the ones that did not fit on the first
    page are on the second rather than past it and gone.
    """
    await seed(uow, *[planned(f"choir {n}", hours=1) for n in range(25)])

    first = await uow.events.page_upcoming(cells=[VIGO], start=ListingStart(at=STARTS), limit=20)
    second = await uow.events.page_upcoming(
        cells=[VIGO],
        start=ListingStart(at=first[-1].starts_at, after_id=first[-1].id),
        limit=20,
    )

    # Which of them comes first is the row's id and nobody's choice, so the assertion is
    # about the shape of the two pages: all of them, once each, in the order given.
    assert len(first) == 20 and len(second) == 5
    seen = [(event.starts_at, event.id) for event in first + second]
    assert len(seen) == 25
    assert len(set(seen)) == 25
    assert seen == sorted(seen)


async def test_a_page_read_backwards_stops_where_it_was_told_to(
    uow: SqlAlchemyEventsUnitOfWork,
) -> None:
    await seed(uow, *[planned(f"event {n}", hours=-(n + 1)) for n in range(5)])

    wall = ListingStart(at=STARTS, backwards=True)
    first = await uow.events.page_upcoming(cells=[VIGO], start=wall, limit=2)
    second = await uow.events.page_upcoming(
        cells=[VIGO],
        start=ListingStart(at=first[-1].starts_at, after_id=first[-1].id, backwards=True),
        limit=2,
    )

    assert [event.title for event in first + second] == ["event 0", "event 1", "event 2", "event 3"]


async def test_how_many_are_going_comes_back_per_event(uow: SqlAlchemyEventsUnitOfWork) -> None:
    booked, quiet = planned("Book club"), planned("Silent reading")
    await seed(uow, booked, quiet)
    await uow.rsvps.add(going_to(booked))
    await uow.rsvps.add(going_to(booked))
    await uow.commit()

    counts = await uow.rsvps.counts_for([booked.id, quiet.id, uuid4()])

    assert counts == {booked.id: 2}
    assert await uow.rsvps.count_for(quiet.id) == 0


async def test_a_place_can_be_found_by_who_took_it(uow: SqlAlchemyEventsUnitOfWork) -> None:
    event = planned("Book swap")
    member = uuid4()
    await seed(uow, event)
    taken = going_to(event, member)
    await uow.rsvps.add(taken)
    await uow.commit()

    found = await uow.rsvps.by_member(event_id=event.id, member_id=member)

    assert found is not None
    assert (found.id, found.event_id, found.member_id, found.created_at) == (
        taken.id,
        event.id,
        member,
        PLANNED,
    )
    assert await uow.rsvps.by_member(event_id=event.id, member_id=uuid4()) is None


async def test_a_place_given_back_is_gone_from_the_table(
    uow: SqlAlchemyEventsUnitOfWork,
) -> None:
    """Only the one who gave it back stops being counted; the rest keep their places."""
    event = planned("Book swap")
    you, them = uuid4(), uuid4()
    await seed(uow, event)
    await uow.rsvps.add(going_to(event, you))
    await uow.rsvps.add(going_to(event, them))
    await uow.commit()

    place = await uow.rsvps.by_member(event_id=event.id, member_id=you)
    assert place is not None
    await uow.rsvps.delete(place)
    await uow.commit()

    assert await uow.rsvps.by_member(event_id=event.id, member_id=you) is None
    assert await uow.rsvps.count_for(event.id) == 1


async def test_the_same_member_cannot_take_two_places(migrated_engine: AsyncEngine) -> None:
    """The unique pair, enforced by the table rather than by a read that got in first."""
    factory = create_session_factory(migrated_engine)
    event = planned("Book swap")
    member = uuid4()
    async with SqlAlchemyEventsUnitOfWork(factory) as unit:
        await unit.events.add(event)
        await unit.rsvps.add(going_to(event, member))
        await unit.commit()

    with pytest.raises(AlreadyRsvpedError):
        async with SqlAlchemyEventsUnitOfWork(factory) as unit:
            await unit.rsvps.add(going_to(event, member))

    async with SqlAlchemyEventsUnitOfWork(factory) as unit:
        assert await unit.rsvps.count_for(event.id) == 1


async def test_one_member_cannot_take_two_places_by_saying_it_twice_at_once(
    migrated_engine: AsyncEngine,
) -> None:
    """Two taps, one place: the loser hears "already going" and not "you're in".

    Each tap runs in its own session, because that is what two taps are. Neither can see
    what the other is writing, so the check in the use case passes for both and the
    unique pair is the only thing left between one member and two places.
    """
    factory = create_session_factory(migrated_engine)
    event = planned("Book swap")
    member = uuid4()
    async with SqlAlchemyEventsUnitOfWork(factory) as unit:
        await unit.events.add(event)
        await unit.commit()

    async def tap() -> int | AlreadyRsvpedError:
        going = RsvpEvent(SqlAlchemyEventsUnitOfWork(factory), Clock())
        try:
            outcome = await going.execute(event_id=event.id, member_id=member)
        except AlreadyRsvpedError as refused:
            return refused
        return outcome.rsvp_count

    results = await asyncio.gather(tap(), tap())

    assert [count for count in results if isinstance(count, int)] == [1]
    assert len([r for r in results if isinstance(r, AlreadyRsvpedError)]) == 1

    async with SqlAlchemyEventsUnitOfWork(factory) as unit:
        assert await unit.rsvps.count_for(event.id) == 1


async def test_two_members_take_two_places(uow: SqlAlchemyEventsUnitOfWork) -> None:
    event = planned("Book swap")

    await seed(uow, event)
    await uow.rsvps.add(going_to(event))
    await uow.rsvps.add(going_to(event))
    await uow.commit()

    assert await uow.rsvps.count_for(event.id) == 2


def rows(cell: str, count: int, first_index: int) -> list[dict[str, object]]:
    return [
        {
            "id": uuid4(),
            "host_id": HOST,
            "title": f"Event {index} in {cell}.",
            "starts_at": STARTS + timedelta(seconds=index + first_index),
            "location_cell": cell,
            "created_at": PLANNED,
        }
        for index in range(count)
    ]


async def load(engine: AsyncEngine, payload: list[dict[str, object]]) -> None:
    """Put the rows in, and give Postgres statistics to plan with.

    Without an ANALYZE the planner reads the whole table instead of the index, so a
    plan read straight after a load would say nothing.
    """
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: sync_conn.execute(insert(EventModel), payload))
    async with engine.connect() as conn:
        if engine.dialect.name == "postgresql":
            await conn.exec_driver_sql("ANALYZE events")
        stored = await conn.scalar(select(func.count()).select_from(EventModel))
    assert stored == len(payload)


async def plan_for(engine: AsyncEngine, statement: Select) -> str:
    """The plan this database would use for a listing, as one string."""
    sql = str(
        statement.compile(
            dialect=engine.sync_engine.dialect, compile_kwargs={"literal_binds": True}
        )
    )
    explain = (
        "EXPLAIN (ANALYZE, FORMAT JSON)"
        if engine.dialect.name == "postgresql"
        else "EXPLAIN QUERY PLAN"
    )
    async with engine.connect() as conn:
        found = (await conn.exec_driver_sql(f"{explain} {sql}")).all()
    # Every column: SQLite puts the words in one and Postgres returns one JSON value.
    return "\n".join(" ".join(str(cell) for cell in row) for row in found)


async def test_the_listing_walks_the_index_it_was_given(
    migrated_engine: AsyncEngine,
) -> None:
    """The index the migration built had better be the one the listing reads through.

    Ten thousand events over two hundred localities, the reader asking for the seven
    cells around them: two hundred rows out of ten thousand, which is the only shape
    in which an index earns its keep. Asked at the default 10 km instead, the same
    listing names 397 cells at once and Postgres reads the table for it, so this is the
    tight-radius shape the index was built for and not the only one the endpoint serves.
    """
    walking = h3.grid_disk(VIGO, rings_for(0.5))
    away = [cell for cell in h3.grid_disk(A_CORUNA, 12)[::2][:200] if cell not in walking]
    payload: list[dict[str, object]] = rows(VIGO, 200, 0)
    for index, cell in enumerate(away):
        payload += rows(cell, 49, index * 49)
    await load(migrated_engine, payload)

    plan = await plan_for(migrated_engine, upcoming_statement(walking, ListingStart(at=STARTS), 21))

    assert "ix_events_location_cell_starts_at" in plan, plan
