"""In-memory sliding-window limiter. One API process is enough at this scale."""

import time
from collections.abc import Callable


class SlidingWindow:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, list[float]] = {}

    def _prune(self) -> None:
        """Drop expired hits for every key, so the table can't grow without bound."""
        cutoff = self._clock() - self.window
        for key in list(self._hits):
            recent = [t for t in self._hits[key] if t > cutoff]
            if recent:
                self._hits[key] = recent
            else:
                del self._hits[key]

    def blocked(self, key: str) -> bool:
        self._prune()
        return len(self._hits.get(key, ())) >= self.limit

    def hit(self, key: str) -> None:
        self._prune()
        self._hits.setdefault(key, []).append(self._clock())

    def clear(self) -> None:
        self._hits.clear()
