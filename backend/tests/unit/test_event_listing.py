"""The page of what is on: the marker that says where the next one starts, and the tally."""

from datetime import UTC, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode
from uuid import UUID

import pytest

from relay.contexts.events.domain.event import InvalidTimeError
from relay.contexts.events.domain.listing import EventDetails, EventListingPage, ListingStart
from tests.fakes.events import STARTS, an_event

TOKYO = timezone(timedelta(hours=9))
NOW = datetime(2026, 3, 4, 12, tzinfo=UTC)
ROW = UUID("22222222-2222-2222-2222-222222222222")


def test_a_page_marker_is_written_in_utc() -> None:
    assert ListingStart(at=STARTS.astimezone(TOKYO)).as_text() == "2026-03-04T18:00:00Z"


def test_a_page_marker_survives_the_query_string_it_is_sent_in() -> None:
    """Why a `Z` and not a `+00:00`: a `+` in a query string is a space by the time it lands."""
    marker = ListingStart(at=STARTS, after_id=ROW).as_text()

    assert parse_qs(urlencode({"from": marker}))["from"][0] == marker


def test_a_marker_read_back_names_the_same_row_it_wrote() -> None:
    """The whole contract of a cursor: out of one response, back into the next request."""
    start = ListingStart(at=STARTS, after_id=ROW)

    assert ListingStart.read(start.as_text(), now=NOW) == start


def test_a_marker_from_the_past_read_back_is_still_from_the_past() -> None:
    """The direction travels in the marker, or the next page reads the wrong way."""
    start = ListingStart(at=STARTS, after_id=ROW, backwards=True)

    assert ListingStart.read(start.as_text(), now=NOW) == start


def test_no_marker_reads_forwards_from_now() -> None:
    assert ListingStart.read(None, now=NOW) == ListingStart(at=NOW)


def test_a_marker_cleared_rather_than_omitted_reads_the_same_way() -> None:
    """An emptied form field is no marker, not a date that happens to be blank."""
    assert ListingStart.read("", now=NOW) == ListingStart(at=NOW)


def test_a_date_without_a_time_is_that_midnight() -> None:
    """A person typing a date means the day, and the day starts at midnight."""
    assert ListingStart.read("2026-03-04", now=NOW) == ListingStart(
        at=datetime(2026, 3, 4, tzinfo=UTC)
    )


def test_the_word_for_the_past_reads_back_from_now() -> None:
    assert ListingStart.read("past", now=NOW) == ListingStart(at=NOW, backwards=True)


def test_a_marker_no_page_ever_handed_out_is_refused() -> None:
    with pytest.raises(InvalidTimeError):
        ListingStart.read("2026-03-04T18:00:00Z~not-a-row", now=NOW)


@pytest.mark.parametrize("text", ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"])
def test_a_start_at_the_edge_of_the_calendar_is_refused(text: str) -> None:
    """Anyone can ask for a page, so the edge of the calendar is a refusal and no 500."""
    with pytest.raises(InvalidTimeError):
        ListingStart.read(text, now=NOW)


def test_an_event_on_its_own_carries_no_tally_until_someone_says_they_are_going() -> None:
    assert EventDetails(event=an_event()).rsvp_count == 0


def test_a_reader_who_did_not_say_who_they_are_is_not_going() -> None:
    """`user_rsvped` is a per-reader answer, and a list has no one reader to answer for."""
    assert EventDetails(event=an_event()).user_rsvped is False


def test_a_page_holds_its_events_in_the_order_it_was_given_them() -> None:
    later = an_event("Later")
    sooner = an_event("Sooner")

    page = EventListingPage(events=(EventDetails(event=sooner), EventDetails(event=later)))

    assert [details.event.title for details in page.events] == ["Sooner", "Later"]
    assert page.next_from is None


def test_a_page_and_its_tallies_survive_being_read_back_as_a_value() -> None:
    """The page is handed across the boundary as data, so equality is the contract."""
    event = an_event()
    marker = ListingStart(at=STARTS, after_id=ROW)
    page = EventListingPage(events=(EventDetails(event=event, rsvp_count=3),), next_from=marker)

    assert page == EventListingPage(
        events=(EventDetails(event=event, rsvp_count=3),), next_from=marker
    )
    assert EventListingPage(events=(EventDetails(event=event),)) != page
