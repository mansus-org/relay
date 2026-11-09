"""Whoever is watching a locality in this process, and what a new post does to them."""

import asyncio

import pytest

from relay.contexts.posts.domain.cells import UnknownCellError
from relay.contexts.posts.domain.post import Post
from relay.contexts.posts.infrastructure.broadcaster import (
    MAX_QUEUED_EVENTS,
    LocalBroadcaster,
    Subscription,
)
from relay.contexts.posts.infrastructure.h3_cells import H3CellNeighbourhood
from tests.fakes.posts import FixedNeighbourhood, a_post

#: Vigo, a cell next to it, and A Coruña. Which cells are neighbours is not left to the
#: real H3 here, so a test says what a reader covers instead of trusting H3 twice.
HOME = "883920cd1bfffff"
NEIGHBOUR = "883920cd7fffff"
FAR_AWAY = "883925cf43fffff"


async def next_post(reader: Subscription) -> Post:
    """The next thing on this stream. Fails the test if nothing turns up."""
    post = await asyncio.wait_for(reader.next_post(), timeout=1)
    assert post is not None, "the stream ended instead of saying something"
    return post


async def stays_quiet(reader: Subscription) -> None:
    """Nothing on this stream, for as long as anyone would wait for one."""
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(reader.next_post(), timeout=0.05)


@pytest.fixture
def node() -> LocalBroadcaster:
    """A node where two cells see each other and nobody else."""
    both = {HOME, NEIGHBOUR}
    return LocalBroadcaster(FixedNeighbourhood({HOME: both, NEIGHBOUR: both}))


async def test_a_post_said_in_the_cell_arrives_on_the_stream(node: LocalBroadcaster) -> None:
    reader = node.subscribe(HOME, radius_km=1)

    node.announce(a_post("The bakery is back.", cell=HOME))

    assert (await next_post(reader)).body == "The bakery is back."


async def test_a_post_said_next_door_arrives_too(node: LocalBroadcaster) -> None:
    """A reader sees what is in their locality, not only what is under them."""
    reader = node.subscribe(HOME, radius_km=1)

    node.announce(a_post("Market on the square.", cell=NEIGHBOUR))

    assert (await next_post(reader)).body == "Market on the square."


async def test_a_post_said_outside_the_locality_never_arrives(node: LocalBroadcaster) -> None:
    reader = node.subscribe(HOME, radius_km=1)

    node.announce(a_post("Someone in A Coruña is happy.", cell=FAR_AWAY))

    await stays_quiet(reader)


async def test_a_post_said_nowhere_arrives_nowhere(node: LocalBroadcaster) -> None:
    """A writer who would not say where they are reaches no locality, feed or stream."""
    reader = node.subscribe(HOME, radius_km=1)

    node.announce(a_post("Anyone seen a grey cat?", cell=None))

    await stays_quiet(reader)


async def test_everybody_in_the_locality_hears_it(node: LocalBroadcaster) -> None:
    first = node.subscribe(HOME, radius_km=1)
    second = node.subscribe(NEIGHBOUR, radius_km=1)
    post = a_post("Free piano, ground floor.", cell=HOME)

    node.announce(post)

    assert await next_post(first) is post
    assert await next_post(second) is post


async def test_a_reader_who_hung_up_hears_no_more(node: LocalBroadcaster) -> None:
    reader = node.subscribe(HOME, radius_km=1)
    node.announce(a_post("First.", cell=HOME))
    await next_post(reader)

    node.unsubscribe(reader)
    node.announce(a_post("Second.", cell=HOME))

    await stays_quiet(reader)


async def test_the_other_readers_keep_reading_when_one_hangs_up(node: LocalBroadcaster) -> None:
    reader = node.subscribe(HOME, radius_km=1)
    other = node.subscribe(HOME, radius_km=1)

    node.unsubscribe(reader)
    node.announce(a_post("Still here.", cell=HOME))

    assert (await next_post(other)).body == "Still here."
    assert node.readers == frozenset({other})


async def test_nobody_is_left_carried_once_everyone_hung_up(node: LocalBroadcaster) -> None:
    """A cell nobody reads is not remembered, or a node fills up with the dead."""
    reader = node.subscribe(HOME, radius_km=1)
    other = node.subscribe(NEIGHBOUR, radius_km=1)

    node.unsubscribe(reader)
    node.unsubscribe(other)

    assert node.readers == frozenset()


async def test_a_reader_who_stops_reading_keeps_the_newest_and_loses_the_oldest() -> None:
    """A phone on bad reception is late, and must not be able to hold up anybody else.

    So the queue has a bottom: the oldest thing still waiting goes, and the reader comes
    back on the present rather than working through a locality's past.
    """
    reader = Subscription({HOME}, limit=2)
    old = a_post("Old news.", cell=HOME)
    middle = a_post("Less old news.", cell=HOME)
    now = a_post("Just said.", cell=HOME)

    for post in (old, middle, now):
        reader.offer(post)

    assert (await next_post(reader)) is middle
    assert (await next_post(reader)) is now
    assert reader.dropped == 1


async def test_a_full_stream_does_not_stop_a_post_being_announced(node: LocalBroadcaster) -> None:
    """Announcing is not waiting: the writer is never the one who pays for a slow reader."""
    reader = node.subscribe(HOME, radius_km=1)
    for index in range(MAX_QUEUED_EVENTS + 10):
        node.announce(a_post(f"Post {index}.", cell=HOME))

    assert reader.dropped == 10
    assert (await next_post(reader)).body == f"Post {10}."


async def test_closing_ends_every_open_stream(node: LocalBroadcaster) -> None:
    """A node going away says so, rather than leave people waiting to notice."""
    reader = node.subscribe(HOME, radius_km=1)

    node.close()

    assert await asyncio.wait_for(reader.next_post(), timeout=1) is None
    assert node.readers == frozenset()


async def test_a_cell_no_feed_reads_is_refused_when_the_stream_opens() -> None:
    """The same refusal as the feed, and before anything is streamed, so a client can
    read a plain error instead of an empty stream."""
    node = LocalBroadcaster(H3CellNeighbourhood())

    with pytest.raises(UnknownCellError):
        node.subscribe("not a cell", radius_km=1)

    assert node.readers == frozenset()
