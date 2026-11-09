"""The feed cursor: a timestamp in and out, and nothing else."""

from datetime import UTC, datetime

import pytest

from relay.contexts.posts.domain.feed import Cursor, InvalidCursorError


def test_a_cursor_survives_being_written_out_and_read_back() -> None:
    cursor = Cursor(value=datetime(2026, 3, 4, 9, 30, 12, 345678, tzinfo=UTC))
    assert Cursor.parse(str(cursor)) == cursor


def test_a_cursor_is_written_in_utc_with_its_offset() -> None:
    assert str(Cursor(value=datetime(2026, 3, 4, 9, 30, tzinfo=UTC))) == "2026-03-04T09:30:00+00:00"


def test_a_timestamp_in_another_zone_is_read_as_the_instant_it_names() -> None:
    tokyo = Cursor.parse("2026-03-04T18:30:00+09:00")
    assert tokyo.value == datetime(2026, 3, 4, 9, 30, tzinfo=UTC)


def test_a_timestamp_that_names_no_zone_is_read_as_utc() -> None:
    assert Cursor.parse("2026-03-04T09:30:00").value == datetime(2026, 3, 4, 9, 30, tzinfo=UTC)


@pytest.mark.parametrize("raw", ["", "yesterday", "not-a-time", "2026-13-45T09:30:00"])
def test_a_cursor_this_feed_never_handed_out_is_refused(raw: str) -> None:
    with pytest.raises(InvalidCursorError):
        Cursor.parse(raw)
