"""Non-writing MatrixPortal S3 smoke test for an already-deployed ScrollKit.

Copy the current source deliberately first, then run this host-side probe:

    make copy-to-circuitpy
    make test-device-s3 PORT=/dev/cu.usbmodemXXXX

The script executes the bounded snippet through CircuitPython's raw REPL. It
does not create or modify files on the board; it only imports the deployed
library, initializes the real panel, paints one frame, and reports memory.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cpy_repl import run_on_device  # noqa: E402


DEVICE_CODE = r'''
import gc
import sys

# ScrollKit's asynchronous runtime is provided by CircuitPython's asyncio
# bundle. Apps normally place it in /lib; this board's app bundle keeps it at
# /src/lib, so make both standard locations visible to the raw-REPL probe.
for _path in ("/lib", "/src/lib"):
    if _path not in sys.path:
        sys.path.append(_path)

import asyncio

import displayio
displayio.release_displays()

from scrollkit.display.boards import MATRIXPORTAL_S3
from scrollkit.display.unified import UnifiedDisplay


async def _smoke():
    display = UnifiedDisplay()
    await display.initialize()
    if display._board_id != MATRIXPORTAL_S3:
        raise RuntimeError("expected MatrixPortal S3, got %r" % (display._board_id,))
    if display.width != 64 or display.height != 32:
        raise RuntimeError("expected 64x32, got %dx%d" % (display.width, display.height))

    await display.clear()
    await display.fill(0x001020)
    await display.fill_rect(0, 0, 64, 8, 0xFF0000)
    await display.fill_rect(0, 8, 64, 8, 0x00FF00)
    await display.fill_rect(0, 16, 64, 8, 0x0000FF)
    await display.draw_text("S3 OK", 15, 29, 0xFFFFFF)
    await display.show()
    gc.collect()
    print("SCROLLKIT_S3_SMOKE PASS board=%s panel=%dx%d mem_free=%d cp=%s" % (
        display._board_id, display.width, display.height, gc.mem_free(),
        getattr(sys.implementation, "version", "unknown")))


asyncio.run(_smoke())
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="CircuitPython serial device")
    parser.add_argument("--baud", type=int, default=115200,
                        help="serial baud rate (default: %(default)s)")
    parser.add_argument("--timeout", type=float, default=45.0,
                        help="raw-REPL execution timeout in seconds (default: %(default)s)")
    args = parser.parse_args(argv)

    output = run_on_device(DEVICE_CODE, port=args.port, baud=args.baud,
                           exec_timeout=args.timeout)
    print(output, end="" if output.endswith("\n") else "\n")
    if "SCROLLKIT_S3_SMOKE PASS" not in output:
        raise RuntimeError("MatrixPortal S3 smoke did not report a passing sentinel")


if __name__ == "__main__":
    main()
