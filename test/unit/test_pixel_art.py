"""Art repair: the two hand-authoring typos must not stop a sign from drawing.

Both fixtures below are the real failures, not invented ones. Across six
documented model-written signs every first-attempt crash was one of these two
and nothing else, each costing a full regeneration round.
"""

from scrollkit.utils.pixel_art import art_problems, normalize_art, normalize_all

SLOTS = {".": 0, " ": 0, "d": 1, "r": 2}

# gf_chapter2/gpt-5_6-sol attempt0: one row of 25 where its neighbours are 26,
# in a 598-line program with 34 sprites. Cost two repair rounds.
LASER_SHEET = (
    "dddddddddddddddddddddddddd",
    "d.r.r.r.r.r.r.r.r.r.r.r.d",
    "dddddddddddddddddddddddddd",
)


def _convert(rows, slots):
    """The conversion loop the pixel-art guide teaches. Must not raise."""
    width = len(rows[0])
    return [[slots[ch] for ch in row] for row in rows if len(row) == width]


class TestRaggedRows:
    def test_detected(self):
        assert art_problems(LASER_SHEET, SLOTS, name="LASER_SHEET") == [
            "LASER_SHEET: ragged rows, widths [25, 26]"]

    def test_padded_to_the_widest_row(self):
        fixed = normalize_art(LASER_SHEET, SLOTS, report=lambda _m: None)
        assert set(len(row) for row in fixed) == {26}
        assert art_problems(fixed, SLOTS) == []
        assert len(_convert(fixed, SLOTS)) == 3      # no row dropped, no IndexError

    def test_pads_on_the_right_only(self):
        fixed = normalize_art(("##", "#"), {".": 0, "#": 1}, report=lambda _m: None)
        assert fixed == ("##", "#.")

    def test_reports_what_it_repaired(self):
        msgs = []
        normalize_art(LASER_SHEET, SLOTS, name="LASER_SHEET", report=msgs.append)
        assert len(msgs) == 1 and "padded 1 ragged row" in msgs[0]


class TestUnmappedCharacters:
    def test_detected(self):
        problems = art_problems(("..+..",), SLOTS, name="SPARK")
        assert problems == ["SPARK: characters not in the slot map: +"]

    def test_a_lit_character_stays_lit(self):
        """The whole sprite was drawn with '+'. Mapping it to transparent would
        silently delete it -- worse than the KeyError it replaces."""
        fixed = normalize_art(("..+..", ".+++.", "..+.."), SLOTS,
                              report=lambda _m: None)
        assert sum(1 for row in fixed for ch in row if SLOTS[ch]) == 5

    def test_picks_the_lowest_lit_slot_deterministically(self):
        fixed = normalize_art(("+",), SLOTS, report=lambda _m: None)
        assert fixed == ("d",)                       # slot 1, not slot 2

    def test_unmapped_whitespace_becomes_transparent(self):
        fixed = normalize_art(("#\t#",), {".": 0, "#": 1}, report=lambda _m: None)
        assert fixed == ("#.#",)

    def test_mapped_space_is_left_alone(self):
        hashes = {".": 0, " ": 0, "#": 1}
        assert normalize_art(("##  ##",), hashes, report=lambda _m: None) == ("##  ##",)

    def test_conversion_no_longer_raises(self):
        rows = normalize_art(("..+..", ".+++.", "..+.."), SLOTS,
                             report=lambda _m: None)
        _convert(rows, SLOTS)                        # KeyError('+') before


class TestContract:
    def test_clean_art_is_untouched(self):
        clean = (".d.", "ddd", ".d.")
        assert normalize_art(clean, SLOTS, report=lambda _m: None) == clean

    def test_idempotent(self):
        once = normalize_art(LASER_SHEET, SLOTS, report=lambda _m: None)
        assert normalize_art(once, SLOTS, report=lambda _m: None) == once

    def test_empty_art_is_not_a_crash(self):
        assert normalize_art((), SLOTS, report=lambda _m: None) == ()
        assert art_problems((), SLOTS) == ["no rows"]

    def test_width_only_when_no_slot_map(self):
        assert normalize_art(("+++", "+"), None, report=lambda _m: None) == ("+++", "+..")

    def test_normalize_all_does_not_mutate_its_input(self):
        art = {"a": ("##", "#")}
        out = normalize_all(art, {".": 0, "#": 1}, report=lambda _m: None)
        assert art == {"a": ("##", "#")}
        assert out == {"a": ("##", "#.")}

    def test_report_defaults_to_visible(self, capsys):
        """A silent repair would hide a real mistake."""
        normalize_art(LASER_SHEET, SLOTS, name="LASER_SHEET")
        assert "padded 1 ragged row" in capsys.readouterr().out


class TestCircuitPythonSafety:
    """The device has no str.translate/maketrans and no random.shuffle."""

    ABSENT = {"maketrans", "translate", "shuffle", "sample", "choices", "gauss"}

    def test_calls_no_absent_methods(self):
        """AST, not grep -- the module's own comments name these APIs."""
        import ast
        import inspect

        from scrollkit.utils import pixel_art
        tree = ast.parse(inspect.getsource(pixel_art))
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    called.add(func.attr)
                elif isinstance(func, ast.Name):
                    called.add(func.id)
        offenders = called & self.ABSENT
        assert not offenders, "pixel_art calls %s, absent on CircuitPython" % offenders
