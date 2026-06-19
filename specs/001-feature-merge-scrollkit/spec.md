# Feature Specification: Merge ScrollKit Library and SLDK into a Single Unified Library

**Feature Branch**: `001-feature-merge-scrollkit`  
**Created**: 2026-06-18  
**Status**: Draft  

## Execution Flow (main)
```
1. Parse user description from Input
   → Merge two parallel LED matrix display frameworks into one
2. Extract key concepts from description
   → Actors: library developers, demo authors, future OSS users
   → Actions: merge module sets, preserve all capabilities, keep app layer separate
   → Data: display content, settings, OTA manifests, effects configurations
   → Constraints: CircuitPython 8.x/9.x compatibility, memory-constrained hardware
3. Ambiguities identified and marked below
4. User Scenarios & Testing defined
5. Functional Requirements generated — all testable
6. Key entities identified
7. Review checklist completed
```

---

## ⚡ Quick Guidelines
- ✅ Focus on WHAT users need and WHY
- ❌ Avoid HOW to implement (no tech stack, APIs, code structure)
- 👥 Written for business stakeholders, not developers

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
As a CircuitPython application developer building an LED matrix display application, I want a single `scrollkit` package that provides everything I need — display management, effects, content queuing, web configuration, and OTA updates — so I don't have to integrate two separate frameworks or navigate overlapping implementations.

As an open-source library user, I want clear tutorials and working demos showing how to build simple through complex LED matrix apps, so I can get started quickly and see the full capabilities of the library.

### Acceptance Scenarios

1. **Given** a developer using `scrollkit` on desktop, **When** they create a display or run an app (not merely `import scrollkit`), **Then** the simulator window opens and they can develop without hardware. Importing the package alone has no side effects.

2. **Given** the same application code, **When** deployed to a MatrixPortal S3, **Then** it runs on real hardware without modification.

3. **Given** a developer calling `scrollkit` display APIs, **When** they run on desktop, **Then** the SLDK-based simulator renders the same content and layout the hardware would show (functionally equivalent; exact color/timing fidelity is not required).

4. **Given** a developer using effects, **When** they request a transition or particle effect, **Then** it plays on both hardware and simulator.

5. **Given** an application using OTA updates, **When** a new version is available, **Then** the manifest-based update system downloads, validates, and installs it with rollback capability.

6. **Given** a developer running the demos directory, **When** they run any demo on desktop, **Then** the simulator displays the demo output without errors.

7. **Given** a developer reading the mkdocs documentation, **When** they follow the trivial tutorial, **Then** they have a working scrolling text app in under 10 minutes.

8. **Given** the merged `scrollkit` library, **When** it is imported with no application code present, **Then** it loads and the demos run successfully (the library stands on its own).

9. **Given** a memory-constrained MatrixPortal S3 device, **When** `gc.mem_free()` is sampled (after `gc.collect()`) immediately after `import scrollkit` and again after full app init, **Then** both readings are at or below the recorded pre-merge SLDK baseline.

10. **Given** a developer using the web configuration interface, **When** they update a setting, **Then** the change is reflected in the running display application without a restart.

### Edge Cases

- What happens when the device runs out of memory during effects processing? → Library degrades gracefully (disables effects, keeps display running).
- How does the library handle a failed OTA download mid-transfer? → Rollback to previous version; device keeps running.
- What happens if the simulator is not installed and code runs on desktop? → Clear error message directing user to install the simulator dependency.
- How does the content queue handle a full queue? → The lowest-priority, oldest non-SYSTEM item is evicted to admit a higher-priority item; an incoming item lower priority than everything present is rejected; SYSTEM-priority items are always accepted (evicting a non-SYSTEM item if needed).
- What happens if a demo's required hardware feature isn't available in simulator? → Demo reports which features are simulated vs skipped.

---

## Requirements *(mandatory)*

### Functional Requirements

**Display Management**
- **FR-001**: System MUST provide a single `scrollkit` package importable on both CircuitPython hardware and desktop Python environments.
- **FR-002**: System MUST auto-detect the runtime environment (CircuitPython hardware vs desktop) and initialize the appropriate display backend without developer intervention.
- **FR-003**: System MUST provide a display interface that supports: set pixel, fill, draw text, show, clear, and set brightness operations.
- **FR-004**: System MUST support 64×32 pixel LED matrix display (MatrixPortal S3 native resolution).

**Content & Queuing**
- **FR-005**: System MUST provide a content queue that accepts text and display content with configurable priorities.
- **FR-006**: System MUST support at least these priority levels: idle, normal, high, system.
- **FR-007**: System MUST support duration-aware content that automatically expires after a specified time.
- **FR-007a**: When the queue is full, the system MUST evict the lowest-priority, oldest non-SYSTEM item to admit a higher-priority item; MUST reject an item lower priority than all present items; and MUST always admit SYSTEM-priority items.
- **FR-008**: System MUST support scrolling text content type.
- **FR-009**: System MUST support static text content type.

**Effects & Animations**
- **FR-010**: System MUST provide an effects engine supporting at least: fade transitions, slide transitions, and particle effects.
- **FR-011**: System MUST limit concurrent active effects to a configurable maximum (default: 2) to stay within memory constraints.
- **FR-012**: Effects MUST run with functionally equivalent behavior on hardware and simulator (same effect types and sequencing; exact pixel/timing fidelity not required).

**Simulator (Desktop Development)**
- **FR-013**: System MUST provide a desktop simulator that visually renders the LED matrix display using the SLDK pygame-based simulator.
- **FR-014**: The simulator MUST emulate the CircuitPython `displayio` API so that application code is identical between hardware and simulator.
- **FR-015**: The simulator MUST support the same font files (BDF format) used by the hardware.

**Web Interface**
- **FR-016**: System MUST provide a web server component accessible from a browser on the local network.
- **FR-017**: The web interface MUST allow reading and updating display settings while the application is running.
- **FR-018**: The web server MUST run on CircuitPython (adafruit_httpserver) and desktop (async HTTP) without code changes in application layer.
- **FR-019**: The web interface MUST be strictly a configuration UI — it runs on the LED device itself, so no display preview is needed or appropriate.

**OTA Updates**
- **FR-020**: System MUST support over-the-air firmware updates using a manifest-based system (from SLDK).
- **FR-021**: The OTA recovery guarantee MUST rest on the immutable `boot.py` and update system — frozen outside `/src` and never modified by OTA. Because they stay intact regardless of any `/src` payload failure, the update system can always re-fetch a known-good version. The library MUST additionally retain the previous `/src` version (backup) so a validated update that later proves bad can be restored. The library MUST NOT require modifying `boot.py` or `code.py` to achieve recovery.
- **FR-022**: OTA MUST validate checksums before applying an update.
- **FR-023**: OTA updates MUST pull firmware from GitHub (releases or a versioned branch). The update mechanism MUST describe what files are at what versions so the device can selectively download only changed files.

**Configuration**
- **FR-024**: System MUST provide a settings manager that persists configuration to the filesystem.
- **FR-025**: Settings MUST be readable and writable while the application is running.
- **FR-026**: Settings MUST survive device reboot.

**Networking**
- **FR-027**: System MUST provide a WiFi manager for connecting to networks on CircuitPython.
- **FR-028**: System MUST provide an HTTP client for making requests from the device.
- **FR-029**: The HTTP client MUST expose a consistent API across platforms, but MUST NOT promise transparent async on CircuitPython — there, `adafruit_requests` calls block the event loop. The application framework MUST render a static/loading frame before yielding to a blocking network call, and long transfers (e.g. OTA downloads) MUST be chunked with cooperative yields (`await asyncio.sleep(0)`) wherever the underlying library allows.

**Application Framework**
- **FR-030**: System MUST provide a minimal base application class (`MinimalLEDApp` or equivalent) for simple use cases with low memory footprint.
- **FR-031**: System MUST provide a full-featured base application class (`SLDKApp` or equivalent) for complex applications needing web server, effects, and data updates.
- **FR-032**: The full-featured app class MUST support cooperative multitasking for concurrent display, data refresh, and web server operation.

**Utilities**
- **FR-033**: System MUST provide color utility functions (RGB/hex conversion).
- **FR-034**: System MUST provide an error handler with file-based logging.
- **FR-035**: System MUST provide timing utility functions.

**Documentation**
- **FR-036**: Documentation MUST be built with mkdocs and cover all major modules.
- **FR-037**: Documentation MUST include an easy tutorial (scrolling text in < 10 lines, no network).
- **FR-038**: Documentation MUST include a medium tutorial (live data from a public no-API-key source — e.g. current temperature via open-meteo — scrolled across the display with periodic refresh).
- **FR-039**: Documentation MUST include a hard tutorial (full app: web config, priority queue, effects, multiple public data sources, OTA, and the chunked-fetch technique in FR-042b).
- **FR-040**: Documentation MUST include API reference for all public classes and functions.

**Demos**
- **FR-041**: The `demos/` directory MUST be organized into three complexity levels — `demos/easy/`, `demos/medium/`, `demos/hard/` — each runnable on desktop against the simulated scrolling LED hardware, with no physical device required.
- **FR-042**: Demos MUST collectively cover: basic scrolling text (easy); live public data scrolled with periodic refresh (medium); and a full app with content-queue prioritization, effects/transitions, and web configuration (hard).
- **FR-042a**: Data-driven demos MUST use public data sources that require no API key (e.g. open-meteo for temperature, CoinGecko for crypto prices). Sources requiring a key (most stock-price APIs) MUST NOT be required to run a demo.
- **FR-042b**: The hard demo MUST illustrate the workaround for CircuitPython's blocking (synchronous) HTTP library: when fetching many items (e.g. prices for a list of tickers), it MUST split the work into sizable chunks — one short blocking request per chunk — and yield to the event loop (`await asyncio.sleep(0)`) between chunks, so the scrolling display does not freeze. The demo MUST be commented to explain the trade-off (slower overall, but no screen lock-up).
- **FR-043**: Each demo MUST include a brief comment header explaining what it demonstrates and which data source (if any) it uses.

**Application Separation**
- **FR-044**: The `scrollkit` library MUST be self-contained and stand on its own — its demos, not any external application, are the demonstration vehicle. Porting the existing ThemeParkWaits application is explicitly OUT OF SCOPE for this work (see Out of Scope).
- **FR-045**: The `scrollkit` library MUST be importable and runnable with no application code present.

**Memory Constraints**
- **FR-046**: Library initialization on CircuitPython MUST use the same or less memory than the pre-merge SLDK baseline. This MUST be verified by a repeatable protocol: run `gc.collect()` then record `gc.mem_free()` (a) immediately after `import scrollkit` and (b) after full app init; both readings MUST be ≤ the recorded SLDK baseline at the same checkpoints. A committed baseline file is the acceptance gate.
- **FR-047**: System MUST support graceful feature degradation when available memory is below a threshold (e.g., disable effects engine, disable web server).

### Out of Scope
- **Porting the ThemeParkWaits application** to the merged library. ThemeParkWaits remains in `src/` untouched; making it run on the merged `scrollkit` is a separate, later effort. This project delivers a standalone library plus demos.
- Any feature requiring an API key or paid data source in a demo.

### Deferred Polish *(handle last, after the merge works)*
- `.mpy` cross-compilation pipeline (`mpy-cross`) and `circup` dependency workflow.
- Optional PCF font track (BDF parity is the requirement; PCF is a later memory optimization).
- OTA pre/post-update script trust model (enabled vs sandboxed vs disabled-by-default on hardware).

### Key Entities *(include if feature involves data)*

- **DisplayContent**: A unit of content to be shown on the display. Has type (static/scrolling/custom), text/data payload, duration, and priority.
- **DisplayQueue**: An ordered collection of DisplayContent items, sorted by priority. Has capacity limits and expiration handling.
- **Effect**: A timed visual transformation (transition, particle burst, etc.) that runs alongside content display. Has type, duration, and memory cost.
- **OTAManifest**: Metadata describing a firmware release — version, checksums, download URL, and rollback pointer.
- **Settings**: A key-value store persisted to filesystem. Keys are namespaced by subsystem.
- **WebRequest / WebResponse**: HTTP request/response pair processed by the web server component.

---

## Review & Acceptance Checklist

### Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

### Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous (where not marked)
- [x] Success criteria are measurable
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

---

## Execution Status

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked and resolved
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified
- [x] Review checklist passed

---
