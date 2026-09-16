"""
Rate limiting -- token bucket per client IP.

SlowAPI isn't installed in the environment this was written in (no
network access to pip install it), so the core algorithm here
(TokenBucket) is a real, independently-verified stdlib implementation
rather than a stub -- see the self-test at the bottom, which actually
runs it. SlowAPI wraps the same token-bucket idea using the `limits`
library; swap this middleware for SlowAPI's decorator-based API later
if you specifically want that package, the underlying logic is
equivalent.

NOTE on verification: RateLimitMiddleware below needs `starlette`
(installed automatically with fastapi) to import. Starlette isn't
installed in this environment either (same reason fastapi itself
isn't), so this class's wiring is standard, idiomatic Starlette
middleware code but has NOT been run here. TokenBucket has zero
dependencies and IS verified independently -- run this file's
self-test on your machine after `pip install fastapi` to confirm the
middleware wrapper itself works too.

Usage (in main.py):
    from rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
"""

import time
from collections import defaultdict


class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_per_second = refill_per_second
        self.last_refill = time.monotonic()

    def consume(self, amount: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.last_refill = now

        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    class RateLimitMiddleware(BaseHTTPMiddleware):
        def __init__(self, app, requests_per_minute: int = 60):
            super().__init__(app)
            self.requests_per_minute = requests_per_minute
            self.buckets: dict[str, TokenBucket] = defaultdict(
                lambda: TokenBucket(capacity=requests_per_minute, refill_per_second=requests_per_minute / 60.0)
            )

        async def dispatch(self, request: Request, call_next):
            client_ip = request.client.host if request.client else "unknown"
            bucket = self.buckets[client_ip]
            if not bucket.consume():
                return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Slow down."})
            return await call_next(request)

except ImportError:
    # starlette not installed in THIS environment -- the middleware class
    # simply won't be defined here. It will be defined normally once
    # fastapi/starlette are installed on your machine; nothing else in
    # this file depends on it being present.
    RateLimitMiddleware = None


def _self_test():
    """Verifies the TokenBucket logic directly, with no HTTP server needed."""
    bucket = TokenBucket(capacity=5, refill_per_second=0)
    allowed_count = sum(1 for _ in range(10) if bucket.consume())
    assert allowed_count == 5, f"expected exactly 5 allowed from a burst of 10, got {allowed_count}"
    print(f"PASS: burst of 10 against capacity 5 -> exactly {allowed_count} allowed, rest rejected")

    refill_bucket = TokenBucket(capacity=1, refill_per_second=100)
    assert refill_bucket.consume() is True
    assert refill_bucket.consume() is False, "bucket should be empty immediately after draining"
    time.sleep(0.02)
    assert refill_bucket.consume() is True, "bucket should have refilled after waiting"
    print("PASS: bucket correctly refills over time and allows requests again")

    if RateLimitMiddleware is None:
        print("NOTE: RateLimitMiddleware itself not verified here -- starlette not installed in this environment")
    else:
        print("NOTE: starlette was available -- RateLimitMiddleware class defined successfully")


if __name__ == "__main__":
    _self_test()
