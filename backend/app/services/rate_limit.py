import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """In-memory limiter: at most max_attempts per key within window_seconds (per process)."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_attempts:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


login_limiter = SlidingWindowLimiter(max_attempts=10, window_seconds=60)

assistant_limiter = SlidingWindowLimiter(max_attempts=20, window_seconds=60)
