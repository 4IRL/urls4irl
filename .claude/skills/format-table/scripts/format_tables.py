#!/usr/bin/env python3
"""Validate and auto-fix alignment in markdown files.

Handles two types of alignment:
1. Markdown tables (pipe-delimited): pads cells so | borders align vertically
2. ASCII box diagrams (box-drawing chars in code blocks): normalizes line widths

Usage:
    python format_tables.py <file>           # check only (exit 1 if misaligned)
    python format_tables.py <file> --fix     # fix in place
    python format_tables.py <dir>            # check all .md files recursively
    python format_tables.py <dir> --fix      # fix all .md files recursively
"""

import re
import sys
from collections import Counter
from pathlib import Path

BOX_CHARS = set("─│┌┐└┘├┤┬┴┼╔╗╚╝║═╠╣╦╩╬▼▲►◄")


def parse_table_row(line):
    cells = line.strip().strip("|").split("|")
    return [cell.strip() for cell in cells]


def is_separator_row(cells):
    return all(re.match(r"^:?-+:?$", cell.strip()) for cell in cells if cell.strip())


def format_table(lines):
    rows = [parse_table_row(line) for line in lines]
    num_cols = max(len(row) for row in rows)

    for row in rows:
        while len(row) < num_cols:
            row.append("")

    col_widths = []
    for col_idx in range(num_cols):
        max_width = max(len(row[col_idx]) for row in rows)
        col_widths.append(max(max_width, 3))

    formatted = []
    for row_idx, row in enumerate(rows):
        # GFM spec: row index 1 is always the header-separator row (e.g. |---|---|)
        if row_idx == 1 and is_separator_row(row):
            cells = ["-" * col_widths[col_idx] for col_idx in range(num_cols)]
        else:
            cells = [
                row[col_idx].ljust(col_widths[col_idx]) for col_idx in range(num_cols)
            ]
        formatted.append("| " + " | ".join(cells) + " |")

    return formatted


def find_tables(lines):
    tables = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].rstrip()
        if re.match(r"^\s*\|.*\|.*\|", line):
            start = idx
            while idx < len(lines) and re.match(r"^\s*\|.*\|", lines[idx].rstrip()):
                idx += 1
            if idx - start >= 2:
                tables.append((start, idx))
        else:
            idx += 1
    return tables


def has_box_chars(line):
    return any(c in BOX_CHARS for c in line)


def find_box_diagrams(lines):
    diagrams = []
    idx = 0
    in_code_block = False
    code_start = -1

    while idx < len(lines):
        stripped = lines[idx].rstrip()
        if stripped.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_start = idx + 1
            else:
                if code_start < idx:
                    block_lines = [lines[i].rstrip() for i in range(code_start, idx)]
                    segments = split_into_segments(block_lines, code_start)
                    diagrams.extend(segments)
                in_code_block = False
        idx += 1

    return diagrams


def split_into_segments(block_lines, global_offset):
    segments = []
    box_lines = []

    for i, bline in enumerate(block_lines):
        if has_box_chars(bline):
            box_lines.append((i, len(bline)))

    if len(box_lines) < 3:
        return segments

    groups = []
    current_group = [box_lines[0]]

    for curr in box_lines[1:]:
        curr_w = curr[1]
        group_widths = [w for _, w in current_group]
        most_common_w = Counter(group_widths).most_common(1)[0][0]

        if abs(curr_w - most_common_w) <= 2:
            current_group.append(curr)
        else:
            groups.append(current_group)
            current_group = [curr]

    groups.append(current_group)

    for group in groups:
        if len(group) < 3:
            continue
        start_idx = group[0][0]
        end_idx = group[-1][0] + 1
        segments.append((global_offset + start_idx, global_offset + end_idx))

    return segments


def find_rightmost_border_col(line):
    for i in range(len(line) - 1, -1, -1):
        if line[i] in "│┐┘┤╣╗╝║":
            return i
    return -1


def fix_box_diagram(lines, target_width):
    changed = False
    result = []

    for original_line in lines:
        stripped = original_line.rstrip()
        current_width = len(stripped)

        if not has_box_chars(stripped) or current_width == target_width:
            result.append(stripped)
            continue

        diff = current_width - target_width
        right_border = find_rightmost_border_col(stripped)

        if right_border == -1:
            result.append(stripped)
            continue

        trailing = stripped[right_border:]
        prefix = stripped[:right_border]

        gap_match = re.search(r"(\s+)$", prefix)
        if gap_match:
            gap = gap_match.group(1)
            before_gap = prefix[: gap_match.start()]
            new_gap_len = len(gap) - diff

            if new_gap_len >= 0:
                result.append(before_gap + " " * new_gap_len + trailing)
                changed = True
                continue

        if diff < 0:
            result.append(prefix + " " * (-diff) + trailing)
            changed = True
        else:
            result.append(stripped)

    return result, changed


def check_tables(filepath, lines, fix, new_lines):
    tables = find_tables(lines)
    all_aligned = True

    for start, end in reversed(tables):
        table_lines = [lines[i].rstrip() for i in range(start, end)]
        formatted = format_table(table_lines)

        if table_lines != formatted:
            all_aligned = False
            if not fix:
                print(f"{filepath}:{start + 1}-{end}: misaligned table")
                for orig, fixed in zip(table_lines, formatted):
                    if orig != fixed:
                        print(f"  - {orig}")
                        print(f"  + {fixed}")
            else:
                new_lines[start:end] = formatted

    return all_aligned


VERTICAL_CHARS = set("│┼┬┴├┤╣╠╬║")
BORDER_CROSSING_CHARS = set("┼┬┴├┤╣╠╬")
HORIZONTAL_BORDER_CHARS = set("─┌┐└┘┬┴┼├┤═╔╗╚╝╦╩╬╠╣")


def is_border_line(line):
    non_space = [c for c in line if c != " "]
    if not non_space:
        return False
    border_count = sum(1 for c in non_space if c in HORIZONTAL_BORDER_CHARS)
    return border_count > len(non_space) * 0.5


def find_nearby_vertical_chars(diagram_lines, row, col, direction, max_gap=5):
    step = 1 if direction == "down" else -1
    found = []
    gap = 0
    current = row + step
    while 0 <= current < len(diagram_lines) and gap <= max_gap:
        dline = diagram_lines[current]
        if col < len(dline) and dline[col] in VERTICAL_CHARS:
            found.append(current)
            gap = 0
        else:
            gap += 1
        current += step
    return found


def check_vertical_pipe_alignment(filepath, lines, start, end):
    diagram_lines = [lines[i].rstrip() for i in range(start, end)]
    if not diagram_lines:
        return True

    max_width = max((len(dl) for dl in diagram_lines), default=0)
    issues = []

    for row_idx, dline in enumerate(diagram_lines):
        if not is_border_line(dline):
            continue

        for col in range(len(dline)):
            if dline[col] not in BORDER_CROSSING_CHARS:
                continue

            above = find_nearby_vertical_chars(diagram_lines, row_idx, col, "up")
            below = find_nearby_vertical_chars(diagram_lines, row_idx, col, "down")
            same_col_neighbors = len(above) + len(below)

            if same_col_neighbors >= 1:
                continue

            for offset in [-1, 1]:
                adj_col = col + offset
                if adj_col < 0 or adj_col >= max_width:
                    continue

                adj_above = find_nearby_vertical_chars(
                    diagram_lines, row_idx, adj_col, "up"
                )
                adj_below = find_nearby_vertical_chars(
                    diagram_lines, row_idx, adj_col, "down"
                )
                adj_count = len(adj_above) + len(adj_below)

                if adj_count >= 2:
                    issues.append(
                        (
                            start + row_idx + 1,
                            col,
                            adj_col,
                            dline[col],
                            adj_count,
                        )
                    )
                    break

    if issues:
        for line_num, border_col, content_col, char, count in issues:
            direction = "right" if content_col > border_col else "left"
            print(
                f"{filepath}:{line_num}: vertical pipe misalignment — "
                f"border '{char}' at col {border_col} but {count} neighbor "
                f"rows have │ at col {content_col} (1 col to the {direction})"
            )

    return len(issues) == 0


def fix_vertical_pipe_alignment(lines, start, end):
    diagram_lines = [lines[i].rstrip() for i in range(start, end)]
    if not diagram_lines:
        return False

    max_width = max((len(dl) for dl in diagram_lines), default=0)
    changed = False

    for row_idx, dline in enumerate(diagram_lines):
        if not is_border_line(dline):
            continue

        for col in range(len(dline)):
            if dline[col] not in BORDER_CROSSING_CHARS:
                continue

            above = find_nearby_vertical_chars(diagram_lines, row_idx, col, "up")
            below = find_nearby_vertical_chars(diagram_lines, row_idx, col, "down")
            if len(above) + len(below) >= 1:
                continue

            for offset in [-1, 1]:
                adj_col = col + offset
                if adj_col < 0 or adj_col >= max_width:
                    continue

                adj_above = find_nearby_vertical_chars(
                    diagram_lines, row_idx, adj_col, "up"
                )
                adj_below = find_nearby_vertical_chars(
                    diagram_lines, row_idx, adj_col, "down"
                )
                if len(adj_above) + len(adj_below) < 2:
                    continue

                row = list(dline)
                crossing_char = row[col]
                row[col] = "─"
                row[adj_col] = crossing_char

                new_line = "".join(row)
                target_width = len(dline)

                if len(new_line) != target_width:
                    right_border = find_rightmost_border_col(new_line)
                    if right_border > 0:
                        trailing = new_line[right_border:]
                        prefix = new_line[:right_border]
                        gap_match = re.search(r"(\s+)$", prefix)
                        if gap_match:
                            gap_len = len(gap_match.group(1))
                            diff = len(new_line) - target_width
                            new_gap = gap_len - diff
                            if new_gap >= 0:
                                new_line = (
                                    prefix[: gap_match.start()]
                                    + " " * new_gap
                                    + trailing
                                )

                diagram_lines[row_idx] = new_line
                dline = new_line
                changed = True
                break

    if changed:
        for i, dl in enumerate(diagram_lines):
            lines[start + i] = dl

    return changed


def check_diagrams(filepath, lines, fix, new_lines):
    diagrams = find_box_diagrams(lines)
    all_aligned = True

    for start, end in reversed(diagrams):
        diagram_lines = [lines[i].rstrip() for i in range(start, end)]

        nonempty_box = [(i, l) for i, l in enumerate(diagram_lines) if has_box_chars(l)]
        if not nonempty_box:
            continue

        widths = [len(l) for _, l in nonempty_box]
        width_counts = Counter(widths)
        if len(set(widths)) > 1:
            target = width_counts.most_common(1)[0][0]
            bad_lines = [
                (start + i, w)
                for i, w in zip([x[0] for x in nonempty_box], widths)
                if w != target
            ]

            if bad_lines:
                all_aligned = False
                if not fix:
                    print(
                        f"{filepath}:{start + 1}-{end}: box diagram has "
                        f"inconsistent widths (target={target})"
                    )
                    for line_num, width in bad_lines:
                        print(
                            f"  line {line_num + 1}: width {width} (expected {target})"
                        )
                else:
                    fixed, changed = fix_box_diagram(diagram_lines, target)
                    if changed:
                        new_lines[start:end] = fixed

        vpipe_ok = check_vertical_pipe_alignment(filepath, lines, start, end)
        if not vpipe_ok:
            all_aligned = False
            if fix:
                fix_vertical_pipe_alignment(new_lines, start, end)

    return all_aligned


def check_file(filepath, fix=False):
    content = Path(filepath).read_text()
    lines = content.splitlines()
    new_lines = list(lines)

    tables_ok = check_tables(filepath, lines, fix, new_lines)
    diagrams_ok = check_diagrams(filepath, lines, fix, new_lines)

    all_ok = tables_ok and diagrams_ok

    if fix and not all_ok:
        had_trailing_newline = content.endswith("\n")
        output = "\n".join(new_lines)
        if had_trailing_newline:
            output += "\n"
        Path(filepath).write_text(output)
        print(f"{filepath}: fixed")

    return all_ok


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    target = Path(sys.argv[1])
    fix = "--fix" in sys.argv

    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = sorted(target.rglob("*.md"))
    else:
        print(f"Error: {target} not found")
        sys.exit(1)

    all_ok = True
    for filepath in files:
        if not check_file(filepath, fix=fix):
            all_ok = False

    if not fix and not all_ok:
        sys.exit(1)
    elif not fix and all_ok:
        print("All tables and diagrams aligned.")


if __name__ == "__main__":
    main()
