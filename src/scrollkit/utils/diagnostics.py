# Copyright (c) 2024-2026 Michael Czeiszperger
"""On-device crash/boot diagnostics, persisted in ``microcontroller.nvm``.

Why this exists: a field device can go black with no usable logs — a flash log
fills and is wiped on every reboot, so a crash erases its own evidence. NVM
survives BOTH soft resets and power loss and is independent of the filesystem, so
a compact fixed-size record here lets an app:

  * **break a reboot loop** from a deterministic fault (bad settings, an API
    change that crashes every boot): after a few fault-resets with no clean run,
    drop into *safe mode* (no fetch; keep the config web UI up) instead of
    resetting forever;
  * **explain "why it went black"** on a config web UI without a serial cable
    (reset reason, last exception, consecutive failures, last success).

NVM is wear-limited, so we write SPARINGLY: once per boot and only on state
changes (first clean run, a crash) — never per refresh.

The store takes an injectable ``backend`` (anything that behaves like a mutable
``bytearray``) so the boot-loop logic is unit-tested on desktop; on hardware the
backend is ``microcontroller.nvm``. On desktop with no NVM, ``open()`` returns a
no-op store so callers never need platform checks.

Usage::

    from scrollkit.utils import diagnostics

    diag = diagnostics.open()                       # NVM on device, no-op on desktop
    diag.record_boot(diagnostics.read_reset_reason())
    if diag.safe_mode:
        ...                                        # skip the fetch; keep the UI up
    diag.note_fetch_result(ok=True)                # on a healthy refresh
"""

# Fixed binary layout at the head of NVM. Tiny and stable; bump _VERSION if it
# changes (a version/magic mismatch resets the record).
_MAGIC = 0x7A
_VERSION = 2                 # v2: WHEN stamps (error time/uptime/boot#, last-ok
                             # time) — a bare error text can't distinguish "one
                             # blip yesterday" from "failing since boot"

_OFF_MAGIC = 0
_OFF_VERSION = 1
_OFF_BOOT_COUNT = 2          # 2 bytes, wraps
_OFF_RAPID_BOOTS = 4         # 1 byte: boots since the last clean run
_OFF_RESET_REASON = 5        # 1 byte: code from _REASON_CODES
_OFF_CONSEC_FAILS = 6        # 1 byte: consecutive fetch failures (last known)
_OFF_FLAGS = 7              # 1 byte: bit0 = entered safe mode last boot
_OFF_ERR_TIME = 8          # 4 bytes: epoch when last_error was recorded (0 = clock unset)
_OFF_ERR_UPTIME = 12       # 4 bytes: seconds since power-up when it was recorded
_OFF_ERR_BOOT = 16         # 2 bytes: boot_count that recorded it
_OFF_OK_TIME = 18          # 4 bytes: epoch of the last successful fetch (0 = never)
_OFF_MSG_LEN = 22          # 1 byte
_OFF_MSG = 23              # ascii crash/exception text
MSG_MAX = 180
_SIZE = _OFF_MSG + MSG_MAX

# RESERVED, not ours: NVM bytes 240 (magic 0x5A) / 241 (counter) belong to the
# consuming app's /safemode.py — the CircuitPython-safe-mode escape hatch runs
# with no imports available, so it hard-codes those offsets. This ledger must
# stay below 240 (_SIZE is 203; a layout test pins the invariant).
SAFEMODE_RESERVED_START = 240

# Epochs below this (2020-01-01) mean the RTC was never set (CircuitPython's
# unset clock starts at 2000-01-01) — stored as 0 so readers can tell.
_EPOCH_VALID = 1577836800


def _now_epoch():
    """Wall-clock epoch, or 0 when the clock was never set / unavailable."""
    try:
        import time
        t = int(time.time())
        return t if t >= _EPOCH_VALID else 0
    except Exception:
        return 0


def _uptime_s():
    """Whole seconds since power-up (monotonic), or 0 when unavailable."""
    try:
        import time
        return int(time.monotonic())
    except Exception:
        return 0


def _u16(buf, off):
    return buf[off] | (buf[off + 1] << 8)


def _u32(buf, off):
    return (buf[off] | (buf[off + 1] << 8)
            | (buf[off + 2] << 16) | (buf[off + 3] << 24))

# After this many resets with no intervening clean run, enter safe mode.
RAPID_BOOT_LIMIT = 4

_FLAG_SAFE_MODE = 0x01
# Set by note_deliberate_reboot() just before a failure-driven auto-reboot and
# cleared only by a SUCCESSFUL fetch (note_fetch_result(ok=True)) — NOT by
# note_clean_run(), which stable uptime also fires. While set, the device is in
# a "failure-reboot epoch": the app has rebooted for failing refreshes and no
# fetch has succeeded since, so the next failure-driven reboot should wait out
# a cooldown instead of firing every ~13 minutes (review 2026-07-19).
_FLAG_DELIBERATE_REBOOT = 0x02

# microcontroller.ResetReason names we care about -> small codes (and back, for
# display). Stored as a code so we don't depend on the enum at read time.
_REASON_NAMES = ("UNKNOWN", "POWER_ON", "BROWNOUT", "SOFTWARE",
                 "DEEP_SLEEP_ALARM", "RESET_PIN", "WATCHDOG")


__all__ = ['Diagnostics', 'open', 'read_reset_reason', 'MSG_MAX', 'RAPID_BOOT_LIMIT']

class Diagnostics:
    """Compact NVM-backed boot/crash record. All methods are failure-tolerant."""

    def __init__(self, backend):
        self._nvm = backend
        # Per-boot snapshot, filled by record_boot().
        self.boot_count = 0
        self.rapid_boots = 0
        self.reset_reason = "UNKNOWN"
        self.safe_mode = False
        self.last_message = ""
        self.consecutive_failures = 0
        # WHEN stamps (0 = unknown): read from NVM by record_boot(), written by
        # record_crash() / note_fetch_result().
        self.last_error_time = 0     # epoch (0 = clock unset when recorded)
        self.last_error_uptime = 0   # seconds after power-up
        self.last_error_boot = 0     # boot_count that recorded it
        self.last_ok_time = 0        # epoch of last successful fetch (persisted)
        self._ram_ok_time = 0        # exact last success, flushed on failure/crash

    # --- low-level helpers ---------------------------------------------------
    def _read(self):
        try:
            n = self._nvm
            if n is None or len(n) < _SIZE:
                return None
            if n[_OFF_MAGIC] != _MAGIC or n[_OFF_VERSION] != _VERSION:
                return None
            return bytes(n[0:_SIZE])
        except Exception:
            return None

    def _write_byte(self, offset, value):
        try:
            self._nvm[offset] = value & 0xFF
        except Exception:
            pass

    def _write_u16(self, offset, value):
        try:
            self._nvm[offset] = value & 0xFF
            self._nvm[offset + 1] = (value >> 8) & 0xFF
        except Exception:
            pass

    def _write_u32(self, offset, value):
        try:
            # One slice assignment (one NVM mutation), not four byte stores.
            self._nvm[offset:offset + 4] = bytes(
                (value >> s) & 0xFF for s in (0, 8, 16, 24))
        except Exception:
            pass

    def _init_blank(self):
        try:
            self._nvm[_OFF_MAGIC] = _MAGIC
            self._nvm[_OFF_VERSION] = _VERSION
            # Zero every fixed field (offsets 2 .. _OFF_MSG_LEN inclusive).
            self._nvm[_OFF_BOOT_COUNT:_OFF_MSG_LEN + 1] = bytes(
                _OFF_MSG_LEN + 1 - _OFF_BOOT_COUNT)
        except Exception:
            pass

    # --- public API ----------------------------------------------------------
    def record_boot(self, reset_reason_name="UNKNOWN"):
        """Call once at the very start of boot. Increments counters, classifies
        whether we're in a reboot loop, and returns ``self`` for chaining.

        ``reset_reason_name`` is the ``microcontroller.cpu.reset_reason`` name
        (the caller reads it; we just store the code so the web UI can show it)."""
        raw = self._read()
        if raw is None:
            self._init_blank()
            raw = self._read() or bytes(_SIZE)

        self.boot_count = _u16(raw, _OFF_BOOT_COUNT) + 1
        self.last_error_time = _u32(raw, _OFF_ERR_TIME)
        self.last_error_uptime = _u32(raw, _OFF_ERR_UPTIME)
        self.last_error_boot = _u16(raw, _OFF_ERR_BOOT)
        self.last_ok_time = _u32(raw, _OFF_OK_TIME)
        # "Boots since the last clean run": every boot increments this; a healthy
        # device zeroes it via note_clean_run() on its first good fetch, so it only
        # climbs when boots keep happening with no clean run between them (a reboot
        # loop). reset_reason is recorded for display but does NOT gate this count.
        self.rapid_boots = raw[_OFF_RAPID_BOOTS] + 1
        self.reset_reason = reset_reason_name
        self.consecutive_failures = raw[_OFF_CONSEC_FAILS]
        msg_len = min(raw[_OFF_MSG_LEN], MSG_MAX)
        try:
            self.last_message = bytes(raw[_OFF_MSG:_OFF_MSG + msg_len]).decode("ascii")
        except Exception:
            self.last_message = ""

        self.safe_mode = self.rapid_boots > RAPID_BOOT_LIMIT

        self._write_u16(_OFF_BOOT_COUNT, self.boot_count)
        self._write_byte(_OFF_RAPID_BOOTS, min(self.rapid_boots, 255))
        try:
            self._write_byte(_OFF_RESET_REASON, _REASON_NAMES.index(reset_reason_name))
        except Exception:
            self._write_byte(_OFF_RESET_REASON, 0)
        flags = _FLAG_SAFE_MODE if self.safe_mode else 0
        # Preserve the failure-reboot-epoch marker across the reboot it caused:
        # note_refresh_result reads it THIS boot to rate-limit the next
        # failure-driven reboot. Cleared only by a successful fetch.
        if raw[_OFF_FLAGS] & _FLAG_DELIBERATE_REBOOT:
            flags |= _FLAG_DELIBERATE_REBOOT
        self._write_byte(_OFF_FLAGS, flags)
        return self

    def note_clean_run(self):
        """Call once the device is healthy (first successful fetch / stable run).
        Zeroes the reboot-loop counter so transient single crashes never
        accumulate into safe mode."""
        self.rapid_boots = 0
        self._write_byte(_OFF_RAPID_BOOTS, 0)

    def note_fetch_result(self, ok, consecutive_failures=0, rearm=None):
        """Record refresh outcome (state-change only — cheap). A success also
        stamps the last-success time; whether it ALSO re-arms recovery state
        (clean run + ending the failure-reboot epoch) is gated by ``rearm``:

        * ``None`` (default): the success itself re-arms — the historical
          behavior, correct for FULL-health callers.
        * ``False``: stamp the time only. For PARTIAL refreshes (some parks
          failed) — a partial must never read as full health to the recovery
          machinery (2026-07-19: three parks failed MemoryError for hours
          behind an all-green dashboard).
        """
        self.consecutive_failures = 0 if ok else consecutive_failures
        self._write_byte(_OFF_CONSEC_FAILS, min(self.consecutive_failures, 255))
        if ok:
            now = _now_epoch()
            if now:
                self._ram_ok_time = now
            # Healthy path: persist at most every 30 min (NVM wear); the exact
            # value is flushed the moment anything goes wrong below.
            self._persist_ok_time(min_gap=1800)
            if rearm is None or rearm:
                self.note_clean_run()
                # A real FULL fetch success ends the failure-reboot epoch
                # (stable uptime alone must NOT — the rate limit exists
                # precisely for boots that stay up but keep failing).
                self._clear_deliberate_reboot()
        else:
            self._persist_ok_time()

    def note_deliberate_reboot(self):
        """Mark that a deliberate failure-driven reboot is about to happen.

        Read back after the reboot via ``was_deliberate_reboot()`` to
        rate-limit the NEXT failure-driven reboot; cleared only by a
        successful fetch (``note_fetch_result(ok=True)``)."""
        try:
            raw = self._read()
            flags = raw[_OFF_FLAGS] if raw else 0
            self._write_byte(_OFF_FLAGS, flags | _FLAG_DELIBERATE_REBOOT)
        except Exception:
            pass

    def was_deliberate_reboot(self):
        """True while in a failure-reboot epoch (a failure-driven reboot with
        no fetch success since). Reads NVM directly so a fresh ``open()`` that
        never ran ``record_boot`` still answers correctly."""
        try:
            raw = self._read()
            return bool(raw and (raw[_OFF_FLAGS] & _FLAG_DELIBERATE_REBOOT))
        except Exception:
            return False

    def _clear_deliberate_reboot(self):
        try:
            raw = self._read()
            if raw and (raw[_OFF_FLAGS] & _FLAG_DELIBERATE_REBOOT):
                self._write_byte(_OFF_FLAGS,
                                 raw[_OFF_FLAGS] & ~_FLAG_DELIBERATE_REBOOT)
        except Exception:
            pass

    def _persist_ok_time(self, min_gap=0):
        """Write the RAM-held last-success epoch to NVM when it moved forward.
        ``min_gap`` throttles healthy-path writes; failure/crash paths pass 0 so
        the persisted value is EXACT whenever a failure gets diagnosed."""
        if not self._ram_ok_time or self._ram_ok_time <= self.last_ok_time:
            return
        if min_gap and (self._ram_ok_time - self.last_ok_time) < min_gap:
            return
        self.last_ok_time = self._ram_ok_time
        self._write_u32(_OFF_OK_TIME, self.last_ok_time)

    def record_crash(self, message):
        """Persist the last fatal exception text (truncated) before a reset,
        stamped with WHEN: wall clock (0 if the clock was never set), uptime,
        and the boot number it happened on."""
        try:
            text = "".join(c for c in str(message) if 32 <= ord(c) < 128)[:MSG_MAX]
            data = text.encode("ascii")
            self._write_byte(_OFF_MSG_LEN, len(data))
            for i, b in enumerate(data):
                self._nvm[_OFF_MSG + i] = b
            self.last_message = text
            self.last_error_time = _now_epoch()
            self.last_error_uptime = _uptime_s()
            # _auto_reboot and top-level crash handlers call record_crash on a
            # FRESH open() that never ran record_boot — read the boot# from the
            # record itself rather than stamping this instance's zero.
            boot = self.boot_count
            if not boot:
                raw = self._read()
                if raw is not None:
                    boot = _u16(raw, _OFF_BOOT_COUNT)
            self.last_error_boot = boot
            self._write_u32(_OFF_ERR_TIME, self.last_error_time)
            self._write_u32(_OFF_ERR_UPTIME, self.last_error_uptime)
            self._write_u16(_OFF_ERR_BOOT, self.last_error_boot)
            self._persist_ok_time()
        except Exception:
            pass

    def summary(self):
        """Dict for the config web UI / logs. Times are raw epochs (0 = unknown;
        error time 0 with a nonzero uptime = clock wasn't set when it happened)."""
        return {
            "boot_count": self.boot_count,
            "reboot_streak": self.rapid_boots,
            "reset_reason": self.reset_reason,
            "safe_mode": self.safe_mode,
            "failure_reboot_epoch": self.was_deliberate_reboot(),
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_message,
            "last_error_time": self.last_error_time,
            "last_error_uptime": self.last_error_uptime,
            "last_error_boot": self.last_error_boot,
            "last_ok_time": self.last_ok_time,
        }


class _NullDiagnostics(Diagnostics):
    """No-op store for desktop / when NVM is unavailable."""
    def __init__(self):
        super().__init__(None)

    def record_boot(self, reset_reason_name="UNKNOWN"):
        return self

    def note_clean_run(self):
        pass

    def note_fetch_result(self, ok, consecutive_failures=0, rearm=None):
        pass

    def record_crash(self, message):
        pass


def read_reset_reason():
    """Return the microcontroller reset-reason NAME, or 'UNKNOWN' off-device."""
    try:
        import microcontroller
        return str(microcontroller.cpu.reset_reason).rsplit(".", 1)[-1]
    except Exception:
        return "UNKNOWN"


def open():
    """Return a Diagnostics bound to NVM on hardware, else a no-op store."""
    try:
        import microcontroller
        nvm = microcontroller.nvm
        if nvm is not None and len(nvm) >= _SIZE:
            return Diagnostics(nvm)
    except Exception:
        pass
    return _NullDiagnostics()
