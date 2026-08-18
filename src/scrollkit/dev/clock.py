# Copyright (c) 2024-2026 Michael Czeiszperger
"""A virtual clock for headless and preview runs — device time, not host time.

ScrollKit's duration-driven content asks the clock how long an item has been on
screen (``display/content.py``), and so do particle effects. Both read wall time,
which is right on the device and wrong everywhere a run is not paced to it:

* **Unpaced, the content freezes.** ``run_headless`` steps frames with no
  inter-frame sleep, so 60 frames pass in about 0.2 s of wall time, a
  ``duration=2.0`` item never expires, the queue never advances, and a perfectly
  correct animated sign scores as "never animates."
* **Paced to the host, the content lies.** A clock derived from a fixed rate —
  say 20 fps — makes a sign that models 71 fps advance its content three and a
  half times slower than the panel will. What you approve is not what runs.

Both go away if time comes from the same place the frame budget does. The
``PerformanceManager`` already accumulates modeled device microseconds per frame,
from operations rather than from wall time, so a clock built on it says what the
board's clock would say, and says it identically on CPython and in Pyodide. Frame
hashes are unaffected by pacing for the same reason.

    from scrollkit.dev import run_headless
    run_headless(app, frames=60, virtual_clock=True)      # the usual way

    from scrollkit.dev.clock import install_virtual_clock, uninstall_virtual_clock
    install_virtual_clock()                                # driving your own loop
    try:
        ...
    finally:
        uninstall_virtual_clock()

The clock resolves the active manager on **every read** rather than capturing it
at install time. A harness creates the manager while building the display, which
is usually after the caller wanted to install the clock, and a run that ends
clears it — a captured reference would be stale in both directions.

Desktop-only, like the rest of ``scrollkit.dev``: on the device, wall time is
device time and there is nothing to inject.
"""

_ORIGINALS = {}


class VirtualClockUnavailable(RuntimeError):
    """Raised when the clock is read with no performance model to read from.

    Loudly, and on the first frame. The alternative — returning 0.0 and letting
    the run continue — is the frozen-content bug this module exists to remove,
    wearing a different hat.
    """


def modeled_device_time():
    """Seconds of modeled device time since the run began.

    The default clock source. Advances by what the frame cost the *panel*, so a
    sign whose content changes every two seconds changes every two seconds of
    device time no matter how fast the host renders it.
    """
    from ..simulator.core.performance_manager import get_active

    pm = get_active()
    if pm is None:
        raise VirtualClockUnavailable(
            "the virtual clock needs the hardware timing model active: run with "
            "run_headless(..., hardware=True) or SCROLLKIT_HW_SIM=1, or pass "
            "install_virtual_clock(source=...) a clock of your own"
        )
    return pm.modeled_elapsed_s


def install_virtual_clock(source=None):
    """Point ScrollKit's content and particle clocks at ``source``.

    ``source`` is any callable returning seconds as a float; it defaults to
    :func:`modeled_device_time`. Returns the installed callable.

    Idempotent in the way that matters: installing twice does not stack, and the
    original wall-clock readers are remembered from the first install, so
    :func:`uninstall_virtual_clock` always restores the real thing rather than a
    previous injection.
    """
    clock = modeled_device_time if source is None else source

    from ..display import content as _content

    if "content" not in _ORIGINALS:
        _ORIGINALS["content"] = _content.get_time
    _content.get_time = clock

    # Imported rather than patched-if-present: a module imported *after* the
    # install would otherwise rebind its own module-level get_time to wall time
    # and silently opt itself out.
    try:
        from ..effects import particles as _particles
    except Exception:                      # pragma: no cover - optional subpackage
        pass
    else:
        if "particles" not in _ORIGINALS:
            _ORIGINALS["particles"] = _particles.get_time
        _particles.get_time = clock

    return clock


def uninstall_virtual_clock():
    """Put the wall-clock readers back. Safe to call when nothing is installed."""
    if "content" in _ORIGINALS:
        from ..display import content as _content

        _content.get_time = _ORIGINALS.pop("content")
    if "particles" in _ORIGINALS:
        from ..effects import particles as _particles

        _particles.get_time = _ORIGINALS.pop("particles")


def virtual_clock_installed():
    """Is a virtual clock currently in place?"""
    return bool(_ORIGINALS)
