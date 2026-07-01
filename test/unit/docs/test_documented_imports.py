"""Every scrollkit import shown in README.md / docs/**/*.md must actually work.

This is the standing anti-drift gate for the public API surface: docs are the
contract users read, and nothing else verifies that a documented ``from
scrollkit.x.y import Z`` line still resolves after a refactor. A statement's
line can opt out with a trailing ``# device-only`` comment (e.g. hardware-only
imports that don't exist on desktop).
"""

import os
import pathlib
import re

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOC_FILES = [_REPO_ROOT / "README.md"] + sorted((_REPO_ROOT / "docs").rglob("*.md"))

_FENCE_RE = re.compile(r"^```python\s*$")
_FENCE_END_RE = re.compile(r"^```\s*$")
_IMPORT_RE = re.compile(
    r"^\s*(from\s+scrollkit[\w.]*\s+import\s+.+|import\s+scrollkit[\w.]*)\s*$"
)


def _extract_python_fences(text):
    """Yield (lineno, code_text) for each ```python ... ``` fenced block."""
    lines = text.splitlines()
    in_fence = False
    start_line = 0
    buf = []
    for i, line in enumerate(lines, start=1):
        if not in_fence and _FENCE_RE.match(line):
            in_fence = True
            start_line = i + 1
            buf = []
            continue
        if in_fence and _FENCE_END_RE.match(line):
            in_fence = False
            yield start_line, "\n".join(buf)
            continue
        if in_fence:
            buf.append(line)


def _collect_import_statements():
    seen = set()
    cases = []
    for doc_path in _DOC_FILES:
        if not doc_path.is_file():
            continue
        text = doc_path.read_text(encoding="utf-8")
        for fence_start, block in _extract_python_fences(text):
            block_lines = block.splitlines()
            i = 0
            while i < len(block_lines):
                line = block_lines[i]
                if "# device-only" in line:
                    i += 1
                    continue
                code_part = line.split("#", 1)[0].strip()
                if not code_part or not _IMPORT_RE.match(code_part):
                    i += 1
                    continue
                start_offset = i
                # Multi-line "from x import (\n  a, b,\n)" — join until parens balance.
                while code_part.count("(") > code_part.count(")"):
                    i += 1
                    next_line = block_lines[i].split("#", 1)[0].strip()
                    code_part += "\n" + next_line
                lineno = fence_start + start_offset
                rel_path = doc_path.relative_to(_REPO_ROOT)
                key = (str(rel_path), code_part)
                if key not in seen:
                    seen.add(key)
                    cases.append((str(rel_path), lineno, code_part))
                i += 1
    return cases


CASES = _collect_import_statements()


@pytest.mark.parametrize(
    "doc_file,lineno,stmt",
    CASES,
    ids=[f"{f}:{n}" for f, n, _ in CASES],
)
def test_documented_import_resolves(doc_file, lineno, stmt):
    if "scrollkit.dev" in stmt:
        pytest.importorskip("pygame")
    try:
        exec(compile(stmt, f"{doc_file}:{lineno}", "exec"), {})
    except ImportError as e:
        pytest.fail(f"{doc_file}:{lineno}: documented import fails: {stmt!r} -> {e}")


def test_at_least_one_documented_import_was_found():
    # Guards against the collector silently finding nothing (e.g. a regex typo)
    # and this whole test module becoming a no-op.
    assert len(CASES) > 5, "expected several documented scrollkit imports to check"
