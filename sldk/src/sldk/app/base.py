"""Base application class for SLDK.

Provides the three-process architecture with graceful degradation for ESP32.
"""

from __future__ import annotations

try:
    # Desktop Python
    import asyncio
    
    async def create_task(coro):
        return asyncio.create_task(coro)
    
    async def gather(*coros, return_exceptions=False):
        return await asyncio.gather(*coros, return_exceptions=return_exceptions)
    
    async def sleep(seconds):
        await asyncio.sleep(seconds)
        
except ImportError:
    # CircuitPython
    import asyncio
    
    # CircuitPython's asyncio is more limited
    async def create_task(coro):
        return asyncio.create_task(coro)
    
    async def gather(*coros, return_exceptions=False):
        # Simple implementation for CircuitPython
        results = []
        for coro in coros:
            try:
                result = await coro
                results.append(result)
            except Exception as e:
                if return_exceptions:
                    results.append(e)
                else:
                    raise
        return results
    
    async def sleep(seconds):
        await asyncio.sleep(seconds)

import gc
from typing import Optional, List
from ..display.content import ContentQueue
from ..display.interface import DisplayInterface
from ..exceptions import DisplayError, NetworkError


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
    
    # Core process implementations
    
    async def _display_process(self) -> None:
        """Process 1: Handle display updates."""
        print("Display process started")
        
        while self.running:
            try:
                # Get content to display
                content = await self.prepare_display_content()
                
                if content and self.display:
                    # Clear display first
                    await self.display.clear()
                    
                    # Render content
                    await content.render(self.display)
                    
                    # Update display
                    await self.display.show()
                
                # Control frame rate
                await sleep(0.05)  # 20 FPS
                
                # Report memory periodically
                await self._report_memory()
                
            except Exception as e:
                print(f"Display error: {e}")
                await sleep(1)
    
    async def _data_update_process(self) -> None:
        """Process 2: Handle data updates."""
        print("Data update process started")
        
        # Initial update
        try:
            await self.update_data()
        except Exception as e:
            print(f"Initial data update error: {e}")
        
        while self.running:
            try:
                # Wait for update interval
                await sleep(self.update_interval)
                
                # Check if we have enough memory
                gc.collect()
                free_memory = gc.mem_free() if hasattr(gc, 'mem_free') else 100000
                
                if free_memory > 20000:  # Need 20KB free
                    await self.update_data()
                else:
                    print(f"Skipping data update - low memory: {free_memory}")
                    
            except Exception as e:
                print(f"Data update error: {e}")
                await sleep(30)  # Back off on error
    
    async def create_web_server(self):
        """Create web server instance.
        
        Override this method to use custom web server configuration.
        
        Returns:
            SLDKWebServer instance or None
        """
        try:
            from ..web import SLDKWebServer
            return SLDKWebServer(app=self)
        except ImportError:
            return None
    
    async def _web_server_process(self) -> None:
        """Process 3: Handle web interface."""
        if not self.enable_web:
            return
            
        # Check if we have enough memory for web server
        gc.collect()
        free_memory = gc.mem_free() if hasattr(gc, 'mem_free') else 100000
        
        if free_memory < 50000:  # Need 50KB free
            print(f"Web server disabled - insufficient memory: {free_memory}")
            return
        
        try:
            # Create web server
            web_server = await self.create_web_server()
            if not web_server:
                print("Web server not available - install with 'pip install sldk[web]'")
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
            print("Web server not available - install with 'pip install sldk[web]'")
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
                free = gc.mem_free() if hasattr(gc, 'mem_free') else -1
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
            
            # Run setup
            await self.setup()
            
            # Create tasks based on available memory
            tasks = []
            
            # Display process always runs
            tasks.append(create_task(self._display_process()))
            
            # Data update process if memory allows
            gc.collect()
            free_memory = gc.mem_free() if hasattr(gc, 'mem_free') else 100000
            
            if free_memory > 30000:  # 30KB free
                tasks.append(create_task(self._data_update_process()))
            else:
                print(f"Data updates disabled - low memory: {free_memory}")
            
            # Web server if enabled and memory allows
            if self.enable_web and free_memory > 50000:
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