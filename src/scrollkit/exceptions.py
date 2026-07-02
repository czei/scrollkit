# Copyright (c) 2024-2026 Michael Czeiszperger
"""ScrollKit exception hierarchy.

Intentionally minimal: only exceptions the library ACTUALLY raises live here.
An earlier hierarchy shipped 13 classes of which the library raised exactly one
(FeasibilityError) — every ``except NetworkError`` etc. could only ever fire if
a *caller* raised it, giving downstream users a false contract. This release
keeps just the four that are raised at a real boundary.

All are plain ``Exception`` subclasses for CircuitPython compatibility.
"""


class ScrollKitError(Exception):
    """Base exception for all ScrollKit errors."""


# 0.8.x compatibility alias: the base was named SLDKError before the rename.
# Kept until a future 0.9.0.
SLDKError = ScrollKitError


class NetworkError(ScrollKitError):
    """A network request failed at the HttpClient boundary.

    Raised by ``HttpClient.get`` / ``get_sync`` / ``post`` after retries are
    exhausted (or when no HTTP client is available). ``HttpClient.last_error``
    retains the raw underlying exception for diagnostics.
    """


class OTAError(ScrollKitError):
    """An OTA update step failed (server error, size or checksum mismatch).

    Raised internally by ``OTAClient`` at its download/verify boundary; the
    public ``OTAClient`` methods catch it and return their ``(ok, reason)``
    tuple, so it does not escape the public API.
    """


class FeasibilityError(ScrollKitError):
    """A modeled frame busts the device time or RAM budget under strict mode.

    Raised only by the desktop simulator's ``PerformanceManager`` when strict
    hardware simulation is enabled and a frame's modeled cost exceeds the
    per-frame budget (steady-state median or the single-frame transient ceiling)
    or modeled peak RAM exceeds the device's usable RAM. Never raised on
    CircuitPython, where the timing model is a no-op. Defined here (not in the
    simulator) so the harness, tests, and callers can import it without pulling
    in the simulator.
    """


__all__ = ["ScrollKitError", "SLDKError", "NetworkError", "OTAError",
           "FeasibilityError"]
