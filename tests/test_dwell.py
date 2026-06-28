"""Dwell delivery checks for HumanTyper's Playwright sync path.

Uses a fake locator that records press(key, delay) the way a Playwright sync
Locator receives it, so no real browser is needed.
"""

from __future__ import annotations

from humantyping import HumanTyper
from humantyping.config import MIN_DWELL_TIME


class _FakeLocator:
    def __init__(self) -> None:
        self.presses: list[tuple[str, float]] = []

    def press(self, key: str, delay: float | None = None) -> None:
        assert delay is not None, "every keystroke must carry a dwell delay"
        self.presses.append((key, delay))


def test_sync_playwright_path_sets_dwell() -> None:
    fake = _FakeLocator()
    HumanTyper(wpm=120).type_playwright_sync(fake, "hi there world")

    assert fake.presses, "no keystrokes dispatched"
    delays = [d for _, d in fake.presses]
    floor_ms = MIN_DWELL_TIME * 1000
    assert all(d >= floor_ms for d in delays), "dwell sample fell below the floor"
    assert len(set(delays)) > 1, "dwell is constant — not sampled per keystroke"


if __name__ == "__main__":
    test_sync_playwright_path_sets_dwell()
    print("ok")
