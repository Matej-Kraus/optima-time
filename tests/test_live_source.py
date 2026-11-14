import time

import numpy as np
import pytest

import optima_time.sources.live as live
from optima_time.sources.base import SourceState
from optima_time.sources.live import LiveSource, SourceUnavailable


class FakeLive(LiveSource):
    """Connect fails `fail_connects` times; then frames until `drop_after`, then breaks once."""

    name = "fake"

    def __init__(self, fail_connects: int = 0, drop_after: int | None = None) -> None:
        super().__init__()
        self.fail_connects = fail_connects
        self.drop_after = drop_after
        self.connects = 0
        self.n = 0

    def _connect(self) -> None:
        self.connects += 1
        if self.fail_connects > 0:
            self.fail_connects -= 1
            raise ConnectionError("not there yet")

    def _grab(self):
        time.sleep(0.005)  # ~200 fps
        self.n += 1
        if self.drop_after is not None and self.n == self.drop_after:
            self.drop_after = None
            raise ConnectionError("cable pulled")
        return np.full((4, 4, 3), self.n % 256, np.uint8)

    def _disconnect(self) -> None:
        pass


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live, "BACKOFF_S", (0.01, 0.02))


def test_latest_wins_and_counts_drops() -> None:
    src = FakeLive()
    src.open()
    try:
        first = src.read_latest(1)
        time.sleep(0.1)
        second = src.read_latest(1)
        assert first and second and second.seq > first.seq + 3
        assert src.state is SourceState.OK
        assert src.stats.dropped > 0
    finally:
        src.close()


def test_reconnects_after_failures() -> None:
    src = FakeLive(fail_connects=3, drop_after=10)
    src.open()
    try:
        for _ in range(100):
            if src.stats.received > 30:
                break
            time.sleep(0.02)
        assert src.connects == 5  # 3 failed, 1 broke after 10 frames, 1 good
        assert src.reconnects == 4
        assert src.state is SourceState.OK and src.error is None
    finally:
        src.close()


def test_unavailable_source_stops_retrying() -> None:
    class Missing(FakeLive):
        def _connect(self) -> None:
            self.connects += 1
            raise SourceUnavailable("no NDI here")

    src = Missing()
    src.open()
    time.sleep(0.1)
    assert src.connects == 1 and src.state is SourceState.LOST and "NDI" in (src.error or "")
    src.close()


def test_read_latest_times_out_without_frames() -> None:
    src = FakeLive(fail_connects=1000)
    src.open()
    t0 = time.monotonic()
    assert src.read_latest(0.1) is None
    assert time.monotonic() - t0 < 0.5
    src.close()
