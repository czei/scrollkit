# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""NVM-backed boot/crash diagnostics + reboot-loop safe-mode breaker.

The store takes an injectable bytearray backend, so the boot-loop logic is fully
testable on desktop with no CircuitPython hardware: a single ``bytearray(_SIZE)``
persists across simulated reboots (each ``Diagnostics(nvm).record_boot()`` is a
fresh boot reading the same NVM).
"""

from scrollkit.utils.diagnostics import (
    Diagnostics, RAPID_BOOT_LIMIT, _SIZE, _MAGIC, _OFF_MAGIC, open as open_diag,
)


def test_boot_loop_breaker_enters_safe_mode():
    """Repeated fault-reboots with no clean run in between trip safe mode; a clean
    run resets the streak."""
    nvm = bytearray(_SIZE)                       # persists across simulated boots

    flags = [Diagnostics(nvm).record_boot("WATCHDOG").safe_mode
             for _ in range(RAPID_BOOT_LIMIT + 2)]
    assert flags[0] is False
    assert flags[-1] is True, "should enter safe mode after repeated fault reboots"

    Diagnostics(nvm).note_clean_run()           # a healthy run clears the streak
    d = Diagnostics(nvm).record_boot("WATCHDOG")
    assert d.rapid_boots == 1
    assert d.safe_mode is False


def test_persists_crash_message_and_counters():
    """Crash text + counters + reset reason survive a simulated reboot."""
    nvm = bytearray(_SIZE)
    d = Diagnostics(nvm).record_boot("POWER_ON")
    assert d.boot_count == 1
    d.record_crash("MemoryError: pystack exhausted")
    d.note_fetch_result(False, consecutive_failures=3)

    d2 = Diagnostics(nvm).record_boot("SOFTWARE")   # next boot reads the record
    assert d2.boot_count == 2
    assert "MemoryError" in d2.last_message
    assert d2.consecutive_failures == 3
    assert d2.summary()["reset_reason"] == "SOFTWARE"


def test_successful_fetch_clears_failure_streak():
    """A healthy refresh resets consecutive failures AND the reboot streak."""
    nvm = bytearray(_SIZE)
    d = Diagnostics(nvm).record_boot("WATCHDOG")
    d.note_fetch_result(False, consecutive_failures=2)
    d.note_fetch_result(True)
    assert d.consecutive_failures == 0
    assert d.rapid_boots == 0
    # The next boot is therefore not in a loop.
    d2 = Diagnostics(nvm).record_boot("WATCHDOG")
    assert d2.rapid_boots == 1
    assert d2.safe_mode is False


def test_magic_or_version_mismatch_resets_record():
    """A garbage/foreign NVM region (wrong magic) is treated as blank and
    re-initialised rather than misread."""
    nvm = bytearray(_SIZE)
    for i in range(_SIZE):                       # poison every byte
        nvm[i] = 0xFF
    assert nvm[_OFF_MAGIC] != _MAGIC
    d = Diagnostics(nvm).record_boot("POWER_ON")
    assert d.boot_count == 1                     # started fresh, not 0xFFFF+1
    assert d.rapid_boots == 1
    assert nvm[_OFF_MAGIC] == _MAGIC             # record was (re)initialised


def test_open_is_noop_off_device():
    """open() must return a usable no-op store on desktop (no NVM)."""
    d = open_diag()
    d.record_boot("UNKNOWN")            # must not raise
    d.record_crash("x")
    d.note_fetch_result(True)
    assert d.safe_mode is False
    assert isinstance(d.summary(), dict)
