# Subagent 3: Ordering, Dependencies & Cleanup

**Role:** Verify step sequencing, intermediate state safety, and cleanup correctness.

**What to read:** The plan in full, plus lint config files (`tox.ini`, `.flake8`, `pyproject.toml`, `.eslintrc`) and any files where the plan defers deletion or cleanup to a later step.

**Review checklist:**

- **Step sequencing**: Are steps ordered so each prerequisite is done before its consumer? Would executing steps out of order cause failures?

- **Intra-step bullet ordering (required):** Within each step, read the sub-bullets in top-to-bottom order and verify that every symbol, constant, or file referenced in a code block is defined or created by an earlier bullet in the same step. A code block that uses `M.SEARCH_RESULTS` before the bullet that adds `SEARCH_RESULTS` to `model_strs.py` is an ordering error even though both bullets are in the same step. Flag as **Minor** if an implementer following the bullets top-to-bottom would encounter an undefined symbol.

- **Intermediate state (required)**: For every step, verify the application is fully working after that step completes — not just at the end of the plan. Any gap where an endpoint is silently broken between steps is a **Major** finding, even if integration tests pass.

- **Deferred cleanup commit gate (required)**: For any symbol (import, function, export, variable) that becomes unused partway through but is only removed later, verify lint config does not enforce a rule blocking the intermediate commit. Common blockers: F401 (unused Python import), `no-unused-vars` (JS). If active, cleanup must move into the same step that makes the symbol unused.

- **Dead import analysis (required for every deletion)**: When a step deletes a function/class/helper or changes a return expression, perform a full transitive import scan:
  1. List every symbol the deleted code uses from imports
  2. Grep the file for remaining usages excluding the deleted code
  3. If no other usage exists, that import is dead and must be removed in the **same step**
  Common misses: `typing` imports used only in deleted helpers, `render_template` whose sole call is deleted, utility functions called only by deleted code, string constants referenced only in deleted branches, `request` whose sole usage was removed.

- **Forward references**: No to-do item should reference a function/class that doesn't exist yet and isn't created in the same or earlier step.

- **Framework lookup / discovery claims (required):** When a plan makes a factual claim about how a framework resolves or discovers resources — pytest fixture scoping and conftest hierarchy, Flask blueprint registration order, SQLAlchemy relationship traversal, Vite module resolution — verify the claim against the framework's documented behaviour rather than accepting the plan's prose. A plan that simultaneously offers "replicated into conftest OR construct inline" AND describes the conftest as "empty" is internally contradictory and signals an unverified fixture-scoping assumption. Flag as **Major** if the plan's stated resolution rule is inconsistent with the framework's actual mechanism.
