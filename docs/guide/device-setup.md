# Physical Device Setup

This guide takes a ScrollKit app from loose parts to a running Adafruit
MatrixPortal S3 and 64×32 HUB75 panel. It is based on the deployment and recovery
workflow used by ThemeParkWaits on real hardware. For the code-side display API,
see [Display](display.md); to add support for a different controller, see
[Adding New Hardware](hardware.md).

## What you need

- An [Adafruit MatrixPortal S3](https://www.adafruit.com/product/5778).
- A 64×32 HUB75 RGB matrix panel.
- The panel power lead supplied with the MatrixPortal, plus a USB-C power supply.
- A known-good **data-capable** USB-C cable for flashing and serial access.
- A ScrollKit application with its own `code.py` and, if needed, `boot.py`.

ScrollKit is a library, so this repository intentionally does not provide an app's
root `code.py` or `boot.py`. Those files and the app-specific settings belong in
the application repository.

## Assemble the panel

Disconnect USB power before attaching or removing the controller or panel power
lead.

1. Remove the protective tape from the MatrixPortal's two panel-power standoffs.
2. Fasten the red lead to **+5V** and the black lead to **GND**.
3. Plug the four-conductor power connector into the matching socket on the panel.
4. Plug the MatrixPortal into the panel's **input** HUB75 connector. Orientation
   matters: on the standard Adafruit arrangement the panel's white direction arrow
   points up and to the right, and the MatrixPortal overhangs the panel edge so its
   buttons remain accessible.
5. Power and program the assembly through the MatrixPortal's USB-C port.

The screw terminals on the MatrixPortal are panel-power **outputs**, not an
alternate power input. For larger or chained panels, follow Adafruit's separate
power guidance instead of feeding external power back through those terminals.
The [official preparation guide](https://learn.adafruit.com/adafruit-matrixportal-s3/prep-the-matrixportal)
has photographs of the connector and lead orientation.

## Install CircuitPython

Use a CircuitPython release you have tested with the app and its compiled
dependencies. A source-only development deploy avoids `.mpy` compatibility issues;
if you ship `.mpy`, compile it with Adafruit's CircuitPython `mpy-cross` as described
in [Saving RAM with .mpy](../getting-started.md#saving-ram-with-mpy-optional).

1. Download the MatrixPortal S3 UF2 from the
   [board's CircuitPython page](https://circuitpython.org/board/adafruit_matrixportal_s3/).
2. Connect the board with a data-capable USB cable.
3. Double-click **RESET**. The status NeoPixel turns purple between clicks, then
   green, and a drive named `MATRXS3BOOT` appears.
4. Copy the UF2 onto `MATRXS3BOOT`. It disconnects and a new `CIRCUITPY` drive
   appears.
5. Open `boot_out.txt` on `CIRCUITPY` and confirm the expected board and
   CircuitPython version.

Some early MatrixPortal S3 boards shipped without the UF2 bootloader. If
`MATRXS3BOOT` never appears after several deliberate double-clicks, use Adafruit's
[bootloader repair instructions](https://learn.adafruit.com/adafruit-matrixportal-s3/factory-reset#factory-reset-and-bootloader-repair-3107941).

## Install the app and libraries

A typical device layout is:

```text
CIRCUITPY/
├── boot.py                    # app-owned startup/filesystem policy (optional)
├── code.py                    # app entry point
├── lib/
│   ├── scrollkit/             # device-safe ScrollKit modules
│   └── adafruit_*.mpy         # matching Adafruit bundle dependencies
├── src/                       # app package, if the app uses this layout
├── settings.json              # app-owned persistent settings, if used
└── secrets.py                 # optional developer WiFi fallback
```

From a ScrollKit checkout, `make copy-to-circuitpy` copies **only the ScrollKit
library** to `CIRCUITPY/lib/scrollkit/`; it does not copy an application's
`code.py`, `boot.py`, or `src/` tree:

```bash
# macOS default mount point; override CIRCUITPY for another mount location
make copy-to-circuitpy

# Install the Adafruit bundle dependencies used by ScrollKit
python -m pip install circup
circup install adafruit_requests adafruit_httpserver adafruit_display_text \
  adafruit_bitmap_font adafruit_matrixportal
```

Then use the application's deploy command, or copy its `code.py`, `boot.py`, and
package tree according to its imports. Keep device-owned state such as credentials,
settings, and logs out of destructive mirror/delete operations.

!!! warning "Know which source tree your deploy command uses"
    Some production deploy scripts intentionally package committed `HEAD`, not the
    working tree. In that design, uncommitted changes will not reach the board.
    Run a dry-run when the app provides one and inspect the copied file list.

## CIRCUITPY has one writer at a time

The USB host and CircuitPython must not write the same flash filesystem
concurrently. By default `CIRCUITPY` is writable by the host and read-only to
CircuitPython. Apps that persist settings, logs, diagnostics, or OTA files normally
reverse that ownership while running: device-writable, host-read-only.

ThemeParkWaits uses a practical two-mode `boot.py` convention:

| Physical action at boot | Filesystem owner | Use it for |
|---|---|---|
| Hold **DOWN**, tap **RESET**, then release DOWN | Host writable; device read-only | USB deploy or editing files on `CIRCUITPY` |
| Tap **RESET** with no button held | Device writable; host read-only | Normal app use, saved settings, logs, and OTA |

This behavior is **not installed by ScrollKit**. An app can adopt it with a small
`boot.py`:

```python
import board
import digitalio
import storage
import time

down = digitalio.DigitalInOut(board.BUTTON_DOWN)
down.direction = digitalio.Direction.INPUT
down.pull = digitalio.Pull.UP

# Let the input settle, then require a solid press. A single immediate sample can
# falsely enter deploy mode and leave settings/OTA unwritable.
time.sleep(0.05)
deploy_mode = all(not down.value for _ in range(3))

# True = read-only to CircuitPython/writable by USB host.
# False = writable to CircuitPython/read-only by USB host.
print("Host-writable deploy mode:", deploy_mode)
storage.remount("/", deploy_mode)
```

After a USB deploy, eject `CIRCUITPY` cleanly and tap **RESET** with no button held
to return to normal device-writable operation. Changing the mount at runtime does
not reliably change what the host sees; the mode must be selected during boot/USB
enumeration.

ThemeParkWaits also treats **UP + RESET** as a factory-reset escape hatch that
deletes its WiFi credentials, settings, log, and pending-update markers. That file
list is application policy, so ScrollKit cannot provide a safe universal version.
If you add one, document exactly what it erases and require an unmistakable physical
gesture.

!!! danger "Deploy mode is not normal runtime"
    An app may render correctly while the device filesystem is read-only, but its
    settings portal, diagnostics, and OTA staging will fail to persist. A host-side
    `Read-only file system` error means you need deploy mode; settings that vanish
    after reboot usually mean you accidentally left the device in deploy mode.

## First boot and WiFi onboarding

WiFi onboarding is opt-in application code, not an automatic result of installing
ScrollKit. If the app uses `WiFiManager.run_setup_portal()` as shown in
[Networking](networking.md#wifi-onboarding-portal-no-file-editing), the physical
first-boot flow is:

1. Power on or tap **RESET** with no buttons held.
2. Read the setup access-point name and URL scrolling on the panel.
3. Join that access point from a phone or laptop and open
   `http://192.168.4.1`.
4. Select the home network and enter its password.
5. The app saves the credentials and reboots onto the selected network.
6. If the app advertises mDNS, open its configured `<hostname>.local` address;
   otherwise use the IP printed on the serial console.

The normal no-button boot must be device-writable for step 4 to survive a reboot.
For development, an app can instead provide `secrets.py`; portal-saved settings take
precedence when both exist.

## Serial console and hardware smoke test

On macOS, find the board and open its 115200-baud console with:

```bash
ls /dev/cu.usbmodem*
screen /dev/cu.usbmodemXXXX 115200
```

After deliberately installing the current ScrollKit source, run the library's
non-writing MatrixPortal S3 smoke probe:

```bash
python -m pip install -e ".[device]"
make copy-to-circuitpy
make test-device-s3 PORT=/dev/cu.usbmodemXXXX
```

It checks board detection, 64×32 initialization, painter/text rendering, refresh,
and free heap without modifying `code.py` or `boot.py`.

## Before calling a device build finished

The simulator catches layout and modeled performance problems, but it cannot prove
flash-write ownership, real WiFi behavior, USB reset behavior, or power-cut
recovery. On the physical board, check at least:

- A fresh device with no credentials enters onboarding and persists the network.
- Wrong or unavailable WiFi shows status and retries without crashing.
- The panel, data updater, and web server continue to run together.
- The settings page works by raw IP and, when enabled, by mDNS name.
- A saved setting survives reset; this also proves the device is not in deploy
  mode.
- Synchronous network fetches show a pre-painted status frame and rendering resumes.
- Free heap and frame rate remain acceptable after the largest expected fetch with
  the web server active.
- If the app ships OTA, both success and interrupted/failure recovery leave a
  bootable device with credentials and settings intact.

Treat a green simulator run as pre-flight, not as a substitute for this final
physical pass.

## Quick troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `MATRXS3BOOT` never appears | Charge-only cable, missed reset timing, or missing/damaged UF2 bootloader | Try a known-good data cable and deliberate double-click; then use the bootloader repair guide |
| Host copy fails with `Read-only file system` | App booted device-writable | Hold DOWN, tap RESET, and redeploy (only if the app implements that convention) |
| Settings or OTA do not persist | Device booted host-writable/read-only | Eject the drive and reset with no buttons held |
| App imports fail after a compiled deploy | Incompatible `.mpy` compiler/version | Reinstall `.py` source, then rebuild with Adafruit's matching CircuitPython `mpy-cross` |
| Simulator passes but the panel is blank or behaves differently | Device-only dependency, connector, filesystem, or CircuitPython behavior | Check `boot_out.txt` and the serial traceback, then run the hardware smoke test |
