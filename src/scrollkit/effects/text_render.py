# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Back-compat shim — the implementation now lives in ``display.text_pixels``.

``pixels_from_font_text`` / ``font_text_width`` (and the private ``_glyph_fields``
/ ``_MISSING_ADVANCE``) were relocated to ``scrollkit.display.text_pixels`` so the
gradient text-fill renderer in ``display/`` can share the one glyph→pixel
function without ``display`` importing ``effects`` (which would form a cycle and
pull the RAM-heavy particle/splash modules in just to render text).

Every existing import path keeps working unchanged:
``from scrollkit.effects import pixels_from_font_text`` and
``from .text_render import pixels_from_font_text`` both still resolve here.
"""

from ..display.text_pixels import (  # noqa: F401  (re-export)
    _MISSING_ADVANCE,
    _glyph_fields,
    font_text_width,
    pixels_from_font_text,
)

__all__ = ["pixels_from_font_text", "font_text_width"]
