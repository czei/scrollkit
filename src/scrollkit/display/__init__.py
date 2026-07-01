# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""ScrollKit Display module.

Kept lean on purpose: importing this package pulls in only the core content
model (``DisplayContent``/``ContentQueue``/text classes) and ``UnifiedDisplay``,
so a basic display app stays small on the RAM-constrained device. Heavier,
optional pieces (effects, the dev/simulator toolkits) are imported directly
from their own modules when needed.
"""

from .content import ContentQueue, DisplayContent, ScrollingText, StaticText
from .unified import UnifiedDisplay

__all__ = ['ContentQueue', 'DisplayContent', 'ScrollingText', 'StaticText', 'UnifiedDisplay']