#!/usr/bin/env python3
"""Unit tests for SLDK app base class."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import sldk
from sldk.app import SLDKApp
from sldk.display import ContentQueue


class TestSLDKApp:
    """Test cases for SLDKApp base class."""
    
    def test_app_initialization(self, mock_circuitpython_imports):
        """Test basic app initialization."""
        app = SLDKApp(enable_web=False)
        
        assert app.enable_web is False
        assert app.update_interval == 300  # Default is 300
        # display_interval is not an attribute of SLDKApp
        assert isinstance(app.content_queue, ContentQueue)
        assert app.content_queue.is_empty
    
    def test_app_with_web_enabled(self, mock_circuitpython_imports):
        """Test app initialization with web server enabled."""
        app = SLDKApp(enable_web=True)  # web_port is not a parameter
        
        assert app.enable_web is True
    
    def test_app_custom_intervals(self, mock_circuitpython_imports):
        """Test app with custom update intervals."""
        app = SLDKApp(
            update_interval=30,
            enable_web=False
        )
        
        assert app.update_interval == 30
    
    @pytest.mark.asyncio
    async def test_create_display_default(self, mock_circuitpython_imports):
        """Test default display creation."""
        app = SLDKApp(enable_web=False)
        
        with patch('sldk.display.UnifiedDisplay') as mock_display_class:
            mock_display = MagicMock()
            mock_display_class.return_value = mock_display
            
            display = await app.create_display()
            
            assert display == mock_display
            mock_display_class.assert_called_once()
    
    def test_setup_abstract_method(self, mock_circuitpython_imports):
        """Test that setup is an abstract method."""
        app = SLDKApp(enable_web=False)
        
        # Should raise NotImplementedError when called directly
        with pytest.raises(NotImplementedError):
            asyncio.run(app.setup())
    
    @pytest.mark.asyncio
    async def test_update_data_abstract_method(self, mock_circuitpython_imports):
        """Test that update_data has a default implementation."""
        app = SLDKApp(enable_web=False)
        
        # update_data has a default implementation that does nothing
        await app.update_data()  # Should not raise


class TestCustomSLDKApp:
    """Test cases for custom SLDK app implementations."""
    
    def setup_method(self):
        """Setup test app class."""
        
        class TestApp(SLDKApp):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.setup_called = False
                self.update_called = False
                self.data_updates = []
            
            async def setup(self):
                self.setup_called = True
            
            async def update_data(self):
                self.update_called = True
                self.data_updates.append(len(self.data_updates) + 1)
        
        self.TestApp = TestApp
    
    def test_custom_app_creation(self, mock_circuitpython_imports):
        """Test creating custom app implementation."""
        app = self.TestApp(enable_web=False)
        
        assert isinstance(app, SLDKApp)
        assert app.setup_called is False
        assert app.update_called is False
    
    @pytest.mark.asyncio
    async def test_custom_setup_call(self, mock_circuitpython_imports):
        """Test calling setup on custom app."""
        app = self.TestApp(enable_web=False)
        
        await app.setup()
        
        assert app.setup_called is True
    
    @pytest.mark.asyncio
    async def test_custom_update_data_call(self, mock_circuitpython_imports):
        """Test calling update_data on custom app."""
        app = self.TestApp(enable_web=False)
        
        await app.update_data()
        
        assert app.update_called is True
        assert len(app.data_updates) == 1
        assert app.data_updates[0] == 1
    
    @pytest.mark.asyncio
    async def test_multiple_update_calls(self, mock_circuitpython_imports):
        """Test multiple update_data calls."""
        app = self.TestApp(enable_web=False)
        
        # Call update_data multiple times
        for i in range(3):
            await app.update_data()
        
        assert len(app.data_updates) == 3
        assert app.data_updates == [1, 2, 3]


class TestSLDKAppContentManagement:
    """Test cases for content queue management in SLDK app."""
    
    def setup_method(self):
        """Setup test app with content methods."""
        
        class ContentApp(SLDKApp):
            async def setup(self):
                pass
            
            async def update_data(self):
                # Add some test content
                from sldk.content import StaticText, ScrollingText
                
                static = StaticText("Test", x=10, y=10, color=0xFF0000, duration=5)
                scroll = ScrollingText("Scroll Test", y=20, color=0x00FF00)
                
                self.content_queue.add_content(static)
                self.content_queue.add_content(scroll)
        
        self.ContentApp = ContentApp
    
    @pytest.mark.asyncio
    async def test_content_queue_population(self, mock_circuitpython_imports):
        """Test that update_data populates content queue."""
        app = self.ContentApp(enable_web=False)
        
        # Initially empty
        assert app.content_queue.is_empty
        
        # Update data should add content
        await app.update_data()
        
        assert not app.content_queue.is_empty
        assert app.content_queue.get_content_count() == 2
    
    def test_content_queue_access(self, mock_circuitpython_imports):
        """Test accessing content queue."""
        app = self.ContentApp(enable_web=False)
        
        # Should have empty queue initially
        assert app.content_queue.is_empty
        assert app.content_queue.get_content_count() == 0
        
        # Add content directly
        from sldk.content import StaticText
        text = StaticText("Direct", x=0, y=0, color=0xFFFFFF, duration=1)
        app.content_queue.add_content(text)
        
        assert not app.content_queue.is_empty
        assert app.content_queue.get_content_count() == 1


@pytest.mark.integration  
class TestSLDKAppIntegration:
    """Integration tests for SLDK app with mocked components."""
    
    @pytest.mark.asyncio
    async def test_app_with_mock_display(self, mock_circuitpython_imports, mock_display):
        """Test app integration with mocked display."""
        
        class IntegrationApp(SLDKApp):
            async def setup(self):
                pass
            
            async def update_data(self):
                from sldk.content import StaticText
                text = StaticText("Integration Test", x=5, y=5, color=0x00FFFF, duration=3)
                self.content_queue.add_content(text)
        
        app = IntegrationApp(enable_web=False)
        
        # Mock the display creation
        with patch.object(app, 'create_display', return_value=mock_display):
            display = await app.create_display()
            
            assert display == mock_display
            assert display.width == 64
            assert display.height == 32
    
    def test_app_version_access(self, mock_circuitpython_imports):
        """Test accessing SLDK version through app."""
        app = SLDKApp(enable_web=False)
        
        # Should be able to access version
        assert hasattr(sldk, '__version__')
        assert isinstance(sldk.__version__, str)