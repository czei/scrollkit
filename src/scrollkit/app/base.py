# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Base application class for SLDK.

Provides the three-process architecture with graceful degradation for ESP32.
"""

from __future__ import annotations

import asyncio


def create_task(coro):
    """Schedule a coroutine as a Task.

    MUST be a plain function (not ``async def``): ``run()`` does
    ``tasks.append(create_task(...))`` and then ``await gather(*tasks)``. If this
    were ``async def`` it would return a coroutine, ``gather`` would await the
    wrapper (which spawns a detached task and returns instantly), and ``run()``
    would fall straight through to its ``finally`` — killing the display loop
    after a single frame. Works on desktop and CircuitPython asyncio.
    """
    return asyncio.create_task(coro)


async def gather(*aws, return_exceptions=False):
    return await asyncio.gather(*aws, return_exceptions=return_exceptions)


async def sleep(seconds):
    await asyncio.sleep(seconds)

import gc
try:
    from typing import Optional, List
except ImportError:  # CircuitPython has no 'typing' module
    pass
from ..display.content import ContentQueue
from ..display.interface import DisplayInterface
from .memory import free_memory


class _SuspendRender:
    """Sync context manager for SLDKApp.suspended_render(): suspend on enter,
    always resume on exit (even if the wrapped block raises)."""

    def __init__(self, app):
        self._app = app

    def __enter__(self):
        self._app.suspend_render()
        return self._app

    def __exit__(self, exc_type, exc, tb):
        self._app.resume_render()
        return False


class SLDKApp:
    """Base class for SLDK applications.
    
    Implements three-process architecture:
    1. Display process - Always runs
    2. Data update process - Runs if memory allows
    3. Web server process - Optional, runs if memory allows
    """
    
    # Skip a data refresh below this much free heap (the synchronous JSON parse
    # spikes memory; starting one with too little headroom OOM-crashes the device
    # to black). Skipping a cycle shows last-good data instead — far better than a
    # crash. On a ~160 KB device running the web server + display, a 50 KB floor is
    # unreachable, so refreshes would be skipped forever (permanently stale); 25 KB
    # is reachable while still leaving parse headroom (a too-low parse now fails
    # gracefully rather than OOMing, so a high floor isn't needed). Tunable; the app
    # can lower it or use the free_mem_before_parse breadcrumb to calibrate.
    MIN_FREE_FOR_UPDATE = 25000

    # Force a refresh attempt after this many consecutive low-memory skips, so a
    # device that never quite clears MIN_FREE_FOR_UPDATE can't serve stale data
    # forever. The forced parse fails gracefully if there genuinely isn't room.
    MAX_LOW_MEM_SKIPS = 5

    # Last-resort auto-reboot: after this many CONSECUTIVE failed data refreshes
    # (reported via note_refresh_result), reboot to clear a wedged radio/HTTP
    # session. Default 12 ≈ one hour at the 300 s default refresh cadence (an app
    # using a faster stale-retry cadence reaches it sooner — tune per app). Only
    # acts when enable_auto_reboot is set. See note_refresh_result()/_auto_reboot().
    MAX_REFRESH_FAILURES = 12

    def __init__(self, enable_web: bool = True, update_interval: int = 300,
                 enable_watchdog: bool = False, watchdog_timeout: int = 8,
                 enable_auto_reboot: bool = False,
                 max_refresh_failures: int = None) -> None:
        """Initialize SLDK application.

        Args:
            enable_web: Whether to enable web server (if memory allows)
            update_interval: Data update interval in seconds
            enable_watchdog: Arm a hardware watchdog (CircuitPython only) that
                resets the board if the display loop stops feeding it — recovers
                from a true freeze (e.g. a hung synchronous socket). Default False
                so existing apps are unaffected; opt in per app.
            watchdog_timeout: Watchdog timeout in seconds. MUST exceed the longest
                expected gap between display-loop iterations (a blocking fetch
                pauses feeding), so keep HTTP timeouts comfortably below it and
                feed it during any long blocking work. Default 8s — short enough for
                quick freeze recovery. (Hardware note: the ESP32-S3 accepts AND
                honors any value on both CP 9.2.7 and the target CP 10.2.1 — the
                once-assumed ~8.3s ValueError cap does not exist; see
                test/claude/RELIABILITY_TESTING.md.)
            enable_auto_reboot: Opt in to the last-resort auto-reboot. The watchdog
                only catches a FROZEN display loop; a box whose outbound fetches all
                fail isn't frozen — the loop runs, the web server serves, the panel
                just shows stale data forever (the real 637-failures-over-2-days
                field outage). When enabled, ``note_refresh_result(ok=False)`` past
                ``max_refresh_failures`` reboots to re-init the radio/session.
                Default False so existing apps are unaffected.
            max_refresh_failures: Consecutive refresh failures before an
                auto-reboot. Defaults to ``MAX_REFRESH_FAILURES`` (12). Composes
                with the diagnostics boot-loop breaker: in safe mode the app stops
                fetching, so it stops reporting failures and this never fires — the
                ~hourly reboot cadence can't spin the way a deterministic crash loop
                would.
        """
        self.enable_web = enable_web
        self.update_interval = update_interval
        self.enable_watchdog = enable_watchdog
        self.watchdog_timeout = watchdog_timeout
        self._watchdog = None  # set by _arm_watchdog() on hardware when enabled

        # --- data-refresh resilience (last-resort auto-reboot) --------------
        self.enable_auto_reboot = enable_auto_reboot
        self.max_refresh_failures = (max_refresh_failures
                                     if max_refresh_failures is not None
                                     else self.MAX_REFRESH_FAILURES)
        self._consecutive_refresh_failures = 0
        self._last_refresh_error = None
        self._last_refresh_success_time = None

        self.running: bool = False
        # When True, the display loop skips rendering queue content (the queue
        # keeps its items) — see suspend_render()/suspended_render(). Used while an
        # app paints an off-queue status frame and then blocks on a fetch, so stale
        # content can't ghost over the status frame. Default off: existing apps and
        # the dev harness are unaffected.
        self._render_suspended: bool = False
        # Web-server -> main-loop handoff: the web server (which runs in its own
        # cooperative task) must never mutate display/queue state itself — see
        # notify_settings_changed(). The display loop applies pending settings at
        # a safe frame boundary instead.
        self._settings_dirty: bool = False
        self.display: Optional[DisplayInterface] = None
        self.content_queue = ContentQueue()
        self._tasks: List[asyncio.Task] = []

        # Memory tracking
        self._last_memory_report: float = 0
        self._memory_report_interval = 60  # Report every minute

        # Runtime metrics (cheap counters — used by the dev/verification harness)
        self._frame_count: int = 0
        self._current_content = None
        self._run_start = None  # time.monotonic() when run() began the loop

        # Default settings — built-in fields (brightness_scale, scroll_speed,
        # default_color) are registered by SettingsManager.__init__ via define().
        from ..config.settings_manager import SettingsManager
        self.settings = SettingsManager("settings.json")

        # Give the content module a reference so ScrollingText/StaticText can
        # read library defaults at construction time without being coupled to the app.
        from ..display import content as _content_mod
        _content_mod._settings = self.settings
    
    # Abstract methods to be implemented by subclasses
    
    async def setup(self) -> None:
        """Initialize application resources.
        
        Called once at startup. Set up your display content here.
        """
        raise NotImplementedError("Subclass must implement setup()")
    
    async def update_data(self) -> None:
        """Update application data.
        
        Called periodically by data update process.
        This is where you fetch new data, update content, etc.
        """
        pass  # Optional - subclass can override if needed
    
    async def prepare_display_content(self):
        """Prepare content for display.

        Called by display process to get content.
        Return a DisplayContent instance or None.
        """
        # While rendering is suspended, draw nothing from the queue (the queue keeps
        # its items, so it resumes exactly where it was). Lets an app paint an
        # off-queue status frame + block on a fetch without stale content ghosting.
        if self._render_suspended:
            return None
        # Default implementation uses content queue
        return await self.content_queue.get_current()

    # --- render suspension --------------------------------------------------
    # An app sometimes needs to paint an off-queue frame (e.g. "Updating…") and
    # then make a blocking call (a synchronous HTTP fetch pauses the whole loop).
    # Suspending render keeps the queue intact but stops the loop drawing it, so
    # the previous item can't ghost over the status frame. Prefer the context
    # manager — it always resumes, even if the blocking work raises.

    def suspend_render(self) -> None:
        """Stop the display loop from drawing queue content (queue is preserved)."""
        self._render_suspended = True

    def resume_render(self) -> None:
        """Resume drawing queue content after suspend_render()."""
        self._render_suspended = False

    @property
    def render_suspended(self) -> bool:
        """Whether queue rendering is currently suspended."""
        return self._render_suspended

    def suspended_render(self):
        """Context manager: suspend rendering for the block, always resume after.

            with app.suspended_render():
                await app.paint_status_frame()
                await app.blocking_fetch()   # loop frozen anyway; no ghosting
        """
        return _SuspendRender(self)
    
    async def cleanup(self) -> None:
        """Clean up resources on shutdown.

        Called when application is stopping.
        """
        pass  # Optional - subclass can override

    async def show_loading(self) -> None:
        """Optional hook: render a "loading" frame before a blocking update.

        ``update_data()`` typically makes blocking HTTP calls — ``adafruit_requests``
        is synchronous on CircuitPython, so the call pauses the display loop until
        it returns. Override this to draw a static loading indicator first, so the
        pause looks intentional rather than a freeze (spec FR-029). Default: no-op.
        """
        pass

    async def _render_loading(self) -> None:
        """Invoke show_loading() defensively (never let it kill the data loop)."""
        try:
            await self.show_loading()
        except Exception as e:
            print(f"show_loading error: {e}")
    
    # Core process implementations
    
    async def _display_process(self) -> None:
        """Process 1: Handle display updates."""
        print("Display process started")
        _prev_content = None
        _active_transition = None
        _prev_advance = 0   # tracks content_queue._advance_count
        # Survives across frames: set when content advances (queue cycle or
        # rebuild); cleared only when a transition fires (or no transition is
        # configured). This lets saves that arrive during a playing transition
        # queue up and fire when the current one finishes.
        _wants_transition = False

        while self.running:
            try:
                # The display loop is the device's liveness heartbeat: feeding the
                # watchdog here means a wedged loop (e.g. a hung synchronous fetch
                # that froze the whole event loop) stops feeding and triggers a
                # self-healing reset. A caught render error just continues + refeeds.
                self._feed_watchdog()

                if self._settings_dirty:
                    self._settings_dirty = False
                    try:
                        self._apply_library_settings()
                    except Exception as e:
                        print("_apply_library_settings error:", e)
                    try:
                        self.on_settings_changed()
                    except Exception as e:
                        print("on_settings_changed error:", e)

                content = await self.prepare_display_content()
                self._current_content = content

                # Detect queue advances (loop, multi-item advance, or rebuild).
                # The advance counter increments on every start() call; _prev_advance > 0
                # skips the very first play (nothing to transition from yet).
                advance = getattr(self.content_queue, "_advance_count", 0)
                if advance != _prev_advance and _prev_advance > 0:
                    _wants_transition = True
                _prev_advance = advance

                if content and self.display:
                    # Fallback: object identity catches custom prepare_display_content()
                    # implementations that don't use ContentQueue.
                    if content is not _prev_content and _prev_content is not None:
                        _wants_transition = True

                    # Fire the deferred transition as soon as nothing is active.
                    if _wants_transition and _active_transition is None:
                        t = self._get_transition()
                        if t is not None:
                            await t.start(self.display, lambda: None)
                            _active_transition = t
                        _wants_transition = False

                    await self.display.clear()

                    # Let the active transition adjust content position before
                    # it renders (used by DropFromSky to animate y each frame).
                    if _active_transition is not None and hasattr(
                            _active_transition, 'pre_render_hook'):
                        _active_transition.pre_render_hook(content)

                    await content.render(self.display)

                    if _active_transition is not None:
                        await _active_transition.render(self.display, content=content)
                        if _active_transition.is_complete:
                            _active_transition = None

                    # show() returns False when the simulator window closes.
                    if await self.display.show() is False:
                        self._request_shutdown()
                        return

                    self._frame_count += 1

                _prev_content = content
                await sleep(0.05)  # 20 FPS
                await self._report_memory()

            except Exception as e:
                print(f"Display error: {e}")
                await sleep(1)

    def _request_shutdown(self) -> None:
        """Stop the app and cancel sibling tasks so it exits promptly.

        Without cancelling siblings, a data-update task asleep for
        ``update_interval`` seconds would keep the process alive long after the
        window closed.
        """
        self.running = False
        current = asyncio.current_task()
        for task in list(self._tasks):
            if task is not current:
                task.cancel()

    async def _data_update_process(self) -> None:
        """Process 2: Handle data updates."""
        print("Data update process started")
        
        # Initial update
        try:
            await self._render_loading()
            await self.update_data()
        except Exception as e:
            print(f"Initial data update error: {e}")

        low_mem_skips = 0
        while self.running:
            try:
                # Wait for update interval
                await sleep(self.update_interval)

                # Check if we have enough memory
                gc.collect()
                free_mem = free_memory()

                # After too many consecutive low-memory skips, force one attempt so a
                # device that never quite clears the floor can't lock onto stale data
                # forever (the forced parse fails gracefully if there's truly no room).
                force = low_mem_skips >= self.MAX_LOW_MEM_SKIPS
                if free_mem > self.MIN_FREE_FOR_UPDATE or force:
                    if force:
                        print(f"Forcing data update after {low_mem_skips} low-memory skips: {free_mem}")
                    low_mem_skips = 0
                    # Show a loading frame before the (possibly blocking) fetch.
                    await self._render_loading()
                    await self.update_data()
                else:
                    # Too little headroom for the parse: skip this cycle and keep
                    # last-good data rather than risk an OOM crash to black.
                    low_mem_skips += 1
                    print(f"Skipping data update - low memory: {free_mem}")
                    
            except Exception as e:
                print(f"Data update error: {e}")
                await sleep(30)  # Back off on error
    
    def _apply_library_settings(self):
        """Apply display-level settings to the live display and content queue.

        Called by the display loop (see _display_process) when a web save sets
        _settings_dirty, immediately before on_settings_changed(). Handles
        settings the library owns: brightness (pushed to the display hardware)
        and scroll speed (propagated to every queue item that exposes a .speed
        attribute). Runs on the display-loop task, never from the web server.
        """
        if self.display is not None:
            try:
                brightness = float(self.settings.get("brightness_scale", 0.5))
                brightness = max(0.0, min(1.0, brightness))
                self.display._brightness = brightness
                hw = getattr(self.display, "hardware", None)
                if hw is not None:
                    hw.display.brightness = brightness
                else:
                    sim = getattr(self.display, "display", None)
                    if sim is not None:
                        sim.brightness = brightness
            except Exception as e:
                print("brightness apply error:", e)

        try:
            speed_px = self.settings.get_scroll_speed_px()
            for item in self.content_queue:
                key = getattr(item, "_color_setting", None)
                if key is not None:
                    item.color = self.settings.get(key, 0xFFFFFF)
                if getattr(item, "_speed_is_default", False):
                    item.speed = speed_px
        except Exception as e:
            print("content settings apply error:", e)

    def _get_transition(self):
        """Return a fresh Transition for the current transition_style setting, or None.

        The name -> class dispatch lives in effects.transitions.transition_factory
        (kept in lockstep with config.transition_names.TRANSITION_NAMES, which is
        what the settings UI offers). Imported lazily so a "None" transition style
        never drags the effects package onto the RAM-constrained device.
        """
        style = self.settings.get("transition_style", "None")
        if not style or style == "None":
            return None
        try:
            from ..effects.transitions import transition_factory
        except ImportError:
            return None
        t = transition_factory(style)
        if t is None:
            # A stale/unknown saved value shouldn't silently disable transitions
            # without a trace — make it visible (non-fatal).
            print("Unknown transition_style %r; using None" % (style,))
        return t

    def notify_settings_changed(self):
        """Web-server -> main-loop handoff: request that saved settings be applied.

        This is the ONLY thing a web server may do besides writing settings —
        it must never mutate display/queue state itself (that's owned solely by
        the display-loop task). Sets a flag; the display loop applies the
        settings (and calls on_settings_changed()) at its next frame boundary.
        Safe to call from a synchronous route handler, and safe to call more
        than once before the loop next runs (multiple saves coalesce into one
        apply — settings are re-read from disk, not queued).
        """
        self._settings_dirty = True

    def on_settings_changed(self):
        """Called by the display loop after a web-saved settings change is applied.

        Override to immediately rebuild display content. Must be synchronous
        and fast — it runs on the display-loop task, not in its own task, so it
        blocks rendering while it runs.
        """
        pass

    async def create_web_server(self):
        """Create web server instance.

        The default implementation returns a ``SettingsWebServer`` driven by
        ``self.settings._schema`` (populated by ``SettingsManager.define()``).
        Override to replace the auto-generated UI with a custom web server.
        Return ``None`` to disable the web server entirely.

        Returns:
            Web server instance (must implement start/run_forever/stop/get_server_url),
            or None to skip the web server process.
        """
        settings = getattr(self, "settings", None)
        if settings is None or not getattr(settings, "_schema", None):
            return None
        try:
            import sys
            from ..web.settings_server import SettingsWebServer
            is_cp = (hasattr(sys, "implementation")
                     and sys.implementation.name == "circuitpython")
            port = 80 if is_cp else 8080
            return SettingsWebServer(settings, app=self, port=port)
        except ImportError:
            return None
    
    async def _web_server_process(self) -> None:
        """Process 3: Handle web interface."""
        if not self.enable_web:
            return
            
        # Check if we have enough memory for web server
        gc.collect()
        free_mem = free_memory()

        if free_mem < 50000:  # Need 50KB free
            print(f"Web server disabled - insufficient memory: {free_mem}")
            return
        
        try:
            # Create web server
            web_server = await self.create_web_server()
            if not web_server:
                return
            
            print("Web server process started")
            
            # Start the web server
            if await web_server.start():
                print(f"Web interface available at: {web_server.get_server_url()}")
                
                # Run web server
                await web_server.run_forever()
            else:
                print("Failed to start web server")
            
        except ImportError:
            print("Web server not available - adafruit_httpserver is required")
        except Exception as e:
            print(f"Web server error: {e}")
    
    async def _report_memory(self) -> None:
        """Report memory usage periodically."""
        try:
            import time
            now = time.monotonic() if hasattr(time, 'monotonic') else 0
            
            if now - self._last_memory_report > self._memory_report_interval:
                gc.collect()
                free = free_memory()
                if free > 0:
                    print(f"Free memory: {free} bytes")
                self._last_memory_report = now
                
        except Exception:
            pass  # Ignore memory reporting errors
    
    # Main application lifecycle
    
    async def run(self) -> None:
        """Run the application with three processes."""
        print("Starting SLDK application")
        
        # Initialize display
        await self._initialize_display()
        
        try:
            self.running = True

            import time
            self._run_start = time.monotonic() if hasattr(time, "monotonic") else None

            # Run setup
            await self.setup()

            # Arm the watchdog AFTER the (possibly long, blocking) boot sequence so
            # boot's network calls can't trip it; the display loop feeds it from here on.
            self._arm_watchdog()

            # Create tasks based on available memory
            tasks = []
            
            # Display process always runs
            tasks.append(create_task(self._display_process()))
            
            # Data update process if memory allows
            gc.collect()
            free_mem = free_memory()

            if free_mem > 30000:  # 30KB free
                tasks.append(create_task(self._data_update_process()))
            else:
                print(f"Data updates disabled - low memory: {free_mem}")

            # Web server if enabled and memory allows
            if self.enable_web and free_mem > 50000:
                tasks.append(create_task(self._web_server_process()))
            
            self._tasks = tasks
            
            # Run until stopped
            await gather(*tasks, return_exceptions=True)
            
        finally:
            self.running = False
            await self.cleanup()
            
            # Cancel any remaining tasks
            for task in self._tasks:
                try:
                    task.cancel()
                except Exception:
                    pass
    
    async def create_display(self) -> DisplayInterface:
        """Create display instance.
        
        Override this method to use custom hardware.
        
        Returns:
            DisplayInterface instance
        """
        # Use unified display which auto-detects platform
        from ..display import UnifiedDisplay
        return UnifiedDisplay()
    
    async def _initialize_display(self) -> None:
        """Initialize the display based on platform."""
        try:
            # Allow application to override display creation
            self.display = await self.create_display()
            await self.display.initialize()
            
        except ImportError as e:
            print(f"Failed to initialize display: {e}")
            print("Install simulator with 'pip install sldk[simulator]' for desktop development")
        except OSError as e:
            print(f"Display initialization failed: {e}")

    def _arm_watchdog(self) -> None:
        """Arm the hardware watchdog (CircuitPython only) if enabled.

        Fed from the display loop (the device's liveness heartbeat): if anything
        wedges that loop — most importantly a hung synchronous HTTP call — feeding
        stops and the board resets, self-recovering instead of sitting frozen/black
        until someone power-cycles it. No-op on desktop, when disabled, or while a
        USB serial console is attached (so the watchdog doesn't reboot during
        interactive debugging)."""
        if not self.enable_watchdog or self._watchdog is not None:
            return
        try:
            import sys
            if not (hasattr(sys, "implementation")
                    and sys.implementation.name == "circuitpython"):
                return
            try:
                import supervisor
                if getattr(supervisor.runtime, "serial_connected", False):
                    print("Watchdog NOT armed: USB serial connected (debugging)")
                    return
            except Exception:
                pass
            import microcontroller
            from watchdog import WatchDogMode
            wdt = microcontroller.watchdog
            # The ESP32-S3 accepts and honors any timeout we set on both CP 9.2.7 and
            # the target CP 10.2.1 — hardware-verified; the once-assumed ~8.3s
            # ValueError cap does not exist (see test/claude/RELIABILITY_TESTING.md).
            # So set it directly. If some future board/version did reject the value,
            # the broad `except` below logs it and leaves the watchdog disarmed.
            wdt.timeout = self.watchdog_timeout
            wdt.mode = WatchDogMode.RESET
            self._watchdog = wdt
            print(f"Watchdog armed: {self.watchdog_timeout}s (RESET)")
        except Exception as e:
            print(f"Watchdog unavailable: {e}")

    def _feed_watchdog(self) -> None:
        """Pet the watchdog so it doesn't reset the board. Safe when disarmed."""
        wdt = self._watchdog
        if wdt is not None:
            try:
                wdt.feed()
            except Exception:
                pass

    # --- data-refresh resilience -------------------------------------------
    # The watchdog only catches a frozen display loop. A box whose every outbound
    # fetch fails is NOT frozen — the loop runs, the web UI serves, the panel just
    # shows stale data indefinitely (the real field outage: 637 failed fetches
    # over ~2 days, never self-recovered). This is the generic, app-driven last
    # resort: the app reports each refresh's outcome and, opt-in, the box reboots
    # to re-init the radio/session after a sustained failure run.

    def note_refresh_result(self, ok: bool, reason=None) -> int:
        """Report the outcome of one data refresh (the app's resilience hook).

        Call once per refresh attempt (typically at the end of ``update_data()``)
        with whether it actually fetched + applied fresh data. On success the
        failure streak resets and the last-success time is stamped; on failure the
        streak grows and — if ``enable_auto_reboot`` is set and the streak reaches
        ``max_refresh_failures`` — a last-resort reboot is triggered to clear a
        wedged radio/session.

        Args:
            ok: True if the refresh succeeded.
            reason: Optional diagnostic string for a failure (e.g.
                ``str(http_client.last_error)``). Surfaced via ``last_refresh_error``
                and persisted to NVM before an auto-reboot so the outage is
                diagnosable after recovery.

        Returns:
            The current consecutive-failure count (0 after a success).
        """
        if ok:
            self._consecutive_refresh_failures = 0
            self._last_refresh_error = None
            import time
            self._last_refresh_success_time = (
                time.monotonic() if hasattr(time, "monotonic") else None)
            return 0

        self._consecutive_refresh_failures += 1
        if reason is not None:
            self._last_refresh_error = reason
        if (self.enable_auto_reboot
                and self._consecutive_refresh_failures >= self.max_refresh_failures):
            self._auto_reboot(
                "%d consecutive refresh failures; last_error=%s"
                % (self._consecutive_refresh_failures, self._last_refresh_error))
        return self._consecutive_refresh_failures

    @property
    def consecutive_refresh_failures(self) -> int:
        """Consecutive failed refreshes reported via ``note_refresh_result``."""
        return self._consecutive_refresh_failures

    @property
    def data_stale(self) -> bool:
        """True when the most recent reported refresh failed (showing old data)."""
        return self._consecutive_refresh_failures > 0

    @property
    def last_refresh_error(self):
        """Diagnostic reason from the last failed refresh, or None."""
        return self._last_refresh_error

    def seconds_since_last_refresh_success(self):
        """Seconds since the last successful refresh, or None if never succeeded.

        A staleness signal the app can read to drive an on-panel "stale data"
        indicator — the box can look alive while the data is hours old.
        """
        if self._last_refresh_success_time is None:
            return None
        import time
        if not hasattr(time, "monotonic"):
            return None
        return time.monotonic() - self._last_refresh_success_time

    def _auto_reboot(self, reason: str) -> None:
        """Last-resort reboot to clear a wedged radio/session (device-only).

        Records the cause to NVM (survives the reset; shown on the config UI after
        recovery) then resets via ``_hardware_reset()``. A no-op on desktop/sim, so
        the simulator and tests never reboot.
        """
        wifi_state = self._wifi_connected()
        full_reason = "auto-reboot: %s (wifi_connected=%s)" % (reason, wifi_state)
        print(full_reason)
        # Best-effort: persist the cause so the next outage is diagnosable. A
        # reboot fixes the wedge; if the link is genuinely down it won't — but an
        # ~hourly retry-reboot is acceptable, and wifi_state records which it was.
        try:
            from ..utils import diagnostics
            diagnostics.open().record_crash(full_reason)
        except Exception as e:
            print("auto-reboot diag record failed:", e)
        self._hardware_reset()

    def _hardware_reset(self) -> None:
        """Reset the board on CircuitPython; no-op elsewhere (test/sim seam)."""
        if not self._is_circuitpython():
            return
        try:
            import microcontroller
            microcontroller.reset()
        except Exception as e:
            print("auto-reboot reset failed:", e)

    @staticmethod
    def _is_circuitpython() -> bool:
        import sys
        return (hasattr(sys, "implementation")
                and sys.implementation.name == "circuitpython")

    @staticmethod
    def _wifi_connected():
        """Best-effort WiFi-associated check; None when undetectable (desktop)."""
        try:
            import wifi
            radio = wifi.radio
            if getattr(radio, "connected", False):
                return True
            return getattr(radio, "ipv4_address", None) is not None
        except Exception:
            return None

    def stop(self) -> None:
        """Stop the application."""
        self.running = False

    # Runtime metrics -------------------------------------------------------
    # Cheap, device-safe introspection used by the desktop verification
    # harness (``scrollkit.dev.run_headless``) so an AI agent can confirm the
    # app actually rendered/advanced. All a few integer reads — no allocation.

    @property
    def frame_count(self) -> int:
        """Number of frames actually shown since ``run()`` started."""
        return self._frame_count

    def fps(self) -> float:
        """Average displayed frames per second since ``run()`` started.

        Returns 0.0 before the loop starts. On the simulator this is desktop
        speed; the *hardware* estimate lives in the feasibility report.
        """
        if self._run_start is None:
            return 0.0
        import time
        if not hasattr(time, "monotonic"):
            return 0.0
        elapsed = time.monotonic() - self._run_start
        return (self._frame_count / elapsed) if elapsed > 0 else 0.0

    def describe(self) -> dict:
        """A small, JSON-able snapshot of the app's current state.

        Reads a supported summary of the content being shown (via its
        ``describe()``) instead of poking private attributes.
        """
        content = self._current_content
        if content is not None and hasattr(content, "describe"):
            try:
                content_desc = content.describe()
            except Exception:
                content_desc = type(content).__name__
        elif content is not None:
            content_desc = type(content).__name__
        else:
            content_desc = None
        return {
            "running": self.running,
            "frame_count": self._frame_count,
            "fps": round(self.fps(), 1),
            "enable_web": self.enable_web,
            "update_interval": self.update_interval,
            "current_content": content_desc,
        }

    def memory_estimate(self) -> dict:
        """Estimated free RAM: real on hardware, modeled/large on desktop.

        Delegates to ``scrollkit.app.memory.free_memory`` so the value matches
        what the memory ladder in the run loop actually gates on.
        """
        from .memory import free_memory
        free = free_memory()
        return {"free_bytes": free}


# Public name for the merged ScrollKit library. `SLDKApp` is retained as a
# backward-compatible alias for code/tests that still reference the old name.
ScrollKitApp = SLDKApp