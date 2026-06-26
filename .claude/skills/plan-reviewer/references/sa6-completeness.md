# Subagent 6: Completeness, Risk & Specificity

**Role:** Identify gaps, risks, and underspecified steps.

**What to read:** The full plan, plus any files where the plan's specificity claims can be checked (schema definitions, factory methods, template structures).

**Review checklist:**

- **Edge cases & completeness**: What scenarios are not covered (empty state, error paths, boundary conditions)? Race conditions, async timing issues, or state management gaps?

- **Implementation specificity**: For every step that defines or modifies a class, function, schema, or template:
  - Does the plan provide enough detail (exact field definitions, method bodies, variable extraction instructions, explicit code patterns) for an implementer to execute without additional research?
  - Flag any step where a developer would need to "figure out" details the plan leaves unstated (factory method bodies, full alias declarations, explicit variable extraction, required refactors). These are **Major** findings.
  - Partial specifications are not acceptable: if a schema has five fields and only one has `Field(alias=...)`, the other four are underspecified even if "derivable."
  - **Variable-binding audit for rewrites and ports (required):** When a plan provides a code body for a function described as a 'rewrite', 'port', or 'analog' of a named existing function, read the original function in the source file and audit the plan's body: every name used in the plan body (as an argument, in an f-string, in a keyword argument, or in a subscript) must be either (a) a parameter of the new function, (b) assigned explicitly earlier in the body, or (c) a module-level name (import or constant). Any name used in the plan body that was bound in the original via an assignment the plan dropped is an undefined-variable bug. Flag as **Major** and cite the missing binding.
  - **Success handler body spec completeness (required for JS/TS plans):** For every AJAX success handler a step covers, verify that the plan provides either: (a) a complete body spec, or (b) an explicit note that the body requires no changes. A success handler with side effects beyond the typed variable assignment (e.g., a modal `.hide()` call, a `window.location.replace`, a status guard, a secondary helper call) that is covered only by a type-signature bullet is underspecified. Flag as **Minor** if the omitted behavior could be dropped by an implementer following only the plan text.
  - **Config file option coverage (required when a plan proposes a new config file):** For every option listed in a proposed config file (tsconfig.json, vite.config.js, pyproject.toml, etc.), verify that the plan's rationale section explains WHY that option is present. Any option with no rationale bullet is a **Minor** finding — either the rationale must be added or the option must be removed.

- **Risk & reversibility**: Which steps are hard to undo (file deletions, DB migrations, API contract changes)? Steps that could break CI or affect shared infrastructure?

- **Cleanup**: Does the plan handle cleanup of temp files, test fixtures, orphaned imports?

- **Pre-existing path collision**: When a plan says "Create directory/file X", read the filesystem to check if X already exists. If it does, flag that the plan should acknowledge pre-existing contents and specify merge/overwrite behavior.

- **Config file scope correctness (required when a plan creates a shared config file):** When a plan proposes a new tsconfig.json, jest.config, or similar config that applies to all source files, check whether any types, globals, plugins, or include entries expose test-only APIs (e.g., vitest/globals, @types/jest) to production code. If so, flag the missing scope boundary (e.g., a separate tsconfig.test.json) as **Minor** and note the trade-off.

- **Breaking changes**: API contracts, shared state, DB schema, cross-module dependencies — does the plan account for all consumers?

- **Single-instance conversion completeness (required):** When a plan fixes only one known instance of a broader pattern (e.g., 'convert this one raw int to an enum'), grep the codebase for all call sites of the same pattern and verify no other instances exist. If others are found, flag as **Major** — the plan must either convert all instances or explicitly acknowledge the remaining ones as intentional.

- **Fragility-pattern sweep (required when reviewing shell scripts / smoke-test files):** When a finding identifies a *fragility pattern* in a specific location — a flat `sleep N` settle, an unquoted variable, a missing readiness wait, a bare `docker exec` without a quoting guard — scan the same file for all other occurrences of that identical pattern. If the plan's fix resolves only the named occurrence while sibling occurrences in the same file share the same fragility, flag as **Major** and require the fix to sweep all siblings. This rule fires regardless of whether the siblings were named in the original finding.
