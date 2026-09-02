# Changelog

All notable changes to ScrollKit are recorded here. This project loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

Marks and acts: the half of a sign that could not previously be reused.

### Added
- **`scrollkit.effects.acts`: build → dwell → exit over any mark.** The palette
  treatments were already portable dwells, because a treatment takes a
  `PalettePartition` and nothing else, which is why twelve of a reference sign's
  fifteen dwells are one-liners. Builds and exits were not: they got written inside
  the app that owned the mark and reached into its tiles, its layout and its palette,
  so reusing one meant copying it. An act is now handed a duck-typed context and
  knows nothing else (`ctx.slots`, `.colors`, `.display`, `.running`, `await
  .frame()`, `.show()`, `.hide()`), so an app passes *itself* and inherits nothing.
  `swarm_build`, `swarm_unbuild`, `drip_in`, `wink_in`, `reveal_via`, `hide_via` and
  `treatment_dwell`, with `act_factory` / `supported_acts` mirroring the transition
  registry. The tests check LIT PIXELS after each act rather than the return value,
  because returning `True` over a black panel is the exact failure this prevents, and
  they cover the early exits too: a stopping sign, a dead surface, and an exit that
  must leave nothing visible. The port also found that the two original acts differed
  by accident rather than design (one checked `running` and one did not; one bounded
  at 2,000 steps and the other at 2,500, and the one that ignored `running` would
  keep a stopping sign on screen for another two thousand frames). Both now share one
  driver.
- **Seven act functions, 39 selections.** Twenty-four of a reference sign's
  thirty-seven acts are not bespoke code at all: they are a transition or a palette
  treatment applied to the mark, chosen by name. So `reveal_via` and `hide_via` each
  wrap 12 transitions and `treatment_dwell` wraps 11 treatments, and `selectable()`
  returns the menu one entry per *choice* rather than per function: 15 builds, 11
  dwells, 13 exits. Each entry carries a visual `family`, and a treatment's family is
  its **partition**, because two treatments animating the same grouping of pixels
  genuinely do look alike. Eleven treatments, nine families.
- **`play_sign()`: a whole sign, not a written sequence.** Draws build, dwell and
  exit from an `ActScheduler` and repeats until told to stop, leading with the
  least-recently-seen entry and never playing two of a family back to back, which is
  why a panel running it for a week does not visibly loop. A choice is a **kind and a
  name** (`"exit:Pixel Dissolve"`), because every transition is both a build and an
  exit and someone who kept a transition to end on did not thereby ask for it to open
  with; a bare name still selects every kind, which is the forgiving reading when
  nobody has said otherwise. A deck with no exit is refused rather than played half,
  since a sign that ended mid-build leaves the panel in a state no act chose.
- **`scrollkit.effects.mark.PixelMark`: the mark an act reveals.** Every build ends
  by calling `ctx.show()` to hand the real thing back and drop its overlay, and that
  step assumes something real is underneath. An app that owns its wordmark has it;
  anything else had nothing to borrow, so the drops landed, the overlay detached, and
  the panel went black while the act cheerfully returned `True`. `PixelMark` is the
  minimal version: lit cells and colours in, one bitmap, one palette and one tile
  out. `from_text()` builds one from the display's own font, so a deck of acts can be
  assembled and judged before any art is drawn; `from_art()` takes rows of characters
  plus `{character: colour}`, the format pixel art is already authored in, so a
  drawing goes on the panel without being converted into anything first. An unmapped
  character is a hole rather than a guess, which is how `.` and space become
  background without being special-cased.
- **`PixelMark.tile`.** The image animators take a `TileGrid`, and a host driving a
  mark along a path had no way to hand them one without reaching into a private
  attribute.
- **`PoseCycler`** (`effects/image_animators`) advances a list of tiles as one
  moving subject, exactly one visible at a time. This is what a sign otherwise writes
  by hand: darkowl's `_fly_pose` is two tiles at period 3, and its `_big_pose` is the
  four-beat `UP → MID → DOWN → MID` cel at period 2, which is why the beat `order` is
  its own argument and not just `len(tiles)`.
- **`MotionAnimator(path="point_to_point", ...)` and `MOTION_PATHS`.** `traverse_lr`
  crosses the panel and exits, so it has no destination and cannot put a subject down
  on a slot. This one **lands**: `from_xy`, `to_xy`, a frame count and a named curve,
  computed with `easing.interp` so a curve behaves here the way it behaves in every
  transition. Like traverse it does not recenter at detach, because snapping a
  subject home would undo the whole move, and it takes `poses` so the subject can flap
  while it flies. `MOTION_PATHS` is exported so a host letting something else choose a
  path validates against the animator's own list rather than a copy that drifts;
  constructing `point_to_point` without endpoints raises rather than quietly
  travelling from `(0, 0)` to `(0, 0)`.
- **`PARTITION_BUILDERS` and `builder_for()`** (`effects/palette_partition`) are the
  inverse of `treatments_for()`. Every treatment advertises the partition it wants as
  a nickname (`HaloPulse.PARTITION` is `"radial"`) and nothing resolved a nickname to
  a callable, so the catalogue emitted the bare string and a reader had to guess
  `map_radial`. Twelve of the thirteen are `map_` plus the nickname, which is worse
  than no convention: regular enough to be trusted and then guessed, and the one that
  breaks it is `"anchor"`, whose builder is `map_anchor_distance`. A code-generating
  agent spent an entire run guessing at exactly that name.
- **`capabilities()["composition"]`**, a new category for the combinators. The
  catalogue named every effect and not one of them, and a treatment cannot run
  without a partition, so it documented thirteen effects that could not be built from
  it. Now carries the `slots → map → PalettePartition → treatment` recipe, all ten
  builders with live signatures, `ActScheduler`, and the transition and treatment
  lookups, in under 1.8 KB of JSON: less than one panel image. Every treatment
  entry also gains `partition_call`,
  rendered from the live signature so it cannot drift:
  `map_anchor_distance(pixel_slots, anchor_x, n=10)`.
- **A "Marks & Acts" guide** (`docs/guide/acts.md`), plus `PoseCycler` and
  `point_to_point` in the character-animation and effects guides and the
  nickname-to-builder resolution in the palette-treatments guide.
- **`_Treatment.EXTRA_ARGS`, and a device-path guard against the reason for it.**
  Deciding which arguments a treatment needs by reading `inspect.signature` works on
  the desktop and raises `ImportError` on CircuitPython, which has no `inspect`, and
  the `except (TypeError, ValueError)` around it did not catch that: on a board,
  `treatments_available()`, `selectable()`, `treatment_dwell()` and `play_sign()`
  all died at import rather than degrading. Each treatment now declares its required
  positional arguments as class metadata, the way it already declares `PARTITION`
  and `FEASIBILITY`, and a test pins every declaration against the real signature so
  it cannot drift. `test_circuitpython_compat.py` gains a static scan of the device
  path for imports of modules CircuitPython lacks; guarded imports (`try: import x /
  except ImportError`) are still allowed, since that is how `typing` is handled.

### Fixed
- **`run_headless(app, frames=N)` now bounds a self-driving app.** `frames` bounded
  only one of the two program shapes. An app whose `setup()` returns is driven by the
  harness's own loop, which counts to `frames`; an app that never returns from
  `setup()` (the `while self.running` shape a generated sign uses) never reached that
  loop, so `frames` was silently ignored and `run_headless(app, frames=20)` rendered
  until something killed the process. The cap now counts at `display.show()`, the one
  call both shapes make exactly once per frame, and stops the run at the frame
  boundary. The wrapper goes on the display *instance* and comes off again, because
  wrapping `UnifiedDisplay.show` on the class leaks into every later app in the same
  process and counts each frame once per wrap; the frame signature is read before the
  stop unwinds, because teardown drops the display, the performance manager and every
  recorded frame on the way out. Stopping a loop that never planned to stop costs one
  thing worth knowing: the unwind goes *through* `show()`, so whatever the app's loop
  does after showing its last frame does not run for that frame.
- **A mark wider than the panel no longer takes the sign down on its first dwell.**
  `PixelMark.attach()` dropped off-panel cells from the bitmap but kept them in
  `slots`, so the mark went on describing pixels it never drew. Six of the seven acts
  survived that; `treatment_dwell` did not, because it hands `ctx.slots` straight to a
  panel-sized `PalettePartition`, which raised `IndexError`. That is the exact failure
  the drop was there to prevent. `attach()` now narrows `slots` to the cells that fit,
  preserving shape (a mapping stays a mapping, so per-pixel indices survive).

## [0.11.1] - 2026-08-21

Brightness that actually dims, a panel renderer that no longer needs pygame, and the
pixel-art chapter the docs never had.

Numbered 0.11.1 because v0.11.0 was tagged and then blocked at the gate: a test asserted
which of two rapidly-cycling items a headless run happened to stop on, which passed on
macOS and failed on Linux CI, and a red CI stops the upload. Nothing was ever published
under 0.11.0 — it is a tag with no release behind it. The test now asserts that content
expires rather than which item is up at the cutoff.

### Added
- **A pygame-free rendering backend, and a 3.7x faster panel composite.** pygame is a C
  extension over SDL with no wasm build — not in Pyodide's package set, no emscripten
  wheels for pygame-ce on PyPI — so six calls (`Surface`, `SRCALPHA`, `draw.circle`,
  `transform.smoothscale`, `BLEND_RGB_ADD`, `image.save`) stranded the entire LED cosmetic
  layer on the desktop, and a browser preview showed flat squares instead of a panel.
  `simulator/core/_surface.py` picks a backend: pygame where importable, numpy where not.
  pygame stays primary wherever it exists, so desktop output is untouched — verified by
  frame hash, unchanged before and after. The composite also replaces up to 4,096 small
  per-LED array ops with a handful of whole-array writes: dots tile exactly on the pitch,
  and 20 px glow sprites overlap on an 11 px pitch but not on a two-cell sub-lattice, where
  the pitch is 22 ≥ 20 — so four passes cover the panel with no overlap inside any pass.
  Additive saturation is order-independent, so the result is bit-identical rather than
  merely close, and the test asserts that. 13.6 → 3.67 ms/frame, and measured end to end in
  Pyodide, 190.7 → 64.8 ms/frame (5.2 → 15.4 fps), with the paint handoff going 127 → ~1 ms
  once the panel composes into a persistent RGBA buffer the host wraps zero-copy.
- **`scrollkit.utils.pixel_art` — `normalize_art()`, `normalize_all()`, `art_problems()`.**
  Hand-authored ASCII art has exactly two typos, and both crash from deep inside the
  conversion loop with nothing on the panel: a ragged row throws `IndexError`, an unmapped
  character throws `KeyError`. Across six documented model-written signs, every
  first-attempt failure was one of those two and nothing else — one of them a single row of
  25 characters where its two neighbours were 26, in a 598-line program with 34 sprites,
  which cost two full regeneration rounds. Short rows now pad with transparent, unmapped
  whitespace becomes transparent, and any other unmapped character becomes the first lit
  slot, because the author drew something there and substituting transparent would silently
  delete the sprite — a worse outcome than the crash. Every repair reports one line naming
  the sprite, and clean art passes through untouched. `art_problems()` returns the same
  findings as a list for tests that would rather assert than repair.
- **A pixel-art chapter.** `docs/guide/pixel-art.md` covers art as ASCII rows over palette
  slots, authoring small and doubling, the width arithmetic for 64x32, converting to a
  `Bitmap` once, and then animating with palette writes, tile moves and hidden flags rather
  than redrawing. `demos/medium/pixel_wordmark.py` is the worked example: hand-authored
  letterforms, a sprite on its own material slots, and four acts through an `ActScheduler`,
  at ~9 palette writes a frame. Given the library's own docs, three models each built a
  competent multi-scene sign — correct areas, real tool lists, inside the frame budget —
  and not one drew a picture. `AGENTS.md` had no pixel-art chapter and led its content
  section with `ScrollingText`/`StaticText`, so a text-oriented prompt produced text signs.
- **`UnifiedDisplay.set_color_scale(brightness)` and `.color_scale`** — the software dimmer
  behind the brightness change below. Synchronous; `set_brightness()` remains as the async
  wrapper for existing callers.
- **`run_headless` / `run_headless_async` take `throttle=None|True|False`.** The harness
  forced the performance manager's throttle off on every headless run, which is right for a
  test suite and left a preview with no supported path to hardware-speed playback at all.
  `True` *sets* the flag rather than leaving it intact: the manager defaults to off, and a
  preview handed an arbitrary app cannot arrange otherwise. Ambient console nags stay off
  regardless — the callers who want pacing are UIs, not terminals.
- **`run_headless` / `run_headless_async` take `virtual_clock=True`, and
  `scrollkit.dev.clock` is the injection point behind it.** Duration-driven content asks
  the clock how long it has been on screen, and in a headless run wall time is the wrong
  answer: frames step with no inter-frame sleep, 60 of them pass in ~0.2 s, a
  `duration=2.0` item never expires, and a correct animated app reports that it never
  animates. With the flag, content time comes from `PerformanceManager.modeled_elapsed_s` —
  what the frames would have cost the *panel* — so a four-second act lasts four seconds of
  device time no matter how fast the host renders. It installs after the display exists,
  uninstalls when the run ends, and raises `VirtualClockUnavailable` rather than returning
  0.0 if there is no timing model to read.
- `PerformanceManager.modeled_elapsed_us` / `.modeled_elapsed_s` / `.frames_ended` — a
  monotonic run total, kept separate from the bounded `frames` history a clock built on it
  would run backwards on.

### Changed
- **Brightness is a software colour scale now, not a hardware property.** `display.brightness`
  on the MatrixPortal S3 is not a dimmer — it is effectively on/off: 0.0 blanks the panel and
  0.15 looks identical to 1.0 (confirmed on hardware, six live changes, no visible
  difference). The re-platform had replaced a working software dimmer with it, so the
  brightness setting did nothing across its whole range for the entire 3.x line, and a
  stored "0" left a customer's sign dark for months with a perfectly healthy app behind it.
  The panel is now pinned to FULL and colours are scaled on their way out, from a RAW
  cached base — pre-dimming the base looks cheaper but double-dims `CoverAnimator`, which
  builds its overlay colours from `base_colors` and passes them through the same
  `_make_overlay` that dims. Covered: `draw_text`/`draw_text_scaled`, the `set_pixel`/`fill`
  paint path, the gradient ramp (with `color_scale` in the layer cache key, or a scrolling
  name would keep its old brightness until the content cycled), all five `BitmapText`
  palette effects, the write-once effect palettes, every icon overlay animator, the pulse,
  and the three cloned palettes `SpriteLift`/`FrameCycle`/`GravityDrip` build. **Note for
  upgraders:** a stored brightness that has been silently ignored will now take effect, so
  a sign configured low will visibly dim on this release.
- **`pixel_write_us` is measured now, not guessed.** The feasibility gate false-rejected a
  field-proven act at 17.7 fps against a 20 fps target, and the whole error was one
  constant: `pixel_writes` decided the verdict (92% of that act's frame) and the term is
  `set_pixel_calls * 3 * profile.pixel_write_us`, where `pixel_write_us` was a hardcoded
  5.0 that never came from a device — inside a profile reporting
  `confidence: CALIBRATED_FROM_DEVICE`. `calibrate_device.py` now measures it (and takes
  `--out`, so a run can be inspected without overwriting the shipped baseline). On a
  MatrixPortal S3 it is 4.333 µs, of which the write is 3.36 µs and 74% of per-pixel cost
  is Python loop overhead — which is why a per-pixel effect is expensive on this board
  regardless of what it writes. The board measured runs CircuitPython 10.2.1 while the rest
  of the baseline is 9.1.0; frame-time terms are stable across the two (bitmap_rebuild
  +0.4%, full_refresh +0.7%), which is why this one is mixed in, while memory is *not*
  (usable_ram −24.6% on 10.2.1) and is deliberately left at 9.1.0. The baseline records
  that in `_pixel_write_us_source`.

### Fixed
- **A browser preview locked the page and painted nothing.** `unified.py`'s no-pygame
  branch skipped the await, so the whole run blocked until it finished; it now refreshes,
  records and yields like the pygame path. `save_surface_png` opened with `import pygame`
  and returned `None` on `ImportError`, which left the public `display.screenshot()` broken
  in exactly the environment the numpy backend exists for, while
  `matrix.save_screenshot()` worked. `capture_frame` and `save_surface_png` handle both
  backends now.
- **`swarm_reveal` was not reproducible across Python versions.** Running 35 acts in
  CPython 3.12 and again in Pyodide's 3.13, 34 matched frame for frame and `swarm` diverged
  from frame 0 — not flakiness, since two runs with the same seed are identical. The queue
  came from `list(self._remaining)` over a set, and `_shuffle()` permutes whatever order it
  is handed; set iteration order is stable within one Python build but is not guaranteed
  across versions, so seeding the RNG was not sufficient. `sorted()` makes the seeded
  shuffle the only source of order. Worth stating as a general rule for anything compared
  across runtimes: never derive an ORDER from iterating a set or dict.
- **Throttled pacing overshot every frame.** It slept the whole modeled frame cost *after*
  the frame had already rendered, so a frame took `real_work + modeled` rather than
  `max(real_work, modeled)` and a host faster than the device still ran slower than it, by
  the render time, every frame. Measured against a browser preview doing its real work in
  14–25% of modeled, that was a 12–25% overshoot: a window claiming to crawl at hardware
  speed while crawling under it. It now sleeps only the unspent remainder, and a frame that
  overruns its budget does not sleep — it cannot un-spend the time, and pacing must never
  run backwards to make it up.
- **`url_decode` mangled every non-ASCII character.** Percent-escapes are bytes, and
  browsers encode form fields as UTF-8, so `é` arrives as `%C3%A9`. Turning each escape
  straight into a character with `chr()` produced `Ã©` — two wrong characters, silently, in
  whatever the user typed. For a WiFi password that means the board stores something the
  user never entered and can never join their network, while the setup portal reports
  success, because the corruption happens before anything checks. The bytes are now
  collected and decoded once, with the old byte-wise reading kept as a fallback for input
  that is not valid UTF-8 (a mangled password beats no password). Note the fix applies to
  new saves only: a board that already stored a mangled credential keeps it until the user
  re-enters it.
- **`SettingsManager.save_settings` truncated the live file before writing.** That file
  holds the WiFi credentials and is rewritten by every ordinary settings save, so a power
  cut anywhere in the window left a 0-byte or half-written file that loaded as `{}` on the
  next boot: factory defaults, credentials included, with nothing in the log to say why. It
  now writes a temp file and swaps it in, and `load_settings` falls back to that temp file
  when the live one is missing. It also returns `True`/`False` rather than swallowing the
  failure, and rejects valid JSON with a non-object root (`null`, `[]`) which previously
  raised during construction.
- **A failed credential save reported success.** `WiFiManager.save_credentials` now returns
  a result and `WiFiSetupPortal` refuses to declare the network saved when the write did
  not land. Saving is what makes `run_setup_portal` reboot the board, so a silently failed
  write sent the user away happy and brought the box back with no credentials at all.
- **A swallowed display-init failure looked healthy.** `_initialize_display` caught
  `ImportError`/`OSError` and carried on, leaving every draw a no-op: a panel black forever
  while the watchdog was fed and the web UI served normally. Nothing reset, nothing retried,
  and every health signal read green. It is still caught, but recorded to `error_log` and
  exposed as `display_init_error`.

### Docs
- **The reveals table had no signatures.** It showed `DripReveal`'s call with `color=BRAND`
  and then listed `SwarmReveal`, `show_reveal_splash` and the transitions with none at all.
  A model reading that generalised the keyword it had seen and wrote
  `SwarmReveal(pixels, color=...)`, which died at frame 1 with
  `TypeError: unexpected keyword argument 'color'` — `SwarmReveal` takes `text_color=` and
  `bird_color=` and has no `color=`. Reasonable inference from what the page showed; the
  page was the problem. The table now carries each constructor's actual colour arguments
  and says plainly that they are not shared.
- **The `random()` availability list was written from recollection.** The warning box
  asserted seven functions including `getrandbits` and `seed`, neither of which is called
  anywhere in this library or in the reference sign — the same failure mode as a profile
  reporting `CALIBRATED_FROM_DEVICE` for a term nobody measured. It now states the five the
  shipped library and the field-proven sign actually call (`random`, `uniform`, `randint`,
  `randrange`, `choice`) as the working set, with the provenance attached, and says what
  `ActScheduler` does instead of shuffling, since "use the scheduler" without the reason
  invites a hand-rolled deck anyway.

## [0.10.0] - 2026-08-02

A sensor layer, and the network work from three field failures on a fielded
MatrixPortal S3 (CircuitPython 9.2.x).

### Added
- **`scrollkit.sensors` — the first sensor package.** `sensors.tilt.TiltSensor`
  reads the MatrixPortal S3's onboard LIS3DH through a minimal built-in
  register driver, so there is no `adafruit_lis3dh` to copy into `/lib`.
  Everything it reports is in PANEL space, not chip space: `gravity_angle`
  (continuous degrees clockwise from "bottom edge down") and `orientation`
  (which edge faces the floor, hysteretic so a sign resting near a diagonal
  does not chatter between two names every frame). Reads throttle to 10 Hz, so
  calling it every frame in a 20 fps loop costs nothing, and it never raises —
  no accelerometer, a busy bus, or no display all give `available == False`
  and `orientation == "flat"`. Note the address gotcha: on the S3 the part
  answers at I2C **0x19**, not the 0x18 Adafruit's own libraries default to.
  Like `scrollkit.effects`, the package imports nothing at package level —
  import `scrollkit.sensors.tilt` directly so a board that never tilts pays no
  RAM.
- `BoardSpec.has_accelerometer` / `accel_i2c_address`, so a board that differs
  is corrected in the registry rather than in the driver (the Interstate 75 W
  has no accelerometer and is never probed). `capabilities()` gains a live
  `sensors` section queried from that registry.
- `GravityDripAnimator` (`effects/image_animators.py`): whatever is on screen
  lets go and pours toward whichever edge is now the floor; `set_gravity()`
  re-aims the pile mid-fall. Pixels lift onto a full-panel overlay, so a
  7-row text strip falls to the panel floor instead of piling up inside its
  own bitmap. It is an image animator, not a `Transition` — it decorates a
  layer already on screen rather than covering, swapping and revealing.
- **Virtual tilt in the simulator**: `display.virtual_tilt` /
  `set_virtual_tilt(angle=, flat=)` carry a gravity vector that `TiltSensor`
  reads when there is no real chip (you cannot tilt a laptop). Arrow keys
  steer it in the pygame window; the setter gives tests and headless runs
  exact, reproducible angles. Same class both places. Plus
  `demos/medium/tilt_drip.py` and `docs/guide/sensors.md`.
- **`HttpClient.get(stream=True)`** returns a socket-owning
  `StreamingResponse`: `iter_content` chunks on the device, a whole-body
  fallback for desktop and mocks, `close()` in `__exit__`. A stream that dies
  mid-iteration raises from the caller's loop and is the caller's retry to
  make.
- **`StreamingResponse.readinto(buf)`** — the drain primitive for a
  drain-then-parse fetch: drain the whole body into your own reusable buffer,
  close, then parse. The response stays open for network time only instead of
  across a multi-second parse, and the loop allocates nothing per iteration.
  It uses adafruit_requests 4.1.17's native `Response._readinto` when present
  (chunked encoding and content-length handled), otherwise drives
  `iter_content` carrying an oversized chunk's tail into the next call. EOF
  returns 0 repeatably, including after `close()`. It is *not* a cure for the
  `-12288` TLS-SRAM exhaustion — that leak scales with bytes read, sits below
  the CircuitPython heap, and is cured only by a reset.
- `note_fetch_result(rearm=)` separates "stamp the success time" from "re-arm
  recovery state", so a PARTIAL refresh can never read as full health.

### Changed
- `BaseResponse.content` is lazy. The eager `text.encode()` kept every payload
  resident TWICE (~180 KB for a 90 KB body) although the hot paths only read
  `.text`; on a non-compacting heap that shattered the largest free block
  until 54 KB requests failed with 1.37 MB free.
- The watchdog now arms BEFORE `setup()` at a boot-sized timeout — boot was
  previously unprotected. CircuitPython 9.2.8 rejects retightening a running
  watchdog, so one window covers boot and runtime.
- A data-progress deadman on the display loop cold-resets on a dead task, an
  attempt that never returns, or a loop that stops iterating. Progress means
  attempts COMPLETING, success or failure alike, so a box that is offline and
  actively retrying reads as healthy. The data task is always created; a
  transient low-memory reading used to omit it permanently.
- `hard_reset()` ladders cold reset → raw reset → `supervisor.reload`, so a
  decided reset never silently no-ops. A failure-reboot epoch flag in NVM
  rate-limits failure-driven reboots, cleared only by a real fetch success.

### Fixed
- **OTA on CircuitPython 9.x.** 9.2.x ships a `hashlib` with no sha256, so
  every OTA download failed verification and rolled back. `_new_digest()` now
  picks the strongest checksum the runtime can actually compute (sha256, else
  native `binascii.crc32`) at all four verification sites, including the delta
  comparison. Verification is never skipped — no usable digest raises a named
  error. Payloads are unsigned either way, so authenticity still rests on TLS;
  the checksum's job is catching corrupt downloads. Staged manifests are
  `json.dump`-streamed rather than built as one string, and the allowlist
  accepts `/safemode.py`.
- A desktop `rtc` mock constructed `adafruit_datetime.datetime()` eagerly and
  raised `TypeError`, silently failing every desktop RTC write.

## [0.9.3] - 2026-07-16

### Fixed
- `scrollkit.utils.system_utils` imports cleanly on a bare desktop install:
  its module-level fallback imported `adafruit_datetime`, which pip does not
  carry — so the `cold_reset()` import 0.9.2's changelog advertises crashed
  any run-unchanged-on-both app at desktop import time. Caught by the
  clean-room wheel check minutes after 0.9.2 shipped.

## [0.9.2] - 2026-07-16

Field-resilience APIs from two days of on-hardware incident work (ESP32-S3,
CircuitPython 10.2.1, a two-node mesh network; the full falsification trail
lives in the ThemeParkWaits repo's docs/ota-check-failure-ledger.md).

### Changed
- **The hardware watchdog now arms even when a USB serial console is
  attached.** The old guard silently skipped arming whenever a host held the
  CDC port open, so a board living next to a computer ran with NO watchdog at
  all. Boards that were silently unprotected become protected on upgrade:
  size `watchdog_timeout` ABOVE your longest legitimate event-loop block
  (e.g. a synchronous HTTP call inside a web handler) or the board will
  reset-loop. Opt out for interactive debugging by creating a `/no_watchdog`
  file on the device (do it BEFORE rebooting into the debug session).
  `ScrollKitApp.watchdog_state` reports the arming outcome.
- The display loop stops feeding the watchdog after
  `MAX_CONSECUTIVE_RENDER_ERRORS` (10) consecutive render errors, so a
  permanently-broken render path hardware-resets instead of sitting frozen
  behind a fed watchdog; one successful frame resumes feeding.
- Every deliberate reboot in the library — OTA apply, the auto-reboot
  watchdog, `WiFiManager.reset()` — is now a COLD reset (radio disabled
  first): a reset issued while the station is associated degrades the next
  session until new outbound connects fail `OSError: 16` while pooled
  keep-alive flows still work.

### Added
- `OTAClient(check_url=...)` (also on `for_github`): point the frequent
  update CHECK at a ~6-byte `version.txt` on a host you control. With it set
  a check never handshakes with `server_url` — useful when the download host
  serves an RSA-2048 chain whose mbedTLS verification needs more internal
  SRAM than a running app has free (`-0x3F80 PK_ALLOC_FAILED`); the manifest
  fetch defers to download time, which can run at early boot with maximal
  headroom.
- `WiFiManager.bounce()` / `bounce_sync()`: forced radio restart + fresh
  association that acts even while the link LOOKS up. Complete every bounce
  with `HttpClient.rebuild_session()` (below) — reassociation alone leaves
  the session's stale socket plumbing failing.
- `HttpClient.rebuild_session()`: public full session rebuild (fresh
  SocketPool + ssl context + Session).
- `scrollkit.utils.system_utils.cold_reset()`: radio-off-then-reset, for app
  code that reboots deliberately.
- `ScrollKitApp.watchdog_state` and `ScrollKitApp.frames_rendered`
  diagnostics attributes (surface them in your status page: a frozen frame
  counter means the display loop died; an advancing counter with a dark
  panel means the output path died below Python).

### Fixed
- OTA: installing `X.mpy` now removes a stale `X.py` sibling (a device
  USB-deployed as source then OTA-updated to compiled accumulated both
  generations interleaved).
- `bounce_sync()` keeps `WiFiManager.is_connected` truthful.

## [0.9.1] - 2026-07-15

First-run developer experience, from a clean-room audit of what
`pip install "scrollkit[simulator]"` actually delivers to a new user.

### Fixed
- Simulator `displayio.FourWire(reset=...)` no longer overwrites its callable
  `reset()` method with the reset pin.
- `StaticText`/`ScrollingText` now accept `(r, g, b)` tuple colors — previously
  a tuple silently rendered the wrong color (the docs' own
  `color=(0, 255, 128)` example drew blue instead of green).
- The `[web]` extra now installs `adafruit-circuitpython-httpserver` — the
  dependency `SettingsWebServer` actually imports — instead of `aiohttp`,
  which nothing in the library uses. `pip install "scrollkit[web]"` gives a
  working browser settings UI on desktop.
- The README / docs Quick Start now opens the simulator window
  (`create_display()` → `SimulatorDisplay`); the previous snippet ran headless
  and invisible on desktop. Dropped the leftover `sys.path.insert(0, "src")`
  repo-ism from the getting-started example.

### Changed
- Quieter, friendlier desktop startup: a missing `adafruit_httpserver` prints
  one actionable line instead of a stack of failures; the meaningless desktop
  "Free memory: 100000 bytes" placeholder is no longer printed (real device
  and hardware-sim numbers still are); "Starting SLDK application" is now
  "Starting ScrollKit application"; and importing the library on desktop no
  longer creates an empty `error_log` in the working directory (the file
  appears on first actual write).

### Added
- Focused simulator primitive, URL utility, and MP4 recording tests, including
  a real ffmpeg/ffprobe H.264 smoke check.
- A non-writing MatrixPortal S3 raw-REPL smoke probe (`make test-device-s3
  PORT=...`) for deployed-library, panel, painter, text, refresh, and memory
  validation.
- CI changed-line coverage on pull requests plus clean-wheel and media-encode
  smoke jobs, so package data and MP4 support are verified before release.

## [0.9.0] - 2026-07-14

The DarkOwl promotion: the effect mechanisms invented for the DarkOwl LED
logo sign — a 24/7 show on a MatrixPortal S3 — generalized into the library.
The headline is palette-partition animation: bake a mark's pixels into an
indexed layer once, then animate purely with palette writes.

### Added
- `effects/palette_partition.py`: `PalettePartition` (indexed layer with
  reserved identity slots) plus ten partition builders (diagonal, anchor
  distance, radial, angular, rain phase, checker, exposure, Voronoi regions,
  stroke topology, BFS route) and `bfs_paths`.
- `effects/palette_treatments.py`: thirteen frame-driven dwell treatments
  (VelvetSweep, AnchorWake, HaloPulse, SonarSweep, CipherRain, InkShimmer,
  RimLight, HeatmapDrift, EclipseCross, GradientDwell, StrokeAnatomy,
  RouteCircuit, PacketTrace) with a 5-stop theme contract, caller-owned
  blink beats (`blink_now`), `TREATMENT_CLASSES` + `treatments_for()`.
- `effects/swirl_in.py`: `SwirlIn` — sprites spiral in around a center onto
  exact target positions (deliberately NOT a named Transition: it needs a
  per-sprite target list).
- `SwarmReveal` true-color and reverse modes: `index_map=` / `pixel_colors=`
  paint an arbitrary source image's exact colors; `reverse=True` pre-lights
  the image and the flock carries it away pixel by pixel.
- `utils/scheduler.py`: `ActScheduler` — weighted-age, family-aware deck
  picking for 24/7 variety (least-recently-seen leads, no family repeats,
  `force=` for openers).
- Visual Reference: a `treatments` gallery category with a sample for every
  treatment class (coverage-gated); `capabilities()` gains a
  `palette_treatments` section.

## [0.8.5] - 2026-07-13

A hardening release forged by a fielded MatrixPortal S3: three of these fixes
were found because a real device failed in the field, not because a test went
red. Detailed post-mortem in the ThemeParkWaits app repo
(`docs/ota-check-failure-ledger.md`).

### Fixed
- `RegionRotateAnimator` now works on real hardware: `math.hypot` does not
  exist on CircuitPython (start() raised, hosts silently fell back to a still
  image), and the erase-everything-then-redraw restamp flickered against the
  panel's continuous refresh — restamps are now pose diffs, byte-identical to
  the old poses.
- OTA client streams manifest and file bodies to flash in small chunks instead
  of `response.json()` / `response.content` — a ~31 KB body needed one
  contiguous allocation that a hot heap often cannot provide (intermittent
  `MemoryError` on update checks).
- `HttpClient._rebuild_session` closes the old pool's sockets before building
  the replacement (new public `close_pooled_sockets()`). Dropping the pool to
  the GC orphaned its native mbedtls TLS contexts (~40 KB of ESP32-S3 internal
  SRAM each); with a rebuild threshold of 2, multi-day uptime starved every
  TLS handshake (`PK_ALLOC_FAILED` / `MemoryError` / `Out of sockets`).
- Update checks use a dedicated 8 s `check_timeout` (downloads keep 30 s): the
  check runs inside a synchronous handler that freezes the display for its
  duration, so one stalled read must not cost 30 frozen seconds.
- OTA takeover messages ("Updating — DO NOT UNPLUG") blank the screen properly:
  new `GraphicsMixin.clear_layers()` strips persistent bitmap layers that
  `clear()` deliberately leaves alone (the message used to paint on top of the
  interrupted content), resetting the bounded painter so it self-heals.

### Added
- ~6-byte update checks: `check_for_updates` reads the channel's `version.txt`
  first and answers "up to date" without fetching the manifest (strict
  MAJOR.MINOR[.PATCH] validation so an error page can never fake the answer;
  404 falls back to the manifest for older channels). Publishers ship
  `version.txt` beside `manifest.json`.
- `WiFiManager(ap_name=...)`: apps brand the onboarding portal's access point
  (e.g. `ThemeParkWaits-XXXX`); the library owns only the MAC-derived
  uniqueness tail and never hardwires a product name.
- Interstate 75 W bring-up: named-matrix-pin fallback coverage, a host-side
  smoke probe, and `--port`-aware device calibration/benchmark tooling.
- CircuitPython math-surface guard test: device-path code is statically checked
  against the REAL board's `math` module (no `hypot`, `tau`, `inf`, `nan`,
  `isclose`, `log2`, `log10`, ...), the same trap class as `random.shuffle`.
- Cel-walk demo: nodding head.

### Docs
- New OTA guide section: shipping the library as `.mpy` — pinned
  CircuitPython-matched mpy-cross (the PyPI `mpy-cross` package is
  MicroPython's compiler and boards reject its bytecode), `-s` for
  deterministic builds, the free-space rule, and the updater's
  no-deletion-by-omission semantics.
- Corrected the `pip install mpy-cross` guidance in getting-started and the
  makefile.

## [0.8.4] - 2026-07-08

### Added
- `scrollkit.effects.image_animators` — twelve per-frame animators that decorate a
  static image layer already on screen (twinkle, tile motion, particle emitter,
  palette pulse, region shift with sine/ramp/ripple/hinge waves, orbiter, blink,
  sprite lift with automatic scene inpainting, cover, vanish, pre-baked frame
  cycling, and combos). Extracted up from the ThemeParkWaits app's ride-intro
  engine; start/step/detach contract, FEASIBILITY dicts on every class, and an
  ordered `ANIMATOR_CLASSES` catalog.
- `RegionRotateAnimator` — the thirteenth image animator: tilts the lit pixels
  inside a box about a pivot *point*, oscillating, for a real rotation (a nodding
  head, a waving arm, a see-sawing plank) rather than `RegionShift`'s upright
  `hinge` shear. Hole-free by inverse-mapping every destination pixel; an `exclude`
  box freezes the attached body it rotates on (no seam tears); cost-guarded
  (refuses >320 lit px or a >1600-cell scan box and falls back), and settles the
  region upright on `detach()`.
- `CelWalkAnimator` — a multi-pose cel walk-cycle primitive: plays an authored
  walk-cycle spritesheet (a sibling `<image>_walk.bmp` of N panel-sized tiles) via a
  tile-indexed `TileGrid` while translating the sprite across the panel, so the legs
  are genuinely different authored drawings frame to frame and the gait reads as real
  stepping. Pose change is a single tile write and travel is a `tile.x` write: no
  per-frame allocation, no layer churn.
- OTA **delta apply** — a device can consume a large combined manifest (app plus a
  bundled library under `/lib/scrollkit`) on thin free space: it hashes its live tree
  and downloads/backs up/installs only the files whose sha256 differs, sizing the
  free-space guard to the delta (`2*delta+50KB`) rather than the whole manifest. The
  full manifest is still verified after apply; a `created_paths` marker deletes
  newly-created files on rollback so an interrupted apply leaves no orphans; plus a
  device-side path-safety allowlist. Verified on hardware.
- `image_animators.read_indexed_bmp()` — decode an 8-bit indexed BMP straight into a
  writable `Bitmap`. On-device `OnDiskBitmap` is not subscriptable, so animators that
  read/rewrite image pixels need this; the demo and reference generator use it as the
  device-correct loader (`OnDiskBitmap` for the palette + `read_indexed_bmp` for pixels).
- Docs: an animated GIF for every image animator, in the **Effects** guide and the
  **Visual Reference** gallery, generated by `demos/render_reference.py` (a new
  `animators` route driven from the live `ANIMATOR_CLASSES`, guarded by
  `test_reference_coverage.py` so a new animator can't ship without a sample).
- `demos/medium/image_intro.py` — a runnable demo showing image animators in context:
  an animated image intro (twinkle / traverse / rocket-liftoff combo) handing off to a
  data screen, illustrating the self-driving display loop vs. the content queue. Added
  to the Demo Gallery.
- `capabilities()` gains a distinct `image_animators` category (its own key, not folded
  into `effects`) enumerated from `ANIMATOR_CLASSES`, with each class's FEASIBILITY
  budget; surfaced in `as_text()` and documented in `AGENTS.md`.

### Fixed
- The extracted twinkle animator now shuffles candidate pixels with a hand-rolled
  Fisher-Yates: the app original used `random.shuffle`, which does not exist on
  CircuitPython — on hardware those animations silently fell back to a still image.
- Composed animators clean up already-started parts when a later part fails to
  start (previously the survivors' overlay layers leaked on the display).
- **OTA now surfaces real failure reasons instead of "up to date."** A failed check,
  download, or apply was reported to the app as "device is current," so an invalid
  published manifest could hide a fleet-wide outage behind a lie. `OTAProgressDisplay`
  records every outcome in `last_error` (cleared only after a successful stage); only
  the genuine `UP_TO_DATE` sentinel reads as "current," and an apply failure now paints
  an "Update / failed" frame on the panel instead of rebooting.
- **OTA apply is now a crash-safe transaction, with real-CircuitPython fixes** found
  live on a MatrixPortal S3: route checksums through `hashlib.new()` (no `sha256()` on
  device), drop `json.dumps(indent=…)` and the `IOError` name (neither exists on
  device), and replace `os.walk`/`os.makedirs` with `listdir`/`mkdir` helpers. Apply
  writes `APPLY_STARTED`/`BACKUP_COMPLETE` markers, backs up once per transaction,
  re-verifies each installed file, writes the `.version` commit marker last, and rolls
  back staging on failure so a bad payload can't reboot-loop. Manifest validation now
  rejects an unparseable version loudly and drops the unused mandatory `required` key
  that had rejected every published manifest.
- The WiFi setup portal now boots on-device and re-scrolls its instructions:
  `import socket` moved into the desktop-only branch (CircuitPython has no stdlib
  `socket`, so the eager import crashed the portal), and the one-line status panel
  restarts its scroll so the AP name, password, and URL can all be read.

## [0.8.3] - 2026-07-02

The post-0.8.2 review fixes (a 4-agent + 3-model-panel code review, then five
fix tranches) plus the restored WiFi onboarding feature. Note that some fixes
change behavior code may have relied on (`ContentQueue` priority/loop are now
real contracts, the OTA manifest script hooks are gone). First release
published to PyPI: a tag push now builds and uploads via GitHub Actions
Trusted Publishing (`.github/workflows/publish.yml`), and the wheel/sdist now
declare the simulator's BDF fonts and hardware-calibration JSONs as package
data (previously only reachable via editable/source installs).

### Added

- **WiFi onboarding portal restored** — configure Wi-Fi from a phone, no file
  editing (`scrollkit.web.wifi_setup.WiFiSetupPortal`, entry point
  `WiFiManager.run_setup_portal(display=...)`). The device starts its own
  access point, scrolls join instructions on the panel, serves a setup page
  (scanned networks with signal bars + manual SSID + password) at
  `http://192.168.4.1`, saves through the `SettingsManager` into
  `settings.json`, and reboots to connect. The original feature had been
  silently unwired since the settings-server rewrite and was then deleted as
  dead code; this is a redesign, not a revert. `start_access_point` /
  `stop_access_point` / `ap_ip_address` are back on `WiFiManager`.
  *Needs hardware verification (AP mode on a real board).*
- WiFi credentials now resolve **settings-first**: portal-saved
  `wifi_ssid`/`wifi_password` in `settings.json` beat a stale `secrets.py`.
- Recording (`start_recording`/`save_gif`/`save_video`), `screenshot()`, and
  the `hardware_timing`/`throttle`/`strict` feasibility flags are now on
  `UnifiedDisplay` (no-ops returning `None` on hardware) — no need to bypass
  the auto-detecting display to record or gate.
- `ContentQueue` honors the documented contracts it previously ignored:
  `priority` (higher plays first, stable within equal priority) and
  `loop=False` (queue exhausts after the last item; `add()` re-arms it).

### Fixed

- **Interstate 75 W was unusable by construction**: `UnifiedDisplay` reached
  the displayio display via `self.hardware.display`, which only exists on the
  S3's Matrix wrapper — every frame raised a swallowed `AttributeError` and
  the panel never refreshed. All paths now use `self.display`.
- **Corrupt `settings.json` no longer bricks boot**: CircuitPython raises
  `ValueError` for bad JSON; `load_settings` caught only `OSError`.
- **`set_pixel`/`fill` now work on hardware and on desktop `UnifiedDisplay`**
  (previously the particle system rendered only on `SimulatorDisplay`): both
  render through the paint-canvas displayio layer, survive refresh, and are
  feasibility-accounted.
- **`run_headless(strict=True)` now exercises transitions**: the harness
  drives the app's own `step_frame()` (new, shared with `_display_process`)
  instead of a hand-copied loop that skipped the transition path.
- `RainDrop`/`Snow` no longer hardcode a 32-px panel height; wrong
  `pip install sldk[simulator]` hints corrected to `scrollkit[simulator]`;
  urllib POST records success for `last_error` bookkeeping; `run_headless`
  restores `SDL_VIDEODRIVER` so later live-window runs aren't silently
  headless.

### Removed / Security

- **OTA manifest scripts**: `OTAClient.apply_update` `exec()`'d
  `pre/post_update_scripts` from the downloaded manifest — unsigned remote
  code execution that no publisher ever used. The whole surface is gone;
  legacy manifests carrying the (empty) keys still parse.
- `SimulatorDisplay` is now a thin subclass of `UnifiedDisplay` — one
  per-frame pipeline for hardware and simulator (its private
  `_overlay_pixels` mechanism and duplicated render loop are gone).
- Zero-reference orphans: `simulator.adafruit_display_text.scrolling_label`,
  `simulator.core.display_manager` (+ `BaseDevice.run`/`run_once`),
  `WiFiManager.disconnect`/`is_available`/`get_ip_address`, all `ColorUtils`
  static helpers, and `UpdateManifest`'s unused builder half.

## [0.8.2] - 2026-07-01

A pre-1.0 legacy-cleanup release: remove dead code and trap APIs, fix real bugs,
and lock down the public surface before a 1.0 freeze. Contains breaking removals
(pre-1.0 semver permits them); the one downstream app (ThemeParkWaits) is
migrated in lockstep.

### Removed

- The entire dead pre-consolidation display pipeline: `scrollkit.content_classes`,
  the top-level `scrollkit.content` shim, `scrollkit.display.strategy` (its
  `DisplayStrategy`/`StrategyRegistry`/`DisplayItem`/`*Strategy` classes),
  `scrollkit.display.queue` (`DisplayQueue`), and `scrollkit.display.manager`
  (`DisplayManager`). These had zero production consumers; `content_classes`'
  `create_*`/`example_usage()` were a *trap* (they built `DisplayItem`s the live
  `ContentQueue` never consumed). **`Priority` survives, relocated to
  `scrollkit.display.content`.**
- `scrollkit.app.minimal` (`MinimalLEDApp`) — disjoint from `ScrollKitApp`,
  nothing built on it, and its desktop fallback was broken.
- `scrollkit.ota.updater` (`OTAUpdater`) and `scrollkit.ota.server` (`OTAServer`)
  — unused duplicates of `ota.client` / `ota.publish`.
- Zero-importer orphans: `scrollkit.utils.timer`, `scrollkit.utils.image_processor`,
  `scrollkit.simulator.devices.generic_matrix`,
  `scrollkit.simulator.adafruit_display_text.bitmap_label`,
  `scrollkit.simulator.terminalio.font_scaler`.
- `wifi_manager`'s unused captive-portal web server, `_save_to_secrets_file`, the
  no-op `update_http_clients`, and the unreachable (shadowed) `is_connected()`
  method.
- `DisplayInterface.scroll_text` / `SimulatorDisplay.scroll_text` — no callers;
  silently no-op'd on hardware.
- Nine caught-but-never-raised / dead exception classes (see below).

### Changed / Renamed

- `scrollkit.display.gradient_text._GradientTextLayer` → public `GradientTextLayer`
  (old name kept as an alias through 0.9.x).
- Exception base `SLDKError` → `ScrollKitError` (old name kept as an alias). The
  hierarchy is collapsed to only what the library raises: `ScrollKitError`,
  `NetworkError`, `OTAError`, `FeasibilityError`. `DisplayError`, `ContentError`,
  `ConfigurationError`, `WebServerError`, `DeploymentError`, `SimulatorError`,
  `ResourceNotFoundError`, `UpdateError`, `ValidationError` are removed.
- `HttpClient.get` / `get_sync` / `post` now **raise `NetworkError`** when every
  retry fails, instead of returning a synthesized `500` response.
  `HttpClient.last_error` retains the raw underlying cause. `OTAClient` raises
  `NetworkError`/`OTAError` internally but preserves its public `(ok, reason)`
  tuple contract.
- `scrollkit.dev.performance.as_text` → `performance_text` (removes a name
  collision with `dev.capabilities.as_text`).
- `MinimalLEDApp.COLORS` → `scrollkit.utils.color_utils.NAMED_COLORS`.
- `scrollkit.effects` is now import-free: import each effect from its submodule
  (`effects.transitions`, `effects.reveal_splash`, `effects.particles`, …) — a
  no-splash app no longer loads the particle/splash modules just to use a
  transition. No plugin/registry was added.

### Fixed

- The settings web server no longer mutates display/queue state from the request
  handler; it sets a flag the display loop applies via the new
  `ScrollKitApp.notify_settings_changed()`.
- `HttpClient` platform detection imported a retired module
  (`display.display_factory.is_dev_mode`), silently always falling back to
  production mode; it now uses `network.wifi_manager.is_dev_mode`.
- Import-time side effects removed: `config.settings_manager`,
  `network.http_client`, and `network.wifi_manager` no longer construct an
  `ErrorHandler` (which write-tests the filesystem) merely on import.
- Two banned `json.JSONDecodeError` uses in `ota.client` / `ota.manifest` (would
  raise `AttributeError` on CircuitPython) → `ValueError`.

### Internal

- `__all__` added to every public module; a new `test/unit/docs/` gate executes
  every `import` shown in the README/docs so advertised APIs can't drift.
- Simulator device setup shared between `UnifiedDisplay` and `SimulatorDisplay`
  via `display/_sim_backend.py`.
- Device deploy (`make copy-to-circuitpy` / `make mpy`) now excludes the
  desktop-only `dev/` and `simulator/` trees and the host-only `ota/publish.py`.

### Migration

| Old | New |
|-----|-----|
| `from scrollkit.app.minimal import MinimalLEDApp` | `from scrollkit.app.base import ScrollKitApp` |
| `from scrollkit.content import ...` | `from scrollkit.display.content import ...` |
| `from scrollkit.display.strategy import Priority` | `from scrollkit.display.content import Priority` |
| `from scrollkit.display.queue import DisplayQueue` | `from scrollkit.display.content import ContentQueue` |
| `from scrollkit.display.gradient_text import _GradientTextLayer` | `... import GradientTextLayer` |
| `from scrollkit.effects import SwarmReveal` | `from scrollkit.effects.swarm_reveal import SwarmReveal` |
| `from scrollkit.exceptions import SLDKError` | `... import ScrollKitError` (alias still works) |
| `resp = await client.get(url)` then check `resp.status_code == 500` | `try: resp = await client.get(url)` / `except NetworkError:` |

## [0.8.1] - 2026-06-28

### Added

#### Reusable infrastructure (extracted up from ThemeParkWaits)

These were app-local; they are generic enough that every ScrollKit app should get
them for free. All are additive — defaults preserve prior behaviour.

- `scrollkit.utils.diagnostics` — NVM-backed boot/crash diagnostics with a
  reboot-loop safe-mode breaker. `diagnostics.open()` binds to `microcontroller.nvm`
  on device and returns a no-op store on desktop (no platform check needed); the
  store takes an injectable backend so the boot-loop logic is unit-tested with a
  plain `bytearray`.
- `scrollkit.network.mdns.advertise(hostname, *, port=80, service_type, protocol)`
  — non-blocking `<hostname>.local` advertising. Returns the `mdns.Server` (the
  caller MUST retain it — GC stops resolution) or `None` on desktop / no radio;
  never raises.
- `scrollkit.ota.display_progress.OTAProgressDisplay` — a display-progress +
  staged-install adapter around an existing `OTAClient` (renders the
  "Installing… DO NOT UNPLUG!" frame, applies, reboots). The client stays headless;
  the update source/channel remains the app's concern.
- `ScrollKitApp.suspend_render()` / `resume_render()` / `suspended_render()` context
  manager + `render_suspended` property — pause queue rendering (queue preserved)
  while painting an off-queue status frame and blocking on a fetch, without
  overriding `prepare_display_content()`. Default: not suspended.
- `BitmapText(complete_after_passes=N)` — frame-based one-pass completion so a
  scrolling banner can advance a `ContentQueue` without subclassing. Keyed on scroll
  POSITION, not wall-clock, so a low frame rate never cuts the text off mid-scroll;
  `start()` now rebuilds the layer so a banner is queue-safe when it cycles back.
  Default `None` keeps the persistent-banner behaviour.

## [0.8.0] - 2026-06-28

First public release: an LED-matrix display framework that runs unchanged on the
Adafruit MatrixPortal S3 (CircuitPython 8.x/9.x/10.x) and a desktop pygame simulator.

### Added

- Opt-in hardware watchdog on `ScrollKitApp` (`enable_watchdog`, `watchdog_timeout`,
  default 8s) that resets the board if the display loop freezes — e.g. a hung
  synchronous fetch — and self-recovers instead of sitting frozen until a power
  cycle. Hardware-validated on CP 9.2.7 and 10.2.1 (`test/claude/RELIABILITY_TESTING.md`).
- Data-refresh memory floor `MIN_FREE_FOR_UPDATE` (default 25000) with a
  force-after-N-skips guard, so a low-memory device can't serve stale data forever.
- `scrollkit.dev.capabilities()` now catalogs the built-in transitions and their
  per-frame feasibility budgets (and renders them in `as_text()`), so AI agents and
  contributors can discover what's available and its modeled cost.

### Changed

- Transition names now have a single source of truth
  (`scrollkit.config.transition_names.TRANSITION_NAMES`), kept in lockstep with the
  dispatch factory in `scrollkit.effects.transitions` by a unit test. Selecting a
  transition can no longer silently fall back to no transition, and an unknown saved
  `transition_style` is now logged instead of silently ignored.
- Field reliability: `HttpClient` default per-request `timeout` 10s → 6s (kept below
  the watchdog window); `ErrorHandler` no longer deletes or truncates the log on boot
  (crash evidence is preserved) and rotates with a tail-preserving trim instead of
  blanking it; PRODUCTION persists only errors to flash; `ErrorHandler` is now a real
  per-file singleton so a read-only-filesystem detection is shared across callers.

### Removed (breaking)

- **Effect-attachment API.** `DisplayItem.add_effect()` / `with_effect()`,
  `BaseContent.with_effect()` / `with_effects()`,
  `DisplayManager.add_item(..., effects=...)`, and the `DisplayQueue._apply_effects`
  render path have been removed. They drove the old `Effect.apply()` contract,
  which no longer exists — the surface was a no-op (and internally buggy), and a
  trap for AI-authored code. Visual variety now comes from the `Transition` system
  (the `transition_style` setting) and the standalone splash/particle helpers.
- The dead `Effect` / `EffectRegistry` / `CompositeEffect` base classes
  (`scrollkit.effects.base`), the `SimpleEffect` / `EffectsEngine` system and its
  concrete effects (`scrollkit.effects.effects`), and the orphaned
  `EnhancedDisplayContent` family (`scrollkit.display.enhanced_content`) — none were
  wired into the display loop, and the latter violated the library's own
  per-frame-allocation / no-per-pixel-loop feasibility rules.
