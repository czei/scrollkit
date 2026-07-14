# Continuation: the ScrollKit teaser showcase + character-animation tutorial

## The task

Build a scrolling demo app for the ScrollKit library, very much like the
DarkOwl logo app, that demos AS MANY of the library's effects as possible,
mixed up act by act — a teaser reel that makes people want to use the
library. The per-effect reference GIFs already serve as tutorials and give
each effect its name; this demo is the "wow" loop. Borrow the flying owl
from DarkOwl and/or create new animated characters that inspire people.
Second deliverable: there is NO tutorial on creating animated characters —
write one (docs/guide page) using the demo's characters as the worked
example.

## Where everything lives

- **ScrollKit library**: `~/Documents/Projects/ScrollKit/ScrollKit Library`
  (source `src/scrollkit/`, remote `scrollkit` = github.com/czei/scrollkit,
  branch `master`). READ `CLAUDE.md` and `AGENTS.md` there first — they carry
  the CircuitPython compatibility table, the 50ms/20fps device budget, the
  per-op cost cheat-sheet, and the release process. v0.9.0 is on PyPI; docs
  live at scrollkit.dev (`make deploy-docs` rsyncs the MkDocs build).
- **DarkOwl app** (the model to imitate): `~/Documents/Projects/darkowl-led-logo`
  (private repo czei/darkowl-led-logo, branch `main`). READ its `CLAUDE.md`.
  Note: its latest commit `bb90097` (consuming ScrollKit 0.9.0) is committed
  but NOT pushed, and the physical MatrixPortal S3 has NOT been redeployed —
  when the board is next connected, `scripts/deploy.sh` ships the migrated
  app + scrollkit 0.9.0 and prunes the stale on-device `palette_fx.py`.
- Demos live in `demos/{easy,medium,hard}/`; the gallery generator is
  `demos/render_reference.py` (`make docs-reference`); GIF capture for demos
  is `demos/render_gifs.py`-style via the built-in recorder ONLY
  (`display.start_recording` / `save_gif` / `save_video` / `screenshot`).

## What the library now has (0.9.0 — promoted from DarkOwl this week)

All CircuitPython-safe, all frame-driven (`step()` / `is_complete` /
`detach()`), all carrying class-attr `FEASIBILITY`:

- `scrollkit.effects.palette_partition` — `PalettePartition(gfx, pixel_slots,
  group_map, n, identity_colors=())` (indexed layer animated purely by
  palette writes; identity slots survive every treatment) + 10 builders:
  `map_diagonal, map_anchor_distance, map_radial, map_angle, map_rain,
  map_checker, map_exposure, map_regions, map_topology, map_route` +
  `bfs_paths`.
- `scrollkit.effects.palette_treatments` — 13 dwell treatments taking a
  5-stop theme `(base, dim, flat, warm, hot)`, starting/ending at `flat`:
  `VelvetSweep, AnchorWake, HaloPulse, SonarSweep, CipherRain, InkShimmer,
  RimLight, HeatmapDrift, EclipseCross, GradientDwell(lo, hi),
  StrokeAnatomy, RouteCircuit(routes), PacketTrace(paths, runs)` (PacketTrace
  owns sprites: `start(display)`/`detach()`). After each `step()`,
  `blink_now` marks the frames where the caller should blink identity slots
  instead of presenting. Registry `TREATMENT_CLASSES`, selector
  `treatments_for(partition)`.
- `scrollkit.effects.swirl_in.SwirlIn(entries)` — entries are
  `(tile, tx, ty, w, h)`; sprites spiral in onto exact targets.
- `SwarmReveal` — now takes `pixel_colors={(x,y): rgb}` or `text_colors` +
  `index_map` (true-color), and `reverse=True` (carry-away).
- `scrollkit.utils.scheduler.ActScheduler` — `pick(deck, key, avoid=(),
  force=None)`; deck entries `(name, family, payload)`; weighted-age
  `(age+1)^2`, new entries lead, no family in `avoid` repeats. This is what
  keeps a 24/7 loop from ever feeling repetitive.
- Everything older: 13 named transitions (`transition_factory`,
  `_TRANSITION_MAP`), `DripReveal`, `show_reveal_splash`, `SwarmReveal`,
  scrollers (`KineticMarquee, WaveRider, SplitFlap`), bitmap-text palette
  effects (`RainbowChase, MonoChase, NeonTubeCrawl, ChromeSheen,
  HazardStripes`), particles (`Sparkle, Snow, Ember`), 14 image animators
  (`ANIMATOR_CLASSES`), easing tables, `pixels_from_text` /
  `pixels_from_font_text`.

## The model to imitate: how DarkOwl is structured

`darkowl_logo.py`: acts = build → dwell (1-2 treatments) → exit, every act
family-tagged, drawn by ActScheduler so nothing similar plays twice in an
act or across adjacent acts; special acts fire ~14% and never consecutively;
a forced opener plays first after boot (`force=` in the scheduler); the big
owl flies between acts ~40% of the time so the panel is never dead. The
treatment driver pattern:

    t = VelvetSweep(fx, THEME)
    while not t.is_complete:
        t.step()
        if t.blink_now: await my_blink(fx)
        else:           await self._frame()   # show() + sleep(0.05)

Character sprites are ASCII rows in `glyphs.py` (chars map to palette
slots; `.#ow` = transparent/red/amber/white, plus dedicated plumage slots
so effects can never recolor the character). The small flying owl has 2
wing poses (`_fly_pose` alternates every 3 frames); the BIG owl has 3
poses cycled UP→MID→DOWN→MID every 2 frames (`_big_pose`) — a true cel
flap. `_mirror()` flips rows for direction changes (index loops, NOT
`[::-1]` — CircuitPython has no extended slices). The hunt act
(rodent scurry → owl stoop → grab → carry off → letters SwirlIn → owl
returns) is the strongest character moment — steal its beats.

## Deliverable 1: the showcase demo

- New self-driving app in the ScrollKit repo (suggest
  `demos/hard/showcase_reel.py`, library-only imports, CircuitPython-safe,
  runs unchanged on device + simulator). Word suggestion: the mark is
  "SCROLLKIT" or per-act words naming the effect being shown — remember the
  brief: the demo should NAME the effects as it plays them (a small label,
  or one word per act that IS the effect's name — e.g. the swarm assembles
  "SWARM", velvet sweeps across "VELVET") so it teaches while it teases.
- Mix maximally: every transition as build/exit, every treatment as dwell,
  splashes, swirl, both swarm directions, scrollers and bitmap-text palette
  effects between acts, particles as garnish, ActScheduler for variety with
  family tags (copy DarkOwl's family taxonomy: letters/swarm/fall/wall/
  sweep/radial/texture/bands/route/layered/collapse).
- Character(s): borrow the DarkOwl flying owl art (copy the ASCII rows —
  the darkowl repo is private, the library repo is public; copying the owl
  art in is fine per Michael) and/or design new mascots (a bee for the
  swarm? a raindrop?). Characters cross between acts like the owl does.
- Verify per house rules: headless smoke (recorder capture pattern in
  darkowl's preview.py / demos/render_reference.py `_capture_self_driving`),
  extract FULL-SIZE frames to judge (never downscaled contact sheets —
  the LED dot grid aliases), `SCROLLKIT_HW_SIM=1` feasibility must show no
  warnings, swarms ≤ ~20 birds.
- Render a GIF/MP4 of the reel for the docs/README (recorder only, fps=20
  for true speed — save_video defaults to 24 and plays fast).

## Deliverable 2: the character-animation tutorial

New `docs/guide/character-animation.md` (+ mkdocs.yml nav): how to build an
animated character from ASCII-row pixel art — sprite-to-TileGrid, palette
slot conventions, pose cycling (2-pose flap vs 3-pose cel cycle), mirroring
for direction, movement with easing (`_ease_out`-style cubic), flight arcs
(the owl's stoop is `y = ease_in` dive + `ease_out` climb), carrying props
(the rodent rides at a talon offset), and the feasibility rules (prebuilt
tiles + moves are cheap; per-pixel loops are not). Use the showcase demo's
character code as the living example; include rendered GIFs. Wire any new
sample into `demos/render_reference.py` + `test_reference_coverage.py` if
you add a gallery category — they gate each other.

## House rules that bit us this session (don't relearn them)

- CircuitPython: no `os.path`, no extended slices (`[::2]`, `[::-1]`), no
  `random.shuffle` (Fisher-Yates idiom in transitions.py), no runtime
  typing; FEASIBILITY/PAIRS_WITH must be CLASS attributes.
- `effects/__init__.py` stays import-free; update the lazy-import guard
  lists in `test_lazy_effects.py` + `test_transition_registry.py` if you add
  effect modules.
- Gate every ScrollKit change with `make test-unit` && `make lint-errors`.
- The sim Palette stores RGB565 — tests comparing palette read-backs must
  convert via `rgb888_to_rgb565`.
- Docs tables: samples go INSIDE the Motion/Animation column at native
  300px above the description text (Michael's requested style, applied to
  transitions.md and bitmap-text.md this session).
- Commit per approved batch; hold pushes until Michael says push. Commits
  end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Open items carried over

- darkowl `bb90097` unpushed; board redeploy pending (needs the box
  plugged in; then `scripts/deploy.sh` + serial check
  `screen /dev/cu.usbmodem* 115200`).
- The five bitmap-text palette sample GIFs scroll their text off-panel for
  part of their loop (pre-existing renders); consider re-rendering with
  stationary text while touching the gallery.
