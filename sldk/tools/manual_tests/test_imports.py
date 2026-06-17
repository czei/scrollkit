#!/usr/bin/env python3
"""Basic test of SLDK library structure."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

def test_imports():
    """Test that basic imports work."""
    print("Testing SLDK imports...")
    
    # Test basic import
    import sldk
    print(f"✓ SLDK version: {sldk.__version__}")
    
    # Test class imports
    from sldk import SLDKApp, ScrollingText, StaticText
    print("✓ Core classes imported")
    
    # Test display module
    from sldk.display import DisplayInterface, DisplayContent
    print("✓ Display module imported")
    
    # Test app module
    from sldk.app import SLDKApp as AppClass
    print("✓ App module imported")
    
    # Test content queue
    from sldk.display import ContentQueue
    queue = ContentQueue()
    print("✓ ContentQueue created")
    
    # Test unified display (might fail if simulator not installed)
    try:
        from sldk.display import UnifiedDisplay
        print("✓ UnifiedDisplay imported")
    except ImportError as e:
        print(f"⚠ UnifiedDisplay not available: {e}")
    
    print("\nAll basic imports successful!")

def test_content_creation():
    """Test creating display content."""
    print("\nTesting content creation...")
    
    from sldk import ScrollingText, StaticText
    
    # Create static text
    static = StaticText("Hello", x=10, y=10, color=0xFF0000, duration=5)
    print(f"✓ Created StaticText: '{static.text}' at ({static.x}, {static.y})")
    
    # Create scrolling text
    scroll = ScrollingText("Welcome to SLDK!", y=16, color=0x00FF00)
    print(f"✓ Created ScrollingText: '{scroll.text}'")
    
    print("\nContent creation successful!")

def test_app_structure():
    """Test app class structure."""
    print("\nTesting app structure...")
    
    from sldk import SLDKApp
    
    class TestApp(SLDKApp):
        async def setup(self):
            print("  - setup() called")
            
        async def update_data(self):
            print("  - update_data() called")
    
    # Create app instance
    app = TestApp(enable_web=False)
    print("✓ TestApp instance created")
    print(f"  - Web enabled: {app.enable_web}")
    print(f"  - Update interval: {app.update_interval}s")
    print(f"  - Content queue empty: {app.content_queue.is_empty}")
    
    print("\nApp structure test successful!")

if __name__ == "__main__":
    print("SLDK Basic Test Suite")
    print("=" * 50)
    
    try:
        test_imports()
        test_content_creation()
        test_app_structure()
        
        print("\n" + "=" * 50)
        print("All tests passed! ✓")
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()