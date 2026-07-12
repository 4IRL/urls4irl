# Design-Doc Research Subagent Prompts

These prompts drive Step 4 of `/design-doc` — grounding a feature's open design questions in
what the codebase already does, before asking the user anything. Focus is **precedent and
constraint discovery**, not implementation depth (that's `/plan-creator`'s
`references/research-prompts.md` once the design doc is settled).

Each subagent is a research-only agent (`model: "sonnet"` explicitly set) exploring via
Glob/Grep/Read. It receives the feature description from Step 3 and the path to write its
findings.

## Response Format (all subagents)

> Write your complete response to `plans/<topic>/tmp/research-<focus>-design.md` using the
> `Write` tool — never a Bash heredoc/redirect. Return only: `Written to <path>`.

```json
{
  "area": "patterns | integration | constraints",
  "files_read": ["..."],
  "findings": { ... },
  "open_questions_narrowed": ["<question the codebase couldn't fully answer, made specific>"],
  "summary": "2-3 sentences"
}
```

---

## Subagent 1: Existing Pattern & Convention Discovery

**Role:** find analogous features already built, so the new feature follows precedent instead
of inventing a fresh pattern.

**What to read:** similar features in the same domain (e.g. an existing panel/modal/filter if
this feature is one), `CLAUDE.md` established patterns, naming/file-layout conventions in the
affected area. **If the feature is UI-facing**, also read the app's actual visual conventions —
CSS custom properties/theme variables, the color palette in use, existing component/modal/panel
markup and class names, spacing/typography patterns — so the design doc's Codebase Context can
ground any visual decision in real values instead of the design doc inventing new ones.

**Checklist:** what's the closest existing analog? What pattern/convention does it follow
(component structure, event bus usage, string-bridge usage, etc.)? Would deviating from it need
explicit justification? For UI-facing features: what colors/spacing/component patterns does the
closest analog already use, and are there any existing "off-brand" exceptions worth flagging?

**Findings shape:**
```json
{
  "closest_analog": {"feature": "Tag panel name filter", "files": ["frontend/tags/filter.ts"], "pattern": "togglable filter box, event-bus driven"},
  "conventions_to_follow": ["destructured object params", "APP_CONFIG.strings bridge for user-facing text"],
  "ui_conventions": {"colors": ["--primary-blue: #...", "..."], "components_to_reuse": ["modal shell in frontend/modals/base.ts"], "notes": "omit this field entirely for non-UI features"},
  "deviation_flags": []
}
```

---

## Subagent 2: Integration & Dependency Surface

**Role:** map what this feature would touch or need to extend, so open questions about "does X
already exist" get answered by evidence, not guesswork.

**What to read:** models/schemas/endpoints in the feature's domain, the metrics event registry
if the feature represents a trackable action, the event bus (`AppEvents`) for existing related
events.

**Checklist:** what already exists that this feature would extend vs. build from scratch? What's
the closest existing endpoint/model/event, if any? Any metrics/registry implications?

**Findings shape:**
```json
{
  "existing_to_extend": [{"what": "UTub model", "file": "backend/models/utub.py", "note": "would need a new column for X"}],
  "net_new": ["export endpoint — nothing today serves this"],
  "metrics_implications": "new DOMAIN event likely needed per CLAUDE.md's Metrics Coverage rule"
}
```

---

## Subagent 3: Constraint & Precedent Discovery

**Role:** surface existing limitations or past decisions that bound the design space, so open
questions don't re-litigate settled constraints.

**What to read:** `CLAUDE.md`, `ARCHITECTURE.md`, any existing plans in `plans/` touching the
same area, recent git history for related reverts/limitations.

**Checklist:** any hard technical constraint (e.g. no timing metrics exist, a fixed dependency
version)? Any prior design decision on record that this feature must respect or explicitly
override?

**Findings shape:**
```json
{
  "hard_constraints": ["Performance/latency is not measured anywhere today (CLAUDE.md) — a 'show load time' idea isn't buildable without a separate metrics effort"],
  "prior_decisions": [{"decision": "device type uses shared int enum", "source": "CLAUDE.md Metrics section", "applies_because": "feature exposes a device-scoped stat"}]
}
```
