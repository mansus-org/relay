"""The live locality: one long-lived response that says what is being said nearby.

Server-Sent Events, because that is what `mobile/src/infrastructure/stream/` already
reads: `event: post` with the post in `data`, and any other event name ignored. The
post is the same object `GET /feed` returns, field for field, so the screen that shows
both never has to tell a streamed post from a pulled one.

Nothing here is asked for twice: the reader subscribes once and then waits, and the
only thing that ends the stream is the reader hanging up, or the node shutting down.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from relay.container import Container
from relay.contexts.posts.api.posts import PostResponse
from relay.contexts.posts.domain.cells import DEFAULT_RADIUS_KM, CellError
from relay.contexts.posts.domain.tally import PostTally
from relay.contexts.posts.infrastructure.broadcaster import LocalBroadcaster, Subscription
from relay.shared.api.dependencies import get_container

router = APIRouter(tags=["stream"])


def get_broadcaster(request: Request) -> LocalBroadcaster:
    """The one broadcaster this process has, made when it started up."""
    broadcaster: LocalBroadcaster = request.app.state.broadcaster
    return broadcaster


def get_keepalive_seconds(
    container: Annotated[Container, Depends(get_container)],
) -> float:
    return container.settings.stream_keepalive_seconds


def _event(name: str, data: BaseModel) -> str:
    """One SSE frame.

    `data` is a single line because JSON escapes every newline in it, which is what the
    protocol asks for and what the client's parser splits on.
    """
    return f"event: {name}\ndata: {data.model_dump_json()}\n\n"


async def _locality(
    broadcaster: LocalBroadcaster, subscription: Subscription, keepalive_seconds: float
) -> AsyncIterator[str]:
    """Every post that lands in this subscription, for as long as the reader stays."""
    try:
        while True:
            try:
                async with asyncio.timeout(keepalive_seconds):
                    post = await subscription.next_post()
            except TimeoutError:
                # Nothing to say, so say that: a comment line is how SSE keeps a
                # connection alive across a proxy or a radio that closes on silence.
                yield ": keepalive\n\n"
                continue
            if post is None:
                return
            # A post nobody has had time to react to or reply to yet, so its tallies are
            # the empty ones - the same answer `POST /posts` gives its author.
            yield _event("post", PostResponse.from_domain(post, PostTally()))
    finally:
        # However this ended - the reader hung up, the node shut down, an exception - the
        # broadcaster stops carrying a queue nobody is reading.
        broadcaster.unsubscribe(subscription)


@router.get(
    "/stream",
    response_class=StreamingResponse,
    summary="What is being said nearby, as it happens",
    description=(
        "Holds the connection open and sends `event: post` for every post said within "
        "`radius` km of `cell` while you are connected, then nothing at all until the "
        "next one. The post is the same object `GET /feed` returns. A quiet locality "
        "sends a comment line now and then to prove the connection is still up; a "
        "client should ignore it. Whatever you missed while you were away is what "
        "`GET /feed` is for. Public, like every read in Relay: what is being said in a "
        "locality is no secret, and a phone that is not signed in still has a locality."
    ),
    responses={
        400: {"description": "The cell or the radius was not usable."},
    },
)
async def watch_locality(
    cell: Annotated[str, Query(description="Your current H3 resolution-8 cell.")],
    broadcaster: Annotated[LocalBroadcaster, Depends(get_broadcaster)],
    keepalive_seconds: Annotated[float, Depends(get_keepalive_seconds)],
    radius: Annotated[
        float,
        Query(description="How far out to watch, in km: between 0 and 25."),
    ] = DEFAULT_RADIUS_KM,
) -> StreamingResponse:
    try:
        subscription = broadcaster.subscribe(cell, radius_km=radius)
    except CellError as error:
        # Before anything is streamed, so the client gets a plain 400 it can read.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return StreamingResponse(
        _locality(broadcaster, subscription, keepalive_seconds),
        media_type="text/event-stream",
        headers={
            # Nobody is meant to cache a locality, and nothing is meant to sit on a
            # chunk of one waiting to be whole: a post arrives the moment it is said.
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
