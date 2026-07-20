# Copyright (c) 2024-2026 Michael Czeiszperger
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


# --------------------------------------------------------------------------- #
# v2: WHEN stamps (2026-07-17) — errors carry wall time / uptime / boot#, and
# the last SUCCESSFUL fetch time is persisted, so the config page can show
# whether the box fetched once at boot and has been failing ever since.
# --------------------------------------------------------------------------- #
from scrollkit.utils.diagnostics import _u32, _OFF_OK_TIME


def test_crash_when_stamps_survive_reboot(monkeypatch):
    import time as _time
    monkeypatch.setattr(_time, "time", lambda: 1789000000)
    monkeypatch.setattr(_time, "monotonic", lambda: 1234.9)
    nvm = bytearray(_SIZE)
    d = Diagnostics(nvm).record_boot("POWER_ON")
    d.record_crash("OSError: 16 at _get_connected_socket")

    s = Diagnostics(nvm).record_boot("SOFTWARE").summary()
    assert s["last_error_time"] == 1789000000
    assert s["last_error_uptime"] == 1234
    assert s["last_error_boot"] == 1          # recorded on the PREVIOUS boot
    assert s["boot_count"] == 2


def test_clock_unset_stores_zero_epoch_but_keeps_uptime(monkeypatch):
    """Pre-NTP crashes (e.g. during WiFi join): wall time must read 'unknown'
    (0), never the bogus year-2000 unset-RTC epoch — uptime still tells WHEN."""
    import time as _time
    monkeypatch.setattr(_time, "time", lambda: 946684805.0)   # unset RTC
    monkeypatch.setattr(_time, "monotonic", lambda: 38.2)
    nvm = bytearray(_SIZE)
    Diagnostics(nvm).record_boot("POWER_ON").record_crash("boom")

    s = Diagnostics(nvm).record_boot("SOFTWARE").summary()
    assert s["last_error_time"] == 0
    assert s["last_error_uptime"] == 38


def test_last_ok_time_throttled_then_flushed_exact_on_failure(monkeypatch):
    """Healthy refreshes persist the success time at most every 30 min (NVM
    wear); the moment a failure happens the EXACT last success is flushed, so
    post-mortems never read a stale 'last worked at' value."""
    import time as _time
    clock = [1789000000]
    monkeypatch.setattr(_time, "time", lambda: clock[0])
    monkeypatch.setattr(_time, "monotonic", lambda: 0.0)
    nvm = bytearray(_SIZE)
    d = Diagnostics(nvm).record_boot("POWER_ON")

    d.note_fetch_result(True)                     # first success: persisted
    assert _u32(nvm, _OFF_OK_TIME) == 1789000000

    clock[0] += 600
    d.note_fetch_result(True)                     # +10 min: RAM only (throttle)
    assert _u32(nvm, _OFF_OK_TIME) == 1789000000

    clock[0] += 60
    d.note_fetch_result(False, consecutive_failures=1)   # failure: exact flush
    assert _u32(nvm, _OFF_OK_TIME) == 1789000600

    s = Diagnostics(nvm).record_boot("WATCHDOG").summary()
    assert s["last_ok_time"] == 1789000600


def test_record_crash_on_fresh_instance_reads_boot_from_nvm():
    """base's _auto_reboot and the top-level crash handler call record_crash on
    a FRESH diagnostics.open() that never ran record_boot — the boot# stamp
    must come from the NVM record, not the instance's zero."""
    nvm = bytearray(_SIZE)
    Diagnostics(nvm).record_boot("POWER_ON")                 # the live boot: #1
    Diagnostics(nvm).record_crash("auto-reboot: 12 consecutive refresh failures")

    s = Diagnostics(nvm).record_boot("SOFTWARE").summary()
    assert s["last_error_boot"] == 1


def test_v1_record_resets_not_misread():
    """A well-formed FIELDED v1 record (magic ok, version byte 1) must be RESET
    once on upgrade, never read through the v2 layout — v1's message bytes sit
    exactly where v2 reads its u32 WHEN stamps, so accepting it would render
    garbage timestamps on every fielded device."""
    from scrollkit.utils.diagnostics import _VERSION, _OFF_VERSION
    nvm = bytearray(_SIZE)
    nvm[_OFF_MAGIC] = _MAGIC
    nvm[_OFF_VERSION] = 1                        # v1 layout follows
    nvm[2] = 130                                 # v1 boot count
    msg = b"OSError: 16"
    nvm[8] = len(msg)                            # v1 _OFF_MSG_LEN
    nvm[9:9 + len(msg)] = msg                    # v1 _OFF_MSG

    s = Diagnostics(nvm).record_boot("POWER_ON").summary()
    assert s["boot_count"] == 1                  # started fresh, not 131
    assert s["last_error"] == ""
    assert s["last_error_time"] == 0
    assert s["last_error_uptime"] == 0
    assert s["last_ok_time"] == 0
    assert nvm[_OFF_VERSION] == _VERSION         # record rewritten as v2


# --- failure-reboot epoch flag + safemode reserved range (2026-07-19) ---------

def test_deliberate_reboot_epoch_lifecycle():
    """The flag marks 'a failure-driven reboot happened; no fetch success
    since' so the NEXT failure reboot is rate-limited. It must survive the
    reboot it announces (record_boot preserves it), survive a stable-uptime
    clean run (note_clean_run), and end ONLY on a real fetch success."""
    nvm = bytearray(_SIZE)
    d = Diagnostics(nvm).record_boot("SOFTWARE")
    assert d.was_deliberate_reboot() is False

    d.note_deliberate_reboot()
    # A fresh open() (no record_boot) reads it straight from NVM — this is how
    # note_refresh_result checks it at runtime.
    assert Diagnostics(nvm).was_deliberate_reboot() is True

    d2 = Diagnostics(nvm).record_boot("SOFTWARE")   # the reboot itself
    assert d2.was_deliberate_reboot() is True        # preserved through boot

    d2.note_clean_run()                              # stable uptime...
    assert d2.was_deliberate_reboot() is True        # ...does NOT end the epoch

    d2.note_fetch_result(True)                       # a real success does
    assert d2.was_deliberate_reboot() is False


def test_deliberate_reboot_epoch_in_summary():
    nvm = bytearray(_SIZE)
    d = Diagnostics(nvm).record_boot("SOFTWARE")
    assert d.summary()["failure_reboot_epoch"] is False
    d.note_deliberate_reboot()
    assert d.summary()["failure_reboot_epoch"] is True


def test_safe_mode_flag_unaffected_by_epoch_flag():
    """Both flags share the NVM flags byte — they must not clobber each other."""
    nvm = bytearray(_SIZE)
    for _ in range(RAPID_BOOT_LIMIT + 2):
        d = Diagnostics(nvm).record_boot("WATCHDOG")
    assert d.safe_mode is True
    d.note_deliberate_reboot()
    d2 = Diagnostics(nvm).record_boot("WATCHDOG")
    assert d2.safe_mode is True                      # still in safe mode
    assert d2.was_deliberate_reboot() is True        # and still in the epoch


def test_ledger_stays_below_safemode_reserved_range():
    """/safemode.py (the app's CP-safe-mode escape hatch) hard-codes NVM bytes
    240/241; the diagnostics ledger must never grow into them."""
    from scrollkit.utils.diagnostics import SAFEMODE_RESERVED_START
    assert SAFEMODE_RESERVED_START == 240
    assert _SIZE <= SAFEMODE_RESERVED_START


def test_note_fetch_result_rearm_false_is_stamp_only():
    """PARTIAL refreshes (2026-07-19): rearm=False stamps the success time but
    must NOT clean-run or end the failure-reboot epoch — a partial success
    must never read as full health to the recovery machinery."""
    nvm = bytearray(_SIZE)
    d = Diagnostics(nvm).record_boot("SOFTWARE")
    d.note_deliberate_reboot()
    assert d.rapid_boots == 1

    d.note_fetch_result(True, rearm=False)
    assert d.rapid_boots == 1                    # no clean run
    assert d.was_deliberate_reboot() is True     # epoch intact

    d.note_fetch_result(True)                    # FULL health (default rearm)
    assert d.rapid_boots == 0
    assert d.was_deliberate_reboot() is False
