# Copyright (c) 2024-2026 Michael Czeiszperger
"""Surface backend for the LED-panel renderer: pygame when present, numpy when not.

``led_matrix`` draws the panel's *appearance* — the near-black ground, the unlit-LED
grid, the round dots with brighter cores, the additive glow halos — and that logic is
several hundred lines of ordinary Python. It needed pygame for exactly six things:

    Surface, SRCALPHA, draw.circle, transform.smoothscale, BLEND_RGB_ADD, image.save

pygame is a C extension around SDL, so those six calls are the *only* reason the
panel cannot be drawn in a browser. The logical pixel path (``PixelBuffer``) is pure
Python + numpy and runs anywhere; the cosmetic layer was stranded on the desktop by
six function calls.

This module supplies them in numpy so the appearance code stays in one place and one
language. Under Pyodide the whole simulator now renders — the real LED look, from the
same source — with no second renderer and no JavaScript.

**pygame stays primary wherever it exists.** ``backend()`` returns the pygame
implementation whenever pygame imports, so desktop output is untouched, byte for byte,
including the rendered hero stills the appearance constants were tuned against. The
numpy path is the fallback, and it is a close approximation rather than a clone: SDL's
``smoothscale`` is not specified pixel-for-pixel, and this uses an exact box average
over the supersampled image, which is what a downscale of an integer factor should be.
Frames may differ from pygame's by a least-significant bit here and there. The
*logical* framebuffer — what feasibility, attestation and cross-runtime comparison all
key on — is produced upstream in ``PixelBuffer`` and is unaffected either way.
"""

from __future__ import annotations

import numpy as np


# --- numpy implementation ---------------------------------------------------------

SRCALPHA = 0x00010000        # same spirit as pygame's flag; only identity matters
BLEND_RGB_ADD = 0x01


class NumpySurface:
    """The subset of pygame's Surface that the panel renderer uses.

    RGB is stored as ``(H, W, 3)`` uint8. Alpha is carried separately and only when
    the surface was created with :data:`SRCALPHA`, mirroring pygame: an RGB surface
    blits as opaque, an SRCALPHA surface blits blended.
    """

    __slots__ = ("rgb", "alpha", "_w", "_h")

    def __init__(self, size, flags=0):
        self._w, self._h = int(size[0]), int(size[1])
        self.rgb = np.zeros((self._h, self._w, 3), dtype=np.uint8)
        # pygame leaves an SRCALPHA surface fully transparent; an RGB one is opaque
        # black. Keeping alpha None for RGB avoids a needless plane per sprite.
        self.alpha = (np.zeros((self._h, self._w), dtype=np.uint8)
                      if flags & SRCALPHA else None)

    def get_size(self):
        return (self._w, self._h)

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def fill(self, color):
        self.rgb[:, :] = np.asarray(color[:3], dtype=np.uint8)
        if self.alpha is not None:
            self.alpha[:, :] = 255

    def blit(self, src, pos, special_flags=0):
        """Copy/blend ``src`` onto this surface at ``pos``, clipped to both surfaces."""
        dx, dy = int(pos[0]), int(pos[1])

        # Clip the source rect against this surface's bounds. A halo centred on an
        # edge LED hangs off the panel, so clipping is the common case, not the
        # exception.
        sx0 = max(0, -dx)
        sy0 = max(0, -dy)
        w = min(src._w - sx0, self._w - max(0, dx))
        h = min(src._h - sy0, self._h - max(0, dy))
        if w <= 0 or h <= 0:
            return

        dx0, dy0 = max(0, dx), max(0, dy)
        s_rgb = src.rgb[sy0:sy0 + h, sx0:sx0 + w]
        d_rgb = self.rgb[dy0:dy0 + h, dx0:dx0 + w]

        if special_flags & BLEND_RGB_ADD:
            # The glow pass. Halos are drawn on black so an additive blit contributes
            # only light, and overlapping halos sum the way a real panel bleeds.
            tmp = d_rgb.astype(np.uint16) + s_rgb
            np.clip(tmp, 0, 255, out=tmp)
            d_rgb[:] = tmp.astype(np.uint8)
            return

        if src.alpha is None:
            d_rgb[:] = s_rgb
            return

        a = src.alpha[sy0:sy0 + h, sx0:sx0 + w].astype(np.uint16)[..., None]
        # Rounded integer lerp: dst + (src - dst) * a / 255, done in uint16 so the
        # anti-aliased dot edges land on the same values pygame's blend produces.
        blended = (d_rgb.astype(np.uint16) * (255 - a) + s_rgb.astype(np.uint16) * a
                   + 127) // 255
        d_rgb[:] = blended.astype(np.uint8)

    def rgb_array(self):
        """This surface as an ``(H, W, 3)`` uint8 array — the panel as pixels.

        The browser preview and the GIF/MP4 recorder both want the *rendered panel*,
        not the logical framebuffer, so this is the numpy counterpart of
        ``pygame.surfarray.array3d`` (without the transpose, already in image order).
        """
        return self.rgb.copy()


def _draw_circle_numpy(surface, color, center, radius):
    """Filled, hard-edged circle — pygame.draw.circle's behaviour, not an AA one.

    Aliasing is correct here: every caller draws supersampled and then downscales,
    which is where the smooth edge comes from.
    """
    cx, cy = int(center[0]), int(center[1])
    r = max(0, int(radius))
    if r == 0:
        return

    x0, x1 = max(0, cx - r), min(surface._w, cx + r + 1)
    y0, y1 = max(0, cy - r), min(surface._h, cy + r + 1)
    if x1 <= x0 or y1 <= y0:
        return

    ys = np.arange(y0, y1)[:, None] - cy
    xs = np.arange(x0, x1)[None, :] - cx
    mask = (xs * xs + ys * ys) <= r * r

    surface.rgb[y0:y1, x0:x1][mask] = np.asarray(color[:3], dtype=np.uint8)
    if surface.alpha is not None:
        # pygame makes drawn pixels opaque on an SRCALPHA surface.
        surface.alpha[y0:y1, x0:x1][mask] = 255


def _smoothscale_numpy(surface, size):
    """Downscale by an exact box average (integer factors) — the supersample step.

    Every caller shrinks by a whole factor (ss = 2, 3 or 4), so a reshape-mean is
    both the exact area average and fast. Non-integer ratios fall back to nearest
    neighbour, which no current caller needs but which keeps this honest rather than
    silently wrong.
    """
    tw, th = int(size[0]), int(size[1])
    sw, sh = surface._w, surface._h
    out = NumpySurface((tw, th), SRCALPHA if surface.alpha is not None else 0)

    if tw <= 0 or th <= 0:
        return out

    if sw % tw == 0 and sh % th == 0:
        fx, fy = sw // tw, sh // th
        out.rgb[:] = (surface.rgb.reshape(th, fy, tw, fx, 3)
                      .mean(axis=(1, 3)) + 0.5).astype(np.uint8)
        if surface.alpha is not None:
            out.alpha[:] = (surface.alpha.reshape(th, fy, tw, fx)
                            .mean(axis=(1, 3)) + 0.5).astype(np.uint8)
        return out

    yi = (np.arange(th) * sh // th)
    xi = (np.arange(tw) * sw // tw)
    out.rgb[:] = surface.rgb[yi[:, None], xi[None, :]]
    if surface.alpha is not None:
        out.alpha[:] = surface.alpha[yi[:, None], xi[None, :]]
    return out


def _save_image_numpy(surface, path):
    """Write the surface as a PNG via Pillow (numpy path has no pygame.image.save)."""
    from PIL import Image
    Image.fromarray(surface.rgb_array(), mode="RGB").save(path)
    return path


class _NumpyBackend:
    """pygame-shaped facade over the functions above."""

    is_pygame = False
    SRCALPHA = SRCALPHA
    BLEND_RGB_ADD = BLEND_RGB_ADD

    Surface = staticmethod(NumpySurface)
    draw_circle = staticmethod(_draw_circle_numpy)
    smoothscale = staticmethod(_smoothscale_numpy)
    save_image = staticmethod(_save_image_numpy)

    @staticmethod
    def ensure_init():
        pass


class _PygameBackend:
    """The desktop path, unchanged: straight through to pygame."""

    is_pygame = True

    def __init__(self, pygame):
        self._pg = pygame
        self.SRCALPHA = pygame.SRCALPHA
        self.BLEND_RGB_ADD = pygame.BLEND_RGB_ADD
        self.Surface = pygame.Surface
        self.draw_circle = pygame.draw.circle
        self.smoothscale = pygame.transform.smoothscale
        self.save_image = pygame.image.save

    def ensure_init(self):
        if not self._pg.get_init():
            self._pg.init()


_backend = None


def backend():
    """The surface backend for this process: pygame if importable, else numpy.

    Cached, because the answer cannot change within a process and the panel renderer
    asks once per sprite build.
    """
    global _backend
    if _backend is None:
        try:
            import pygame
            _backend = _PygameBackend(pygame)
        except ImportError:
            _backend = _NumpyBackend()
    return _backend


def is_numpy_surface(obj):
    """True when ``obj`` came from the numpy backend (used by the frame recorder)."""
    return isinstance(obj, NumpySurface)
