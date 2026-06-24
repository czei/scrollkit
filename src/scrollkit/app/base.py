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
from ..exceptions import DisplayError, NetworkError, WebServerError
from .memory import free_memory


class SLDKApp:
    """Base class for SLDK applications.
    
    Implements three-process architecture:
    1. Display process - Always runs
    2. Data update process - Runs if memory allows
    3. Web server process - Optional, runs if memory allows
    """
    
    def __init__(self, enable_web: bool = True, update_interval: int = 300) -> None:
        """Initialize SLDK application.
        
        Args:
            enable_web: Whether to enable web server (if memory allows)
            update_interval: Data update interval in seconds
        """
        self.enable_web = enable_web
        self.update_interval = update_interval
        self.running: bool = False
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
        # Default implementation uses content queue
        return await self.content_queue.get_current()
    
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
        # Flag survives across frames: if a save triggers a content change while
        # a transition is still playing, _prev_content catches up within one frame
        # and the identity check would miss it. The flag defers the trigger until
        # the active transition finishes.
        _wants_transition = False

        while self.running:
            try:
                content = await self.prepare_display_content()
                self._current_content = content

                if content and self.display:
                    # Mark that content changed; persist across frames so saves
                    # that arrive during an active transition aren't silently lost.
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
                    await content.render(self.display)

                    if _active_transition is not None:
                        await _active_transition.render(self.display)
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

        while self.running:
            try:
                # Wait for update interval
                await sleep(self.update_interval)

                # Check if we have enough memory
                gc.collect()
                free_mem = free_memory()

                if free_mem > 20000:  # Need 20KB free
                    # Show a loading frame before the (possibly blocking) fetch.
                    await self._render_loading()
                    await self.update_data()
                else:
                    print(f"Skipping data update - low memory: {free_mem}")
                    
            except Exception as e:
                print(f"Data update error: {e}")
                await sleep(30)  # Back off on error
    
    def _apply_library_settings(self):
        """Apply display-level settings to the live display and content queue.

        Called by SettingsWebServer immediately after saving, before
        on_settings_changed().  Handles settings the library owns: brightness
        (pushed to the display hardware) and scroll speed (propagated to every
        queue item that exposes a .speed attribute).
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
        """Return a fresh Transition for the current transition_style setting, or None."""
        style = self.settings.get("transition_style", "None")
        if not style or style == "None":
            return None
        try:
            from ..effects.transitions import (
                IrisSnap, VenetianShutters, MosaicResolve,
                CRTCollapse, LightSlitRewrite,
            )
            _map = {
                "Iris Snap": IrisSnap,
                "Venetian Shutters": VenetianShutters,
                "Mosaic Resolve": MosaicResolve,
                "CRT Collapse": CRTCollapse,
                "Light Slit": LightSlitRewrite,
            }
            cls = _map.get(style)
            return cls() if cls else None
        except ImportError:
            return None

    def on_settings_changed(self):
        """Called synchronously after the web UI saves settings.

        Override to immediately rebuild display content. Must be synchronous —
        it is called from an adafruit_httpserver route handler.
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
        except WebServerError as e:
            print(f"Web server error: {e}")
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
        except DisplayError as e:
            print(f"Display initialization failed: {e}")
    
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