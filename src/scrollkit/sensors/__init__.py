# Copyright (c) 2024-2026 Michael Czeiszperger
"""ScrollKit Sensors package — reading the physical world back into an app.

Kept deliberately empty of imports, exactly like ``scrollkit.effects``: importing
``scrollkit.sensors`` must not pull a driver into RAM on a device that never uses
one. Import the submodule directly instead::

    from scrollkit.sensors.tilt import TiltSensor

- **Tilt / orientation** (``sensors.tilt``) — the MatrixPortal S3's onboard LIS3DH
  accelerometer, read through a minimal built-in register driver (no
  ``adafruit_lis3dh`` install step). Reports which way is down as a continuous
  angle and as a panel-edge name, and degrades to "flat" and
  ``available == False`` on a board without an accelerometer (e.g. the Pimoroni
  Interstate 75 W) or on the desktop with no simulator display attached.

On the desktop the same ``TiltSensor`` class reads the simulator's *virtual*
gravity vector (steered with the arrow keys, or set programmatically for tests),
so an app that responds to tilt is developed and verified against the identical
API it will use on hardware.
"""
