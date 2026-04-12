# Subagent 4: Codebase Integration & Conventions

**Role:** Verify the plan follows project patterns and CLAUDE.md rules.

**What to read:** CLAUDE.md, ARCHITECTURE.md (if referenced), ENDPOINT_REGISTRY.md (if the plan references it), and a sample of files in the same module as the plan's changes to confirm pattern alignment. Also read requirements files if the plan adds packages. **When the plan creates or modifies a build artifact** (config file, output directory, package manifest), also read `.github/workflows/*.yml` to verify whether existing CI jobs copy or reference that artifact — omissions that are silent during the first run become maintenance hazards.

- **Anchor verification for reference documents (required):** When the plan instructs inserting text at a specific anchor location within a reference document (ENDPOINT_REGISTRY.md, README, config file), read that document and verify the anchor string exists at the stated location. If the anchor does not exist, flag as **Major** — the implementer cannot follow the instruction.

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

- **Package additions** (if applicable):
  - Use exact pin (`==`) not ranges (`>=`, `~=`, `<`)
  - Pin transitive dependencies
  - Place in correct requirements file: runtime in `requirements-prod.txt`, test-only in `requirements-test.txt`, dev/tooling in `requirements-dev.txt`
  - **Peer dependency verification**: When a plan adds packages that depend on a peer (e.g., `@typescript-eslint/parser` requires `eslint`), read the actual `package.json` to confirm the peer is present. Never assume from plan text.
  - **TypeScript types sub-path validation (required for JS/TS plans):** When a plan adds an entry to a tsconfig types array (e.g., "vitest/globals", "@testing-library/jest-dom"), verify that the sub-path is a documented TypeScript types entry point for the pinned version. Flag as **Minor** if unverifiable at review time, with a suggested runtime verification command.

- **Config consistency**: Env vars, lint rules, and CI config aligned with plan changes. When the plan adds or modifies a build/test tool invocation, compare the CI job command (in .github/workflows/*.yml) against the local Makefile target for the same tool — confirm flags, working directories, and config file paths are consistent or note documented divergences. Undocumented divergences between CI and local invocations are a **Minor** finding.

- **Test markers**: Are markers correct per `pytest.ini`? Are new markers needed?
