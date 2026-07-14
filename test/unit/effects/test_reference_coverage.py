"""The Visual Reference generator must have a sample for every live effect.

``demos/render_reference.py`` enumerates the effect sets from the LIVE selectors
(``supported_names`` / ``scrollers_for`` / ``palette_effects_for``) and renders one
sample per effect into ``docs/assets/reference/``. Its tailored per-effect config
(``TRANSITIONS`` / ``SCROLLERS`` / ``PALETTE``) must stay in lockstep with those
selectors — otherwise a newly added transition/scroller/palette effect would ship
with no documented sample. This test fails fast when that drifts, so the docs
gallery can't silently fall behind the code.

No rendering happens here (import + config comparison only), so it stays a cheap
unit test.
"""

import importlib.util
import os
import pathlib

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _load_generator():
    """Import ``demos/render_reference.py`` (not a package) by file path."""
    path = pathlib.Path(__file__).resolve().parents[3] / "demos" / "render_reference.py"
    spec = importlib.util.spec_from_file_location("render_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_transition_has_a_sample():
    rr = _load_generator()
    from scrollkit.effects.transitions import supported_names
    assert set(supported_names()) == set(rr.TRANSITIONS)


def test_every_scroller_has_a_sample():
    rr = _load_generator()
    from scrollkit.effects.scrolling import scrollers_for
    live = {c.__name__ for c in scrollers_for("scrolling") + scrollers_for("static")}
    assert live == set(rr.SCROLLERS)


def test_every_palette_effect_has_a_sample():
    rr = _load_generator()
    from scrollkit.display.bitmap_text import palette_effects_for
    live = {c.__name__ for c in
            palette_effects_for("static") + palette_effects_for("scrolling")}
    assert live == set(rr.PALETTE)


def test_every_image_animator_has_a_sample():
    rr = _load_generator()
    from scrollkit.effects.image_animators import ANIMATOR_CLASSES
    live = {c.__name__ for c in ANIMATOR_CLASSES}
    assert live == set(rr.IMAGE_ANIMATORS)
    # every referenced subject BMP is committed alongside the generator
    for bmp_name, *_ in rr.IMAGE_ANIMATORS.values():
        assert os.path.exists(os.path.join(rr.ANIMATOR_ART_DIR, bmp_name)), bmp_name


def test_build_jobs_enumerates_every_category_with_unique_slugs():
    rr = _load_generator()
    jobs = rr.build_jobs()
    slugs = [j["slug"] for j in jobs]
    assert len(slugs) == len(set(slugs)), "duplicate sample slug(s)"
    categories = {j["category"] for j in jobs}
    assert categories == {"transitions", "scrollers", "palette", "content",
                          "splashes", "treatments", "particles", "characters",
                          "animators", "gradient", "colors"}
    # a representative slug from each animated + still route resolves
    for slug in ("iris-snap", "kinetic-marquee", "rainbow-chase",
                 "scrollingtext-scroll", "drip", "velvet-sweep", "snow",
                 "owl-cel-flap", "twinkle-animator", "vertical", "spectrum",
                 "named-colors"):
        assert slug in slugs, slug


def test_every_palette_treatment_has_a_sample():
    rr = _load_generator()
    from scrollkit.effects.palette_treatments import TREATMENT_CLASSES
    live = {cls.__name__ for cls in TREATMENT_CLASSES}
    assert live == set(rr.TREATMENTS)


def test_character_samples_animate_the_reel_demos_own_art():
    """Every character sample must be generatable from the live showcase-reel
    demo — the tutorial (docs/guide/character-animation.md) quotes that code,
    so the sample config and the demo must not drift apart."""
    rr = _load_generator()
    reel = rr._load_reel()
    for name in ("OWL_FLY_UP", "OWL_FLY_DOWN", "BIG_OWL_UP", "BIG_OWL_MID",
                 "BIG_OWL_DOWN", "BEE_UP", "BEE_DOWN", "SPRITE_CHARS",
                 "SPRITE_COLORS", "_mirror", "_ease_in", "_ease_out"):
        assert hasattr(reel, name), name
    assert set(rr.CHARACTERS) == {"owl-flap", "owl-cel-flap", "owl-stoop",
                                  "bee-zigzag", "letter-drop"}
