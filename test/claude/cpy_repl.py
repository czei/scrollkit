"""Host-side CircuitPython raw-REPL driver (calibration scratch tool).

Drives a CircuitPython board's serial REPL programmatically so we can run a block
of code on the device and capture its stdout — WITHOUT touching the device's
filesystem (no code.py/boot.py changes, no new root files). Uses the raw REPL
protocol (Ctrl-A enter, Ctrl-D execute, output framed by \\x04), the same
mechanism ampy/mpremote use.

Usage:
    python test/claude/cpy_repl.py            # run the built-in recon snippet
    from cpy_repl import run_on_device
    out = run_on_device(CODE_STRING)
"""

import sys
import time

import serial

PORT = "/dev/cu.usbmodem84722EB307461"
BAUD = 115200


def run_on_device(code, port=PORT, baud=BAUD, exec_timeout=60.0):
    """Run `code` on the board via raw REPL; return its stdout as a string.

    Raises RuntimeError if the device reports a traceback.
    """
    with serial.Serial(port, baud, timeout=1) as ser:
        # Interrupt any running program and settle.
        ser.write(b"\r\x03\x03")
        time.sleep(0.3)
        ser.reset_input_buffer()

        # Enter raw REPL.
        ser.write(b"\r\x01")
        _read_until(ser, b"raw REPL; CTRL-B to exit\r\n>", timeout=5)

        # Send code + execute (Ctrl-D).
        ser.write(code.encode("utf-8"))
        ser.write(b"\x04")

        # Response framing: b"OK" + stdout + b"\x04" + stderr + b"\x04" + b">".
        # Read the WHOLE thing (until two \x04 seen) before parsing — reading
        # piecemeal loses stdout bundled in the same chunk as "OK".
        resp = _read_until_markers(ser, b"\x04", 2, timeout=exec_timeout)

        # Leave raw REPL.
        ser.write(b"\r\x02")
        time.sleep(0.2)

        i = resp.find(b"OK")
        if i < 0:
            raise RuntimeError("raw REPL did not ack (got %r)" % resp[:200])
        parts = resp[i + 2:].split(b"\x04")
        stdout = parts[0].decode("utf-8", "replace")
        stderr = (parts[1] if len(parts) > 1 else b"").decode("utf-8", "replace").strip()
        if stderr:
            raise RuntimeError("device error:\n" + stderr + "\n--- stdout ---\n" + stdout)
        return stdout


def _read_until(ser, marker, timeout):
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(256)
        if chunk:
            buf.extend(chunk)
            if marker in buf:
                return bytes(buf)
        else:
            time.sleep(0.01)
    return bytes(buf)


def _read_until_markers(ser, marker, count, timeout):
    """Accumulate bytes until `marker` has been seen `count` times (or timeout)."""
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(256)
        if chunk:
            buf.extend(chunk)
            if buf.count(marker) >= count:
                return bytes(buf)
        else:
            time.sleep(0.01)
    return bytes(buf)


RECON = """
import sys, os, gc
gc.collect()
print("IMPL", sys.implementation)
print("VERSION", sys.version)
try:
    import board
    print("BOARD_ID", getattr(board, "board_id", "?"))
except Exception as e:
    print("BOARD_ERR", repr(e))
print("ROOT", os.listdir("/"))
try:
    print("LIB", os.listdir("/lib"))
except Exception as e:
    print("LIB_ERR", repr(e))
print("MEM_FREE", gc.mem_free())
"""


if __name__ == "__main__":
    code = sys.stdin.read() if not sys.stdin.isatty() else RECON
    print(run_on_device(code))
