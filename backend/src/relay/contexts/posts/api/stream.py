"""The live edge of the posts context: watch a locality and have new posts said to you.

`GET /api/stream` is the push half of what `GET /api/feed` is the pull half of. Same
locality, same radius bounds, same refusal for a cell no feed reads - a client that can
read a feed can watch one, and a client that would be refused a feed is refused here
before a single byte of stream is written. Nothing is remembered between connections:
what was said while you were away is the feed's to give you.

The path, the query names and the event name are the ones the mobile client already
codes against (`mobile/src/infrastructure/stream/fetch-post-stream.ts`), which is the
only thing that has to agree with this file: it asks for `/stream?cell=`, listens for
`event: post`, and ignores everything else, comments included.
"""

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from relay.container import Container
from relay.contexts.posts.api.posts import PostResponse
from relay.contexts.posts.domain.cells import DEFAULT_RADIUS_KM, CellError
from relay.contexts.posts.domain.post import Post
from relay.contexts.posts.domain.tally import PostTally
from relay.contexts.posts.infrastructure.broadcaster import LocalBroadcaster, Subscription
from relay.shared.api.dependencies import get_container

router = APIRouter(tags=["posts"])


def get_broadcaster(container: Annotated[Container, Depends(get_container)]) -> LocalBroadcaster:
    """The streams open in this process. Public, like every read in Relay."""
    return container.live_feed


def watch_locality(
    broadcaster: Annotated[LocalBroadcaster, Depends(get_broadcaster)],
    cell: Annotated[str, Query(description="Your current H3 resolution-8 cell.")],
    radius: Annotated[
        float,
        Query(description="How far out to watch, in km: between 0 and 25."),
    ] = DEFAULT_RADIUS_KM,
) -> Iterator[Subscription]:
    """One reader of this locality, forgotten once the response is done with it.

    A dependency rather than a line in the route, because this is torn down even when
    the client hung up before a single event was written: a queue nobody will ever read
    again must not be left behind in the process.
    """
    try:
        reader = broadcaster.subscribe(cell, radius_km=radius)
    except CellError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    try:
        yield reader
    finally:
        broadcaster.unsubscribe(reader)


async def _events(reader: Subscription, *, keepalive_seconds: float) -> AsyncIterator[str]:
    """One `post` event per post said in this locality, and a comment when nothing is.

    The keepalive is the whole protocol: it is what stops whatever sits in front of
    Relay deciding an idle stream is a dead one. Only the timeout is caught here, so a
    client that hung up is not swallowed on the way out - the dependency above is what
    makes the cleanup happen either way.
    """
    while True:
        try:
            post = await asyncio.wait_for(reader.next_post(), timeout=keepalive_seconds)
        except TimeoutError:
            yield ": keepalive\n\n"
            continue
        if post is None:
            # This node is going away. Say so, rather than leave them waiting to notice.
            yield ": closed\n\n"
            return
        yield _event(post)


def _event(post: Post) -> str:
    """The post as the feed would have shown it, on the wire.

    The tally is empty and always will be: this goes out the moment a post is said, and
    a post that was just said has nothing on it yet. Whoever is watching picks the
    reactions up from the feed, same as they would have by pulling to refresh.
    """
    return f"event: post\ndata: {PostResponse.from_domain(post, PostTally()).model_dump_json()}\n\n"


@router.get(
    "/stream",
    summary="Watch this locality",
    description=(
        "An open stream of the posts being said within `radius` km of `cell`: the same "
        "locality `GET /feed` reads, arriving as it happens. Each one is a `post` event "
        "with the same body a feed page carries, and a comment is sent whenever nothing "
        "has been said for a while. Public, like every read in Relay. Nothing is "
        "remembered between connections - what was said while you were away is the "
        "feed's to give you."
    ),
    responses={400: {"description": "The cell or the radius was not usable."}},
)
async def stream(
    reader: Annotated[Subscription, Depends(watch_locality)],
    container: Annotated[Container, Depends(get_container)],
) -> StreamingResponse:
    return StreamingResponse(
        _events(reader, keepalive_seconds=container.settings.stream_keepalive_seconds),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
