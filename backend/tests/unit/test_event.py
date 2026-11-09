"""An event: what it takes to plan one, and what it keeps of what it was given."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from relay.contexts.events.domain.event import (
    MAX_DETAILS_LENGTH,
    MAX_TITLE_LENGTH,
    MAX_VENUE_LENGTH,
    Event,
    InvalidTimeError,
)
from relay.shared.domain import ValidationError
from tests.fakes.events import STARTS

TOKYO = timezone(timedelta(hours=9))


def planned(**fields: object) -> Event:
    """An event with the boring parts filled in, and one thing under test."""
    given: dict[str, object] = {
        "host_id": uuid4(),
        "title": "Neighbourhood clean-up",
        "starts_at": STARTS,
        "created_at": STARTS - timedelta(days=1),
    }
    given.update(fields)
    return Event.plan(**given)  # type: ignore


def test_an_event_keeps_the_time_it_was_planned_separate_from_the_time_it_happens() -> None:
    event = planned()

    assert event.title == "Neighbourhood clean-up"
    assert event.starts_at == STARTS
    assert event.created_at == STARTS - timedelta(days=1)


def test_an_event_needs_a_title() -> None:
    with pytest.raises(ValidationError):
        planned(title="   ")


def test_a_title_keeps_its_words_and_loses_the_spaces_around_them() -> None:
    assert planned(title="  Book swap  ").title == "Book swap"


@pytest.mark.parametrize(
    ("field", "limit"),
    [
        ("title", MAX_TITLE_LENGTH),
        ("details", MAX_DETAILS_LENGTH),
        ("venue_name", MAX_VENUE_LENGTH),
    ],
)
def test_a_field_exactly_as_long_as_the_screen_that_shows_it_is_taken(
    field: str, limit: int
) -> None:
    event = planned(**{field: "a" * limit})  # type: ignore[arg-type]

    assert len(getattr(event, field)) == limit


@pytest.mark.parametrize(
    ("field", "limit"),
    [
        ("title", MAX_TITLE_LENGTH),
        ("details", MAX_DETAILS_LENGTH),
        ("venue_name", MAX_VENUE_LENGTH),
    ],
)
def test_one_character_over_the_field_is_refused(field: str, limit: int) -> None:
    with pytest.raises(ValidationError):
        planned(**{field: "a" * (limit + 1)})  # type: ignore[arg-type]


def test_an_event_with_no_description_or_venue_is_still_an_event() -> None:
    """A blank is a blank: kept as nothing rather than a line of whitespace."""
    event = planned(details="   ", venue_name="  ")

    assert event.details is None
    assert event.venue_name is None


def test_an_event_that_ends_before_it_starts_is_refused() -> None:
    with pytest.raises(ValidationError):
        planned(ends_at=STARTS - timedelta(minutes=1))


def test_an_event_that_ends_the_instant_it_starts_is_refused() -> None:
    """A zero-length event is a mistake about one of the two times, not a third thing."""
    with pytest.raises(ValidationError):
        planned(ends_at=STARTS)


def test_an_event_keeps_the_end_it_was_given() -> None:
    assert planned(ends_at=STARTS + timedelta(hours=2)).ends_at == STARTS + timedelta(hours=2)


def test_a_time_written_without_a_zone_is_the_instant_it_names_in_utc() -> None:
    """Events are stored in UTC, so a naive time is read as UTC and not as local."""
    naive = datetime(2026, 3, 4, 18)

    assert planned(starts_at=naive).starts_at == STARTS


def test_a_time_in_another_zone_is_kept_as_the_instant_it_names() -> None:
    """Six in the evening in Tokyo is not six in the evening here."""
    in_tokyo = datetime(2026, 3, 5, 3, tzinfo=TOKYO)

    assert planned(starts_at=in_tokyo).starts_at == STARTS


def test_a_time_written_as_text_is_read_as_a_time() -> None:
    """The same string comes back as the `next_after` of a page, so it has to read back."""
    assert planned(starts_at="2026-03-04T18:00:00Z").starts_at == STARTS


@pytest.mark.parametrize("text", ["", "next Tuesday", "2026-13-04T18:00:00"])
def test_a_time_relay_cannot_read_is_refused(text: str) -> None:
    with pytest.raises(InvalidTimeError):
        planned(starts_at=text)


def test_an_event_does_not_have_to_say_where_it_is() -> None:
    """A plan whose place is not settled yet is still a plan; it just reaches nobody."""
    assert planned().location_cell is None
