---
name: format-table
description: Format markdown tables and ASCII box diagrams so all borders align vertically. Use this skill whenever writing, editing, or reviewing a markdown file with tables or box-drawing diagrams (plans, reviews, architecture docs, etc.) to ensure properly aligned columns and consistent line widths. Also use when asked to fix table or diagram formatting.
---

# Format Table

Ensure markdown tables have vertically aligned `|` borders and ASCII box diagrams have consistent line widths within each visual section.

## Usage

Run `scripts/format_tables.py` (located in this skill's directory) after writing or editing any markdown file containing tables or box diagrams.

```bash
# Check a single file (exit 1 if misaligned)
python .claude/skills/format-table/scripts/format_tables.py <file.md>

# Fix a single file in place
python .claude/skills/format-table/scripts/format_tables.py <file.md> --fix

# Check all .md files in a directory recursively
python .claude/skills/format-table/scripts/format_tables.py <dir>

# Fix all .md files in a directory recursively
python .claude/skills/format-table/scripts/format_tables.py <dir> --fix
```

## What It Fixes

### Markdown Tables
- Computes max content width per column
- Pads all cells and separator dashes to align `|` borders vertically

### ASCII Box Diagrams (in code blocks)
- Detects code blocks containing box-drawing characters (─│┌┐└┘┬┴┼ etc.)
- Groups lines into segments by width similarity (separate boxes at different widths are treated independently)
- Normalizes line widths within each segment by adjusting padding before trailing border characters

## When to Run

- After writing or editing any markdown file with tables or box diagrams
- After a skill or subagent produces a markdown file with tables
- When asked to fix table or diagram formatting

## Limitations

- Box diagram fix only adjusts **padding** (spaces), not structural issues like a box's content rows being wider than its border row
- For structural diagram issues, regenerate the diagram with a generator script (see gen_diagram examples in `/tmp/claude/`)
