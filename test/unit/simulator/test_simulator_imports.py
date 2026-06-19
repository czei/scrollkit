#!/usr/bin/env python3
"""Unit tests for simulator imports."""

import pytest
import sys
import os

# Add path to enable scrollkit imports
scrollkit_src_path = os.path.join(os.path.dirname(__file__), '../../../src')
if scrollkit_src_path not in sys.path:
    sys.path.insert(0, scrollkit_src_path)


class TestSimulatorImports:
    """Test cases for simulator module imports."""
    
    def test_simulator_module_exists(self):
        """Test that simulator module can be imported."""
        try:
            import scrollkit.simulator
            assert scrollkit.simulator is not None
        except ImportError:
            pytest.fail("Could not import scrollkit.simulator module")
    
    def test_displayio_import(self):
        """Test that displayio can be imported from simulator."""
        try:
            from scrollkit.simulator import displayio
            assert displayio is not None
        except ImportError:
            pytest.fail("Could not import displayio from scrollkit.simulator")
    
    def test_core_components_import(self):
        """Test that core components can be imported."""
        try:
            from scrollkit.simulator.core import LEDMatrix, PixelBuffer, DisplayManager
            assert LEDMatrix is not None
            assert PixelBuffer is not None
            assert DisplayManager is not None
        except ImportError:
            pytest.fail("Could not import core components from scrollkit.simulator")
    
    def test_devices_import(self):
        """Test that device classes can be imported."""
        try:
            from scrollkit.simulator.devices.matrixportal_s3 import MatrixPortalS3
            assert MatrixPortalS3 is not None
        except ImportError:
            pytest.fail("Could not import MatrixPortalS3 from scrollkit.simulator")
    
    def test_adafruit_compatibility_imports(self):
        """Test that Adafruit compatibility layers can be imported."""
        try:
            from scrollkit.simulator.adafruit_display_text.label import Label
            from scrollkit.simulator.adafruit_bitmap_font import bitmap_font
            from scrollkit.simulator.terminalio import FONT
            assert Label is not None
            assert bitmap_font is not None
            assert FONT is not None
        except ImportError:
            pytest.fail("Could not import Adafruit compatibility layers")
    
    def test_fonts_directory_exists(self):
        """Test that fonts directory exists and contains BDF files."""
        import scrollkit.simulator
        simulator_path = os.path.dirname(scrollkit.simulator.__file__)
        fonts_path = os.path.join(simulator_path, 'fonts')
        
        assert os.path.exists(fonts_path), "Fonts directory should exist"
        
        # Check for at least one BDF font file
        bdf_files = [f for f in os.listdir(fonts_path) if f.endswith('.bdf')]
        assert len(bdf_files) > 0, "Should contain at least one BDF font file"


class TestSimulatorIntegration:
    """Integration tests for simulator components."""
    
    def test_simulator_in_scrollkit_main_import(self):
        """Test that simulator is available from main SLDK package."""
        try:
            import scrollkit
            # simulator should be available, even if None when not installed
            assert hasattr(scrollkit, 'simulator')
        except ImportError:
            pytest.fail("Could not import scrollkit package")
    
    @pytest.mark.skipif(
        not pytest.importorskip("pygame", minversion="2.0.0"),
        reason="pygame 2.0+ required for simulator"
    )
    def test_matrixportal_s3_creation(self):
        """Test that MatrixPortal S3 device can be created (requires pygame)."""
        try:
            from scrollkit.simulator.devices.matrixportal_s3 import MatrixPortalS3
            device = MatrixPortalS3(width=64, height=32)
            assert device is not None
            assert device.width == 64
            assert device.height == 32
        except ImportError:
            pytest.skip("pygame not available, skipping device creation test")