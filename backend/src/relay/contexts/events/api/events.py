"""The HTTP edge of the events context: plan something, see what is on, say you are going.

Three operations and no more. An event is created by its host, read by anyone, and
RSVP'd to by a member — there is no edit, no cancel and no guest list to page through,
because none of those are decided yet and an event that needs them is a different
product than the one being built.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from relay.container import Container
from relay.contexts.events.application import CreateEvent, GetEvent, GetEvents, RsvpEvent
from relay.contexts.events.domain.cells import DEFAULT_RADIUS_KM, CellError
from relay.contexts.events.domain.event import (
    MAX_DETAILS_LENGTH,
    MAX_TITLE_LENGTH,
    EventNotFoundError,
)
from relay.contexts.events.domain.listing import EventDetails, EventListingPage, as_text
from relay.contexts.events.domain.rsvp import RsvpOutcome
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
    """Soonest first. `next_after` is null once there is nothing later to ask for."""

    events: list[EventResponse]
    next_after: str | None = None

    @classmethod
    def from_domain(cls, page: EventListingPage) -> "EventListResponse":
        return cls(
            events=[EventResponse.from_domain(details) for details in page.events],
            next_after=as_text(page.next_after),
        )


class RsvpResponse(BaseModel):
    """What saying you are going came to.

    `was_new` is false when you were already going, so a client that counts taps does
    not count one twice. You are going either way.
    """

    event_id: str
    rsvp_count: int
    was_new: bool

    @classmethod
    def from_domain(cls, outcome: RsvpOutcome) -> "RsvpResponse":
        return cls(
            event_id=str(outcome.event.id), rsvp_count=outcome.rsvp_count, was_new=outcome.was_new
        )


class NewEventRequest(BaseModel):
    """An event as its host states it.

    `starts_at` is a timestamp with a zone, and it is read here rather than by
    pydantic so that a time nobody can place gets Relay's sentence about it and a 400,
    not a field-error shape of its own. `location_cell` is where it happens, in H3:
    leaving it out means the event reaches no locality's list, and Relay does not
    guess a locality from the venue's text.
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


@router.post(
    "/events",
    response_model=EventResponse,
    status_code=201,
    summary="Plan an event",
    description=(
        "Saves an event and returns it. `starts_at` is a timestamp with a zone, and "
        "`ends_at` has to be after it. `location_cell` has to be a real resolution-8 "
        "H3 cell, because an event filed anywhere else is an event no locality's list "
        "will ever read."
    ),
    responses={
        400: {
            "description": f"The title was empty or over {MAX_TITLE_LENGTH} characters, "
            f"the description over {MAX_DETAILS_LENGTH}, the times unreadable or the "
            "wrong way round, or `location_cell` was not a resolution-8 H3 cell."
        },
        401: {"description": "No bearer token to plan as."},
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
    summary="What is on nearby, soonest first",
    description=(
        "Events starting after now within `radius` km of `cell`, which is the reader's "
        "current H3 resolution-8 cell. Paged by `starts_at`: pass `next_after` back as "
        "`after` for the later pages. An event that has already started is not here, "
        "and neither is one that named no cell. Public, like every read in Relay."
    ),
    responses={400: {"description": "The cell, the radius or the `after` was not usable."}},
)
async def read_events(
    cell: Annotated[str, Query(description="Your current H3 resolution-8 cell.")],
    use_case: Annotated[GetEvents, Depends(get_events_use_case)],
    radius: Annotated[
        float,
        Query(description="How far out to read, in km: between 0 and 25."),
    ] = DEFAULT_RADIUS_KM,
    after: Annotated[
        str | None,
        Query(description="The next_after from the page before this one. Default: now."),
    ] = None,
) -> EventListResponse:
    try:
        page = await use_case.execute(cell=cell, radius_km=radius, after=after)
    except (ValidationError, CellError) as error:
        # Including the `after`: a marker this list never handed out is the client's
        # mistake to hear about, not a 500 to retry forever.
        raise HTTPException(status_code=400, detail=str(error)) from error
    return EventListResponse.from_domain(page)


@router.get(
    "/events/{event_id}",
    response_model=EventResponse,
    summary="One event",
    description="An event by id, with how many people are going.",
    responses={404: {"description": "No event with that id."}},
)
async def read_event(
    event_id: UUID,
    use_case: Annotated[GetEvent, Depends(get_event_use_case)],
) -> EventResponse:
    try:
        details = await use_case.execute(event_id)
    except EventNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return EventResponse.from_domain(details)


@router.post(
    "/events/{event_id}/rsvp",
    response_model=RsvpResponse,
    summary="Say you are going",
    description=(
        "Takes your place at an event. Saying it again changes nothing and is not an "
        "error; `was_new` tells a first tap from a second one. There is no un-RSVP: "
        "leaving an event is not decided yet."
    ),
    responses={
        401: {"description": "No bearer token to go as."},
        404: {"description": "No event with that id."},
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
    return RsvpResponse.from_domain(outcome)
