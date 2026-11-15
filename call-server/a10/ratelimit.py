import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict


class RateLimiter:
    """Sliding-window limiter kept in memory (fine for one server process)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.hits: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_s: float) -> bool:
        now = self.clock()
        q = self.hits[key]
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        if len(self.hits) > 20000:  # crude memory guard
            for k in [k for k, v in self.hits.items() if not v][:5000]:
                self.hits.pop(k, None)
        return True
