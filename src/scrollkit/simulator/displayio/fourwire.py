"""CircuitPython displayio.FourWire equivalent."""


class FourWire:
    """FourWire interface for display communication.
    
    This is a stub implementation for API compatibility.
    The simulator doesn't need actual SPI communication.
    """
    
    def __init__(self, spi_bus, *, command=None, chip_select=None, reset=None, 
                 baudrate=24000000, polarity=0, phase=0):
        """Initialize FourWire interface.
        
        Args:
            spi_bus: SPI bus object (ignored in simulator)
            command: Command pin (ignored in simulator)
            chip_select: Chip select pin (ignored in simulator)
            reset: Reset pin (ignored in simulator)
            baudrate: SPI baudrate (ignored in simulator)
            polarity: SPI polarity (ignored in simulator)
            phase: SPI phase (ignored in simulator)
        """
        self.spi_bus = spi_bus
        self.command = command
        self.chip_select = chip_select
        self.reset = reset
        self.baudrate = baudrate
        self.polarity = polarity
        self.phase = phase
        self._locked = False
        
    def reset(self):
        """Reset the display (no-op in simulator)."""
        pass
        
    def send(self, command, data):
        """Send command and data (no-op in simulator).
        
        Args:
            command: Command byte
            data: Data bytes
        """
        pass
        
    def __enter__(self):
        """Context manager entry."""
        self._locked = True
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self._locked = False