"""Host-side probe for the MatrixPortal S3's onboard LIS3DH accelerometer.

Nothing about ScrollKit's tilt support can be verified from the desktop: the
simulator has no I2C bus, so the address, the WHO_AM_I probe, the register writes,
the burst read, and — above all — **which way the chip's axes actually point
relative to the panel** are only ever confirmed by a board on the end of a cable.
This script is that confirmation.

    make copy-to-circuitpy
    PYTHONPATH=src python test/claude/tilt_probe_s3.py --port /dev/cu.usbmodemXXXX

It writes nothing to the board — it imports the deployed library through the raw
REPL, reads the sensor, and prints what it sees.

Two modes:

* default — a single snapshot: bus scan, WHO_AM_I, control registers, and one
  vector/angle/orientation reading. Use it to confirm the part answers at 0x19.
* ``--watch`` — stream readings for N seconds. **Physically turn the board while
  this runs.** Confirm that the reported ``orientation`` names the edge actually
  pointing at the floor. If it is consistently rotated or mirrored, fix
  ``AXIS_MAP`` in ``src/scrollkit/sensors/tilt.py`` — that one constant is the
  only place the chip-to-panel mounting is encoded, and every angle, orientation
  and tilt-driven effect follows from it.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cpy_repl import run_on_device  # noqa: E402


_PREAMBLE = r'''
import sys
for _path in ("/lib", "/src/lib"):
    if _path not in sys.path:
        sys.path.append(_path)
'''

SNAPSHOT_CODE = _PREAMBLE + r'''
import board
import busio

from scrollkit.display.boards import detect_board_id, resolve_board
from scrollkit.sensors.tilt import TiltSensor

bid = detect_board_id()
spec = resolve_board(bid)
print("board=%s has_accel=%s expect_addr=0x%02X"
      % (bid, spec.has_accelerometer, spec.accel_i2c_address or 0))

# Raw bus scan FIRST: if 0x19 is missing from this list, nothing else matters.
i2c = board.STEMMA_I2C()
while not i2c.try_lock():
    pass
try:
    found = i2c.scan()
finally:
    i2c.unlock()
print("i2c_scan=%s" % ([hex(a) for a in found],))
print("addr_0x19_present=%s addr_0x18_present=%s"
      % (0x19 in found, 0x18 in found))

tilt = TiltSensor(min_interval=0.0, smoothing=1.0)
print("available=%s source=%s" % (tilt.available, tilt.source))
if tilt.available:
    v = tilt.read(force=True)
    print("vector_g=(%.3f, %.3f, %.3f)" % v)
    print("panel_gravity=(%.3f, %.3f) magnitude=%.3f"
          % (tilt.panel_gravity[0], tilt.panel_gravity[1], tilt.magnitude))
    print("angle=%.1f orientation=%s flat=%s"
          % (tilt.gravity_angle, tilt.orientation, tilt.is_flat))
print("SCROLLKIT_TILT_PROBE %s" % ("PASS" if tilt.available else "FAIL"))
'''

WATCH_TEMPLATE = _PREAMBLE + r'''
import time

from scrollkit.sensors.tilt import TiltSensor

tilt = TiltSensor(min_interval=0.0)
if not tilt.available:
    print("SCROLLKIT_TILT_PROBE FAIL (no accelerometer answering)")
else:
    print("Turn the board now. 'orientation' must name the edge facing the floor.")
    deadline = time.monotonic() + %(seconds)s
    while time.monotonic() < deadline:
        v = tilt.read(force=True)
        print("x=%%+.2f y=%%+.2f z=%%+.2f | angle=%%6.1f | %%s"
              %% (v[0], v[1], v[2], tilt.gravity_angle, tilt.orientation))
        time.sleep(%(interval)s)
    print("SCROLLKIT_TILT_PROBE PASS")
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="CircuitPython serial device")
    parser.add_argument("--baud", type=int, default=115200,
                        help="serial baud rate (default: %(default)s)")
    parser.add_argument("--watch", type=float, metavar="SECONDS",
                        help="stream readings for SECONDS while you turn the board")
    parser.add_argument("--interval", type=float, default=0.5,
                        help="seconds between watch samples (default: %(default)s)")
    args = parser.parse_args(argv)

    if args.watch:
        code = WATCH_TEMPLATE % {"seconds": args.watch, "interval": args.interval}
        timeout = args.watch + 30.0
    else:
        code = SNAPSHOT_CODE
        timeout = 45.0

    output = run_on_device(code, port=args.port, baud=args.baud,
                           exec_timeout=timeout)
    print(output, end="" if output.endswith("\n") else "\n")
    if "SCROLLKIT_TILT_PROBE PASS" not in output:
        raise RuntimeError("tilt probe did not report a passing sentinel — the "
                           "LIS3DH is not answering at 0x19 (check the i2c_scan "
                           "line above)")


if __name__ == "__main__":
    main()
