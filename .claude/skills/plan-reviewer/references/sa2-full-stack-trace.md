# Subagent 2: Full-Stack Trace

**Role:** For every endpoint the plan modifies, trace the complete request/response cycle by reading actual code.

**What to read:** For each touched endpoint: the route handler, its decorators, the service function + private helpers (one level deep), the frontend JS that calls the endpoint (read ALL JS files in the module directory, not just ones the plan names), and the HTML template that renders the form/page. **When the plan involves a command or script run inside a Docker container** (npm scripts, shell scripts, pytest invocations), also read the relevant docker/compose*.yaml file to verify: (a) the container WORKDIR, (b) all bind-mount paths, (c) where the referenced file actually resolves given (a) and (b). Do NOT trust the plan's prose description of the container environment.

When a plan instructs inserting code into an existing function, read the full function body — not just the lines the plan cites. This surfaces: (a) existing imports the new code depends on, (b) established defensive patterns already in use nearby, (c) variable names or parameter types the new code must match.

**Replacement code block diff (required):** When a plan provides a code block that is a *replacement specification* for an existing function (not an insertion), read the full source function and perform a line-by-line diff against the plan's code block. Check specifically for:
- Outer guards dropped (status checks, `hasOwnProperty` guards, `responseJSON` presence checks, HTML-response early-returns)
- Else-branches silently removed (fallback error banners, redirect calls)
- Side-effect calls omitted (cleanup DOM mutations, secondary helper calls)
Flag any dropped guard or side-effect as **Critical** — these are behavioral regressions that TypeScript compilation will not catch.

**Review checklist — Request path (check each link):**

0. **Global hook conflict check (required):** For any file the plan modifies that registers a global side effect — jQuery prefilters (`$.ajaxPrefilter`, `$.ajaxSetup`), global event listeners (`document.addEventListener`), window-level interceptors — grep the codebase for all other registrations of the same hook. If another file registers the same hook (and both files are loaded on the same page), flag the double-registration as **Major** and note the behavioral consequence (e.g., handler fires twice per request). Do not trust the plan's prose claim that 'X is already handled' — trace the full registration chain.

1. **JS serialization**: What `data:` format does the current JS send (`serialize()`, `JSON.stringify`, etc.)? What does the plan change it to? Does the format change land in the **same step** as the backend format change? A gap where the browser sends the old format to a new backend is a **Major** finding.

2. **CSRF token delivery (full trace required)**:
   - **Source**: Read the template that renders the token (meta tag, hidden input, cookie). Check for conditional guards (`{% if auth %}`, feature flags). Verify the condition is True for every user state hitting this endpoint (unauthenticated, authenticated-not-validated, authenticated-validated, test clients).
   - **Reader**: Read the JS that extracts the token. Confirm the DOM element or cookie it reads actually exists in the rendered page for all user states.
   - **Transport**: Confirm the token reaches the server (header, body, cookie) and that Flask-WTF checks that location.
   - If the plan asserts "CSRF is already handled," **do not accept this at face value** — trace it yourself.

3. **Route method + decorators**: What HTTP method(s) does the route accept? What decorators wrap it and in what order? Does the plan's decorator placement match the required stack?

4. **Service function + private helpers**: For every helper the service calls, if the public function's signature changes, does the plan also update the helper's signature and internal uses? Flag any missed helper as **Major**.

5. **Established defensive patterns (required):** When a plan adds an attribute read (`obj.attr`, `dict[key]`) to an existing function, read the full body of that function to identify whether similar reads already use defensive patterns (e.g., `getattr(obj, 'attr', None)`, `dict.get(key)`). If the established pattern in that function is defensive and the plan uses direct access, flag as **Major** — inconsistency invites `AttributeError`/`KeyError` on edge cases.

**Review checklist — Response path (check each link):**

6. **Status codes after migration**: List every status code the endpoint can return after migration. Compare to before.

7. **JS failure handler dispatch**: For each status code, does the JS failure handler branch correctly? A handler still checking an old status code after the backend changes falls to the `else` branch and silently discards errors. Flag as **Major**.

8. **`handleImproperFormErrors` field key alignment**: Do the keys in the service's `errors` dict match the `case` labels in the handler's switch? Those keys must match `id` attributes on `<input>` elements (camelCase). A mismatch silently discards the error.
