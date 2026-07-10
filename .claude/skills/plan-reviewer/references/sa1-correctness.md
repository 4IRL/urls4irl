# Subagent 1: Correctness, Accuracy & Codebase Integration

**Role:** Verify that the plan's claims match the actual codebase, AND that the plan follows project patterns and CLAUDE.md rules. Both lenses read the same source files, so they run as one pass: first confirm the code does what the plan says, then confirm the plan does it the way this codebase does things.

**What to read:** Every source file the plan references (file paths in to-do items, modified/deleted file lists) — imports, function signatures, class definitions, decorator stacks, data shapes. Also CLAUDE.md, ARCHITECTURE.md (if referenced), ENDPOINT_REGISTRY.md (if the plan references it), a sample of files in the same module as the plan's changes to confirm pattern alignment, and requirements files if the plan adds packages. **When the plan creates or modifies a build artifact** (config file, output directory, package manifest), also read `.github/workflows/*.yml` to verify whether existing CI jobs copy or reference that artifact — omissions that are silent during the first run become maintenance hazards.

- **Anchor verification for reference documents (required):** When the plan instructs inserting text at a specific anchor location within a reference document (ENDPOINT_REGISTRY.md, README, config file), read that document and verify the anchor string exists at the stated location. If the anchor does not exist, flag as **Major** — the implementer cannot follow the instruction.

## Part A — Correctness & Accuracy

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

- **Grounding Rule — new symbol reference → verify import (required):** When a plan adds any symbol reference (`isinstance`, `issubclass`, type hint, function call) to an existing file, read that file's import block and confirm the symbol is imported; flag a missing import as **Major** (don't assume the plan would have mentioned it). If the plan adds a new bare-name import that collides with an existing binding, flag **Major** and require an alias — see the import name-collision check in Part B below for the full mechanism.

When a plan instructs inserting code into an existing function, read the full function body — not just the lines the plan cites. This surfaces: (a) existing imports the new code depends on, (b) established defensive patterns already in use nearby, (c) variable names or parameter types the new code must match.

**Grounding Rule — replacement code block (required):** When a plan gives a code block that *replaces* an existing function, read the source function and diff it: flag dropped outer guards (status checks, `hasOwnProperty`, `responseJSON` presence), removed else-branches (fallback banners, redirects), or omitted side-effects as **Critical** (TypeScript won't catch these). SA#2 owns the full line-by-line diff checklist.

## Part B — Codebase Integration & Conventions

**Review checklist:**

- **Project patterns**: Does the plan follow established patterns (test structure, naming, module conventions)? Are new files placed in the right directories per project architecture?

- **CLAUDE.md rules**:
  - No window globals for module communication
  - Use typehints — no shortcuts
  - Never use quoted type hints (files use `from __future__ import annotations`)
  - Never use single-letter variable names — all variables must be descriptively named
  - No relative imports — always use absolute paths like `from backend.schemas.requests._sanitize import ...`
  - **Import discipline in test prose (required):** Scan ALL test sub-step bullets (not just code blocks) for wording implying local imports: 'dynamically import', 'import inside the test', 'import at call time', `importlib.import_module`. Any such phrasing violates the top-level-imports-only rule. Flag as **Minor** and specify the replacement wording ('reference the top-level import', 'use the module-level import').

- **Import ordering**: Three groups (stdlib, third-party, project), each alphabetized internally, separated by blank lines.
  - **Grounding Rule — import name-collision check (required for shared files, canonical home):** When a plan adds a new import into a shared file (conftest.py, a shared utilities module, a shared init file), read the file's full existing import block and confirm that no other import already binds the same bare name from a different source module. A bare re-import of an already-bound name silently shadows the original at module scope — a runtime error no linter catches. If a collision exists, flag as **Major** and require one import to use an alias.

- **Package additions** (if applicable):
  - Use exact pin (`==`) not ranges (`>=`, `~=`, `<`)
  - Pin transitive dependencies
  - Place in correct requirements file: runtime in `requirements-prod.txt`, test-only in `requirements-test.txt`, dev/tooling in `requirements-dev.txt`
  - **Peer dependency verification**: When a plan adds packages that depend on a peer (e.g., `@typescript-eslint/parser` requires `eslint`), read the actual `package.json` to confirm the peer is present. Never assume from plan text.
  - **TypeScript types sub-path validation (required for JS/TS plans):** When a plan adds an entry to a tsconfig types array (e.g., "vitest/globals", "@testing-library/jest-dom"), verify that the sub-path is a documented TypeScript types entry point for the pinned version. Flag as **Minor** if unverifiable at review time, with a suggested runtime verification command.

- **Config consistency**: Env vars, lint rules, and CI config aligned with plan changes. When the plan adds or modifies a build/test tool invocation, compare the CI job command (in .github/workflows/*.yml) against the local Makefile target for the same tool — confirm flags, working directories, and config file paths are consistent or note documented divergences. Undocumented divergences between CI and local invocations are a **Minor** finding.

- **Test markers**: Are markers correct per `pytest.ini`? Are new markers needed?

- **Grounding Rule — response-assertion style conformance (required for test code blocks):** When a plan's test code block asserts an HTTP response property (status code, headers, redirect location, cookies, body field), grep existing tests in the same `tests/integration/` tree for assertions on the same property. If the existing pattern differs from the plan's form (e.g., existing redirect tests use `urlsplit(response.location).path` but the plan uses `response.headers['Location']`), flag as **Minor** and cite the canonical form. Never approve a new assertion style for a property already asserted uniformly elsewhere.
