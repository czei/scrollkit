"""
Factory for creating the appropriate display implementation.
Uses GenericDisplay from the ScrollKit Library, which works on both CircuitPython
and the SLDK Simulator.
Copyright 2024 3DUPFitters LLC
"""
import sys
from scrollkit.utils.error_handler import ErrorHandler
from scrollkit.display.generic_display import GenericDisplay

logger = ErrorHandler("error_log")


def is_circuitpython():
    """Check if running on CircuitPython."""
    return hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython'


def is_dev_mode():
    """Check if running in development mode."""
    return '--dev' in sys.argv


def use_simple_simulator():
    """Check if simple simulator should be used."""
    return '--simple-sim' in sys.argv


def create_display(config=None):
    """
    Factory function to create the appropriate display.

    Uses the ScrollKit Library's GenericDisplay as the base, which auto-detects
    between CircuitPython hardware and the SLDK Simulator. Theme Park Waits
    extends GenericDisplay with application-specific content.

    Args:
        config: Optional configuration dictionary

    Returns:
        Display implementation appropriate for the current platform
    """
    if is_dev_mode() and use_simple_simulator():
        logger.info("Dev mode with --simple-sim, using simple simulator")
        try:
            from src.ui.simulator_display import SimulatedLEDMatrix
            return SimulatedLEDMatrix(config)
        except ImportError as e:
            logger.error(e, "Error importing simple simulator")

    try:
        from src.ui.unified_display import UnifiedDisplay
        logger.info(f"Creating UnifiedDisplay (extends ScrollKit GenericDisplay) "
                     f"for {'CircuitPython' if is_circuitpython() else 'Desktop/SLDK'}")
        return UnifiedDisplay(config)
    except ImportError as e:
        logger.error(e, "Error importing UnifiedDisplay")

        if is_circuitpython():
            try:
                from src.ui.hardware_display import MatrixDisplay
                logger.info("Falling back to legacy hardware display")
                return MatrixDisplay(config)
            except ImportError:
                logger.error(None, "Legacy hardware display also failed")
                from src.ui.display_base import Display
                return Display(config)
        else:
            try:
                from src.ui.sldk_simulator_display import SLDKSimulatorDisplay
                logger.info("Falling back to SLDK simulator display")
                return SLDKSimulatorDisplay(config)
            except ImportError:
                logger.info("Simulator not available, using GenericDisplay directly")
                return GenericDisplay(config)