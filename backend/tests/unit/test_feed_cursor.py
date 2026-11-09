"""The feed cursor: a timestamp in and out, and nothing else."""

from datetime import UTC, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode

import pytest

from relay.contexts.posts.domain.feed import Cursor, InvalidCursorError

TOKYO = timezone(timedelta(hours=9))


def test_a_cursor_survives_being_written_out_and_read_back() -> None:
    cursor = Cursor(value=datetime(2026, 3, 4, 9, 30, 12, 345678, tzinfo=UTC))
    assert Cursor.parse(str(cursor)) == cursor


def test_a_cursor_is_written_in_utc() -> None:
    assert str(Cursor(value=datetime(2026, 3, 4, 9, 30, tzinfo=UTC))) == "2026-03-04T09:30:00Z"


def test_a_cursor_written_from_a_timestamp_in_another_zone_is_written_in_utc() -> None:
    tokyo = Cursor(value=datetime(2026, 3, 4, 18, 30, tzinfo=TOKYO))
    assert str(tokyo) == "2026-03-04T09:30:00Z"


def test_a_cursor_travels_through_a_query_string_unchanged() -> None:
    cursor = Cursor(value=datetime(2026, 3, 4, 9, 30, 12, 345678, tzinfo=UTC))
    arrived = parse_qs(urlencode({"cursor": str(cursor)}))["cursor"][0]

    assert Cursor.parse(arrived) == cursor


def test_a_cursor_written_with_an_offset_would_not_survive_the_query_string() -> None:
    """Why a cursor is written with `Z` and not `+00:00`: a `+` means space by the time it lands."""
    arrived = parse_qs("cursor=2026-03-04T09:30:00+00:00")["cursor"][0]

    assert arrived == "2026-03-04T09:30:00 00:00"
    with pytest.raises(InvalidCursorError):
        Cursor.parse(arrived)


def test_a_timestamp_in_another_zone_is_read_as_the_instant_it_names() -> None:
    tokyo = Cursor.parse("2026-03-04T18:30:00+09:00")
    assert tokyo.value == datetime(2026, 3, 4, 9, 30, tzinfo=UTC)


def test_a_timestamp_that_names_no_zone_is_read_as_utc() -> None:
    assert Cursor.parse("2026-03-04T09:30:00").value == datetime(2026, 3, 4, 9, 30, tzinfo=UTC)


@pytest.mark.parametrize("raw", ["", "yesterday", "not-a-time", "2026-13-45T09:30:00"])
def test_a_cursor_this_feed_never_handed_out_is_refused(raw: str) -> None:
    with pytest.raises(InvalidCursorError):
        Cursor.parse(raw)
