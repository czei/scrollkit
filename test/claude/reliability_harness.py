"""On-device reliability harness — host-orchestrated over USB (v1: watchdog + HTTP).

Validates the field-reliability fixes that the desktop simulator physically cannot
reproduce, by driving a real MatrixPortal S3 (ESP32-S3, CircuitPython) over the raw
REPL and *deliberately* inducing the failure modes the fixes recover from:

  Phase A  watchdog premise + step-down   (non-destructive)
           - the board rejects a >8.3s timeout with ValueError (the premise behind
             base.ScrollKitApp._arm_watchdog stepping 8->6->4), and arms at the
             largest accepted value.
  Phase B  watchdog actually resets        (REBOOTS THE BOARD)
           - arm at 8s, then stop feeding for ~12s (a stand-in for a hung
             synchronous fetch). The board must hard-reset; after reboot
             microcontroller.cpu.reset_reason must read WATCHDOG.
  Phase C  HTTP timeout < watchdog window  (positive is safe; negative REBOOTS)
           - positive: HttpClient(timeout=6).get(slow, max_retries=1) blocks ~6s
             (one attempt) while the 8s watchdog is armed, then returns a 500 ->
             NO reset (6 < 8). Proves fix #3's invariant. (get() swallows the
             timeout and returns a MockResponse rather than raising.)
           - negative control: timeout=20 > 8s watchdog -> the single synchronous
             attempt blocks the loop past the watchdog window -> a *false* reset
             (WATCHDOG). Proves the invariant matters — this is what fix #3 lowered
             the default to 6 to avoid.
           NOTE: max_retries=1 isolates one request. get() retries 3x by default,
           but the `await asyncio.sleep` backoff between retries yields, so in the
           real app the concurrent display loop feeds the watchdog between attempts;
           a single synchronous attempt is the longest unfed window, which is why
           "per-request timeout < watchdog" is the invariant that matters.

WHY HOST-ORCHESTRATED CAN TEST THE WATCHDOG AT ALL
--------------------------------------------------
base.ScrollKitApp._arm_watchdog deliberately SKIPS arming while
`supervisor.runtime.serial_connected` (so it never reboots you mid-debug). Because
this harness is attached over USB, that guard would always fire — so the phases arm
`microcontroller.watchdog` DIRECTLY (bypassing the guard) to exercise the hardware
reset path. The *hardware* watchdog resets regardless of USB. Consequence: this
runner validates the hardware behaviour + the timeout invariant; the library's full
`_arm_watchdog` method (including the serial guard) is only exercised end-to-end by
running the harness headless (no USB console). That gap is intentional and noted.

PREREQUISITES
-------------
  * A MatrixPortal S3 on USB serial. Set PORT below (or pass as argv[1]).
  * The UPDATED scrollkit (with the six reliability fixes) copied to the board's
    /lib — Phase C imports scrollkit.network.http_client.HttpClient.
  * The board idling at the REPL is ideal. If a code.py auto-runs an app, the
    runner's Ctrl-C will interrupt it, but remove/rename code.py for a clean run.
  * Phase C needs WiFi + outbound network. CircuitPython auto-connects at boot when
    settings.toml has CIRCUITPY_WIFI_SSID / CIRCUITPY_WIFI_PASSWORD; the phase skips
    itself (not fail) if the radio can't connect. SLOW_URL must be a host that
    accepts the connection but doesn't answer within the timeout.

THIS DELIBERATELY REBOOTS THE BOARD. It is a dev diagnostic, never shipped.

NOTE: written against the hardware contract but NOT executed here (no board on this
host). Tuning points are flagged inline; PORT and SLOW_URL are the usual ones.

    python test/claude/reliability_harness.py [/dev/cu.usbmodemXXXX]
"""

import sys
import time

import serial

from cpy_repl import run_on_device, _read_until, PORT, BAUD

# A routable-but-unanswering target keeps Phase C's clock dominated by the socket
# timeout (no DNS / no TLS handshake to inflate it): TEST-NET-1 (RFC 5737) is not
# routed on the public internet, so the connect hangs until the timeout fires. If
# your network returns ICMP-unreachable quickly instead, switch to a slow responder
# such as "http://<host>/delay" that holds the connection open past the timeout.
SLOW_URL = "http://192.0.2.1/"

WATCHDOG_ARM_S = 8          # real default after fix #1
HTTP_OK_TIMEOUT = 6         # fix #3 default: below the watchdog
HTTP_BAD_TIMEOUT = 20       # negative control: above the watchdog


# --------------------------------------------------------------------------- #
# Low-level reset-aware orchestration (run_on_device can't survive a reboot)   #
# --------------------------------------------------------------------------- #
def run_until_reset(code, port, baud=BAUD, settle=18.0):
    """Send `code` via raw REPL and watch for the board to reset.

    Returns (reset: bool, output: str). A reset is detected when the native-USB
    serial drops (the board re-enumerates on reset) or the CircuitPython boot
    banner reappears. `settle` bounds how long we wait for the expected reset.
    """
    out = bytearray()
    try:
        with serial.Serial(port, baud, timeout=1) as ser:
            ser.write(b"\r\x03\x03")          # interrupt anything running
            time.sleep(0.3)
            ser.reset_input_buffer()
            ser.write(b"\r\x01")              # enter raw REPL
            _read_until(ser, b"raw REPL; CTRL-B to exit\r\n>", timeout=5)
            ser.write(code.encode("utf-8"))
            ser.write(b"\x04")                # execute
            deadline = time.monotonic() + settle
            while time.monotonic() < deadline:
                try:
                    chunk = ser.read(256)
                except (serial.SerialException, OSError):
                    return True, out.decode("utf-8", "replace")   # port dropped == reset
                if chunk:
                    out.extend(chunk)
                    # A hard (watchdog) reset reprints the full CircuitPython banner.
                    if b"Adafruit CircuitPython" in out:
                        return True, out.decode("utf-8", "replace")
            return False, out.decode("utf-8", "replace")          # no reset in window
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


_RESET_REASON = """
import microcontroller as m
print("RESET_REASON", str(m.cpu.reset_reason))
"""


def read_reset_reason(port):
    """Return the microcontroller reset-reason name (e.g. 'WATCHDOG'), or '?'.

    Safe to call from a fresh connection: run_on_device enters raw REPL without a
    soft reboot, so it does not clobber the reason set by the last hard reset.
    """
    out = run_on_device(_RESET_REASON, port=port)
    for line in out.splitlines():
        if line.startswith("RESET_REASON"):
            return line.split(None, 1)[1].strip() if len(line.split(None, 1)) > 1 else "?"
    return "?"


# --------------------------------------------------------------------------- #
# Device-side snippets                                                         #
# --------------------------------------------------------------------------- #
_PHASE_A = """
import microcontroller
wdt = microcontroller.watchdog
res = {}
# Premise behind fix #1: the ESP32-S3 rejects timeouts over ~8.3s.
try:
    wdt.timeout = 30
    res["rejects_30"] = False
except ValueError:
    res["rejects_30"] = True
# Step-down mirrors _arm_watchdog: the largest accepted of (8, 6, 4). Setting only
# .timeout (never .mode) does NOT arm the watchdog, so this phase can't reboot us.
applied = None
for c in (8, 6, 4):
    try:
        wdt.timeout = c
        applied = c
        break
    except ValueError:
        continue
res["applied"] = applied
print("PHASE_A", res)
"""

_PHASE_B = """
import time, microcontroller
from watchdog import WatchDogMode
wdt = microcontroller.watchdog
wdt.timeout = 8                       # real default; arm DIRECTLY (bypass serial guard)
wdt.mode = WatchDogMode.RESET
print("PHASE_B armed=8 wedging")      # board should hard-reset at ~8s, never reaching below
time.sleep(12)                        # stand-in for a hung synchronous fetch: never feeds
print("PHASE_B ERROR survived")       # must never reach the host
"""

# Phase C positive: ONE request whose timeout (6s) is below the 8s watchdog. We pass
# max_retries=1 to isolate a single request: get() retries up to 3x by default, and
# in the real app the display loop feeds the watchdog during the `await asyncio.sleep`
# backoff *between* retries (the backoff yields; the synchronous session.get does not).
# This harness runs get() with nothing else feeding, so only a single attempt isolates
# the per-request invariant. get() swallows the timeout and RETURNS a 500 MockResponse
# (it does not raise), so we judge by elapsed time + "we got here, no reset".
_PHASE_C_POS = """
import time, microcontroller, os
from watchdog import WatchDogMode
try:
    import wifi, socketpool, ssl, asyncio, adafruit_requests
    if not wifi.radio.connected:
        wifi.radio.connect(os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD"))
    pool = socketpool.SocketPool(wifi.radio)
    session = adafruit_requests.Session(pool, ssl.create_default_context())
    from scrollkit.network.http_client import HttpClient
    client = HttpClient(session=session, timeout=%d)
    client.using_adafruit = True
    wdt = microcontroller.watchdog
    wdt.timeout = 8
    wdt.mode = WatchDogMode.RESET
    wdt.feed()
    t0 = time.monotonic()
    resp = asyncio.run(client.get("%s", max_retries=1))   # returns; does not raise
    dt = time.monotonic() - t0
    try:
        wdt.mode = WatchDogMode.NONE                       # disarm before reporting
    except Exception:
        pass
    print("PHASE_C_POS dt=%%.1f status=%%s" %% (dt, getattr(resp, "status_code", "?")))
except Exception as e:
    print("PHASE_C_SKIP", type(e).__name__, str(e)[:60])
""" % (HTTP_OK_TIMEOUT, SLOW_URL)

# Phase C negative control: ONE request whose timeout (20s) exceeds the 8s watchdog,
# so the single synchronous attempt blocks the loop past the window -> a false WATCHDOG
# reset. This is exactly what fix #3 lowered the default to 6 to avoid.
_PHASE_C_NEG = """
import time, microcontroller, os
from watchdog import WatchDogMode
try:
    import wifi, socketpool, ssl, asyncio, adafruit_requests
    if not wifi.radio.connected:
        wifi.radio.connect(os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD"))
    pool = socketpool.SocketPool(wifi.radio)
    session = adafruit_requests.Session(pool, ssl.create_default_context())
    from scrollkit.network.http_client import HttpClient
    client = HttpClient(session=session, timeout=%d)
    client.using_adafruit = True
    wdt = microcontroller.watchdog
    wdt.timeout = 8
    wdt.mode = WatchDogMode.RESET
    wdt.feed()
    print("PHASE_C_NEG blocking")               # board should reset before this returns
    asyncio.run(client.get("%s", max_retries=1))
    print("PHASE_C_NEG ERROR survived")
except Exception as e:
    print("PHASE_C_NEG_SKIP", type(e).__name__, str(e)[:60])
""" % (HTTP_BAD_TIMEOUT, SLOW_URL)


# --------------------------------------------------------------------------- #
# Phases                                                                       #
# --------------------------------------------------------------------------- #
def phase_a(port):
    print("\n[A] watchdog premise + step-down (non-destructive)")
    out = run_on_device(_PHASE_A, port=port)
    line = next((l for l in out.splitlines() if l.startswith("PHASE_A")), "")
    rejects = "'rejects_30': True" in line
    applied8 = "'applied': 8" in line
    print("    device:", line or out.strip())
    if rejects and applied8:
        return _verdict("A", True, "board rejects >8.3s and arms at 8s (fix #1 premise holds)")
    if not rejects:
        return _verdict("A", False, "board did NOT reject 30s — fix #1's premise is wrong; revisit the step-down")
    return _verdict("A", False, "did not settle at 8s: %s" % line)


def phase_b(port):
    print("\n[B] watchdog resets a wedged loop (REBOOTS THE BOARD)")
    reset, out = run_until_reset(_PHASE_B, port)
    if "PHASE_B ERROR survived" in out:
        return _verdict("B", False, "loop survived 12s unfed — watchdog never reset the board")
    if not reset:
        return _verdict("B", False, "no reset detected within the window (did the watchdog arm?)")
    print("    reset detected; waiting for re-enumeration...")
    if not wait_for_board(port):
        return _verdict("B", False, "board did not re-enumerate after reset")
    time.sleep(2.0)
    reason = read_reset_reason(port)
    print("    reset_reason:", reason)
    return _verdict("B", "WATCHDOG" in reason,
                    "reset_reason=%s (want WATCHDOG)" % reason)


def phase_c(port):
    print("\n[C] HTTP timeout vs watchdog window (positive safe; negative REBOOTS)")
    # Positive: one request times out (~6s) below the 8s watchdog -> no reset. The
    # board returning to the REPL at all (run_on_device completes) means it didn't
    # reset; get() returns a 500 MockResponse on timeout.
    out = run_on_device(_PHASE_C_POS, port=port, exec_timeout=45.0)
    pos_line = next((l for l in out.splitlines() if l.startswith("PHASE_C")), out.strip())
    print("    positive:", pos_line)
    if "PHASE_C_SKIP" in out:
        return _verdict("C", None, "skipped — no WiFi/network (%s)" % pos_line)
    if "PHASE_C_POS dt=" not in out:
        return _verdict("C", False, "positive case produced no result: %s" % pos_line)
    dt = _parse_dt(pos_line)
    if dt is not None and dt >= WATCHDOG_ARM_S:
        return _verdict("C", False,
                        "request blocked %.1fs >= watchdog %ds (would reset in situ)" % (dt, WATCHDOG_ARM_S))
    if dt is not None and dt < 3.0:
        return _verdict("C", None,
                        "inconclusive — endpoint answered/refused in %.1fs (didn't hang); point SLOW_URL at a black-hole" % dt)

    # Negative control: timeout above the watchdog -> expect a false reset.
    print("    negative control (timeout=%ds > watchdog=%ds): expecting a reset..."
          % (HTTP_BAD_TIMEOUT, WATCHDOG_ARM_S))
    reset, nout = run_until_reset(_PHASE_C_NEG, port, settle=15.0)
    if "PHASE_C_NEG_SKIP" in nout:
        return _verdict("C", None, "positive PASS (~%.1fs); negative skipped — no network" % (dt or -1))
    if not reset:
        return _verdict("C", False,
                        "positive PASS but negative did NOT reset — invariant unproven")
    if not wait_for_board(port):
        return _verdict("C", False, "board did not re-enumerate after negative control")
    time.sleep(2.0)
    reason = read_reset_reason(port)
    print("    negative reset_reason:", reason)
    if "WATCHDOG" in reason:
        return _verdict("C", True,
                        "timeout fired at ~%.1fs (no reset); over-long timeout caused WATCHDOG reset"
                        % (dt if dt is not None else -1))
    return _verdict("C", False, "negative control reset for the wrong reason: %s" % reason)


# --------------------------------------------------------------------------- #
# Helpers + main                                                              #
# --------------------------------------------------------------------------- #
def _verdict(name, ok, detail):
    return {"phase": name, "ok": ok, "detail": detail}


def _parse_dt(line):
    try:
        return float(line.split("dt=")[1].split()[0])
    except (IndexError, ValueError):
        return None


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else PORT
    print("ScrollKit reliability harness (watchdog + HTTP) on", port)
    print("WARNING: phases B and C-negative deliberately reboot the board.\n")

    results = []
    try:
        results.append(phase_a(port))
        results.append(phase_b(port))
        results.append(phase_c(port))
    except KeyboardInterrupt:
        print("\ninterrupted")
    except Exception as e:           # surface transport errors without a bare crash
        print("\nharness error:", type(e).__name__, e)

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
