"""UUIDv7 generation (RFC 9562). Python 3.13's stdlib has no uuid7()."""

import os
import threading
import time
import uuid

_lock = threading.Lock()
_last_ms = 0
_counter = 0  # 12-bit sequence in rand_a keeps ids monotonic within one millisecond


def uuid7() -> uuid.UUID:
    """Return a time-ordered UUIDv7, monotonic within this process."""
    global _last_ms, _counter
    with _lock:
        ms = time.time_ns() // 1_000_000
        if ms > _last_ms:
            _last_ms = ms
            _counter = int.from_bytes(os.urandom(2)) & 0x7FF  # leave headroom before overflow
        else:
            _counter += 1
            if _counter > 0xFFF:  # sequence exhausted: borrow the next millisecond
                _last_ms += 1
                _counter = 0
            ms = _last_ms
        rand_a = _counter

    rand_b = int.from_bytes(os.urandom(8)) & ((1 << 62) - 1)
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76  # version
    value |= rand_a << 64
    value |= 0b10 << 62  # RFC 4122 variant
    value |= rand_b
    return uuid.UUID(int=value)
