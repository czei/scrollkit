"""On-device reliability harness — host-orchestrated over USB (6 phases).

Validates the field-reliability fixes (base.py watchdog/memory, http_client timeout,
error_handler rotation/singleton) against a REAL MatrixPortal S3, by deliberately
inducing the failure modes the simulator physically cannot reproduce. Each phase
maps to a fix and tests the genuinely hardware/CircuitPython-specific part of it
(the pure logic is already covered by the desktop unit suite).

  A  watchdog timeout premise   (non-destructive)  — fix #1
       Probe which timeouts microcontroller.watchdog accepts. On the ESP32-S3
       (CP 9.2.7 AND 10.2.1) every value up to 30s is accepted — the once-assumed
       ~8.3s ValueError cap does not exist. PASS = the default 8s is accepted (so
       the watchdog can arm); the cap finding is reported as info.
  B  watchdog actually resets    (REBOOTS)          — fix #1
       Arm 8s, stop feeding ~15s (a stand-in for a hung synchronous fetch). The
       board must hard-reset; after reboot microcontroller.cpu.reset_reason must
       read WATCHDOG.
  C  HTTP timeout < watchdog      (neg REBOOTS)      — fix #3
       A single synchronous adafruit_requests GET to a black-hole. timeout=6 blocks
       ~6s < the 8s watchdog -> NO reset (positive). The negative control timeout=20
       blocks past the window -> a false WATCHDOG reset. (Tests the real socket-
       timeout-vs-watchdog interaction; HttpClient passing the timeout to session.get
       is separately unit-verified by test_get_request_adafruit.)
  D  log tail-trim primitive      (non-destructive)  — fix #4
       The rotation fallback rewrites the log keeping its last N bytes via a binary
       end-relative seek. Confirm `seek(-8192, 2)` works on the device filesystem and
       that the trim shrinks the file while preserving the most recent line.
  E  singleton identity           (non-destructive)  — fix #5
       Confirm a __new__-based singleton + _initialized guard returns one shared
       instance with shared state on CircuitPython (the pattern ErrorHandler uses;
       __new__ on CircuitPython was a long-standing open compat question).
  F  memory floor + force logic   (non-destructive)  — fix #2
       Report the device's real free heap (is the 25000 floor reachable?) and verify
       the "force a refresh after N consecutive low-memory skips" counter logic.

WHY HOST-ORCHESTRATED CAN TEST THE WATCHDOG AT ALL
--------------------------------------------------
ScrollKitApp._arm_watchdog skips arming while supervisor.runtime.serial_connected
(so it never reboots you mid-debug). Because this harness is attached over USB, that
guard would always fire — so the phases arm microcontroller.watchdog DIRECTLY. The
hardware watchdog resets regardless of USB. Consequence: this validates the hardware
behaviour + the timeout invariant; the library's full _arm_watchdog path (with the
serial guard) is only exercised when the app runs headless.

PREREQUISITES
-------------
  * A MatrixPortal S3 on USB serial. Set PORT below or pass it as argv[1]. Find it
    with: ls /dev/cu.usbmodem*    (macOS) — the default matches cpy_repl.py.
  * Ideally the board idles at the REPL. If a code.py auto-runs an app, the runner's
    Ctrl-C interrupts it each phase; results are unaffected, but a clean board is
    tidier. (No scrollkit install is required — the phases are self-contained.)
  * Phase C needs WiFi + outbound network: it reads CIRCUITPY_WIFI_SSID/PASSWORD,
    falling back to secrets.py keys ssid/password; it self-skips if neither connects.
    adafruit_requests must be importable — it auto-adds /src/lib to sys.path (where
    ThemeParkWaits keeps it); adjust if your board stores it elsewhere.
  * SLOW_URL must accept the connection but not answer within the timeout. The
    default TEST-NET-1 address is unrouted, so the connect hangs until the timeout.

THIS DELIBERATELY REBOOTS THE BOARD (phases B and C-negative). Dev diagnostic only,
never shipped. Full background, findings and repeat instructions:
test/claude/RELIABILITY_TESTING.md

    python test/claude/reliability_harness.py [/dev/cu.usbmodemXXXX]
"""

import sys
import time

import serial

from cpy_repl import run_on_device, _read_until, PORT, BAUD

SLOW_URL = "http://192.0.2.1/"   # TEST-NET-1 (RFC 5737): unrouted -> connect hangs
WATCHDOG_ARM_S = 8               # honored on CP 9.2.7 and 10.2.1
HTTP_OK_TIMEOUT = 6              # fix #3 default: below the watchdog
HTTP_BAD_TIMEOUT = 20            # negative control: above the watchdog


# --------------------------------------------------------------------------- #
# Reset-aware orchestration (run_on_device can't survive a reboot)            #
# --------------------------------------------------------------------------- #
def run_until_reset(code, port, baud=BAUD, settle=20.0):
    """Send `code` via raw REPL and watch for a reset. Returns (reset, output).

    A reset is detected when the native-USB serial drops (the board re-enumerates on
    reset) or the CircuitPython boot banner reappears.
    """
    out = bytearray()
    try:
        with serial.Serial(port, baud, timeout=1) as ser:
            ser.write(b"\r\x03\x03")
            time.sleep(0.3)
            ser.reset_input_buffer()
            ser.write(b"\r\x01")
            _read_until(ser, b"raw REPL; CTRL-B to exit\r\n>", timeout=5)
            ser.write(code.encode("utf-8"))
            ser.write(b"\x04")
            deadline = time.monotonic() + settle
            while time.monotonic() < deadline:
                try:
                    chunk = ser.read(128)
                except (serial.SerialException, OSError):
                    return True, out.decode("utf-8", "replace")
                if chunk:
                    out.extend(chunk)
                    if b"Adafruit CircuitPython" in out:
                        return True, out.decode("utf-8", "replace")
            return False, out.decode("utf-8", "replace")
    except (serial.SerialException, OSError):
        return True, out.decode("utf-8", "replace")


def wait_for_board(port, baud=BAUD, timeout=40.0):
    """Block until the board's USB serial re-enumerates and opens, or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with serial.Serial(port, baud, timeout=1):
                return True
        except (serial.SerialException, OSError):
            time.sleep(0.5)
    return False


def read_reset_reason(port):
    """Return the reset-reason name (e.g. 'WATCHDOG'). run_on_device enters raw REPL
    without a soft reboot, so it does not clobber the last hard reset's reason."""
    out = run_on_device("import microcontroller as m\nprint('RR', str(m.cpu.reset_reason))\n",
                        port=port, exec_timeout=15)
    for line in out.splitlines():
        if line.startswith("RR"):
            return line[3:].strip()
    return "?"


def reboot_and_check_reason(port, want="WATCHDOG"):
    """After a phase that reset the board: wait for re-enumeration, read the reason."""
    if not wait_for_board(port):
        return False, "board did not re-enumerate after reset"
    time.sleep(2.0)
    reason = read_reset_reason(port)
    return (want in reason), "reset_reason=%s (want %s)" % (reason, want)


# --------------------------------------------------------------------------- #
# Device-side snippets                                                        #
# --------------------------------------------------------------------------- #
_PHASE_A = """
import microcontroller
wdt = microcontroller.watchdog
maxacc = None; rejected = []
for t in (30, 20, 16, 12, 10, 9, 8.5, 8.3, 8, 6, 4):
    try:
        wdt.timeout = t
        if maxacc is None: maxacc = t
    except ValueError:
        rejected.append(t)
print("A maxaccepted=%s rejected=%s accepts8=%s" % (maxacc, rejected, 8 not in rejected))
"""

_PHASE_B = """
import time, microcontroller
from watchdog import WatchDogMode
wdt = microcontroller.watchdog
wdt.timeout = 8
wdt.mode = WatchDogMode.RESET
wdt.feed()
print("B_ARMED")
time.sleep(15)
print("B_SURVIVED_ERROR")
"""

# Shared WiFi/imports prefix for phase C. Tries CIRCUITPY_WIFI_*, then secrets.py.
_WIFI = """
import sys
if "/src/lib" not in sys.path: sys.path.append("/src/lib")
import time, os, microcontroller, wifi, socketpool, ssl, adafruit_requests
from watchdog import WatchDogMode
ssid = os.getenv("CIRCUITPY_WIFI_SSID"); pw = os.getenv("CIRCUITPY_WIFI_PASSWORD")
if not ssid:
    try:
        from secrets import secrets
        ssid = secrets.get("ssid"); pw = secrets.get("password")
    except Exception: pass
if not wifi.radio.connected and ssid:
    try: wifi.radio.connect(ssid, pw); time.sleep(1)
    except Exception as e: print("WIFI_ERR", e)
if not wifi.radio.connected:
    print("C_SKIP no_wifi")
"""

_PHASE_C_POS = _WIFI + """
if wifi.radio.connected:
    pool = socketpool.SocketPool(wifi.radio)
    session = adafruit_requests.Session(pool, ssl.create_default_context())
    wdt = microcontroller.watchdog
    wdt.timeout = 8; wdt.mode = WatchDogMode.RESET; wdt.feed()
    t0 = time.monotonic(); err = "none"
    try:
        r = session.get("%s", timeout=%d); err = "got_%%s" %% r.status_code
    except Exception as e:
        err = type(e).__name__
    dt = time.monotonic() - t0
    try: wdt.mode = WatchDogMode.NONE
    except Exception: pass
    print("C_POS dt=%%.1f err=%%s" %% (dt, err))
""" % (SLOW_URL, HTTP_OK_TIMEOUT)

_PHASE_C_NEG = _WIFI + """
if wifi.radio.connected:
    pool = socketpool.SocketPool(wifi.radio)
    session = adafruit_requests.Session(pool, ssl.create_default_context())
    wdt = microcontroller.watchdog
    wdt.timeout = 8; wdt.mode = WatchDogMode.RESET; wdt.feed()
    print("C_NEG_BLOCK")
    session.get("%s", timeout=%d)
    print("C_NEG_SURVIVED_ERROR")
""" % (SLOW_URL, HTTP_BAD_TIMEOUT)

_PHASE_D = r"""
import storage, os
try: storage.remount("/", readonly=False)   # device-writable for the file test
except Exception: pass
p = "/reliability_d.txt"
with open(p, "w") as f:
    for i in range(600): f.write("line %04d ..............................\n" % i)
size0 = os.stat(p)[6]; keep = 8192; seekok = True
with open(p, "rb") as f:
    try: f.seek(-keep, 2)                     # last `keep` bytes (whence 2 = end)
    except (OSError, ValueError): f.seek(0); seekok = False
    tail = f.read()
with open(p, "wb") as f:
    f.write(b"[trim]\n"); f.write(tail)
size1 = os.stat(p)[6]
with open(p, "rb") as f: data = f.read()
os.remove(p)
print("D seek_from_end=%s size0=%d size1=%d shrank=%s recent=%s"
      % (seekok, size0, size1, size1 < size0, b"line 0599" in data))
"""

_PHASE_E = """
class _S:
    _inst = {}
    def __new__(cls, k):
        i = cls._inst.get(k)
        if i is None:
            i = super().__new__(cls); cls._inst[k] = i
        return i
    def __init__(self, k):
        if getattr(self, "_init", False): return
        self._init = True; self.k = k; self.flag = False
a = _S("x"); b = _S("x"); a.flag = True; c = _S("y")
print("E same=%s shared=%s distinct=%s" % (a is b, b.flag, a is not c))
"""

_PHASE_F = """
import gc
gc.collect(); free = gc.mem_free()
MAX = 5; skips = 0; forced = []
for i in range(8):
    force = skips >= MAX
    if (20000 > 25000) or force:    # 20000 < the 25000 floor -> only 'force' lets it through
        forced.append(i); skips = 0
    else:
        skips += 1
print("F free=%d floor=25000 reachable=%s forced_at=%s" % (free, free > 25000, forced))
"""


# --------------------------------------------------------------------------- #
# Phases                                                                      #
# --------------------------------------------------------------------------- #
def phase_a(port):
    print("\n[A] watchdog timeout premise (non-destructive)")
    out = run_on_device(_PHASE_A, port=port, exec_timeout=20)
    line = next((l for l in out.splitlines() if l.startswith("A ")), out.strip())
    print("    device:", line)
    accepts8 = "accepts8=True" in line
    capped = "rejected=[]" not in line
    if not accepts8:
        return _v("A", False, "board rejected the default 8s timeout: %s" % line)
    note = "a cap EXISTS (premise true here)" if capped else "no cap — accepts all (premise false; matches CP 9.2.7/10.2.1)"
    return _v("A", True, "8s accepted; %s" % note)


def phase_b(port):
    print("\n[B] watchdog resets a wedged loop (REBOOTS)")
    reset, out = run_until_reset(_PHASE_B, port)
    if "B_SURVIVED_ERROR" in out:
        return _v("B", False, "loop survived 15s unfed — watchdog never reset")
    if not reset:
        return _v("B", False, "no reset detected (did the watchdog arm?)")
    print("    reset detected; waiting for re-enumeration...")
    ok, detail = reboot_and_check_reason(port)
    return _v("B", ok, detail)


def phase_c(port):
    print("\n[C] HTTP timeout vs watchdog (positive safe; negative REBOOTS)")
    out = run_on_device(_PHASE_C_POS, port=port, exec_timeout=45)
    pos = next((l for l in out.splitlines() if l.startswith("C_")), out.strip())
    print("    positive:", pos)
    if "C_SKIP" in out:
        return _v("C", None, "skipped — WiFi unavailable")
    if "C_POS dt=" not in out:
        return _v("C", False, "positive produced no result: %s" % pos)
    dt = _dt(pos)
    if dt is not None and dt >= WATCHDOG_ARM_S:
        return _v("C", False, "request blocked %.1fs >= watchdog %ds" % (dt, WATCHDOG_ARM_S))
    if dt is not None and dt < 3.0:
        return _v("C", None, "inconclusive — endpoint didn't hang (%.1fs); set SLOW_URL to a black-hole" % dt)
    print("    negative control (timeout=%ds > watchdog=%ds): expecting reset..."
          % (HTTP_BAD_TIMEOUT, WATCHDOG_ARM_S))
    reset, nout = run_until_reset(_PHASE_C_NEG, port, settle=18.0)
    if "C_SKIP" in nout:
        return _v("C", None, "positive PASS (~%.1fs); negative skipped — no WiFi" % (dt or -1))
    if not reset:
        return _v("C", False, "positive PASS but negative did NOT reset — invariant unproven")
    ok, detail = reboot_and_check_reason(port)
    if ok:
        return _v("C", True, "timeout fired ~%.1fs (no reset); over-long timeout -> WATCHDOG reset" % (dt or -1))
    return _v("C", False, "negative reset for the wrong reason: %s" % detail)


def phase_d(port):
    print("\n[D] log tail-trim primitive — binary end-relative seek (non-destructive)")
    out = run_on_device(_PHASE_D, port=port, exec_timeout=25)
    line = next((l for l in out.splitlines() if l.startswith("D ")), out.strip())
    print("    device:", line)
    ok = "shrank=True" in line and "recent=True" in line
    return _v("D", ok, line.replace("D ", "") or "no result")


def phase_e(port):
    print("\n[E] singleton identity — __new__ + _initialized guard (non-destructive)")
    out = run_on_device(_PHASE_E, port=port, exec_timeout=15)
    line = next((l for l in out.splitlines() if l.startswith("E ")), out.strip())
    print("    device:", line)
    ok = "same=True" in line and "shared=True" in line and "distinct=True" in line
    return _v("E", ok, line.replace("E ", "") or "no result")


def phase_f(port):
    print("\n[F] memory floor + force-after-N logic (non-destructive)")
    out = run_on_device(_PHASE_F, port=port, exec_timeout=15)
    line = next((l for l in out.splitlines() if l.startswith("F ")), out.strip())
    print("    device:", line)
    ok = "forced_at=[5]" in line   # the counter must force on the 6th consecutive skip
    return _v("F", ok, line.replace("F ", "") or "no result")


# --------------------------------------------------------------------------- #
# Helpers + main                                                              #
# --------------------------------------------------------------------------- #
def _v(name, ok, detail):
    return {"phase": name, "ok": ok, "detail": detail}


def _dt(line):
    try:
        return float(line.split("dt=")[1].split()[0])
    except (IndexError, ValueError):
        return None


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else PORT
    print("ScrollKit reliability harness (6 phases) on", port)
    print("WARNING: phases B and C-negative deliberately reboot the board.\n")

    phases = [phase_a, phase_b, phase_c, phase_d, phase_e, phase_f]
    results = []
    try:
        for ph in phases:
            results.append(ph(port))
    except KeyboardInterrupt:
        print("\ninterrupted")
    except Exception as e:
        print("\nharness error:", type(e).__name__, e)

    # Leave the board running its app again.
    try:
        with serial.Serial(port, BAUD, timeout=1) as ser:
            ser.write(b"\r\x03\x03"); time.sleep(0.3); ser.write(b"\x04")
    except (serial.SerialException, OSError):
        pass

    print("\n==================== RELIABILITY SUMMARY ====================")
    worst = 0
    for r in results:
        mark = {True: "PASS", False: "FAIL", None: "SKIP"}[r["ok"]]
        if r["ok"] is False:
            worst = 1
        print("  [%s] %s — %s" % (r["phase"], mark, r["detail"]))
    print("=============================================================")
    sys.exit(worst)


if __name__ == "__main__":
    main()
