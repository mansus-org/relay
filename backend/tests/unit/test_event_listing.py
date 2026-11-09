"""The page of what is on: the marker that says where the next one starts, and the tally."""

from datetime import timedelta, timezone
from urllib.parse import parse_qs, urlencode

from relay.contexts.events.domain.listing import EventDetails, EventListingPage, as_text
from tests.fakes.events import STARTS, an_event

TOKYO = timezone(timedelta(hours=9))


def test_a_page_marker_is_written_in_utc() -> None:
    assert as_text(STARTS) == "2026-03-04T18:00:00Z"


def test_a_page_marker_written_from_a_time_in_another_zone_is_written_in_utc() -> None:
    assert as_text(STARTS.astimezone(TOKYO)) == "2026-03-04T18:00:00Z"


def test_the_last_page_promises_no_next_one() -> None:
    assert as_text(None) is None


def test_a_page_marker_survives_the_query_string_it_is_sent_in() -> None:
    """Why a `Z` and not a `+00:00`: a `+` in a query string is a space by the time it lands."""
    marker = as_text(STARTS) or ""

    assert parse_qs(urlencode({"next_after": marker}))["next_after"][0] == marker


def test_an_event_on_its_own_carries_no_tally_until_someone_says_they_are_going() -> None:
    assert EventDetails(event=an_event()).rsvp_count == 0


def test_a_page_holds_its_events_in_the_order_it_was_given_them() -> None:
    later = an_event("Later")
    sooner = an_event("Sooner")

    page = EventListingPage(events=(EventDetails(event=sooner), EventDetails(event=later)))

    assert [details.event.title for details in page.events] == ["Sooner", "Later"]
    assert page.next_after is None


def test_a_page_and_its_tallies_survive_being_read_back_as_a_value() -> None:
    """The page is handed across the boundary as data, so equality is the contract."""
    event = an_event()
    page = EventListingPage(
        events=(EventDetails(event=event, rsvp_count=3),),
        next_after=STARTS,
    )

    assert page == EventListingPage(
        events=(EventDetails(event=event, rsvp_count=3),), next_after=STARTS
    )
    assert EventListingPage(events=(EventDetails(event=event),)) != page
