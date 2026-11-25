"""Guard: production frontend code must use `frontend/types/error-codes.ts`,
never hand-copied numeric error codes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
EXCLUDED_DIR_NAMES = {"__tests__", "node_modules", "vendor"}
GENERATED_FILE = FRONTEND_DIR / "types" / "error-codes.ts"

CONST_PATTERN = re.compile(r"(ERROR_CODE|ERR_[A-Z_]+)\s*[:=]\s*\d+")
COMPARE_PATTERN = re.compile(r"errorCode\s*[!=]==?\s*\d+")
REVERSED_COMPARE_PATTERN = re.compile(r"\d+\s*[!=]==?\s*[\w.?]*errorCode\b")
CODE_FIELD_PATTERN = re.compile(r"\bcode\s*:\s*\d+")
CASE_PATTERN = re.compile(r"\bcase\s+\d+\s*:")
SWITCH_PATTERN = re.compile(r"\bswitch\s*\(")


def _blank_comments(source: str) -> str:
    """Replace comments with spaces, keeping newlines so line numbers hold."""

    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return re.sub(r"/\*.*?\*/|//[^\n]*", blank, source, flags=re.DOTALL)


def _line_of(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def _match_close(source: str, open_index: int, open_ch: str, close_ch: str) -> int:
    """Index of the bracket closing the one at open_index, or -1."""
    depth = 0
    for index in range(open_index, len(source)):
        char = source[index]
        if char == open_ch:
            depth += 1
        elif char == close_ch:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _error_code_case_lines(source: str) -> list[int]:
    """Lines of `case N:` at the own depth of a `switch (...errorCode...)` body."""
    lines: list[int] = []
    for switch in SWITCH_PATTERN.finditer(source):
        paren_open = switch.end() - 1
        paren_close = _match_close(source, paren_open, "(", ")")
        if paren_close == -1 or "errorCode" not in source[paren_open:paren_close]:
            continue
        body_open = source.find("{", paren_close)
        if body_open == -1:
            continue
        body_close = _match_close(source, body_open, "{", "}")
        if body_close == -1:
            continue
        depth = 0
        for index in range(body_open, body_close + 1):
            char = source[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif depth == 1 and CASE_PATTERN.match(source, index):
                lines.append(_line_of(source, index))
    return lines


def scan_source(source: str) -> list[int]:
    """Sorted unique line numbers holding a hand-mirrored error code."""
    cleaned = _blank_comments(source)
    lines = {
        _line_of(cleaned, match.start())
        for pattern in (
            CONST_PATTERN,
            COMPARE_PATTERN,
            REVERSED_COMPARE_PATTERN,
            CODE_FIELD_PATTERN,
        )
        for match in pattern.finditer(cleaned)
    }
    lines.update(_error_code_case_lines(cleaned))
    return sorted(lines)


def _production_ts_files() -> list[Path]:
    files = []
    for path in FRONTEND_DIR.rglob("*.ts"):
        relative_parts = path.relative_to(FRONTEND_DIR).parts
        if EXCLUDED_DIR_NAMES.intersection(relative_parts):
            continue
        if path.name.endswith((".test.ts", ".d.ts")) or path == GENERATED_FILE:
            continue
        files.append(path)
    return sorted(files)


def test_scanner_flags_error_code_switch_case():
    """
    GIVEN a switch on errorCode with a numeric case
    WHEN the source is scanned
    THEN the case line is flagged
    """
    source = "switch (errorJson.errorCode) {\n  case 1: {\n    break;\n  }\n}\n"
    assert scan_source(source) == [2]


def test_scanner_ignores_http_status_switch():
    """
    GIVEN a switch on an HTTP status with numeric cases
    WHEN the source is scanned
    THEN nothing is flagged
    """
    source = "switch (xhr.status) {\n  case 400:\n  case 429: {\n  }\n}\n"
    assert scan_source(source) == []


def test_scanner_skips_nested_non_error_code_switch():
    """
    GIVEN an errorCode switch containing a nested status switch with numeric cases
    WHEN the source is scanned
    THEN the nested numeric cases are not flagged
    """
    source = (
        "switch (errorJson.errorCode) {\n"
        "  case Codes.A: {\n"
        "    switch (xhr.status) {\n"
        "      case 400:\n"
        "        break;\n"
        "    }\n"
        "    break;\n"
        "  }\n"
        "}\n"
    )
    assert scan_source(source) == []


def test_scanner_flags_error_code_constant():
    """
    GIVEN ERROR_CODE / ERR_* constants assigned numeric literals
    WHEN the source is scanned
    THEN those lines are flagged
    """
    assert scan_source("const FOO_ERROR_CODE = 4;\n") == [1]
    assert scan_source("const ERR_THING: number = 4;\nconst ERR_X = 5;\n") == [2]


def test_scanner_flags_inline_compare():
    """
    GIVEN an errorCode compared to a numeric literal
    WHEN the source is scanned
    THEN the line is flagged
    """
    assert scan_source("if (json.errorCode === 3) {}\n") == [1]


def test_scanner_flags_reversed_compare():
    """
    GIVEN a numeric literal compared against errorCode (literal on the left)
    WHEN the source is scanned
    THEN the line is flagged
    """
    assert scan_source("if (3 === json.errorCode) {}\n") == [1]
    assert scan_source("if (4 !== errorCode) {}\n") == [1]
    assert scan_source("if (4 == errorJson?.errorCode) {}\n") == [1]


def test_scanner_flags_code_object_field():
    """
    GIVEN an object literal with a numeric `code:` field
    WHEN the source is scanned
    THEN the line is flagged, but `code:` holding a non-literal is not
    """
    assert scan_source("const rule = { code: 4, action: x };\n") == [1]
    assert scan_source("const rule = { code: Codes.A, action: x };\n") == []
    assert scan_source("const n = { errorCode: Codes.A, status: 400 };\n") == []


def test_scanner_ignores_status_constants_and_comments():
    """
    GIVEN a status constant and a commented-out errorCode compare
    WHEN the source is scanned
    THEN nothing is flagged
    """
    source = "const NOT_FOUND_STATUS = 404;\n// errorCode === 3\n"
    assert scan_source(source) == []


def test_no_hand_mirrored_error_codes_in_production_frontend():
    """
    GIVEN the production frontend TypeScript files
    WHEN each is scanned
    THEN no hand-mirrored numeric error codes are found
    """
    scanned = _production_ts_files()
    if FRONTEND_DIR / "splash" / "login-form.ts" not in scanned:
        pytest.skip("full frontend tree not mounted (only frontend/types)")
    hits = []
    for path in scanned:
        for line in scan_source(path.read_text(encoding="utf-8")):
            hits.append(f"{path.relative_to(FRONTEND_DIR.parent)}:{line}")
    assert not hits, (
        "Hand-mirrored error codes (use types/error-codes.ts):\n" + "\n".join(hits)
    )
