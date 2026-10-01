"""Single-letter identifier lint, run by `make lint-python` from the repo root.

Fails when any given Python file binds a single-letter name (anything of
length 1 other than `_`): assignment / loop / comprehension / walrus targets,
function and lambda args, `except … as`, `with … as`, import aliases, match
captures, and def/class names. Names that are only read are not flagged.
There is no allowlist: a wire-format key that must stay short (a query param,
a JSON key) is mapped with a Pydantic `alias`, never kept as a Python name.
"""

from __future__ import annotations

import ast
import sys

ALLOWED_SHORT_NAME: str = "_"


def _is_single_letter(name: str | None) -> bool:
    return name is not None and len(name) == 1 and name != ALLOWED_SHORT_NAME


def _bound_names(node: ast.AST) -> list[str | None]:
    if isinstance(node, ast.Name):
        return [node.id] if isinstance(node.ctx, ast.Store) else []
    if isinstance(node, ast.arg):
        return [node.arg]
    if isinstance(node, ast.ExceptHandler):
        return [node.name]
    if isinstance(node, ast.alias):
        return [node.asname]
    if isinstance(node, (ast.MatchAs, ast.MatchStar)):
        return [node.name]
    if isinstance(node, ast.MatchMapping):
        return [node.rest]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    return []


def find_single_letter_names(source: str | bytes, path: str) -> list[str]:
    findings: list[tuple[int, int, str]] = []
    for node in ast.walk(ast.parse(source, filename=path)):
        for name in _bound_names(node):
            if _is_single_letter(name):
                findings.append(
                    (getattr(node, "lineno", 0), getattr(node, "col_offset", 0), name)
                )
    return [
        f"{path}:{line_number}:{column} {name}"
        for line_number, column, name in sorted(findings)
    ]


def main(argv: list[str] | None = None) -> None:
    paths = sys.argv[1:] if argv is None else argv
    findings: list[str] = []
    for path in paths:
        with open(path, "rb") as source_file:
            source = source_file.read()
        try:
            findings.extend(find_single_letter_names(source, path))
        except (SyntaxError, UnicodeDecodeError, ValueError) as parse_error:
            findings.append(f"{path}: could not parse ({parse_error})")
    if findings:
        sys.exit(
            "Single-letter names are not allowed (rename descriptively):\n"
            + "\n".join(findings)
        )


if __name__ == "__main__":
    main()
