"""
Contract: App Framework
Public API for ScrollKitApp.
"""


class ScrollKitAppContract:
    """
    Base class for full-featured LED matrix applications.

    Subclasses override setup(), update_data(), and prepare_display_content().
    The framework calls them in an async loop with three concurrent tasks:
      1. display_process   — always runs, 20 FPS
      2. data_update_process — runs if ≥30KB free, period = update_interval
      3. web_server_process — runs if ≥50KB free and enable_web=True
    """

    def __init__(
        self,
        update_interval: float = 300.0,
        enable_web: bool = True,
    ):
        raise NotImplementedError

    async def setup(self) -> None:
        """Called once at startup before the main loop begins."""
        pass

    async def update_data(self) -> None:
        """Called every update_interval seconds to refresh application data."""
        pass

    async def prepare_display_content(self):
        """
        Called every display frame. Return a DisplayContent to show,
        or None to keep the current content.
        """
        raise NotImplementedError

    async def run(self) -> None:
        """Start the application. Blocks until stopped."""
        raise NotImplementedError


# --- Contract tests ---

def test_scrollkit_app_can_be_subclassed():
    """ScrollKitApp must support subclassing with async overrides."""
    from scrollkit.app.base import ScrollKitApp
    from scrollkit.display.content import StaticText

    class MyApp(ScrollKitApp):
        async def prepare_display_content(self):
            return StaticText("Hello", color=(255, 255, 0))

    app = MyApp(update_interval=60, enable_web=False)
    assert app is not None


def test_scrollkit_app_setup_is_optional():
    """Subclasses must NOT need to override setup() or update_data()."""
    from scrollkit.app.base import ScrollKitApp
    from scrollkit.display.content import StaticText

    class MinimalSubclass(ScrollKitApp):
        async def prepare_display_content(self):
            return StaticText("Test")

    # No setup() or update_data() override — should still work
    app = MinimalSubclass(enable_web=False)
    assert hasattr(app, 'run')


def test_scrollkit_app_run_is_coroutine():
    """ScrollKitApp.run() must be an async coroutine."""
    import asyncio
    from scrollkit.app.base import ScrollKitApp
    from scrollkit.display.content import StaticText

    class TestApp(ScrollKitApp):
        async def prepare_display_content(self):
            return StaticText("Hi")

    app = TestApp(enable_web=False)
    assert asyncio.iscoroutinefunction(app.run)
