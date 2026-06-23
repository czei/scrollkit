# ScrollKit Studio — `/specify` Input (Original Source)

**Created**: 2026-06-22
**Status**: Draft input for GitHub Spec Kit `speckit.specify`
**Suggested feature name**: `scrollkit-studio` (Spec Kit will auto-number, e.g. `003-scrollkit-studio`)

## What this file is

This is the **original, authoritative natural-language feature description** that is
fed to `speckit.specify` to generate the formal `specs/00N-scrollkit-studio/spec.md`.
It is stored here in `plans/` (outside the Spec Kit `specs/` tree) so an original
version exists independent of the Spec Kit environment, in case the generated spec is
regenerated, edited, or lost.

**Scope notes for the maintainer (not part of the `/specify` input):**

- This describes the **product** (the showcase web app), not the job-search rationale.
  The build-rationale / "verifier-not-generator" thesis essay lives on the author's
  personal site (czei.org) and is only *linked* from the app — by design.
- The description is intentionally **WHAT/WHY only**. The HOW — simulator-in-browser
  runtime (e.g. Pyodide vs. server-rendered), browser-to-device transport (e.g.
  WebSerial), frontend stack, and the flagship-repo decision — is deliberately left
  for `/plan`.
- Expect `/specify` to surface `[NEEDS CLARIFICATION]` markers around the **enclosure
  source** and the **sharing/persistence model**; those were left open on purpose
  rather than inventing answers.

---

## `/specify` input (verbatim — this is the text to paste)

Build "ScrollKit Studio" (working name): a web application that takes a complete
beginner from idea to a physically running LED scrolling sign, with no coding and
no toolchain setup, targeting Adafruit hardware. It is the companion showcase site
for the ScrollKit library — the same display code a user designs in the browser
runs unchanged on the device. The first supported configuration is the Adafruit
MatrixPortal S3 driving a 64x32 RGB LED matrix.

WHY: Today, building a custom LED scroller requires installing CircuitPython,
gathering libraries, writing Python, and knowing the board's RAM and speed limits —
a wall for non-programmers. Worse, you cannot tell whether a design will actually
run until you flash it. ScrollKit already ships a simulator and a performance model
calibrated from a real MatrixPortal S3; this product brings both into the browser so
anyone can design a sign, verify it against real hardware limits, and deploy it —
without owning hardware to start, and without a terminal to finish.

PRIMARY USERS:
- A non-programmer maker / Adafruit customer who wants a custom scrolling sign
  (store hours, sports scores, a name badge, a message board) but is intimidated by
  code and the toolchain.
- A curious visitor with no hardware who wants to try designing a sign in seconds
  and may then buy the parts.

SCOPE DISCIPLINE: The first release supports ONE golden path end to end, polished:
one board (MatrixPortal S3), one panel (64x32), one printable enclosure, one guided
authoring mode, and working browser-to-device deploy. Additional boards, panel
sizes, and authoring modes are explicitly deferred.

USER JOURNEYS, in suggested priority order:

P1 - Design and preview in the browser, no hardware required. A visitor composes a
scrolling display using guided forms (pick content type, text, colors, speed,
layout — never raw code) and watches it render live in an accurate in-browser
simulator that needs no physical device. They can try it within seconds with no
sign-up and no install. This is the core value and the experience strangers will
share.

P1 - Know it will run: an honest hardware-feasibility verdict. As the user designs,
the app continuously shows whether the design will actually run on the target board —
estimated frame rate, RAM headroom, and a clear go / caution / over-budget verdict —
using the device-calibrated model, and can optionally play the preview at true
modeled device speed so the user feels the real hardware before committing. A design
that will not fit is flagged with the specific reason and a concrete fix.

P2 - Deploy to the device from the browser, zero toolchain. A user who owns the
hardware connects the board over USB and, from the web page, installs the generated
code and assets directly onto the device — no terminal, no manual library wrangling,
no separate software to install. A downloadable project bundle is offered as a
fallback for users who prefer to copy files themselves.

P2 - Get everything needed to build the physical unit. The site provides a curated
parts list with direct links to the Adafruit products, a 3D-printable enclosure
(downloadable model plus print settings), and a step-by-step assembly guide, so a
beginner can go from nothing to a finished, running sign.

P3 - Describe it in plain English. The user types what they want ("scroll our store
hours in blue, then show the time") and the app generates the design for them — but
every generated result is automatically checked against the feasibility model and
validator before it is shown, so the user only ever receives something that provably
runs on the hardware. Creativity comes from the model; correctness comes from the
device-calibrated oracle.

P3 - Save, share, and remix. A user can save a creation, share it via a link, and
start from someone else's design as a template, forming a small gallery of examples.

KEY CONSTRAINTS:
- The core design-and-preview experience MUST be tryable instantly in a browser with
  no hardware, no account, and no install.
- Code a user designs MUST run unchanged on the real device: a single shared display
  implementation, and the simulator must match reported hardware behavior.
- Hardware-only target is Adafruit / CircuitPython; the first supported setup is the
  MatrixPortal S3 plus a 64x32 panel. Generated code MUST be CircuitPython
  8.x/9.x-compatible.
- The feasibility verdict MUST reflect the real device's measured limits, not desktop
  performance.

NON-GOALS (explicit):
- Supporting non-Adafruit hardware.
- Becoming a general-purpose LED/sign tool that competes with WLED, MakeCode, or
  Tidbyt.
- Arbitrary panel sizes or boards beyond the supported set in v1.
- A cloud-locked or server-rendered architecture, or user accounts beyond what
  sharing requires.
- The project's build-rationale write-up, which lives on the author's personal site
  and is only linked from the app.

SUCCESS CRITERIA (measurable, technology-agnostic):
- A first-time visitor with no hardware can design and see a live preview of a custom
  scroller within about 60 seconds of landing, with no install and no sign-up.
- A user who owns the supported hardware can go from the landing page to code running
  on their physical device in under about 20 minutes without ever opening a terminal.
- The feasibility verdict's predictions (will run / will not run, approximate frame
  rate) match what the design actually does on a real MatrixPortal S3.
- Every design the app lets a user deploy runs on the device with no manual fixes.
- A natural-language request never returns a design that fails on the hardware; it is
  repaired or rejected before being shown.
</content>
</invoke>
