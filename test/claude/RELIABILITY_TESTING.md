# Hardware reliability testing

How to validate ScrollKit's field-reliability fixes on a **real** Adafruit
MatrixPortal S3, and the results of doing so. These are the failure modes the
desktop simulator physically cannot reproduce (the hardware watchdog, real flash,
real OOM pressure, real hung sockets, CircuitPython's `__new__`). The pure logic of
each fix is covered by the desktop unit suite; this is about the
hardware/CircuitPython-specific behaviour.

Driver: `test/claude/reliability_harness.py` (host-orchestrated over USB), built on
the raw-REPL driver `test/claude/cpy_repl.py`.

## Library smoke test

For a quick end-to-end check of the **currently deployed ScrollKit library** on
a MatrixPortal S3, deliberately copy the source first, then run the non-writing
raw-REPL probe:

```bash
python -m pip install -e ".[device]"
make copy-to-circuitpy
make test-device-s3 PORT=/dev/cu.usbmodemXXXX
```

It verifies MatrixPortal S3 board selection, 64×32 initialization, painter/text
rendering, refresh completion, and reports `gc.mem_free()`. It does not modify
the board filesystem or run network, OTA, or watchdog fault injection; use the
reliability harness below for those specialised diagnostics.

---

## The fixes under test

From the field-reliability work (commit `9868167`, comment/simplification follow-ups
`2e63863` and later):

| # | Fix | File |
|---|-----|------|
| 1 | Watchdog: opt-in arm, default 8 s, recover from a wedged loop | `app/base.py` |
| 2 | `MIN_FREE_FOR_UPDATE` 50 000 → 25 000 + force-after-N-skips | `app/base.py` |
| 3 | HTTP per-request `timeout` 10 → 6 (below the watchdog) | `network/http_client.py` |
| 4 | Log rotation never blind-truncates; tail-preserving trim | `utils/error_handler.py` |
| 5 | `ErrorHandler` real singleton via `__new__` | `utils/error_handler.py` |
| 6 | `error()` uses the filtered stack string | `utils/error_handler.py` |

---

## Prerequisites

- A MatrixPortal S3 (ESP32-S3) on USB serial.
- Python host deps: `pyserial` (`pip install pyserial`).
- Find the serial port:
  ```bash
  ls /dev/cu.usbmodem*        # macOS
  ```
  Pass it as the first arg (the default in `cpy_repl.py` may be stale per board).
- **Phase C only:** WiFi + outbound network. The harness reads
  `CIRCUITPY_WIFI_SSID`/`CIRCUITPY_WIFI_PASSWORD`, falling back to `secrets.py`
  (`ssid`/`password`); it self-skips if neither connects. `adafruit_requests` must be
  importable — the harness adds `/src/lib` to `sys.path` (where ThemeParkWaits keeps
  it); adjust if your board differs.
- **No scrollkit install is required** — every phase is self-contained, testing the
  hardware/CircuitPython mechanism each fix relies on rather than importing the
  library. (See "Testing the library code itself" if you want the end-to-end path.)

> ⚠️ **This deliberately reboots the board** (phases B and C-negative trigger a
> watchdog reset). It is a developer diagnostic — never ship it. The board recovers
> fully on reboot; the harness restarts the app when it finishes.

---

## Running it

```bash
python test/claude/reliability_harness.py /dev/cu.usbmodemXXXX
```

Runs all six phases and prints a `PASS`/`FAIL`/`SKIP` summary; exit code is non-zero
if any phase fails. To run a single phase, import and call it:

```python
import sys; sys.path.insert(0, "test/claude")
import reliability_harness as h
print(h.phase_a("/dev/cu.usbmodemXXXX"))
```

`cpy_repl.run_on_device(code, port=...)` runs a snippet via the raw REPL **without
writing to the device filesystem**; the harness adds reset-aware helpers
(`run_until_reset`, `wait_for_board`, `read_reset_reason`) that survive the board
re-enumerating on USB after a watchdog reset.

---

## The six phases

| Phase | Fix | What it injects | PASS criterion | Reboots? |
|-------|-----|-----------------|----------------|----------|
| **A** | #1 | sets `wdt.timeout` across 30…4 | the default 8 s is accepted (watchdog can arm); cap status reported as info | no |
| **B** | #1 | arm 8 s, stop feeding ~15 s | board hard-resets; `reset_reason == WATCHDOG` | **yes** |
| **C** | #3 | `GET timeout=6` vs `timeout=20`, watchdog armed 8 s | 6 s → no reset; 20 s → `WATCHDOG` reset | neg **yes** |
| **D** | #4 | write >16 KB log, `seek(-8192, 2)`, rewrite | binary end-seek works; file shrinks; newest line preserved | no |
| **E** | #5 | construct a `__new__`-singleton twice | same instance, shared state, distinct keys distinct | no |
| **F** | #2 | force-after-N counter + `gc.mem_free()` | counter forces on the 6th consecutive skip; reports real free heap | no |

### Why arming directly is legitimate
`ScrollKitApp._arm_watchdog` **skips arming while `supervisor.runtime.serial_connected`**
so it never reboots you mid-debug. Attached over USB, that guard always fires, so the
phases set `microcontroller.watchdog` directly. The hardware watchdog resets
regardless of USB. The runner therefore validates the hardware behaviour + the
timeout invariant; the library's full `_arm_watchdog` path (serial guard included) is
only exercised when the app runs **headless** (no USB console).

---

## Results — 2026-06-28

Two boards, both Adafruit MatrixPortal S3 / ESP32-S3:
- **CP 9.2.7** (UID 84722EB3564F) — older pre-scrollkit ThemeParkWaits.
- **CP 10.2.1** (UID 84722EB307461) — the target version; scrollkit-based app.

| Phase | CP 9.2.7 | CP 10.2.1 |
|-------|----------|-----------|
| A premise | accepts 30 s, honors 16 s — **no cap** | accepts 30 s — **no cap** |
| B watchdog reset | reset ~8 s & ~16 s, `WATCHDOG` ✅ | reset ~8.3 s, `WATCHDOG` ✅ |
| C HTTP timeout | 6 s → no reset; 20 s → `WATCHDOG` ✅ | 6.1 s → no reset; 20 s → `WATCHDOG` ✅ |
| D tail-trim | n/a | `seek(-8192,2)` works; 24600→8199 B, newest line kept ✅ |
| E singleton | n/a | same instance + shared state ✅ |
| F memory/force | n/a | force fires at skip 5; idle free ~2 MB ✅ |

### Headline finding — fix #1's premise is false
The brief (and the original code comments) asserted *"the ESP32-S3 rejects watchdog
timeouts over ~8.3 s with `ValueError`."* **Hardware-disproven on BOTH 9.2.7 and the
target 10.2.1** — every value up to 30 s is accepted (and 9.2.7 was measured to
*honor* a 16 s timeout, resetting at ~16 s). So the bug fix #1 claimed to fix (15 s
default → `ValueError` → watchdog never arms) does not occur on this hardware. The
watchdog *recovery itself works correctly*; only the rationale was wrong. The
step-down loop was therefore removed and `_arm_watchdog` now sets the timeout
directly; the default stays 8 s for fast freeze recovery.

---

## Gotchas (hard-won)

1. **Watchdog vs. the USB console.** With a serial console attached, the library
   won't arm (`serial_connected` guard) — so the reset phases arm the hardware
   directly. To exercise the *library's* arming end-to-end, run headless and read
   results back from flash.
2. **Read-only filesystem from the host.** Once its app boots, the board remounts
   `/` writable *for the device*, which makes it **read-only from the USB host**. A
   runtime `storage.remount("/", readonly=True)` + `diskutil unmount/mount` did **not**
   flip the host's writable bit (it's fixed at USB enumeration). Practical upshot: to
   push files you must either (a) catch the brief host-writable window before the app
   boots, (b) write device-side over the REPL, or (c) reflash. The harness avoids this
   entirely by being self-contained.
3. **WiFi creds.** May be in `secrets.py` (`ssid`/`password`) rather than
   `settings.toml` (`CIRCUITPY_WIFI_*`). The harness reads the device's own secrets —
   it never transfers the password to the host.
4. **The radio doesn't persist across REPL calls** — connect WiFi inside the same
   snippet that makes the request (the harness does this).
5. **Reset survival.** A watchdog reset drops the USB serial; re-open with retries
   (`wait_for_board`). `run_on_device` enters the raw REPL **without** a soft reboot,
   so reading `reset_reason` afterward is safe (a soft reboot would overwrite it).
6. **`get()` retries.** `HttpClient.get(max_retries=3)` blocks `N × timeout`, but the
   `await asyncio.sleep` backoff *yields*, so the real app's display loop feeds the
   watchdog between attempts — which is exactly why *per-request* timeout < watchdog
   is the right invariant. The harness/Phase-C tests a single request to isolate it.
7. **PSRAM heap.** `gc.mem_free()` reported **~2 MB** idle (PSRAM), so the 25 000
   floor is trivially reachable at idle — Phase F validates the *force-after-N logic*,
   not the under-load headroom. Measure real free heap with the full app (web +
   display) running to judge whether 25 000 is the right floor in situ.

---

## Repeating / extending

- **Re-run on a new CP version** to re-check the watchdog premise (phase A) — that is
  the most version-sensitive result.
- **Testing the library code itself** (not just the mechanism): install the *updated*
  `scrollkit` on the device (`/lib/scrollkit`) and exercise the real `HttpClient`,
  `ErrorHandler`, and `ScrollKitApp` classes. You must first make the filesystem
  host-writable (see gotcha #2) or push files device-side over the REPL. Phase C's
  `HttpClient`-passes-the-timeout behaviour is already covered by
  `test/unit/network/test_http_client.py::test_get_request_adafruit`.
- **Phase D (full)** could additionally test no-delete-on-boot across a reboot (write
  a marker via the updated `ErrorHandler` in PRODUCTION, reset, confirm it survived).
  That needs the updated library installed and a reboot-spanning state file.
- **Phase F (under load)** could instrument the running app to log `free_memory()`
  before each parse and confirm the floor is reached/cleared in production.

All device snippets are plain CircuitPython and compile-checked by importing the
module and `compile()`-ing each `_PHASE_*` constant.
