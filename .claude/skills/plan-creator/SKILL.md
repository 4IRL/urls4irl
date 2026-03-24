---
name: plan-creator
description: Creates structured planning documents for new features or tasks in the @plans directory. Use when the user asks to create, write, or draft a plan for a feature, task, or implementation.
---

## Plan Creation

1. Create `@plans/<feature-name>.md` (create `@plans/` if missing).
2. Name the file after the feature/task (kebab-case).
3. Structure the plan as follows:

```markdown
# <Feature Name>

## Summary
<2-4 sentence description of what this feature does and why.>

## Steps

### 1. <Phase Title>
<One sentence describing what this phase accomplishes.>

**To-do:**
- [ ] <Specific, actionable sub-task>
- [ ] <Specific, actionable sub-task>

### 2. <Phase Title>
...

## Status
finished: false
```

**Rules:**
- Think like a staff engineer: anticipate edge cases, dependencies, and ordering constraints.
- Each phase must have at least one actionable to-do checkbox.
- To-do items must be detailed enough that a junior engineer can execute them without ambiguity — include file paths, function names, data shapes, or API contracts where relevant.
- The to-do list carries the detail; phase descriptions should be brief overviews.
- **Verify before you write.** Any constant, function, template tag, import path, or configuration value you reference in a to-do item must be confirmed to exist (and exist in the right context) by reading the relevant file before writing the to-do. Never write "use X from Y" based on memory or inference alone — read Y first.
- **Specify exact data structures.** When a to-do item constructs or populates a dict, list, or object, name the exact keys and value types — e.g., `errors["email"] = [USER_FAILURE.EMAIL_TAKEN]`, not "add `EMAIL_TAKEN` to the errors dict." Vague structure descriptions produce silent runtime failures when the implementer guesses the wrong key.
- **No forward references within a step.** If a step's to-do item calls or imports a function, that function must either already exist in the codebase or have been created earlier in the same step. If a function is first defined in step N, no to-do in steps 1–(N-1) may reference it. Check this before finalising step order.

## End-to-End Chain Tracing

For any plan that changes a request/response cycle (route, form, AJAX call, template), trace the **full chain** before writing to-dos and include a to-do item for every link that needs changing:

```
Client sends request
  → CSRF / auth middleware (where does the token come from?)
  → Route handler (method, decorators, request parsing)
  → Service layer (and its callees — one level deep)
  → Template rendering (values passed and their conditional guards)
  → Test fixtures (how does the test obtain CSRF tokens, session state, DB state?)
  → Frontend JS (request data format, field IDs, success/failure handler branches)
```

Skipping layers produces plans that break in the gaps between what's described. Common omissions:
- A middleware or decorator that gates the flow (auth condition, CSRF guard) that is only satisfied in some contexts
- A private helper inside a service that also holds the dependency being migrated
- A test fixture that extracts a value (CSRF token, response field) from HTML that no longer contains it after a template change
- A frontend handler branch that checks a status code or error code that changes after the migration

### Verification Layer Matching

Every step must include a verification command. The test type must match the layer changed:

| Change layer | Required verification | Why |
|---|---|---|
| Template / rendered HTML (meta tags, field IDs, conditional blocks) | UI test marker (`make test-marker-parallel m=<module>_ui`) or Playwright smoke | `client.get()`/`client.post()` never parse the DOM; template regressions are invisible to integration tests |
| Frontend JS (AJAX format, handlers, DOM reads) | `make test-js` + UI test marker or Playwright | JS unit tests catch logic; UI tests catch integration with real DOM |
| Backend only (service, route, DB) | `make test-marker-parallel m=<marker>` | Integration tests are sufficient and faster |
| Cross-layer (backend format + JS handler in same step) | Integration tests + `make test-js` + `make vite-build` | All three layers must be green |

If a step changes what the browser sees or reads but only runs integration tests, the plan is undertested — add the appropriate UI-level verification.

### Dead Import Elimination Protocol

When any to-do item **deletes a function, class, or helper**, you must trace its import footprint within the same file and include cleanup of every import that becomes dead. This is a mechanical, exhaustive check — not a judgment call.

**Procedure (for every deletion in a step):**

1. **List the symbols the deleted code uses.** Read the function body. Note every name it references that comes from an import at the top of the file — standard library types (`Sequence`, `cast`), framework functions (`render_template`, `request`), project utilities (`build_form_errors`), string constants (`EMAILS`, `REGISTER_FORM`), model classes, etc.
2. **For each such symbol, grep the file for other usages.** Exclude the deleted function(s) and their internal helpers. If no remaining usage exists in the file after the deletion, that import is dead.
3. **Add an explicit removal to-do** for every dead import found. Group them in the same bullet as the deletion (not in a later cleanup step) — F401 / `no-unused-vars` enforcement blocks the commit otherwise.

**Also apply when changing a function's return expression** (e.g., `render_template(...)` → `APIResponse(...).to_response()`). The old return may have been the sole consumer of an import (`render_template`, a form class passed to the template, etc.).

**Do not defer dead-import removal to a cleanup step.** If a symbol becomes unused in Step N, it must be removed in Step N. Linters enforce this at commit time — a deferred removal blocks every commit between Step N and the cleanup.

### Function Signature Change Protocol

When any to-do item changes a function's signature (parameter type, name, count, or structure), **read the function body** before writing the to-do and explicitly enumerate:

1. **Every private helper inside it** that receives or uses the changed parameter — add a separate to-do to update each one's signature and internal uses.
2. **Every direct call site in other files** — grep for callers and add a to-do for each one.

A plan that says "update `public_fn(form)` → `public_fn(value: str)`" without listing `_private_helper(form)` called inside it will produce an `AttributeError` at runtime. The callee enumeration must be explicit to-do items, not implied.

### Frontend/Backend Colocation Rule

For every endpoint where the plan changes the request format, response codes, or wire contract, the frontend JS changes **must appear in the same step** as the backend change — never in a later "frontend" or "cleanup" step. This includes:

- `data:` serialization format (`serialize()` → `JSON.stringify(...)`)
- `contentType:` header
- Failure handler status code checks (`xhr.status === 401` → `xhr.status === 400`)
- `handleImproperFormErrors` dispatch keys

Integration tests send the final format directly and will not catch a gap where the browser is silently broken between steps. Write the frontend to-do in the same step bullet block as the backend to-do it pairs with.

### CSRF / Auth / Session specifics

When a plan touches form submission, authentication, or CSRF:
1. **Token rendering**: Read the template. Note any `{% if ... %}` guards. Explicitly state whether the condition is satisfied for all relevant user states (authenticated, unauthenticated, unvalidated). If not, add a to-do to fix the guard.
2. **Test token acquisition**: Read the fixture. State exactly which HTML element the fixture parses to get the CSRF token, and verify that element will exist in the response after the template changes.
3. **Frontend token consumption**: Read the JS. Confirm the DOM element it targets (`meta[name=csrf-token]`, hidden input, etc.) is present in the rendered page for all user states the form is shown to.

## Package Pinning

Any plan step that adds a new Python package **must**:

1. Pin it to the **latest stable version** (check PyPI: `curl -s https://pypi.org/pypi/<package>/json | python3 -c "import sys,json,re; d=json.load(sys.stdin); vs=[v for v in d['releases'] if re.match(r'^\d+\.\d+\.\d+$',v)]; print(sorted(vs,key=lambda v:tuple(int(x) for x in v.split('.')))[-1])"`)
2. If stable is incompatible with the existing stack, use the latest working version instead — document why in the to-do item.
3. Pin **all transitive dependencies** introduced by the new package to exact versions as well. Run `pip install <package>==<version>` in the container, then `pip show <package>` and inspect the `Requires:` field. Add each unlisted dependency at its installed version.

**When using a new feature of an already-pinned package** (e.g., `EmailStr` requires `email-validator >= 2.0`, a new API method requires a minimum version), check the current pin in `requirements-prod.txt` before writing any to-do that depends on that feature. If the current pin is too old, add a pre-work to-do to update it — with a `make build` and container-level smoke test — before any to-do that uses the feature. Do not assume the existing pin is compatible.

**Always use `==` (not `>=`, `~=`, or ranges).** Add the package and its transitive deps to the appropriate requirements file based on usage:

| File | Use when |
|---|---|
| `requirements-prod.txt` | Needed at runtime in production |
| `requirements-test.txt` | Only needed for running tests (includes prod via `-r`) |
| `requirements-dev.txt` | Only needed for local dev tooling / pre-commit (includes test via `-r`) |

## Final Verification Step

For **every plan that touches code or tests**, the last phase must be:

```markdown
### N. Verify All Tests Pass

Run the full test suites to confirm nothing is broken:

**To-do:**
- [ ] Run `make test-integration-parallel` and confirm all integration tests pass
- [ ] Run `make test-ui-parallel-built` and confirm all UI/functional tests pass
- [ ] Investigate and fix any failures before marking the plan finished
```

Do not omit this phase even if only one test file was touched.

## TDD Enforcement

For any plan involving a **new feature or bug fix** (not pure refactoring or cleanup), the steps must follow a strict Red → Green → Refactor loop. Do not bulk-code then bulk-test.

**The Loop (one requirement at a time):**
1. **Red** – Write a focused test for one specific requirement. Run it; confirm it fails with a relevant error.
2. **Green** – Write the minimum code to make that test pass. Run it; confirm it passes.
3. **Refactor** – Clean up for readability and project patterns. Confirm tests stay green.
4. Repeat until the feature is complete.

**Implementation standards:**
- **Backend (Flask):** Prioritize integration or unit tests. Match existing style and directory structure in `tests/`.
- **Frontend – logic/state:** Use Vitest with JSDOM (fast, isolated).
- **Frontend – navigation/critical flows:** Use Selenium (end-to-end verification).
- **Philosophy:** Tests are the contract; code is the fulfillment. Never write tests to fit existing feature code.