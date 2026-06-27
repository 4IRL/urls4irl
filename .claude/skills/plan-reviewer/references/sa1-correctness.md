# Subagent 1: Correctness & Accuracy

**Role:** Verify that the plan's claims match the actual codebase.

**What to read:** Every source file the plan references (file paths in to-do items, modified/deleted file lists). For each file, focus on imports, function signatures, class definitions, decorator stacks, and data shapes.

**Review checklist:**
- Do proposed changes match the actual API/interface of the code they touch?
- Are import paths, function signatures, and data shapes accurate as stated in the plan?
- Does the plan delete or modify things that other modules depend on? Grep for usages of any deleted/renamed symbol.
- Are type annotations correct per the codebase's actual types?
- **Grounding Rule — named-symbol triggers (required):** Apply the Grounding Rule to every named symbol the plan references (constant, union member, function, class, attribute, route id). In particular, for **every function call in a code block or snippet** (especially success/failure handler bodies), grep to confirm it exists — a fabricated/misremembered name (e.g., `showSplashFlashBanner` vs `showSplashModalAlertBanner`) is a runtime `ReferenceError` TypeScript won't catch; flag **Critical** on zero matches.

**Pydantic specifics (apply whenever the plan defines or modifies Pydantic schemas):**
- **Cross-field validators**: if a validator reads `info.data.get("field")` and that field has its own validation, verify the guard `if "field" not in info.data: return value` is present. Pydantic v2 omits failed fields from `info.data`, so without the guard a spurious second error fires.
- **`from_attributes=True` factories**: verify that ORM attribute names match schema *field names* (not aliases). If they differ, `model_validate(orm_obj)` raises `AttributeError`.
- **Alias completeness**: if any field in a schema uses `Field(alias=...)`, ALL fields must have explicit alias declarations. Partial alias specs cause silent `model_validate` failures.
- **Error-handling pattern**: `try/except ValidationError -> log` swallows schema drift. Schema validation calls must be bare (no try/except) so `ValidationError` propagates as a 500.

**Stale line number detection and symbol-anchor preference (required):** When the plan references a specific line number in a source file, read that file and verify the referenced symbol is actually at that line. If it is not, flag as **Minor** and write the correction using a symbol anchor as the primary navigation aid (e.g., 'search for `EventName.UI_DECK_EXPAND` to locate the insertion point') rather than a replacement absolute line number. Absolute line numbers become stale as the source file evolves; symbol anchors are stable. If a line number is included alongside a symbol anchor, mark it explicitly approximate (e.g., 'around line N — verify via grep'). This rule also applies when writing any mechanical fix that cites a line number: do NOT introduce a new bare absolute line number into plan text even when correcting an old one.

**Transitive reads (required):** When a plan modifies a function, also read what that code calls — one level of callees. Plans frequently miss helper signatures, conditional guards, and indirect dependencies.

- **Config inheritance chains**: When a plan modifies a parent config (tsconfig, eslint, etc.), trace `extends` references to child configs and verify the change doesn't silently break inherited behavior.

- **Grounding Rule — new symbol reference → verify import (required):** When a plan adds any symbol reference (`isinstance`, `issubclass`, type hint, function call) to an existing file, read that file's import block and confirm the symbol is imported; flag a missing import as **Major** (don't assume the plan would have mentioned it). If the plan adds a new bare-name import that collides with an existing binding, flag **Major** and require an alias — see SA#4's import name-collision check for the full mechanism.

When a plan instructs inserting code into an existing function, read the full function body — not just the lines the plan cites. This surfaces: (a) existing imports the new code depends on, (b) established defensive patterns already in use nearby, (c) variable names or parameter types the new code must match.

**Grounding Rule — replacement code block (required):** When a plan gives a code block that *replaces* an existing function, read the source function and diff it: flag dropped outer guards (status checks, `hasOwnProperty`, `responseJSON` presence), removed else-branches (fallback banners, redirects), or omitted side-effects as **Critical** (TypeScript won't catch these). SA#2 owns the full line-by-line diff checklist.
