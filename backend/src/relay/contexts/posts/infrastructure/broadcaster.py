"""Whoever is reading a locality in this process, and how a new post reaches them.

In memory and in process: one queue per open stream, no broker, nothing that outlives a
restart - a reader who was away misses what was said while they were away, exactly as
someone who never opened the feed does. The cells a reader covers come from the same
`CellNeighbourhood` the feed is read with, so a post arrives on a stream precisely when
that reader would have found it by pulling to refresh.

One process holds all of it, so every worker has its own readers and cannot see
another's posts. The node runs one process; see `relay.main`.
"""

import asyncio
import logging
from collections.abc import Iterable

from relay.contexts.posts.domain.ports import CellNeighbourhood, LiveFeed
from relay.contexts.posts.domain.post import Post

logger = logging.getLogger(__name__)

#: How far behind a reader may fall before its oldest event starts being dropped. A
#: phone on bad reception reads late or not at all, and must not be able to hold up the
#: write that made the post, nor fill up the process on the way.
MAX_QUEUED_EVENTS = 64


class Subscription:
    """One open stream: the cells it covers, and the posts waiting to be written to it."""

    def __init__(self, cells: Iterable[str], *, limit: int = MAX_QUEUED_EVENTS) -> None:
        self._cells = frozenset(cells)
        self._limit = limit
        self._queue: asyncio.Queue[Post | None] = asyncio.Queue(maxsize=limit)
        self.dropped = 0

    @property
    def cells(self) -> frozenset[str]:
        """Every cell a post here would reach this reader in."""
        return self._cells

    async def next_post(self) -> Post | None:
        """Wait for the next post said nearby. None once there will not be another."""
        return await self._queue.get()

    def offer(self, post: Post) -> None:
        """Hand this reader a post, never waiting on it."""
        if self._queue.full():
            # The oldest is the stalest thing it still has and the one worth losing, so
            # a reader that fell behind comes back on the present rather than the past.
            self._queue.get_nowait()
            self.dropped += 1
            logger.warning(
                "stream reader fell behind and lost an event",
                extra={"dropped": self.dropped, "cells": len(self._cells)},
            )
        self._queue.put_nowait(post)

    def end(self) -> None:
        """Tell a waiting reader that nobody is going to say anything again."""
        if self._queue.full():
            self._queue.get_nowait()
        self._queue.put_nowait(None)


class LocalBroadcaster(LiveFeed):
    """The open streams of this process, filed by the cells they watch."""

    def __init__(self, neighbourhood: CellNeighbourhood) -> None:
        self._neighbourhood = neighbourhood
        self._readers: dict[str, set[Subscription]] = {}

    def subscribe(self, cell: str, *, radius_km: float) -> Subscription:
        """Open a stream over the locality a reader standing in `cell` can see.

        Raises whatever the neighbourhood raises for a cell no feed reads or a radius no
        feed reaches, so a route can answer 400 before it starts streaming.
        """
        reader = Subscription(self._neighbourhood.visible_from(cell, radius_km))
        for one in reader.cells:
            self._readers.setdefault(one, set()).add(reader)
        return reader

    def unsubscribe(self, reader: Subscription) -> None:
        """Forget a reader. Called when its stream ends, however it ended."""
        for one in reader.cells:
            readers = self._readers.get(one)
            if readers is not None:
                readers.discard(reader)
                if not readers:
                    del self._readers[one]

    @property
    def readers(self) -> frozenset[Subscription]:
        """Who is reading somewhere right now."""
        return frozenset(one for group in self._readers.values() for one in group)

    def announce(self, post: Post) -> None:
        """Tell every reader watching where this post was said. The `LiveFeed` port."""
        if post.location_cell is None:
            return
        for reader in self._readers.get(post.location_cell, ()):
            reader.offer(post)

    def close(self) -> None:
        """End every open stream, so a shutdown does not leave anyone hanging."""
        readers = self.readers
        self._readers.clear()
        for reader in readers:
            reader.end()
