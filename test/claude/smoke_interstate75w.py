"""Render a diagnostic frame through automatic Interstate 75 W selection.

The library must already be installed on the connected board. This host-side
raw-REPL probe writes no files to the device; it releases any existing display,
constructs ``UnifiedDisplay()`` without ``board=``, and leaves a color-bar frame
visible for a few seconds.

Usage:
    PYTHONSAFEPATH=1 python test/claude/smoke_interstate75w.py \
        --port /dev/cu.usbmodemXXXX
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cpy_repl import run_on_device  # noqa: E402


DEVICE_CODE = r'''
import asyncio
import displayio
import time

displayio.release_displays()
from scrollkit.display.unified import UnifiedDisplay

async def _smoke():
    display = UnifiedDisplay()
    await display.initialize()
    print("SCROLLKIT_BOARD", display._board_id)
    print("PANEL", display.width, display.height)
    await display.fill(0x001020)
    await display.fill_rect(0, 0, 64, 8, 0xFF0000)
    await display.fill_rect(0, 8, 64, 8, 0x00FF00)
    await display.fill_rect(0, 16, 64, 8, 0x0000FF)
    await display.fill_rect(0, 24, 64, 8, 0xFFFFFF)
    await display.show()
    time.sleep(3)

asyncio.run(_smoke())
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True,
                        help="CircuitPython serial device")
    parser.add_argument("--baud", type=int, default=115200,
                        help="serial baud rate (default: %(default)s)")
    args = parser.parse_args()
    print(run_on_device(DEVICE_CODE, port=args.port, baud=args.baud,
                        exec_timeout=30.0))


if __name__ == "__main__":
    main()
