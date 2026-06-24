# ScrollKit Studio — `/specify` Input (Original Source)

**Created**: 2026-06-22
**Updated**: 2026-06-24 — AI conversational authoring promoted to the primary
interface; added the explicit interaction model (simulator hero + chat box +
effects/transitions GUI); added the first-run onboarding hook (living default demo +
active controls + AI greeting; no blank canvas). Made explicit that the AI can wholly
rewrite the entire running app; the starter demo is a disposable seed, not a template.
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
- **AI is now on the MVP critical path.** The primary authoring interface is a
  conversation with an AI that designs and codes the app, verified live against the
  simulator + device model. This is more on-thesis (the verifier loop is the
  centerpiece) but a bigger/riskier build than a forms-first MVP. The
  **effects/transitions GUI doubles as a non-AI authoring fallback** so users aren't
  dead in the water if the AI struggles on a given request — keep that property.
- The description is intentionally **WHAT/WHY only**, including the user-facing
  interaction model. The HOW — simulator-in-browser runtime (e.g. Pyodide vs.
  server-rendered), how the AI generates/validates code, browser-to-device transport
  (e.g. WebSerial), frontend stack, and the flagship-repo decision — is deliberately
  left for `/plan`.
- The GUI directly controls **color and transition/effect** on the live design
  (confirmed). Residual open question for `/specify` to surface as
  `[NEEDS CLARIFICATION]`: whether the GUI also offers **direct message-text editing**,
  or whether message content is always authored via the AI. Also still open: the
  **enclosure source** and the **sharing/persistence model**.

---

## `/specify` input (verbatim — this is the text to paste)

Build "ScrollKit Studio" (working name): a website where a non-programmer designs a
custom scrolling LED-matrix sign by talking to an AI and watching it run live in a
simulator, then builds and deploys it to real Adafruit hardware — with no coding and
no toolchain setup. It is the companion showcase site for the ScrollKit library: the
same display code a user designs in the browser runs unchanged on the device. The
first supported configuration is the Adafruit MatrixPortal S3 driving a 64x32 RGB LED
matrix.

WHY: Today, building a custom LED scroller requires installing CircuitPython,
gathering libraries, writing Python, and knowing the board's RAM and speed limits — a
wall for non-programmers. Worse, you cannot tell whether a design will actually run
until you flash it. ScrollKit already ships a simulator and a performance model
calibrated from a real MatrixPortal S3; this product brings both into the browser and
lets anyone design a sign just by describing what they want, see it running
immediately, verify it against real hardware limits, and deploy it — without owning
hardware to start, and without a terminal to finish.

PRIMARY INTERACTION MODEL (what the user sees and does):
- The app opens in a living, pre-populated state — never a blank canvas. On load the
  simulator is already playing a default scrolling message, the GUI controls are
  active, and the AI box shows a welcoming prompt, so the user is invited to poke at
  something that already works rather than face an empty display and an empty text box.
- A mock-up of the LED display — the live in-browser simulator — is the centerpiece,
  shown prominently at the top.
- Directly beneath it is a text/conversation input box. The user describes the sign
  they want, and the AI designs and codes the app in response. This conversational
  loop is the primary way the user builds and refines their sign, and the AI can
  completely and totally rewrite the entire app running in the simulator — not just
  tweak it. The starting demo is only a seed to get the ball rolling, never a template
  that limits what can be built.
- Beside the simulator and chat is a compact GUI control panel for picking colors and
  applying transitions and effects to the current design — for first-touch enticement,
  for users who would rather click than type, and to refine what the AI produced.
- Every design — whether produced by the AI or chosen in the GUI — renders live in
  the simulator so the user immediately sees the result.

PRIMARY USERS:
- A non-programmer maker / Adafruit customer who wants a custom scrolling sign (store
  hours, sports scores, a name badge, a message board) but is intimidated by code and
  the toolchain.
- A curious visitor with no hardware who wants to try designing a sign in seconds and
  may then buy the parts.

SCOPE DISCIPLINE: The first release supports ONE golden path end to end, polished: one
board (MatrixPortal S3), one panel (64x32), one printable enclosure, the
conversational-design-plus-live-simulator experience with the effects/transitions GUI
as the core authoring surface, and working browser-to-device deploy. Additional
boards, panel sizes, and authoring modes are explicitly deferred.

USER JOURNEYS, in suggested priority order:

P1 - Land into a living demo, not a blank canvas (the onboarding hook). On load, the
simulator is already animating a default scrolling message; the GUI controls (color,
transition, effect) are immediately usable and change that demo instantly; and the AI
text box opens with a friendly invitation (for example, "Let's design a scrolling
app"). The user learns the interaction by clicking and seeing instant change before
any commitment to typing. There is never a blank display or a blank text box: the
pre-populated, responsive starting state is what entices the user to begin. Once the
user has the feel of it (clicked a color, saw it change), the AI prompts them to
modify what is there or create something wholly new.

P1 - Design by describing it, and watch it run. The user types what they want
("scroll our store hours in blue, then show the time") into the text box beneath the
LED mock-up; the AI designs and codes the app; it runs immediately in the in-browser
simulator so the user sees it — and an AI design can completely and totally rewrite
the entire app running in the simulator, not merely adjust the starter (which is just
a seed to get going). The AI escalates the user along: after they have played with the direct
controls, it invites them to either modify what is on screen or create something
wholly new. The user refines through continued conversation. No hardware, account, or
install is needed to start. This is the core value and the experience strangers will
share.

P1 - Trustworthy by construction (the verifier loop). Every app the AI produces is run
through the simulator and the device-calibrated feasibility model before it is shown,
so the user only ever sees a design that actually renders and provably fits the target
board. The app continuously shows a clear hardware verdict — estimated frame rate, RAM
headroom, and a go / caution / over-budget reading — and can play the preview at true
modeled device speed so the user feels the real hardware before committing. A design
that will not fit is flagged with the specific reason and a concrete fix, which the AI
can then apply. Creativity comes from the AI; correctness comes from the
device-calibrated oracle.

P1 - Direct controls: colors, transitions, and effects. A compact GUI beside the
simulator lets the user pick colors and browse ScrollKit's transitions and effects
(characterful scrolling, theatrical transitions, palette-animated bitmap text) and
apply them to the current design, seeing the change live. These controls serve three
roles: the first-touch enticement on the default demo (click a color, watch it
change), a click-don't-type authoring path, and a way to refine AI output.

P2 - Deploy to the device from the browser, zero toolchain. A user who owns the
hardware connects the board over USB and, from the web page, installs the generated
code and assets directly onto the device — no terminal, no manual library wrangling,
no separate software to install. A downloadable project bundle is offered as a
fallback for users who prefer to copy files themselves.

P2 - Get everything needed to build the physical unit. The site provides a curated
parts list with direct links to the Adafruit products, a 3D-printable enclosure
(downloadable model plus print settings), and a step-by-step assembly guide, so a
beginner can go from nothing to a finished, running sign.

P3 - Save, share, and remix. A user can save a creation, share it via a link, and
start from someone else's design as a template, forming a small gallery of examples.

KEY CONSTRAINTS:
- The core experience — describe a sign, watch it run in the simulator, adjust effects
  — MUST be tryable instantly in a browser with no hardware, no account, and no
  install.
- The AI MUST be able to generate a complete, new app that wholly replaces whatever is
  currently running in the simulator — full authorship, not parameter tweaks on a
  fixed template. The starter demo is a disposable seed; nothing about it constrains
  what the AI can build, and the simulator MUST hot-swap to and run the AI's new app.
- Every app the AI generates MUST be validated against the simulator and the
  device-calibrated feasibility model before it is shown to the user; the user never
  sees a design that fails to render or cannot run on the target board.
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
- A cloud-locked or server-rendered architecture, or user accounts beyond what sharing
  requires.
- The project's build-rationale write-up, which lives on the author's personal site
  and is only linked from the app.

SUCCESS CRITERIA (measurable, technology-agnostic):
- A first-time visitor changes something on the display (for example a color or a
  transition) within the first few seconds, without instructions — the living default
  state successfully entices interaction.
- A first-time visitor with no hardware can describe a sign in plain English and watch
  it running in the simulator within about 60 seconds of landing, with no install and
  no sign-up.
- For a typical request, the AI's design renders and passes the hardware-feasibility
  gate without the user having to manually fix it.
- A user who owns the supported hardware can go from the landing page to code running
  on their physical device in under about 20 minutes without ever opening a terminal.
- The feasibility verdict's predictions (will run / will not run, approximate frame
  rate) match what the design actually does on a real MatrixPortal S3.
- Every design the app lets a user deploy runs on the device with no manual fixes.
- A natural-language request never returns a design that fails on the hardware; it is
  repaired or rejected before being shown.
</content>
