# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""SLDK Display module.

Kept lean on purpose: importing this package must not drag in the heavier
optional pieces (DisplayManager/DisplayQueue/strategies), so a basic display app
stays small on the RAM-constrained device. Import those directly from their
modules when needed, e.g. ``from scrollkit.display.manager import DisplayManager``.
"""

from .content import ContentQueue, DisplayContent, ScrollingText, StaticText
from .unified import UnifiedDisplay

__all__ = ['ContentQueue', 'DisplayContent', 'ScrollingText', 'StaticText', 'UnifiedDisplay']