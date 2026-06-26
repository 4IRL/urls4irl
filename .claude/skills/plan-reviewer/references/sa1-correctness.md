# Subagent 1: Correctness & Accuracy

**Role:** Verify that the plan's claims match the actual codebase.

**What to read:** Every source file the plan references (file paths in to-do items, modified/deleted file lists). For each file, focus on imports, function signatures, class definitions, decorator stacks, and data shapes.

**Review checklist:**
- Do proposed changes match the actual API/interface of the code they touch?
- Are import paths, function signatures, and data shapes accurate as stated in the plan?
- Does the plan delete or modify things that other modules depend on? Grep for usages of any deleted/renamed symbol.
- Are type annotations correct per the codebase's actual types?
- **Function name existence check (required for every code block):** For every function call that appears in a plan's code block or snippet — especially success/failure handler bodies — grep the codebase to confirm the function exists. A fabricated or misremembered name (e.g., `showSplashFlashBanner` instead of `showSplashModalAlertBanner`) produces a runtime `ReferenceError` that no TypeScript check catches. Flag as **Critical** if grep returns zero matches.
- **Named-symbol presence/absence requires a file read (required):** Any claim that a named symbol — constant, union member, function, class, attribute, or route identifier — exists, is absent, or lives at a specific location MUST be backed by an actual Read or Grep of that file. Never assert presence or absence from plan prose, from another reviewer's claim, or from inference. If you have not read the file, do not make the claim — open the file first.

**Pydantic specifics (apply whenever the plan defines or modifies Pydantic schemas):**
- **Cross-field validators**: if a validator reads `info.data.get("field")` and that field has its own validation, verify the guard `if "field" not in info.data: return value` is present. Pydantic v2 omits failed fields from `info.data`, so without the guard a spurious second error fires.
- **`from_attributes=True` factories**: verify that ORM attribute names match schema *field names* (not aliases). If they differ, `model_validate(orm_obj)` raises `AttributeError`.
- **Alias completeness**: if any field in a schema uses `Field(alias=...)`, ALL fields must have explicit alias declarations. Partial alias specs cause silent `model_validate` failures.
- **Error-handling pattern**: `try/except ValidationError -> log` swallows schema drift. Schema validation calls must be bare (no try/except) so `ValidationError` propagates as a 500.

**Stale line number detection and symbol-anchor preference (required):** When the plan references a specific line number in a source file, read that file and verify the referenced symbol is actually at that line. If it is not, flag as **Minor** and write the correction using a symbol anchor as the primary navigation aid (e.g., 'search for `EventName.UI_DECK_EXPAND` to locate the insertion point') rather than a replacement absolute line number. Absolute line numbers become stale as the source file evolves; symbol anchors are stable. If a line number is included alongside a symbol anchor, mark it explicitly approximate (e.g., 'around line N — verify via grep'). This rule also applies when writing any mechanical fix that cites a line number: do NOT introduce a new bare absolute line number into plan text even when correcting an old one.

**Transitive reads (required):** When a plan modifies a function, also read what that code calls — one level of callees. Plans frequently miss helper signatures, conditional guards, and indirect dependencies.

- **Config inheritance chains**: When a plan modifies a parent config (tsconfig, eslint, etc.), trace `extends` references to child configs and verify the change doesn't silently break inherited behavior.

- **New symbol reference → verify import (required):** When a plan instructs adding any symbol reference (`isinstance`, `issubclass`, type hint, function call) to an existing file, read that file's import block and confirm the symbol is already imported. If it is not, flag the missing import as **Major**. Do NOT assume the plan would have mentioned it.
  - **Import name-collision check (required):** When a plan instructs adding a new import of bare name S into file F — whether as a new `import` line or as part of a `from X import S` — read file F's full import block and grep for any existing `import S` or `from ... import ... S` (bare name, not aliased). If a collision is found, flag as **Major**: Python silently rebinds the name at module scope, the new import shadows the original, and every existing call site that depended on the shadowed version will receive the wrong function signature at runtime. The fix must alias one of the two imports (e.g., `from X import S as S_playwright`) and update all call sites for the aliased version.

When a plan instructs inserting code into an existing function, read the full function body — not just the lines the plan cites. This surfaces: (a) existing imports the new code depends on, (b) established defensive patterns already in use nearby, (c) variable names or parameter types the new code must match.

**Replacement code block diff (required):** When a plan provides a code block that is a *replacement specification* for an existing function, read the full source function and diff it against the plan's block. Check for: outer guards dropped (status checks, `hasOwnProperty`, `responseJSON` presence), else-branches removed (fallback banners, redirect calls), and side-effect calls omitted. Flag any dropped guard or side-effect as **Critical** — TypeScript will not catch behavioral regressions from dropped runtime guards.
