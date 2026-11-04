from app.services.rate_limit import SlidingWindow


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_blocks_only_after_the_limit():
    limiter = SlidingWindow(limit=2, window_seconds=60, clock=Clock())
    assert not limiter.blocked("a")
    limiter.hit("a")
    assert not limiter.blocked("a")
    limiter.hit("a")
    assert limiter.blocked("a")


def test_recovers_after_the_window():
    clock = Clock()
    limiter = SlidingWindow(limit=1, window_seconds=60, clock=clock)
    limiter.hit("a")
    clock.now += 59
    assert limiter.blocked("a")
    clock.now += 1
    assert not limiter.blocked("a")


def test_keys_are_independent():
    limiter = SlidingWindow(limit=1, window_seconds=60, clock=Clock())
    limiter.hit("a")
    assert not limiter.blocked("b")


def test_expired_keys_are_forgotten():
    clock = Clock()
    limiter = SlidingWindow(limit=1, window_seconds=60, clock=clock)
    limiter.hit("a")
    clock.now += 60
    limiter.hit("b")
    assert "a" not in limiter._hits


def test_clear():
    limiter = SlidingWindow(limit=1, window_seconds=60, clock=Clock())
    limiter.hit("a")
    limiter.clear()
    assert not limiter.blocked("a")
