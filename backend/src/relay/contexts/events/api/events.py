"""The HTTP edge of the events context: plan something, see what is on, say you are going.

Three operations and no more: an event is created by its host, read by anyone, and
RSVP'd to by a member — including taking the hand back down. There is no edit and no
list of who is coming, because neither is decided yet and an event that needs them is a
different product than the one being built.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

from relay.container import Container
from relay.contexts.events.application import (
    CancelRsvp,
    CreateEvent,
    GetEvent,
    GetEvents,
    RsvpEvent,
)
from relay.contexts.events.domain.cells import DEFAULT_RADIUS_KM, CellError
from relay.contexts.events.domain.event import (
    MAX_DETAILS_LENGTH,
    MAX_TITLE_LENGTH,
    EventNotFoundError,
)
from relay.contexts.events.domain.listing import EventDetails, EventListingPage
from relay.contexts.events.domain.rsvp import AlreadyRsvpedError, NotGoingError, RsvpOutcome
from relay.shared.api.dependencies import get_container
from relay.shared.domain import ValidationError

router = APIRouter(tags=["events"])


async def get_member_id(authorization: Annotated[str | None, Header()] = None) -> UUID:
    """Who is planning, who is going. The one place this context asks for identity.

    PLACEHOLDER UNTIL RELY-87 LANDS. There are no accounts yet, so there is no token
    to verify: the bearer value is taken to be the member's id and anything that is
    not an id is refused. At rebase time this function is deleted and the two write
    endpoints' `Depends(get_member_id)` points at RELY-87's auth dependency instead.
    Nothing else in this file changes, and both reads stay public either way.
    """
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401, detail="Relay has no accounts yet: send your id as a bearer token."
        )
    try:
        return UUID(token)
    except ValueError as error:
        raise HTTPException(
            status_code=401, detail="That bearer token is not a user id yet."
        ) from error


def display_name(member_id: UUID) -> str:
    """The name shown for a host until RELY-87's user records replace it."""
    return f"Member {str(member_id)[:8]}"


async def get_maybe_member_id(
    authorization: Annotated[str | None, Header()] = None,
) -> UUID | None:
    """Who is reading, when they chose to say.

    Reading an event is public; whether the reader is going is not a public fact about
    them. A token that does not parse is the same as no token — the event still shows,
    it just cannot answer a question it was not asked. Same placeholder as above.
    """
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return UUID(token)
    except ValueError:
        return None


class EventResponse(BaseModel):
    """One event, with how many people are going.

    `starts_at` and `ends_at` are instants with a zone, so a phone renders an 19:30
    event at 19:30 wherever the phone is. `rsvp_count` is the whole tally: there is no
    list of names to page through, and a number is what a card shows.
    """

    id: str
    host_id: str
    host_name: str
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    venue_name: str | None = None
    details: str | None = None
    location_cell: str | None = None
    rsvp_count: int = 0

    @classmethod
    def from_domain(cls, details: EventDetails) -> "EventResponse":
        event = details.event
        return cls(
            id=str(event.id),
            host_id=str(event.host_id),
            host_name=display_name(event.host_id),
            title=event.title,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            venue_name=event.venue_name,
            details=event.details,
            location_cell=event.location_cell,
            rsvp_count=details.rsvp_count,
        )


class EventListResponse(BaseModel):
    """The rows of one page, in the order they were read.

    `next_from` is null once there is nothing left to ask for.
    """

    events: list[EventResponse]
    next_from: str | None = None

    @classmethod
    def from_domain(cls, page: EventListingPage) -> "EventListResponse":
        return cls(
            events=[EventResponse.from_domain(details) for details in page.events],
            next_from=page.next_from.as_text() if page.next_from is not None else None,
        )


class EventDetailResponse(EventResponse):
    """One event, and whether the reader asking is in that number.

    `user_rsvped` is only ever true for a request that came with a token: the count is
    the same for everyone, this one is not. It is on the detail and not on the list
    because the list is read by everyone at once.
    """

    user_rsvped: bool = False

    @classmethod
    def from_domain(cls, details: EventDetails) -> "EventDetailResponse":
        return cls(
            **EventResponse.from_domain(details).model_dump(), user_rsvped=details.user_rsvped
        )


class RsvpResponse(BaseModel):
    """What saying you are going came to: the event, and the tally beside it now.

    There is no list of names behind the number, and a second tap is a 409 rather than
    a second place.
    """

    event_id: str
    rsvp_count: int = Field(
        description="Counted after your place was saved, so it includes you, and anyone "
        "who said they were coming in the same moment."
    )

    @classmethod
    def from_domain(cls, outcome: RsvpOutcome) -> "RsvpResponse":
        return cls(event_id=str(outcome.event.id), rsvp_count=outcome.rsvp_count)


class NewEventRequest(BaseModel):
    """An event as its host states it.

    `starts_at` is a timestamp with a zone, and it is read here rather than by
    pydantic so that a time nobody can place gets Relay's sentence about it and a 400,
    not a field-error shape of its own. An `ends_at` sent as blanks is a field cleared:
    the same as not sending it. `location_cell` is where it happens, in H3: leaving it
    out means the event reaches no locality's list, and Relay does not guess a locality
    from the venue's text.
    """

    title: str
    starts_at: str
    ends_at: str | None = None
    venue_name: str | None = None
    details: str | None = None
    location_cell: str | None = None


def get_create_event(
    container: Annotated[Container, Depends(get_container)],
) -> CreateEvent:
    return container.get_create_event()


def get_events_use_case(
    container: Annotated[Container, Depends(get_container)],
) -> GetEvents:
    return container.get_events()


def get_event_use_case(
    container: Annotated[Container, Depends(get_container)],
) -> GetEvent:
    return container.get_event()


def get_rsvp_event(
    container: Annotated[Container, Depends(get_container)],
) -> RsvpEvent:
    return container.get_rsvp_event()


def get_cancel_rsvp(
    container: Annotated[Container, Depends(get_container)],
) -> CancelRsvp:
    return container.get_cancel_rsvp()


@router.post(
    "/events",
    response_model=EventResponse,
    status_code=201,
    summary="Plan an event",
    description=(
        "Saves an event and returns it. `starts_at` is a timestamp with a zone — a time "
        "that does not say which zone it is in is refused rather than read as someone "
        "else's evening — and `ends_at` has to be after it. `location_cell` has to be a "
        "real resolution-8 H3 cell, because an event filed anywhere else is an event no "
        "locality's list will ever read."
    ),
    responses={
        400: {
            "description": f"The title was empty or over {MAX_TITLE_LENGTH} characters, "
            f"the description over {MAX_DETAILS_LENGTH}, the times unreadable or the "
            "wrong way round, or `location_cell` was not a resolution-8 H3 cell."
        },
        401: {"description": "No bearer token to plan as."},
        422: {"description": "A field was not a string at all."},
    },
)
async def create_event(
    payload: NewEventRequest,
    host_id: Annotated[UUID, Depends(get_member_id)],
    use_case: Annotated[CreateEvent, Depends(get_create_event)],
) -> EventResponse:
    try:
        event = await use_case.execute(
            host_id=host_id,
            title=payload.title,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            venue_name=payload.venue_name,
            details=payload.details,
            location_cell=payload.location_cell,
        )
    except (ValidationError, CellError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return EventResponse.from_domain(EventDetails(event=event))


@router.get(
    "/events",
    response_model=EventListResponse,
    summary="What is on nearby",
    description=(
        "Events starting at or after `from` within `radius` km of `cell`, which is the "
        "reader's current H3 resolution-8 cell. `from` is a date (2026-03-04) or a full "
        "timestamp and defaults to now, so the default page is what has not started yet, "
        "and whatever starts exactly at the time you wrote is on it. `from=past` reads "
        "the other way: what has already started, most recent first. Pass `next_from` "
        "back as `from` for the next page — it names one row and cuts past it, so twenty "
        "events that all start at seven still come out twenty at a time. An event that "
        "named no cell is not here at all. Public, like every read in Relay."
    ),
    responses={400: {"description": "The cell, the radius, or `from` was not usable."}},
)
async def read_events(
    cell: Annotated[str, Query(description="Your current H3 resolution-8 cell.")],
    use_case: Annotated[GetEvents, Depends(get_events_use_case)],
    radius: Annotated[
        float,
        Query(description="How far out to read, in km: between 0 and 25."),
    ] = DEFAULT_RADIUS_KM,
    from_: Annotated[
        str | None,
        Query(
            alias="from",
            description="A date, an instant, `past` for what already started (most "
            "recent first), or the `next_from` of the last page. Default: now, forwards.",
        ),
    ] = None,
) -> EventListResponse:
    try:
        page = await use_case.execute(cell=cell, radius_km=radius, from_=from_)
    except (ValidationError, CellError) as error:
        # A date this list never handed out is the client's mistake to hear about,
        # not a 500 to retry forever.
        raise HTTPException(status_code=400, detail=str(error)) from error
    return EventListResponse.from_domain(page)


@router.get(
    "/events/{event_id}",
    response_model=EventDetailResponse,
    summary="One event",
    description=(
        "An event by id, with how many people are going. Send a bearer token and it "
        "says whether you are one of them; send none and `user_rsvped` is false."
    ),
    responses={404: {"description": "No event with that id."}},
)
async def read_event(
    event_id: UUID,
    use_case: Annotated[GetEvent, Depends(get_event_use_case)],
    member_id: Annotated[UUID | None, Depends(get_maybe_member_id)],
) -> EventDetailResponse:
    try:
        details = await use_case.execute(event_id, member_id)
    except EventNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return EventDetailResponse.from_domain(details)


@router.post(
    "/events/{event_id}/rsvp",
    response_model=RsvpResponse,
    summary="Say you are going",
    description=(
        "Takes your place at an event. One place per person: saying it again is a 409, "
        "not a second place. Give it back with DELETE on the same path."
    ),
    responses={
        401: {"description": "No bearer token to go as."},
        404: {"description": "No event with that id."},
        409: {"description": "You are already going."},
    },
)
async def rsvp_event(
    event_id: UUID,
    member_id: Annotated[UUID, Depends(get_member_id)],
    use_case: Annotated[RsvpEvent, Depends(get_rsvp_event)],
) -> RsvpResponse:
    try:
        outcome = await use_case.execute(event_id=event_id, member_id=member_id)
    except EventNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AlreadyRsvpedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return RsvpResponse.from_domain(outcome)


@router.delete(
    "/events/{event_id}/rsvp",
    status_code=204,
    summary="Give your place back",
    description=(
        "Stops going to an event. There is nothing to give back when the event is gone "
        "or you were never going, so both are a 404: a tap that lands after the one "
        "that worked does not get to claim it undid anything."
    ),
    responses={
        401: {"description": "No bearer token to leave as."},
        404: {"description": "No event with that id, or you were not going to it."},
    },
)
async def cancel_rsvp(
    event_id: UUID,
    member_id: Annotated[UUID, Depends(get_member_id)],
    use_case: Annotated[CancelRsvp, Depends(get_cancel_rsvp)],
) -> Response:
    try:
        await use_case.execute(event_id=event_id, member_id=member_id)
    except (EventNotFoundError, NotGoingError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)
