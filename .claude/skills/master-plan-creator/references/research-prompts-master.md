# Master-Plan Research Subagent Prompts

These prompts drive the research phase for **master plans** — multi-PR initiatives that need to be decomposed into phases. The focus is **breadth** (scope, phase boundaries, ordering, conventions) rather than **depth** (signatures, data shapes). Use `plan-creator/references/research-prompts.md` for sub-plan depth research.

Each subagent is a **research-only** general-purpose agent that explores the codebase using Glob, Grep, and Read. It receives the user's initiative description. All subagents discover and read source files independently (use Glob to find files by pattern, Grep to search for symbols/usages, Read to examine contents — do NOT guess file paths, discover them) and write their output file using the Write tool, returning only a one-line confirmation.

## Response Format (all subagents)

> **File delivery:** Write your complete response to the file path provided in your prompt (`plans/<parent-topic>/tmp/research-<focus>-master.md`) **using the `Write` tool** — NEVER `cat <<EOF`, `python3 << 'EOF'`, `cat >`, `tee`, `printf >`, `echo >`, or any Bash heredoc/redirect. Any heredoc or inline script containing `{` and quotes triggers the brace+quote security prompt; the `Write` tool bypasses this. Return only this one-line confirmation: `Written to <path>`.

```json
{
  "area": "scope | phases | ordering | conventions",
  "files_read": ["list of files actually read during research"],
  "findings": {
    // area-specific structured data — see per-subagent sections below
  },
  "summary": "2-3 sentence summary of key discoveries relevant to phase planning"
}
```

Rules:
- Every file path cited must be one you actually read — no inference from convention alone.
- Be thorough but targeted: surface enough detail to decide phase boundaries, not enough to implement.
- Return ONLY the JSON block — no other text before or after.

---

## Subagent 1: Scope Enumeration

**Role:** Enumerate the total surface area affected by the initiative so the master plan has an accurate overall count, module breakdown, and complexity estimate.

**What to read:**
- All directories named in the user's initiative description
- Any manifest/index files (e.g., `vite.config.js` `rollupOptions.input`, `conftest.py` test discovery) that reveal full file lists
- `CLAUDE.md` / `ARCHITECTURE.md` if relevant to the initiative's scope

**Research checklist:**
- Total file count affected, broken out by directory/layer
- Total test-file count affected (if migration/refactor, count both source and test files)
- Any files that look scope-adjacent but should be excluded — call them out explicitly with reason
- Approximate line-count or complexity indicators per module (small/medium/large)

**Response `findings` shape:**

```json
{
  "total_files": 104,
  "by_directory": [
    {"path": "src/lib", "count": 11, "size": "small", "notes": "utilities, no UI"},
    {"path": "src/home", "count": 51, "size": "large", "notes": "main feature cluster"}
  ],
  "test_files": {"source_tests": 24, "ui_tests": 18, "total": 42},
  "excluded_files": [
    {"path": "src/vendor/*", "reason": "third-party, not ours to migrate"}
  ],
  "complexity_signals": ["51 files in home/ → likely needs further sub-splitting"]
}
```

---

## Subagent 2: Natural Phase Boundaries

**Role:** Identify cohesive groupings of work that can ship as a single PR without leaving the codebase in a broken state.

**What to read:**
- Directory structure of the affected surface area
- Import graphs at the module level (who imports whom) — read a sample of files per module to confirm
- Existing PR history (skim recent git log) for clues about how this repo typically splits work

**Research checklist:**
- What are the natural cohesive units? (e.g., "all of `lib/`", "splash feature", "URLs feature")
- Which groupings can ship without breaking anything that hasn't been migrated yet?
- Are there any "foundation" groupings that must ship first because everything else imports from them?
- Are there groupings that are too large and should be split further?

**Response `findings` shape:**

```json
{
  "proposed_phases": [
    {
      "name": "Foundation utilities",
      "covers": ["src/lib/*"],
      "rationale": "imported by every feature module — must ship first",
      "pr_size_estimate": "medium"
    },
    {
      "name": "Splash feature",
      "covers": ["src/splash/*"],
      "rationale": "self-contained, no imports from home/",
      "pr_size_estimate": "small"
    }
  ],
  "too_large_to_ship_as_one": [
    {"group": "src/home/*", "reason": "51 files spanning 4 features", "split_hint": "split by feature: utubs, urls, members, tags"}
  ]
}
```

---

## Subagent 3: Ordering Dependencies

**Role:** Identify hard ordering constraints between phases so the plan doesn't propose an impossible sequence.

**What to read:**
- Files flagged as "foundation" by Subagent 2 — read their callers to confirm breadth of impact
- Any shared infrastructure the initiative touches (build config, types, shared schemas)
- Migration-style work: read which direction imports flow

**Research checklist:**
- Which phases must complete before others can start?
- Are there any bidirectional dependencies that force merging in a single PR?
- Are there "infrastructure" steps (toolchain, codegen) that must land before any implementation work?
- Are there any phases that could run in parallel (no dependency between them)?

**Response `findings` shape:**

```json
{
  "ordering_constraints": [
    {"before": "TypeScript toolchain setup", "after": "any .ts file", "reason": "no tsconfig = no compilation"},
    {"before": "OpenAPI type codegen", "after": "API-call typing", "reason": "generated types are prerequisite"}
  ],
  "parallelizable_phases": [
    {"phases": ["Splash feature", "Navbar module"], "reason": "no imports between them"}
  ],
  "hard_sequential_chains": ["toolchain → codegen → foundation → features"]
}
```

---

## Subagent 4: Branch Naming Conventions

**Role:** Surface the repo's observed branch-naming patterns so each proposed phase gets a branch name that fits in.

**What to read:**
- Recent git log: `git log --all --format='%D' | head -100` (and equivalent for local branches)
- Any `CLAUDE.md` / contributing docs mentioning branch conventions

**Research checklist:**
- What prefixes are in use? (e.g., `feat/`, `fix/`, `refactor/`, `ts/`, `infra/`, `review/`)
- Which prefix is used for which category of work?
- What's the separator after the prefix? (`/`, `-`, `_`)
- Are branch names kebab-case, snake_case, or something else?
- Any conventions around this specific initiative's domain?

**Response `findings` shape:**

```json
{
  "observed_prefixes": [
    {"prefix": "ts/", "used_for": "TypeScript migration work", "example": "ts/feature-splash"},
    {"prefix": "infra/", "used_for": "build/toolchain/CI", "example": "infra/typescript-toolchain"},
    {"prefix": "feat/", "used_for": "new features", "example": "feat/utub-search"}
  ],
  "separator_after_prefix": "/",
  "name_style": "kebab-case",
  "suggested_prefix_for_this_initiative": "ts/",
  "suggested_prefix_rationale": "matches existing TypeScript migration branches"
}
```
