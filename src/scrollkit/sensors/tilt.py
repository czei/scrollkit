# Copyright (c) 2024-2026 Michael Czeiszperger
"""Tilt / orientation sensing — which way is down, in panel coordinates.

The Adafruit MatrixPortal S3 carries an onboard **LIS3DH** triple-axis
accelerometer on the shared I2C bus. This module reads it through a minimal
built-in register driver (~1 KB of code, no ``adafruit_lis3dh`` to copy into
``/lib``) and turns the raw vector into the two things a display app actually
wants: a continuous ``gravity_angle`` and an ``orientation`` naming which edge of
the panel is pointing at the floor.

**The address gotcha.** On the MatrixPortal S3 the LIS3DH answers at I2C address
**0x19**, *not* the 0x18 that Adafruit's own libraries default to. Adafruit
documents this explicitly on the S3 pinout page. Probing 0x18 finds nothing and
looks exactly like "no accelerometer fitted", so the address lives in the board
registry (``display/boards.py``) rather than being hard-coded here.

**Panel coordinate convention.** Everything this module reports is in *panel*
space, not chip space: +X is toward the panel's right edge and +Y is toward its
bottom edge (the displayio convention, where y increases downward). So:

- ``gravity_angle`` is degrees clockwise from "bottom edge down" — 0° is a
  normally-hung sign, +90° means the panel's right edge is pointing at the floor.
- ``orientation`` is the nearest edge name: ``"bottom"`` (upright), ``"right"``,
  ``"top"``, ``"left"``, or ``"flat"`` when the panel is lying face up/down and
  in-plane gravity is too weak to have a direction.

The chip-axes-to-panel-axes mapping is a single constant, :data:`AXIS_MAP`, so
when a real board disagrees with the default it is corrected in ONE place and
every effect follows — see ``test/claude/tilt_probe_s3.py``, which prints the
live vector while you physically turn the board.

Everything degrades quietly. A board with no accelerometer (the Interstate 75 W),
a busy I2C bus, a desktop run with no simulator attached: ``available`` is False,
``orientation`` is ``"flat"``, and nothing raises.

Typical usage::

    from scrollkit.sensors.tilt import TiltSensor

    tilt = TiltSensor(display)          # same call on device and desktop
    if tilt.available and tilt.orientation != "bottom":
        ...                             # the sign is on its side
"""

import math
import time


__all__ = ['TiltSensor', 'AXIS_MAP', 'ORIENTATIONS']

# --- LIS3DH register map (only what a tilt reading needs) ---------------------
_REG_WHO_AM_I = 0x0F
_REG_CTRL1 = 0x20
_REG_CTRL4 = 0x23
_REG_OUT_X_L = 0x28
_DEVICE_ID = 0x33          # WHO_AM_I answer for a genuine LIS3DH
_AUTO_INCREMENT = 0x80     # OR into a sub-address to burst-read consecutive regs
_CTRL1_100HZ_XYZ = 0x57    # ODR=100 Hz, normal mode, X/Y/Z enabled
_CTRL4_BDU_HR_2G = 0x88    # block-data-update + high resolution, +/-2 g
_MG_PER_LSB = 0.001        # high-res 12-bit at +/-2 g == 1 mg per count

# Chip axes -> panel axes: (panel_x_from, panel_y_from) as chip-axis indices with
# a sign. Index 0/1/2 = chip X/Y/Z. The default assumes the chip is mounted with
# its X along the panel's width and Y down the panel's height. If a real board
# disagrees, fix it HERE — every angle, orientation and effect derives from it.
AXIS_MAP = ((0, 1.0), (1, 1.0))

# Edge names by 90-degree sector, starting at "bottom edge down" (0 degrees) and
# advancing clockwise: 90 = right edge down, 180 = top, 270 = left.
ORIENTATIONS = ("bottom", "right", "top", "left")

_FLAT = "flat"


class TiltSensor:
    """Which way is down, in panel coordinates — on hardware or in the simulator.

    On CircuitPython this talks to the board's onboard accelerometer. On the
    desktop it reads the simulator's virtual gravity vector (arrow keys, or
    :meth:`~scrollkit.display.unified.UnifiedDisplay.set_virtual_tilt` for
    deterministic tests), so an app is written and verified once.

    Args:
        display: A ScrollKit display. Supplies the board id (so the right I2C
            address is used, and a board with no accelerometer is never probed)
            and, on the desktop, the virtual gravity vector. ``None`` is allowed
            — the sensor then resolves the board the same way the display does.
        board: Explicit canonical board id, overriding ``display``'s.
        min_interval: Seconds between real reads. The display loop runs at
            ~20 fps and an I2C transaction is not free while the panel is being
            driven, so ``read()`` returns the cached vector in between. The
            default (0.1 s / 10 Hz) is far quicker than anyone can tilt a sign.
        smoothing: Exponential-moving-average weight for a NEW sample, 0..1.
            Lower is steadier and laggier. The default takes the hand-shake out
            without making the response feel sticky.
        flat_threshold: In-plane gravity magnitude (g) below which the panel is
            reported ``"flat"`` — lying face up or down, where "which edge is
            down" has no meaningful answer.
        hysteresis: Degrees of overshoot required past the 45-degree boundary
            before ``orientation`` flips. Without it, a sign resting near a
            diagonal chatters between two names every frame and any effect
            keyed to it thrashes.
    """

    def __init__(self, display=None, board=None, min_interval=0.1,
                 smoothing=0.35, flat_threshold=0.4, hysteresis=8.0):
        self._display = display
        self._min_interval = min_interval if min_interval > 0 else 0.0
        self._smoothing = _clamp01(smoothing)
        self._flat_threshold = flat_threshold
        self._hysteresis = hysteresis

        # Resolve the board WITHOUT importing hardware modules (boards.py keeps
        # every hardware import function-local, so this is desktop/test safe).
        from ..display.boards import resolve_board
        if board is None:
            board = getattr(display, "board_id", None)
        self._spec = resolve_board(board)

        self._i2c = None
        self._address = None
        self._source = None          # "lis3dh" | "virtual" | None
        self._buf = None             # preallocated 6-byte read buffer (device only)
        self._out = None             # preallocated 1-byte sub-address buffer
        self._vector = (0.0, 0.0, 1.0)   # smoothed, chip axes, g
        self._seeded = False             # False until the first real sample lands
        self._last_read = None
        self._orientation = _FLAT

        if self._spec.has_accelerometer:
            self._connect()

    # --- connection ----------------------------------------------------------
    def _connect(self):
        """Pick a source. Never raises — failure just means ``available`` is False."""
        if _is_circuitpython():
            self._connect_lis3dh()
        elif self._display is not None and hasattr(self._display, "virtual_tilt"):
            self._source = "virtual"

    def _connect_lis3dh(self):
        """Open the I2C bus and wake the LIS3DH. Quiet no-op on any failure."""
        try:
            import board
        except ImportError:
            return
        i2c = None
        # Prefer the board's shared bus singletons: they return the EXISTING bus
        # rather than constructing a second one, so grabbing the accelerometer
        # can't collide with a STEMMA QT peripheral the app already opened.
        for attr in ("STEMMA_I2C", "I2C"):
            factory = getattr(board, attr, None)
            if factory is None:
                continue
            try:
                i2c = factory()
                break
            except (OSError, ValueError, RuntimeError):
                i2c = None
        if i2c is None:
            try:
                import busio
                i2c = busio.I2C(board.SCL, board.SDA)
            except (ImportError, AttributeError, OSError, ValueError, RuntimeError):
                return

        address = self._spec.accel_i2c_address
        if address is None:
            return
        self._i2c = i2c
        self._address = address
        self._buf = bytearray(6)
        self._out = bytearray(1)
        try:
            if self._read_register(_REG_WHO_AM_I) != _DEVICE_ID:
                self._i2c = None       # something else lives at this address
                return
            self._write_register(_REG_CTRL1, _CTRL1_100HZ_XYZ)
            self._write_register(_REG_CTRL4, _CTRL4_BDU_HR_2G)
        except (OSError, ValueError):
            self._i2c = None
            return
        self._source = "lis3dh"

    # --- raw I2C -------------------------------------------------------------
    def _lock(self):
        """Take the shared bus lock, bounded. False means "someone else has it"."""
        i2c = self._i2c
        for _ in range(200):           # ~ms of spinning, never an unbounded hang
            if i2c.try_lock():
                return True
        return False

    def _write_register(self, reg, value):
        if not self._lock():
            raise OSError("I2C bus busy")
        try:
            self._i2c.writeto(self._address, bytes((reg, value)))
        finally:
            self._i2c.unlock()

    def _read_register(self, reg):
        if not self._lock():
            raise OSError("I2C bus busy")
        try:
            self._out[0] = reg
            result = bytearray(1)
            self._i2c.writeto_then_readfrom(self._address, self._out, result)
            return result[0]
        finally:
            self._i2c.unlock()

    def _read_vector(self):
        """One burst read of OUT_X_L..OUT_Z_H -> (x, y, z) in g (chip axes)."""
        if not self._lock():
            raise OSError("I2C bus busy")
        try:
            # The MSB of the sub-address is the LIS3DH's auto-increment flag, so
            # all six output registers arrive in a single transaction.
            self._out[0] = _REG_OUT_X_L | _AUTO_INCREMENT
            self._i2c.writeto_then_readfrom(self._address, self._out, self._buf)
        finally:
            self._i2c.unlock()
        buf = self._buf
        return (_counts_to_g(buf[0], buf[1]),
                _counts_to_g(buf[2], buf[3]),
                _counts_to_g(buf[4], buf[5]))

    # --- public API ----------------------------------------------------------
    @property
    def available(self):
        """True if a real (or simulated) accelerometer is answering."""
        return self._source is not None

    @property
    def source(self):
        """Where readings come from: ``"lis3dh"``, ``"virtual"``, or ``None``."""
        return self._source

    @property
    def board_id(self):
        """Canonical id of the board this sensor resolved against."""
        return self._spec.board_id

    def read(self, force=False):
        """The smoothed acceleration vector ``(x, y, z)`` in g, in CHIP axes.

        Throttled to ``min_interval``; in between it returns the cached vector,
        so calling this every frame costs nothing. ``force=True`` bypasses the
        throttle. Returns ``(0.0, 0.0, 1.0)`` (panel face up, flat) when no
        sensor is available. A read error is swallowed and the last good vector
        kept — a single dropped I2C transaction must not blank an effect.
        """
        if self._source is None:
            return self._vector
        now = time.monotonic()
        if not force and self._last_read is not None \
                and (now - self._last_read) < self._min_interval:
            return self._vector
        self._last_read = now
        try:
            if self._source == "virtual":
                sample = self._display.virtual_tilt
            else:
                sample = self._read_vector()
        except (OSError, ValueError, AttributeError):
            return self._vector
        if sample is None:
            return self._vector
        if not self._seeded:
            # Seed the average with the first real observation. Blending it
            # against the "lying flat" placeholder instead would make a normally
            # hung sign report "flat" for the first few reads — long enough for
            # an effect armed at startup to misfire.
            self._seeded = True
            self._vector = (sample[0], sample[1], sample[2])
            return self._vector
        a = self._smoothing
        prev = self._vector
        self._vector = (prev[0] + a * (sample[0] - prev[0]),
                        prev[1] + a * (sample[1] - prev[1]),
                        prev[2] + a * (sample[2] - prev[2]))
        return self._vector

    @property
    def panel_gravity(self):
        """Gravity projected onto the panel plane as ``(gx, gy)`` in g.

        +X is toward the panel's right edge, +Y toward its bottom edge.
        """
        v = self.read()
        if self._source == "virtual":
            # AXIS_MAP corrects for how the physical chip is soldered onto the
            # board. A virtual sensor has no chip, so the simulator hands over
            # panel-space gravity directly and applying the map here would
            # rotate the simulator's answer away from the hardware's.
            return (v[0], v[1])
        (xi, xs), (yi, ys) = AXIS_MAP
        return (v[xi] * xs, v[yi] * ys)

    @property
    def magnitude(self):
        """Strength of in-plane gravity in g — ~1.0 hanging, ~0.0 lying flat."""
        gx, gy = self.panel_gravity
        # math.hypot is absent on CircuitPython.
        return math.sqrt(gx * gx + gy * gy)

    @property
    def is_flat(self):
        """True when the panel is lying face up/down (no meaningful "down")."""
        return self.magnitude < self._flat_threshold

    @property
    def gravity_angle(self):
        """Degrees clockwise from "bottom edge down", in ``[0, 360)``.

        0 is a normally-hung sign; 90 means the panel's right edge points at the
        floor. Continuous — use this to drive an effect that varies smoothly with
        angle, rather than snapping to the four :data:`ORIENTATIONS`.
        """
        gx, gy = self.panel_gravity
        if gx == 0.0 and gy == 0.0:
            return 0.0
        # atan2(gx, gy) is 0 when gravity points at +Y (the bottom edge) and
        # grows as gravity swings toward +X (the right edge) — i.e. clockwise on
        # a y-down panel, which is how a viewer describes turning the box.
        return math.degrees(math.atan2(gx, gy)) % 360.0

    @property
    def orientation(self):
        """Which panel edge is pointing down: an :data:`ORIENTATIONS` name or ``"flat"``.

        Hysteretic: the name only changes once the angle is ``hysteresis``
        degrees past the halfway boundary, so a sign resting near a diagonal
        reports one stable answer instead of chattering.
        """
        if not self.available or self.is_flat:
            self._orientation = _FLAT
            return _FLAT
        angle = self.gravity_angle
        current = self._orientation
        if current == _FLAT:
            self._orientation = _nearest_edge(angle)
            return self._orientation
        # Stay put until the angle leaves the current edge's 90-degree sector by
        # more than the hysteresis margin.
        center = ORIENTATIONS.index(current) * 90.0
        if abs(_signed_delta(angle, center)) <= (45.0 + self._hysteresis):
            return current
        self._orientation = _nearest_edge(angle)
        return self._orientation

    def describe(self):
        """A JSON-able snapshot — handy for diagnostics and the device probe."""
        return {
            "available": self.available,
            "source": self._source,
            "board_id": self._spec.board_id,
            "vector_g": self.read(),
            "panel_gravity": self.panel_gravity,
            "angle_deg": self.gravity_angle,
            "orientation": self.orientation,
            "flat": self.is_flat,
        }


# --- helpers -----------------------------------------------------------------
def _counts_to_g(lo, hi):
    """Two LIS3DH output bytes -> g. 12-bit high-res, left-justified, 2's complement."""
    raw = lo | (hi << 8)
    if raw & 0x8000:
        raw -= 0x10000
    return (raw >> 4) * _MG_PER_LSB


def _clamp01(value):
    if value < 0.0:
        return 0.0
    return 1.0 if value > 1.0 else value


def _signed_delta(angle, center):
    """Shortest signed difference ``angle - center`` in degrees, in (-180, 180]."""
    return ((angle - center + 180.0) % 360.0) - 180.0


def _nearest_edge(angle):
    """The :data:`ORIENTATIONS` name whose 90-degree sector contains ``angle``."""
    return ORIENTATIONS[int((angle + 45.0) % 360.0 // 90.0)]


def _is_circuitpython():
    import sys
    return (hasattr(sys, "implementation")
            and sys.implementation.name == "circuitpython")
