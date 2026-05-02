"""
utils/rate_limiter.py (local model: only keep a small delay to avoid CPU thrashing)
"""

import time
import threading

class RateLimiter:
    def __init__(self, min_delay_between_calls: float = 0.3):
        self.min_delay = min_delay_between_calls
        self._last_call_time: float = 0.0
        self._lock = threading.Lock()

    def wait_if_needed(self, estimated_tokens: int = 0) -> None:
        with self._lock:
            since_last = time.time() - self._last_call_time
            if since_last < self.min_delay:
                time.sleep(self.min_delay - since_last)

    def record(self, tokens_used: int = 0) -> None:
        with self._lock:
            self._last_call_time = time.time()

# Singleton
rate_limiter = RateLimiter(min_delay_between_calls=0.5)  # gentle for local CPU