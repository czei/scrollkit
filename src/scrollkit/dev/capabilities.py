# Copyright (c) 2024-2026 Michael Czeiszperger
"""Machine-readable catalog of what a ScrollKit app can use — for AI authoring.

``capabilities()`` returns a JSON-able dict describing the building blocks an
agent should reach for when writing an app: the panel geometry, the content
types and their constructor parameters, priority levels, the effect categories
(standalone splash/particle ``effects``, content-swap ``transitions``,
``scrolling`` presentations, BitmapText ``palette_effects``, and the
``image_animators`` that decorate a static image), named colors, and the display
drawing API — plus a pointer at the headless verification loop.

Everything is **introspected from live code** (the real ``Priority`` class, the
``effects`` package's ``__all__``, ``NAMED_COLORS``, the
``DisplayInterface`` methods, and the ``DisplayContent`` subclasses), so the
catalog can't silently drift out of sync with the library. Each lookup is
defensive: if a piece can't be imported, that section is simply omitted rather
than crashing the whole catalog.

Desktop-only (imported via ``scrollkit.dev``).
"""

import inspect

# The Adafruit MatrixPortal S3's standard HUB75 panel — the canonical target the
# simulator emulates. (Color is 24-bit RGB; the panel itself is far coarser.)
PANEL_WIDTH = 64
PANEL_HEIGHT = 32


def _first_line(obj):
    doc = inspect.getdoc(obj) or ""
    return doc.strip().split("\n", 1)[0] if doc else ""


def _init_params(cls):
    """``[{name, default}]`` for a class __init__, skipping self/var-args."""
    out = []
    try:
        sig = inspect.signature(cls.__init__)
    except (ValueError, TypeError):
        return out
    for name, p in sig.parameters.items():
        if name == "self" or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        default = None if p.default is inspect.Parameter.empty else p.default
        out.append({"name": name, "default": default})
    return out


def _content_types():
    from ..display import content as _content
    base = _content.DisplayContent
    types = []
    for name in dir(_content):
        obj = getattr(_content, name)
        if (inspect.isclass(obj) and issubclass(obj, base)
                and obj is not base
                and obj.__module__ == _content.__name__):
            types.append({"name": name, "doc": _first_line(obj),
                          "params": _init_params(obj),
                          "feasibility": getattr(obj, "FEASIBILITY", None)})
    types.sort(key=lambda t: t["name"])
    return types


def _text_fills():
    """Gradient text-fill capability for the Label-based content types.

    The fill *params* (``palette``/``direction``/``palette_steps``) already surface
    via ``_content_types`` signature introspection; this section adds the
    machine-usable detail an author needs — the valid directions and step bounds —
    read **live** from ``display.text_fill`` (never a hardcoded copy), so it can't
    drift from the renderer.
    """
    from ..display.text_fill import (DEFAULT_PALETTE_STEPS, MAX_PALETTE_STEPS,
                                     gradient_directions)
    return {
        "gradient": {
            "applies_to": ["StaticText", "ScrollingText"],
            "params": ["palette", "direction", "palette_steps"],
            "directions": list(gradient_directions()),
            "default_direction": "vertical",
            "default_palette_steps": DEFAULT_PALETTE_STEPS,
            "max_palette_steps": MAX_PALETTE_STEPS,
            "palette": ("a sequence of 2+ 0xRRGGBB stops (2 = simple gradient, 3+ "
                        "= multi-stop). When set, `color` is ignored. "
                        "depth_palette(color) derives a subtle close ramp from one "
                        "base colour. Static fill, zero per-frame cost — for "
                        "ANIMATED colour use BitmapText + a palette_effect."),
        }
    }


def _color_utilities():
    """Continuous colour generators/transforms (NOT named palettes).

    Surfaced as live signatures from ``display.colors`` so an author samples the
    full 24-bit space rather than reaching for a fixed named subset.
    """
    from ..display import colors as _c
    out = []
    for nm in ("gradient", "multi_gradient", "depth_palette", "spectrum",
               "hsv", "scale", "lerp", "wheel"):
        fn = getattr(_c, nm, None)
        if fn is None:
            continue
        try:
            sig = "%s%s" % (nm, inspect.signature(fn))
        except (ValueError, TypeError):
            sig = nm
        out.append({"name": nm, "signature": sig, "doc": _first_line(fn)})
    return out


def _priorities():
    from ..display.content import Priority
    levels = {}
    for name in dir(Priority):
        if name.isupper() and isinstance(getattr(Priority, name), int):
            levels[name] = getattr(Priority, name)
    return dict(sorted(levels.items(), key=lambda kv: kv[1]))


def _effects():
    """``[{name, doc}]`` for the standalone splash/particle effect classes.

    Deep-imports each submodule directly (``effects/__init__.py`` is
    deliberately import-free — see its docstring) so this catalog build never
    loads a heavier module than the one it's cataloging.
    """
    out = []
    try:
        from ..effects.particles import ParticleEngine, Sparkle, Snow
        for name, obj in (("ParticleEngine", ParticleEngine),
                          ("Sparkle", Sparkle), ("Snow", Snow)):
            out.append({"name": name, "doc": _first_line(obj)})
    except ImportError:
        pass
    try:
        from ..effects.drip_splash import DripReveal
        out.append({"name": "DripReveal", "doc": _first_line(DripReveal)})
    except ImportError:
        pass
    try:
        from ..effects.swarm_reveal import SwarmReveal
        out.append({"name": "SwarmReveal", "doc": _first_line(SwarmReveal)})
    except ImportError:
        pass
    try:
        from ..effects.palette_partition import PalettePartition
        out.append({"name": "PalettePartition",
                    "doc": _first_line(PalettePartition)})
    except ImportError:
        pass
    try:
        from ..effects.swirl_in import SwirlIn
        out.append({"name": "SwirlIn", "doc": _first_line(SwirlIn)})
    except ImportError:
        pass
    return out


def _image_animators():
    """``[{name, doc, feasibility}]`` for the per-frame image-layer animators.

    Its OWN category — these decorate a *static image already on screen* via the
    start/step/detach contract, distinct from the content-swap ``transitions`` and from
    the standalone splash/particle ``effects``. Enumerated via the module's explicit
    ``ANIMATOR_CLASSES`` catalog (not ``__subclasses__``) so the order is stable and the
    base ``IntroAnimator`` scaffolding is excluded. No ``pairs_with`` — they attach to an
    image, not to text presentations; ``feasibility`` is each class's FEASIBILITY budget.
    """
    out = []
    try:
        from ..effects.image_animators import ANIMATOR_CLASSES
    except ImportError:
        return out
    for cls in ANIMATOR_CLASSES:
        out.append({"name": cls.__name__, "doc": _first_line(cls),
                    "feasibility": getattr(cls, "FEASIBILITY", None)})
    return out


def _transitions():
    """``[{name, doc, feasibility, pairs_with}]`` for the built-in content-swap transitions.

    Enumerated via the explicit ``_TRANSITION_MAP`` (not ``Transition.__subclasses__``)
    so the duck-typed ``DropFromSky`` is included and the user-facing names match the
    settings UI. ``feasibility`` is each class's ``FEASIBILITY`` budget and
    ``pairs_with`` says which content style it suits (static / scrolling / fullscreen).
    """
    from ..effects.transitions import _TRANSITION_MAP
    out = []
    for name, cls in _TRANSITION_MAP.items():
        out.append({"name": name, "doc": _first_line(cls),
                    "feasibility": getattr(cls, "FEASIBILITY", None),
                    "pairs_with": list(getattr(cls, "PAIRS_WITH", ()))})
    return out


def _scrolling():
    """``[{name, doc, feasibility, pairs_with}]`` for the Class-1 scrolling effects.

    These ARE content presentations (DisplayContent subclasses); ``pairs_with`` says
    which content style each suits (see PAIRS_WITH in ``effects/scrolling.py``).
    """
    out = []
    try:
        from ..effects import scrolling as _sc
    except ImportError:
        return out
    for nm in ("KineticMarquee", "WaveRider", "SplitFlap"):
        cls = getattr(_sc, nm, None)
        if cls is not None:
            out.append({"name": nm, "doc": _first_line(cls),
                        "feasibility": getattr(cls, "FEASIBILITY", None),
                        "pairs_with": list(getattr(cls, "PAIRS_WITH", ()))})
    return out


def _palette_effects():
    """``[{name, doc, applies_to, pairs_with}]`` for the BitmapText palette animations.

    They animate the colour palette of bitmap text (no glyph rebuild); ``pairs_with``
    says they read well on static or scrolling text.
    """
    out = []
    try:
        from ..display import bitmap_text as _bt
    except ImportError:
        return out
    for nm in ("RainbowChase", "NeonTubeCrawl", "ChromeSheen", "HazardStripes",
               "MonoChase"):
        cls = getattr(_bt, nm, None)
        if cls is not None:
            out.append({"name": nm, "doc": _first_line(cls),
                        "applies_to": "BitmapText",
                        "pairs_with": list(getattr(cls, "PAIRS_WITH", ()))})
    return out


def _palette_treatments():
    """``[{name, doc, partition, feasibility}]`` for the partition dwell
    treatments (see :mod:`scrollkit.effects.palette_treatments`).

    Frame-driven classes animating a :class:`PalettePartition` purely with
    palette writes; ``partition`` names the recommended partition builder.
    Enumerated via the module's explicit ``TREATMENT_CLASSES`` catalog.
    """
    out = []
    try:
        from ..effects.palette_treatments import TREATMENT_CLASSES
    except ImportError:
        return out
    for cls in TREATMENT_CLASSES:
        out.append({"name": cls.__name__, "doc": _first_line(cls),
                    "partition": cls.PARTITION,
                    "feasibility": getattr(cls, "FEASIBILITY", None)})
    return out


def _named_colors():
    """name -> 0xRRGGBB int, from the tooling color table (deduped)."""
    from ..utils.color_utils import NAMED_COLORS
    colors = {}
    for name, rgb in NAMED_COLORS.items():
        try:
            r, g, b = rgb
            colors[name] = (int(r) << 16) | (int(g) << 8) | int(b)
        except (TypeError, ValueError):
            continue
    return colors


def _display_api():
    from ..display.interface import DisplayInterface
    methods = []
    for name in dir(DisplayInterface):
        if name.startswith("_"):
            continue
        attr = inspect.getattr_static(DisplayInterface, name, None)
        is_prop = isinstance(attr, property)
        member = getattr(DisplayInterface, name, None)
        if not (is_prop or inspect.isfunction(member) or inspect.iscoroutinefunction(member)):
            continue
        entry = {"name": name, "property": is_prop, "doc": _first_line(member)}
        target = attr.fget if is_prop else member
        try:
            entry["signature"] = "%s%s" % (name, inspect.signature(target))
        except (ValueError, TypeError):
            entry["signature"] = name
        methods.append(entry)
    methods.sort(key=lambda m: m["name"])
    return methods


def _hardware():
    from ..simulator.core.hardware_profile import matrixportal_s3_profile
    p = matrixportal_s3_profile()
    ceiling = int(1_000_000 / p.full_refresh_us) if p.full_refresh_us else 0
    return {
        "target": p.name,
        "usable_ram_bytes": p.usable_ram_bytes,
        "confidence": p.confidence,
        "calibrated": p.is_calibrated,
        "refresh_fps_ceiling": ceiling,
        "guidance": ("Every frame pays one display.refresh() (~%d us, a hard "
                     "ceiling near %d FPS) plus a glyph-bitmap rebuild for any "
                     "text that changed. Redrawing many text fields every frame "
                     "is the main way to fall to single-digit FPS — cache Labels "
                     "and only change .text when the value changes. RAM budget is "
                     "~%d KB." % (round(p.full_refresh_us), ceiling,
                                  p.usable_ram_bytes // 1024)),
    }


def _performance():
    from .performance import performance_guide
    return performance_guide()


def capabilities():
    """Return the JSON-able capability catalog (see module docstring).

    Sections are best-effort: any that can't be introspected is omitted, so the
    call never fails just because one optional submodule is missing.
    """
    cat = {
        "panel": {
            "width": PANEL_WIDTH,
            "height": PANEL_HEIGHT,
            "color": "24-bit RGB int 0xRRGGBB, or an (r, g, b) tuple (0-255 each)",
            "note": "Adafruit MatrixPortal S3 standard 64x32 panel",
            "coordinates": {
                "origin": "top-left",
                "x": "rightward, 0..%d" % (PANEL_WIDTH - 1),
                "y": "downward, 0..%d" % (PANEL_HEIGHT - 1),
                "y_anchor": "baseline",
                "note": ("(0, 0) is the top-left corner; x grows right, y grows "
                         "down (standard displayio). y sets the text baseline, "
                         "not the glyph top, so y=0 clips a line off the top. "
                         "For the 8px font, y=12 vertically centers one line."),
            },
        },
        "verification": (
            "Build a scrollkit.app.base.ScrollKitApp subclass, then run it "
            "headless with scrollkit.dev.run_headless(app, frames=N, "
            "screenshot=path) to get rendered-pixel metrics and an estimated "
            "hardware feasibility report. Use scrollkit.dev.validate(app) for "
            "structured pre-flight checks."
        ),
    }
    for key, fn in (("content_types", _content_types), ("priorities", _priorities),
                    ("effects", _effects), ("transitions", _transitions),
                    ("scrolling", _scrolling), ("palette_effects", _palette_effects),
                    ("palette_treatments", _palette_treatments),
                    ("image_animators", _image_animators),
                    ("text_fills", _text_fills), ("color_utilities", _color_utilities),
                    ("named_colors", _named_colors),
                    ("display_api", _display_api), ("hardware", _hardware),
                    ("performance", _performance)):
        try:
            cat[key] = fn()
        except Exception as e:  # one bad section shouldn't sink the catalog
            cat[key] = {"error": "introspection failed: %r" % (e,)}
    return cat


def as_text(cat=None):
    """Render the catalog as a compact human/AI-readable summary."""
    cat = cat or capabilities()
    lines = ["=== ScrollKit capabilities ==="]
    p = cat.get("panel", {})
    lines.append("Panel: %sx%s, color=%s" % (p.get("width"), p.get("height"),
                                             p.get("color")))
    coords = p.get("coordinates")
    if isinstance(coords, dict) and coords.get("note"):
        lines.append("Coordinates: %s" % coords["note"])
    ct = cat.get("content_types")
    if isinstance(ct, list):
        lines.append("Content types:")
        for t in ct:
            params = ", ".join(
                "%s=%r" % (q["name"], q["default"]) if q["default"] is not None
                else q["name"] for q in t["params"])
            lines.append("  - %s(%s) — %s" % (t["name"], params, t["doc"]))
    pr = cat.get("priorities")
    if isinstance(pr, dict):
        lines.append("Priorities: " + ", ".join("%s=%d" % (k, v)
                                                 for k, v in pr.items()))
    fx = cat.get("effects")
    if isinstance(fx, list) and fx:
        lines.append("Effects: " + ", ".join(e["name"] for e in fx))
    def _pairs(e):
        pw = e.get("pairs_with")
        return " [best on: %s]" % ", ".join(pw) if pw else ""
    tr = cat.get("transitions")
    if isinstance(tr, list) and tr:
        lines.append("Transitions (transition_style setting):")
        for t in tr:
            feas = t.get("feasibility") or {}
            ms = feas.get("modeled_frame_ms")
            budget = " (~%sms/frame)" % ms if ms is not None else ""
            lines.append("  - %s%s%s — %s" % (t["name"], budget, _pairs(t), t["doc"]))
    sc = cat.get("scrolling")
    if isinstance(sc, list) and sc:
        lines.append("Scrolling effects:")
        for e in sc:
            lines.append("  - %s%s — %s" % (e["name"], _pairs(e), e["doc"]))
    pe = cat.get("palette_effects")
    if isinstance(pe, list) and pe:
        lines.append("Palette effects (on BitmapText):")
        for e in pe:
            lines.append("  - %s%s — %s" % (e["name"], _pairs(e), e["doc"]))
    ia = cat.get("image_animators")
    if isinstance(ia, list) and ia:
        lines.append("Image animators (decorate a static image on screen):")
        for e in ia:
            feas = e.get("feasibility") or {}
            ms = feas.get("modeled_frame_ms")
            budget = " (~%sms/frame)" % ms if ms is not None else ""
            lines.append("  - %s%s — %s" % (e["name"], budget, e["doc"]))
    tf = cat.get("text_fills")
    if isinstance(tf, dict) and isinstance(tf.get("gradient"), dict):
        g = tf["gradient"]
        lines.append("Text fills: gradient palette=(c1,c2[,...]) direction=%s on %s"
                     % ("|".join(g.get("directions", [])),
                        "/".join(g.get("applies_to", []))))
    cu = cat.get("color_utilities")
    if isinstance(cu, list) and cu:
        lines.append("Color utilities: " + ", ".join(u["name"] for u in cu))
    nc = cat.get("named_colors")
    if isinstance(nc, dict) and nc:
        lines.append("Named colors: " + ", ".join(sorted(nc)))
    hw = cat.get("hardware")
    if isinstance(hw, dict) and "guidance" in hw:
        lines.append("Hardware: %s" % hw["guidance"])
    return "\n".join(lines)
