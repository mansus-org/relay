from datetime import UTC, datetime, timedelta

from relay.shared.application import Clock


class FixedClock(Clock):
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now


class SteppingClock(Clock):
    """Moves forward a little on every call, so a test can tell two of its posts apart."""

    def __init__(self, now: datetime | None = None, step: timedelta = timedelta(minutes=1)) -> None:
        self._now = now or datetime(2026, 1, 1, tzinfo=UTC)
        self._step = step

    def now(self) -> datetime:
        said = self._now
        self._now = said + self._step
        return said
