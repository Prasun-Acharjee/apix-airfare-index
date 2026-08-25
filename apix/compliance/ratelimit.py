"""Per-host politeness limiter: crawl-delay spacing plus an hourly ceiling."""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class HostLimiter:
    delay_s: float = 5.0
    max_per_hour: int = 240
    _last: dict[str, float] = field(default_factory=dict)
    _window: dict[str, deque] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def acquire(self, host: str, sleep=time.sleep, now=time.monotonic) -> float:
        """Block until it is polite to hit `host`. Returns seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                t = now()
                win = self._window.setdefault(host, deque())
                while win and t - win[0] > 3600.0:
                    win.popleft()
                if len(win) >= self.max_per_hour:
                    wait = 3600.0 - (t - win[0]) + 0.01
                else:
                    since = t - self._last.get(host, -1e9)
                    wait = max(0.0, self.delay_s - since)
                if wait <= 0.0:
                    self._last[host] = t
                    win.append(t)
                    return waited
            sleep(wait)
            waited += wait
