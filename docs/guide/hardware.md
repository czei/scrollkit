# Adding New Hardware

ScrollKit runs the same app on more than one HUB75 driver board. Two boards are
supported today:

| Board | Chip | Notes |
|-------|------|-------|
| **Adafruit MatrixPortal S3** | ESP32-S3 | The default. Calibrated from a real device. |
| **Pimoroni Interstate 75 W** | RP2350 | Wired in code; ships with an **uncalibrated estimate** profile until a baseline is captured on the board. |

A board differs from the others in only three places: how the RGB matrix is
constructed on CircuitPython, the default panel geometry, and the calibrated
performance profile the feasibility model uses. Everything else (the content
types, effects, transitions, the web/OTA stack) is board-agnostic. This page
covers how the abstraction works and how to add a board.

## How board selection works

`UnifiedDisplay` resolves which board it's on at construction time, in this order:

1. An explicit `board=` argument.
2. The `SCROLLKIT_HW_BOARD` environment variable.
3. Auto-detection on CircuitPython, reading `board.board_id`.
4. Falling back to the MatrixPortal S3.

```python
from scrollkit.display.unified import UnifiedDisplay

UnifiedDisplay()                                   # auto-detect; S3 on the desktop
UnifiedDisplay(board="pimoroni_interstate75_w")    # force a board
```

On the real device step 3 means a flashed board "just works" with no code change.
On the desktop there is no board, so auto-detect returns the S3 and you select a
different board explicitly (or via `SCROLLKIT_HW_BOARD`) when you want to model its
performance in the simulator. The registry and resolver live in
`src/scrollkit/display/boards.py`; that module is import-safe on the device (all
hardware imports are function-local), so it never drags `rgbmatrix` onto a desktop
or test import.

!!! info "Estimate vs. calibrated"
    A board's performance profile is **calibrated** once real timing is captured
    from the device (a `*_baseline.json` ships in the package); until then it uses
    a clearly-labeled `ROUGH_ESTIMATE_UNCALIBRATED` profile. Feasibility reports
    built from an estimate say so and round to one significant figure. The
    Interstate 75 W is in the estimate state today. See the
    [Performance](performance.md) guide for the cost model behind these profiles.

## Adding a board, step by step

1. **Register the board** in `BOARDS` in `src/scrollkit/display/boards.py`. Add a
   `BoardSpec` with its geometry, LED pitch, HUB75 address-pin count (4 for a
   64-row panel, 5 for 64-tall), and a `make_matrix` builder that constructs the
   panel on-device. Prefer the board's own RGBMatrix aliases so no GPIO numbers
   are hard-coded; fall back to an explicit pin list:

    ```python
    def _make_matrix_myboard(spec, width, height, bit_depth):
        import board, rgbmatrix, framebufferio
        matrix = rgbmatrix.RGBMatrix(
            width=width, height=height, bit_depth=bit_depth,
            addr_pins=board.MTX_ADDRESS[:spec.addr_pin_count],
            **board.MTX_COMMON)          # rgb_pins, clock/latch/oe
        display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)
        return matrix, display, matrix   # (hardware, display, matrix)
    ```

2. **Map its on-device id** by adding the board's `board.board_id` string(s) to
   `_ONDEVICE_ID_MAP` so auto-detection resolves it to your canonical id.

3. **Add an estimate profile** in
   `src/scrollkit/simulator/core/hardware_profile.py` (an `*_estimate()` function
   returning a `HardwareProfile` with `confidence=CONFIDENCE_ESTIMATE`). Set the
   RAM and timing fields to the chip's honest ballpark; this is what the
   feasibility gate uses until you calibrate. Register it in `_estimate_for()` and
   give the board a baseline filename in `_BASELINE_FILENAMES`.

4. **Calibrate once you have the board.** Flash CircuitPython, wire the panel, and
   first inspect the board's raw identifier and matrix-pin API over USB:

    ```bash
    PYTHONSAFEPATH=1 python test/claude/cpy_repl.py --port /dev/cu.usbmodemXXXX
    ```

    Confirm that the reported `BOARD_ID` / `MACHINE` maps to the new board and
    that either `MTX_COMMON` + `MTX_ADDRESS` or `NAMED_MATRIX_PINS` is true. Then
    capture real numbers:

    ```bash
    PYTHONSAFEPATH=1 python test/claude/calibrate_device.py \
        --board <id> --port /dev/cu.usbmodemXXXX --cp 10.2.1
    PYTHONSAFEPATH=1 python test/claude/device_benchmarks.py \
        --board <id> --port /dev/cu.usbmodemXXXX --cp 10.2.1
    ```

    These write `<id>_baseline.json` and `<id>_benchmarks.json` into
    `src/scrollkit/simulator/core/`. The profile then auto-upgrades to
    `CALIBRATED_FROM_DEVICE` with no further code change.

5. **Verify.** On the desktop, model the board and prove your app stays in budget:

    ```python
    from scrollkit.dev import run_headless
    result = run_headless(my_app, frames=120, strict=True)   # board via SCROLLKIT_HW_BOARD
    assert result.ok
    ```

    Then flash the real board and confirm the panel drives correctly.

   The calibration baseline drives feasibility reports; the benchmark table also
   feeds `scrollkit.dev.performance_guide("<id>")`.

!!! warning "Confirm the board id and pin aliases on real hardware"
    The exact `board.board_id` string and whether a given CircuitPython build
    exposes `board.MTX_COMMON` / `board.MTX_ADDRESS` (vs. individual pin names)
    should be checked on the device. The `make_matrix` builder falls back to an
    explicit pin list when those aliases are absent.

See also the [Performance](performance.md) guide for what the feasibility budget
means, and the [Display](display.md) guide for the `UnifiedDisplay` API your app
talks to.
