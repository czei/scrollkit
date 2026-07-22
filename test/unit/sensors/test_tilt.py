# Copyright (c) 2024-2026 Michael Czeiszperger
"""Tests for scrollkit.sensors.tilt (LIS3DH orientation sensing).

Two halves. The panel-space MATH (angle, edge naming, hysteresis, flat) runs
against the simulator's virtual gravity, exactly as a desktop app would. The
DEVICE driver — bus selection, the 0x19 address, the WHO_AM_I probe, the
auto-increment burst read, 12-bit two's-complement decoding — is exercised
against a fake I2C bus, because that code cannot otherwise be reached without a
MatrixPortal S3 on the end of a USB cable.
"""
import sys

import pytest

from scrollkit.display.boards import INTERSTATE75_W, MATRIXPORTAL_S3
from scrollkit.sensors import tilt as tilt_mod
from scrollkit.sensors.tilt import TiltSensor


class FakeDisplay:
    """The bit of UnifiedDisplay a TiltSensor actually touches."""

    def __init__(self, vector=(0.0, 1.0, 0.0), board_id=MATRIXPORTAL_S3):
        self.virtual_tilt = vector
        self.board_id = board_id


def _sensor(vector=(0.0, 1.0, 0.0), **kw):
    """A sensor reading a fixed virtual vector, with smoothing off for exactness."""
    kw.setdefault("smoothing", 1.0)
    kw.setdefault("min_interval", 0.0)
    return TiltSensor(FakeDisplay(vector), **kw)


# --- availability ------------------------------------------------------------

def test_virtual_source_on_a_board_with_an_accelerometer():
    s = _sensor()
    assert s.available
    assert s.source == "virtual"
    assert s.board_id == MATRIXPORTAL_S3


def test_board_without_an_accelerometer_is_unavailable():
    """The Interstate 75 W has no LIS3DH — degrade, never raise."""
    s = TiltSensor(FakeDisplay(board_id=INTERSTATE75_W))
    assert not s.available
    assert s.source is None
    assert s.orientation == "flat"
    assert s.read() == (0.0, 0.0, 1.0)


def test_no_display_is_unavailable_but_still_answers():
    s = TiltSensor(None)
    assert not s.available
    assert s.orientation == "flat"
    assert s.gravity_angle == 0.0


# --- panel-space math --------------------------------------------------------

@pytest.mark.parametrize("vector,angle", [
    ((0.0, 1.0, 0.0), 0.0),       # hanging normally: gravity toward the bottom
    ((1.0, 0.0, 0.0), 90.0),      # right edge down
    ((0.0, -1.0, 0.0), 180.0),    # upside down
    ((-1.0, 0.0, 0.0), 270.0),    # left edge down
])
def test_gravity_angle_is_clockwise_from_bottom_down(vector, angle):
    assert _sensor(vector).gravity_angle == pytest.approx(angle, abs=1e-6)


@pytest.mark.parametrize("vector,edge", [
    ((0.0, 1.0, 0.0), "bottom"),
    ((1.0, 0.0, 0.0), "right"),
    ((0.0, -1.0, 0.0), "top"),
    ((-1.0, 0.0, 0.0), "left"),
])
def test_orientation_names_the_edge_pointing_down(vector, edge):
    assert _sensor(vector).orientation == edge


def test_lying_flat_has_no_meaningful_edge():
    s = _sensor((0.0, 0.0, 1.0))
    assert s.is_flat
    assert s.orientation == "flat"
    assert s.magnitude == pytest.approx(0.0)


def test_hysteresis_holds_the_edge_across_the_diagonal():
    """A sign resting near 45 degrees must report ONE stable name, not chatter."""
    d = FakeDisplay((0.0, 1.0, 0.0))
    s = TiltSensor(d, smoothing=1.0, min_interval=0.0, hysteresis=8.0)
    assert s.orientation == "bottom"
    # Just past the 45-degree boundary, but inside the hysteresis margin.
    d.virtual_tilt = _unit(50.0)
    assert s.orientation == "bottom"
    # Beyond the margin it commits to the new edge...
    d.virtual_tilt = _unit(60.0)
    assert s.orientation == "right"
    # ...and now the same 50 degrees reads "right" — that's the point of hysteresis.
    d.virtual_tilt = _unit(50.0)
    assert s.orientation == "right"


def test_first_reading_is_not_blended_with_the_flat_placeholder():
    """A hung sign must read "bottom" immediately, not "flat" for a few frames."""
    s = TiltSensor(FakeDisplay((0.0, 1.0, 0.0)), smoothing=0.2, min_interval=0.0)
    assert s.orientation == "bottom"
    assert s.read() == pytest.approx((0.0, 1.0, 0.0))


def test_smoothing_eases_toward_a_new_reading():
    d = FakeDisplay((0.0, 1.0, 0.0))
    s = TiltSensor(d, smoothing=0.5, min_interval=0.0)
    s.read()                                       # settle on the initial vector
    d.virtual_tilt = (1.0, 1.0, 0.0)
    first = s.read()
    assert 0.0 < first[0] < 1.0                    # part way, not a jump
    for _ in range(12):
        s.read()
    assert s.read()[0] == pytest.approx(1.0, abs=0.01)


def test_reads_are_throttled_between_intervals():
    d = FakeDisplay((0.0, 1.0, 0.0))
    s = TiltSensor(d, smoothing=1.0, min_interval=3600.0)
    assert s.read()[1] == pytest.approx(1.0)
    d.virtual_tilt = (1.0, 0.0, 0.0)
    assert s.read()[0] == pytest.approx(0.0)       # cached — no new I2C traffic
    assert s.read(force=True)[0] == pytest.approx(1.0)


def test_a_failing_source_keeps_the_last_good_vector():
    """One dropped read must not blank an effect."""
    class Flaky(FakeDisplay):
        @property
        def virtual_tilt(self):
            raise OSError("bus wobble")

        @virtual_tilt.setter
        def virtual_tilt(self, value):
            pass

    d = FakeDisplay((1.0, 0.0, 0.0))
    s = TiltSensor(d, smoothing=1.0, min_interval=0.0)
    good = s.read()
    s._display = Flaky()
    assert s.read() == good


def test_describe_is_json_able():
    snap = _sensor((1.0, 0.0, 0.0)).describe()
    assert snap["available"] is True
    assert snap["orientation"] == "right"
    assert snap["angle_deg"] == pytest.approx(90.0)


# --- the LIS3DH register driver ---------------------------------------------

class FakeI2C:
    """Just enough LIS3DH to exercise the driver: registers plus a burst read."""

    def __init__(self, device_id=0x33, vector=(0.0, 0.0, 1.0)):
        self.registers = {tilt_mod._REG_WHO_AM_I: device_id}
        self.vector = vector
        self.locked = False
        self.addresses = []
        self.lock_balance = 0

    def try_lock(self):
        self.locked = True
        self.lock_balance += 1
        return True

    def unlock(self):
        self.locked = False
        self.lock_balance -= 1

    def writeto(self, address, buf):
        assert self.locked, "wrote without holding the bus lock"
        self.addresses.append(address)
        self.registers[buf[0]] = buf[1]

    def writeto_then_readfrom(self, address, out, inb):
        assert self.locked, "read without holding the bus lock"
        self.addresses.append(address)
        reg = out[0]
        if reg & tilt_mod._AUTO_INCREMENT:
            assert (reg & 0x7F) == tilt_mod._REG_OUT_X_L
            assert len(inb) == 6, "must burst all six output registers at once"
            for i, g in enumerate(self.vector):
                lo, hi = _encode(g)
                inb[i * 2] = lo
                inb[i * 2 + 1] = hi
        else:
            inb[0] = self.registers.get(reg, 0)


def _encode(g):
    """g -> the two bytes a LIS3DH would return (12-bit, left-justified)."""
    raw = int(round(g / tilt_mod._MG_PER_LSB)) << 4
    if raw < 0:
        raw += 0x10000
    return raw & 0xFF, (raw >> 8) & 0xFF


@pytest.fixture
def fake_board(monkeypatch):
    """Pretend to be CircuitPython with a board exposing a shared I2C bus."""
    import types

    bus = FakeI2C()
    board = types.ModuleType("board")
    board.STEMMA_I2C = lambda: bus
    monkeypatch.setitem(sys.modules, "board", board)
    monkeypatch.setattr(tilt_mod, "_is_circuitpython", lambda: True)
    return bus


def test_device_probe_uses_0x19_not_0x18(fake_board):
    """The S3's LIS3DH answers at 0x19; Adafruit's libraries default to 0x18."""
    s = TiltSensor(FakeDisplay())
    assert s.available
    assert s.source == "lis3dh"
    assert set(fake_board.addresses) == {0x19}


def test_device_init_writes_the_expected_control_registers(fake_board):
    TiltSensor(FakeDisplay())
    assert fake_board.registers[tilt_mod._REG_CTRL1] == tilt_mod._CTRL1_100HZ_XYZ
    assert fake_board.registers[tilt_mod._REG_CTRL4] == tilt_mod._CTRL4_BDU_HR_2G


def test_wrong_who_am_i_means_no_accelerometer(fake_board, monkeypatch):
    """Something else at 0x19 must not be driven as if it were a LIS3DH."""
    import types
    bus = FakeI2C(device_id=0x00)
    board = types.ModuleType("board")
    board.STEMMA_I2C = lambda: bus
    monkeypatch.setitem(sys.modules, "board", board)
    s = TiltSensor(FakeDisplay())
    assert not s.available
    assert s.orientation == "flat"


def test_bus_lock_is_always_released(fake_board):
    s = TiltSensor(FakeDisplay())
    s.read(force=True)
    assert fake_board.lock_balance == 0
    assert not fake_board.locked


@pytest.mark.parametrize("vector", [
    (0.0, 1.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.25, -0.5, 0.75),
])
def test_burst_read_decodes_signed_12_bit_counts(fake_board, vector):
    fake_board.vector = vector
    s = TiltSensor(FakeDisplay(), smoothing=1.0, min_interval=0.0)
    got = s.read(force=True)
    assert got == pytest.approx(vector, abs=0.002)


def test_device_orientation_honors_the_axis_map(fake_board):
    """AXIS_MAP is the one place a mis-soldered chip gets corrected."""
    fake_board.vector = (1.0, 0.0, 0.0)
    s = TiltSensor(FakeDisplay(), smoothing=1.0, min_interval=0.0)
    assert s.orientation == "right"
    assert s.panel_gravity == pytest.approx((1.0, 0.0), abs=0.002)


def test_i2c_error_during_read_is_swallowed(fake_board):
    s = TiltSensor(FakeDisplay(), smoothing=1.0, min_interval=0.0)
    last = s.read(force=True)

    def boom(*_a, **_k):
        raise OSError("bus went away")

    fake_board.writeto_then_readfrom = boom
    assert s.read(force=True) == last              # keeps the last good vector


# --- helpers -----------------------------------------------------------------

def _unit(angle_deg):
    """A unit gravity vector at ``angle_deg`` clockwise from "bottom edge down"."""
    import math
    rad = math.radians(angle_deg)
    return (math.sin(rad), math.cos(rad), 0.0)
