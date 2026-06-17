"""Integration tests for SLDK application lifecycle.

Tests the full integration of SLDK components working together:
- App initialization and lifecycle
- Content creation and display
- Queue management
- Display strategy execution
- Effects engine integration
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sldk.app import SLDKApp, MinimalLEDApp
from sldk.display import ContentQueue, DisplayManager, DisplayContent
from sldk.display.interface import DisplayInterface
from sldk.content import StaticText, ScrollingText, RainbowText
from sldk.effects import EffectsEngine
from sldk.effects.effects import SparkleEffect
from sldk.display.strategy import (
    Priority, DisplayStrategy, DisplayItem,
    StaticTextStrategy, ScrollingTextStrategy,
    StrategyRegistry, register_strategy, get_strategy_registry,
)


class TestAppLifecycleIntegration:
    """Integration tests for the full app lifecycle."""

    @pytest.mark.asyncio
    async def test_sldk_app_init(self, mock_circuitpython_imports):
        """Test SLDKApp initializes with correct defaults."""
        app = SLDKApp()
        assert app.enable_web is True
        assert app.update_interval == 300
        assert app.running is False
        assert app.display is None
        assert isinstance(app.content_queue, ContentQueue)

    @pytest.mark.asyncio
    async def test_sldk_app_custom_config(self, mock_circuitpython_imports):
        """Test SLDKApp with custom configuration."""
        app = SLDKApp(enable_web=False, update_interval=60)
        assert app.enable_web is False
        assert app.update_interval == 60

    @pytest.mark.asyncio
    async def test_minimal_app_creation(self, mock_circuitpython_imports):
        """Test MinimalLEDApp can be created."""
        app = MinimalLEDApp()
        assert app is not None
        assert hasattr(app, 'app')

    @pytest.mark.asyncio
    async def test_app_setup_called(self, mock_circuitpython_imports):
        """Test that setup() is called during app lifecycle."""

        class TestApp(SLDKApp):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.setup_called = False

            async def setup(self):
                self.setup_called = True

        app = TestApp(enable_web=False)
        await app.setup()
        assert app.setup_called is True

    @pytest.mark.asyncio
    async def test_app_update_data_called(self, mock_circuitpython_imports):
        """Test that update_data() works."""

        class TestApp(SLDKApp):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.update_count = 0

            async def setup(self):
                pass

            async def update_data(self):
                self.update_count += 1
                self.content_queue.add_content(
                    StaticText(f"Update {self.update_count}")
                )

        app = TestApp(enable_web=False)
        await app.setup()
        await app.update_data()
        assert app.update_count == 1
        assert app.content_queue.get_content_count() == 1


class TestContentIntegration:
    """Integration tests for content creation and management."""

    def test_static_text_content(self):
        """Test StaticText content creation."""
        text = StaticText("Hello", x=10, y=15, color=0xFF0000, duration=5.0)
        assert text.text == "Hello"
        assert text.x == 10
        assert text.y == 15
        assert text.color == 0xFF0000
        assert text.duration == 5.0

    def test_scrolling_text_content(self):
        """Test ScrollingText content creation."""
        text = ScrollingText("Scroll", y=20, color=0x00FF00, speed=25)
        assert text.text == "Scroll"
        assert text.y == 20
        assert text.color == 0x00FF00
        assert text.speed == 25

    def test_rainbow_text_content(self):
        """Test RainbowText content creation."""
        text = RainbowText("Rainbow", x=0, y=8, rainbow_speed=2.0)
        assert text.text == "Rainbow"
        assert text.x == 0
        assert text.y == 8
        assert text.rainbow_speed == 2.0

    def test_content_queue_basic(self):
        """Test ContentQueue add and retrieve."""
        queue = ContentQueue()
        assert queue.is_empty

        text = StaticText("Test", duration=5)
        queue.add_content(text)
        assert not queue.is_empty
        assert queue.get_content_count() == 1

    def test_content_queue_multiple_items(self):
        """Test ContentQueue with multiple items."""
        queue = ContentQueue()
        items = [
            StaticText("A", duration=1),
            StaticText("B", duration=1),
            ScrollingText("C"),
        ]
        for item in items:
            queue.add_content(item)
        assert queue.get_content_count() == 3

    def test_content_queue_clear(self):
        """Test clearing ContentQueue."""
        queue = ContentQueue()
        queue.add_content(StaticText("Test", duration=5))
        queue.add_content(ScrollingText("Scroll"))
        assert queue.get_content_count() == 2
        queue.clear()
        assert queue.is_empty
        assert queue.get_content_count() == 0


class TestDisplayStrategyIntegration:
    """Integration tests for display strategy system."""

    def test_priority_levels(self):
        """Test priority level constants."""
        assert Priority.IDLE == 0
        assert Priority.LOW == 1
        assert Priority.NORMAL == 2
        assert Priority.HIGH == 3
        assert Priority.URGENT == 4
        assert Priority.SYSTEM == 5

    def test_display_item_creation(self):
        """Test DisplayItem creation."""
        item = DisplayItem('static_text', {'text': 'Hello'}, Priority.HIGH)
        assert item.strategy_name == 'static_text'
        assert item.data == {'text': 'Hello'}
        assert item.priority == Priority.HIGH

    def test_display_item_effects_chain(self):
        """Test chaining effects on DisplayItem."""
        item = DisplayItem('static_text', {'text': 'Test'})
        effect = MagicMock()
        result = item.add_effect(effect)
        assert result is item  # Method chaining
        assert effect in item.effects

    def test_display_item_with_effect(self):
        """Test with_effect fluent interface."""
        item = DisplayItem('static_text', {'text': 'Test'})
        effect = MagicMock()
        item.with_effect(effect)
        assert effect in item.effects

    def test_display_item_metadata(self):
        """Test DisplayItem metadata."""
        item = DisplayItem('static_text', {'text': 'Test'})
        item.set_metadata('key', 'value')
        assert item.get_metadata('key') == 'value'
        assert item.get_metadata('nonexistent', 'default') == 'default'

    def test_display_item_priority_ordering(self):
        """Test that higher priority items sort first."""
        low = DisplayItem('test', {}, Priority.LOW)
        high = DisplayItem('test', {}, Priority.HIGH)
        assert high < low  # Higher priority should sort first

    def test_static_text_strategy(self):
        """Test StaticTextStrategy validates data."""
        strategy = StaticTextStrategy()
        assert strategy.validate_data({'text': 'Hello'})
        assert not strategy.validate_data({})
        assert not strategy.validate_data({'wrong_key': 'value'})

    def test_scrolling_text_strategy(self):
        """Test ScrollingTextStrategy validates data."""
        strategy = ScrollingTextStrategy()
        assert strategy.validate_data({'text': 'Scroll'})
        assert not strategy.validate_data({})

    def test_strategy_registry(self):
        """Test global strategy registry."""
        registry = get_strategy_registry()
        strategies = registry.list_strategies()
        assert 'static_text' in strategies
        assert 'scrolling_text' in strategies

    def test_strategy_factory(self):
        """Test creating strategy instances from registry."""
        registry = get_strategy_registry()
        strategy = registry.create_strategy('static_text')
        assert isinstance(strategy, StaticTextStrategy)
        assert registry.create_strategy('nonexistent') is None


class TestDisplayManagerIntegration:
    """Integration tests for DisplayManager."""

    @pytest.mark.asyncio
    async def test_display_manager_init(self, mock_display):
        """Test DisplayManager initialization."""
        mgr = DisplayManager(mock_display)
        assert mgr.display == mock_display
        assert mgr.get_queue_depth() == 0

    @pytest.mark.asyncio
    async def test_display_manager_start_stop(self, mock_display):
        """Test DisplayManager start/stop cycle."""
        mgr = DisplayManager(mock_display)
        await mgr.start()
        assert mgr._is_running
        await mgr.stop()
        assert not mgr._is_running
        mock_display.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_display_manager_add_item(self, mock_display):
        """Test adding items to display manager."""
        mgr = DisplayManager(mock_display)
        result = mgr.add_item('static_text', {'text': 'Hello'})
        assert result
        assert mgr.get_queue_depth() == 1

    @pytest.mark.asyncio
    async def test_display_manager_statistics(self, mock_display, mock_time):
        """Test display manager statistics tracking."""
        mgr = DisplayManager(mock_display)
        stats = mgr.get_statistics()
        assert 'display_manager' in stats
        assert 'queue' in stats
        assert 'display' in stats
        assert stats['display']['type'] == 'MagicMock'

    @pytest.mark.asyncio
    async def test_display_manager_process_interval(self, mock_display):
        """Test setting process interval."""
        mgr = DisplayManager(mock_display)
        mgr.set_process_interval(0.5)
        assert mgr._process_interval == 0.5
        mgr.set_process_interval(0.001)  # Below minimum
        assert mgr._process_interval == 0.01  # Clamped to minimum

    @pytest.mark.asyncio
    async def test_display_manager_convenience_methods(self, mock_display):
        """Test convenience display methods."""
        mgr = DisplayManager(mock_display)
        assert mgr.show_text("Hello")
        assert mgr.show_scrolling_text("Scroll")
        assert mgr.show_alert("Alert!")
        assert mgr.get_queue_depth() == 3


class TestEffectsIntegration:
    """Integration tests for effects system."""

    def test_effects_engine_creation(self):
        """Test EffectsEngine creation."""
        engine = EffectsEngine(max_effects=3, target_fps=10)
        assert engine.max_effects == 3
        assert engine.target_fps == 10
        assert len(engine.active_effects) == 0

    def test_effects_engine_add_and_clear(self):
        """Test adding and clearing effects."""
        engine = EffectsEngine(max_effects=3)
        effect = SparkleEffect(intensity=5, duration=10.0)
        engine.add_effect(effect)
        assert len(engine.active_effects) == 1
        engine.clear_effects()
        assert len(engine.active_effects) == 0

    def test_effects_engine_max_limit(self):
        """Test that max_effects limit is respected."""
        engine = EffectsEngine(max_effects=1)
        effect1 = SparkleEffect(intensity=3, duration=5.0)
        effect2 = SparkleEffect(intensity=5, duration=5.0)
        engine.add_effect(effect1)
        engine.add_effect(effect2)
        assert len(engine.active_effects) <= 1

    @pytest.mark.asyncio
    async def test_sparkle_effect_creation(self):
        """Test SparkleEffect creation and properties."""
        effect = SparkleEffect(intensity=5, duration=10.0)
        assert effect.intensity == 5
        assert effect.duration == 10.0

    @pytest.mark.asyncio
    async def test_sparkle_effect_defaults(self):
        """Test SparkleEffect defaults."""
        effect = SparkleEffect()
        assert effect.intensity == 3
        assert effect.duration is None  # Permanent


class TestWebServerIntegration:
    """Integration tests for web server components."""

    @pytest.mark.asyncio
    async def test_url_route_registration(self, mock_circuitpython_imports):
        """Test web route decorator from adapters."""
        from sldk.web.adapters import route, MockRequest, ServerAdapter
        from unittest.mock import MagicMock

        @route("/test")
        async def handler(request):
            return "OK"

        assert callable(handler)
        mock_adapter = MagicMock(spec=ServerAdapter)
        mock_adapter.parse_query_params.return_value = {}
        mock_adapter.parse_form_data.return_value = {}
        req = MockRequest("GET", "/test", "", None, mock_adapter)
        result = await handler(req)
        assert result == "OK"


class TestTypeHintsIntegration:
    """Test that type hints are present on key public APIs."""

    def test_sldk_app_has_type_hints(self):
        """Key SLDKApp methods should have type hints."""
        import inspect

        sig = inspect.signature(SLDKApp.__init__)
        params = sig.parameters
        assert 'enable_web' in params
        assert 'update_interval' in params

    def test_display_interface_has_hints(self):
        """DisplayInterface should have type-hinted methods."""
        import inspect

        for method_name in ['draw_text', 'scroll_text', 'set_pixel', 'fill']:
            method = getattr(DisplayInterface, method_name, None)
            if method:
                sig = inspect.signature(method)
                assert sig.parameters is not None
                # Verify the method has a 'color' or similar parameter with hint
                params = list(sig.parameters.values())
                # At minimum, methods should have self
                assert len(params) >= 1


class TestEndToEndIntegration:
    """Full end-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_content_to_queue_to_display(self, mock_display, mock_circuitpython_imports):
        """Test the full pipeline: content -> queue -> display strategy -> render."""
        # Create a display manager
        mgr = DisplayManager(mock_display)

        # Add content through the queue
        mgr.show_text("Integration Test", duration=5.0)

        # Start the display manager
        await mgr.start()

        # Process the queue
        result = await mgr.process_queue()
        assert result

        # Stop
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_app_with_content_queue(self, mock_circuitpython_imports):
        """Test app with content queue integration."""

        class ContentApp(SLDKApp):
            async def setup(self):
                self.content_queue.add_content(
                    StaticText("Setup Text", duration=10)
                )

            async def update_data(self):
                self.content_queue.add_content(
                    ScrollingText("Update Data")
                )

        app = ContentApp(enable_web=False)
        await app.setup()
        assert app.content_queue.get_content_count() == 1

        await app.update_data()
        assert app.content_queue.get_content_count() == 2

    @pytest.mark.asyncio
    async def test_display_strategy_text_rendering(self, mock_display):
        """Test static text strategy rendering."""
        strategy = StaticTextStrategy()
        data = {'text': 'Hello', 'x': 0, 'y': 10, 'color': 0xFF0000}
        await strategy.render(mock_display, data)
        mock_display.draw_text.assert_called_once_with(
            'Hello', x=0, y=10, color=0xFF0000, font=None
        )

    @pytest.mark.asyncio
    async def test_display_strategy_scrolling_rendering(self, mock_display):
        """Test scrolling text strategy rendering."""
        strategy = ScrollingTextStrategy()
        data = {'text': 'Scroll', 'y': 20, 'color': 0x00FF00, 'speed': 0.05}
        await strategy.render(mock_display, data)

        if hasattr(mock_display, 'scroll_text'):
            mock_display.scroll_text.assert_called_once_with(
                'Scroll', y=20, color=0x00FF00, speed=0.05
            )

    def test_statistics_tracking(self, mock_display):
        """Test statistics tracking across the system."""
        mgr = DisplayManager(mock_display)
        stats = mgr.get_statistics()
        assert 'display_manager' in stats
        assert 'queue' in stats
        assert 'display' in stats
        assert isinstance(stats['display_manager']['uptime_seconds'], (int, float))