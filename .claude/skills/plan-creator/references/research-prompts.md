# Research Subagent Prompts

Each subagent receives the user's feature/task description and a list of affected modules, files, or endpoints identified by the main agent. All subagents return structured JSON and must independently read source files — the main agent does NOT pre-read files for them.

## Response Format (all subagents)

> **File delivery:** Write your complete response to the file path provided in your prompt (`plans/<topic>/tmp/research-<focus>.md`), then return only this one-line confirmation: `Written to <path>`. The orchestrator will read the file. The format below is unchanged.

```json
{
  "area": "architecture | dependencies | request-chain | tests | schemas",
  "files_read": ["list of files actually read during research"],
  "findings": {
    // area-specific structured data — see per-subagent sections below
  },
  "summary": "2-3 sentence summary of key discoveries relevant to planning"
}
```

Rules:
- Every file path cited must be one you actually read — do not infer paths from convention alone.
- If a file does not exist or is empty, note it in your summary rather than guessing its contents.
- Return ONLY the JSON block — no other text before or after.
- Be thorough but targeted: read files relevant to the task, not the entire codebase.

---

## Subagent 1: Architecture & Patterns

**Role:** Understand the structural patterns and conventions in the modules the plan will touch, so the plan follows established approaches.

**What to read:**
- `ARCHITECTURE.md` — overall codebase structure
- `CLAUDE.md` — coding rules and conventions
- 2-3 representative files in each affected module (routes, services, templates, JS modules) to observe patterns

**Research checklist:**
- How are routes structured in this blueprint? (decorator stacks, method handling, return patterns)
- How are services structured? (function signatures, error handling, return types)
- What template patterns are used? (base templates, block structure, macro usage)
- What JS module patterns are used? (imports, exports, AJAX patterns, DOM manipulation)
- What naming conventions are in use? (files, functions, classes, constants)
- Are there any module-specific patterns that differ from the general architecture?

**Response `findings` shape:**

```json
{
  "modules_analyzed": ["backend/src/splash", "src/splash"],
  "route_patterns": {
    "decorator_stack": "description of typical decorator ordering",
    "return_pattern": "description of how routes return responses",
    "error_handling": "description of error handling approach"
  },
  "service_patterns": {
    "signature_style": "description of typical function signatures",
    "return_types": "description of return type patterns",
    "helper_conventions": "description of private helper patterns"
  },
  "template_patterns": {
    "base_template": "which base template is extended",
    "block_structure": "key blocks used",
    "macro_usage": "any macros in use"
  },
  "js_patterns": {
    "module_style": "ES6 modules / IIFE / etc.",
    "ajax_pattern": "fetch / jQuery.ajax / XMLHttpRequest",
    "dom_conventions": "how DOM elements are accessed"
  },
  "naming_conventions": {
    "files": "kebab-case / snake_case / etc.",
    "functions": "naming patterns observed",
    "constants": "naming patterns observed"
  },
  "notable_deviations": ["any module-specific patterns that differ from general architecture"]
}
```

---

## Subagent 2: Dependency & Impact Mapping

**Role:** Map what depends on the code being changed, so the plan accounts for all downstream impacts.

**What to read:**
- Files the user identified as being changed or affected
- One level of callers for each function/class being modified (grep for usages)
- One level of callees inside each function being modified (read the function body)
- Import consumers of any module being restructured

**Research checklist:**
- For each function/class being changed: who calls it? Who imports it?
- For each file being changed: what other files import from it?
- Are there any circular dependencies or tight couplings to be aware of?
- Are there test files that directly import or mock the changed code?
- Are there any database models, migrations, or schema dependencies?

**Response `findings` shape:**

```json
{
  "targets": [
    {
      "symbol": "function_name or ClassName",
      "file": "path/to/file.py",
      "callers": [
        {"file": "path/to/caller.py", "line": 42, "context": "brief usage context"}
      ],
      "callees": [
        {"symbol": "helper_name", "file": "path/to/same_or_other.py"}
      ],
      "importers": [
        {"file": "path/to/importer.py", "import_statement": "from X import Y"}
      ]
    }
  ],
  "cross_module_impacts": ["description of any cross-module effects"],
  "test_dependencies": [
    {"test_file": "path/to/test.py", "depends_on": "symbol or fixture name"}
  ],
  "circular_risks": ["any circular dependency concerns"]
}
```

---

## Subagent 3: Request/Response Chain Tracing

**Role:** For every endpoint the plan will touch, trace the full request/response cycle through all layers so no link is missed.

**What to read:**
- Route handler files for affected endpoints
- Decorator definitions (auth, CSRF, validation)
- Service functions called by the route + their private helpers (one level deep)
- HTML templates rendered by the route
- JS modules that call the endpoint (read ALL JS files in the module directory, not just ones the user names)
- Test files that exercise the endpoint

**Research checklist:**
- For each endpoint: what HTTP methods? What decorators and in what order?
- What does the route handler do? What service does it call?
- What does the service return? What status codes are possible?
- What template is rendered? What variables are passed? What conditional guards exist?
- What JS sends requests to this endpoint? What format (FormData, JSON, serialized)?
- How does JS handle success/failure responses? What status codes does it check?
- Where does the CSRF token come from? (meta tag, hidden input, cookie) Is it conditional?
- What test fixtures exist? How do they obtain CSRF tokens, session state, DB state?

**Response `findings` shape:**

```json
{
  "endpoints": [
    {
      "method": "POST",
      "path": "/splash/register",
      "handler": {"file": "path/to/routes.py", "function": "register_user", "line": 42},
      "decorators": ["@login_required", "@csrf.exempt"],
      "service": {"file": "path/to/service.py", "function": "create_user", "line": 10},
      "service_helpers": [
        {"function": "_validate_email", "file": "path/to/service.py", "line": 25}
      ],
      "template": {"file": "path/to/template.html", "variables_passed": ["form", "errors"]},
      "js_module": {
        "file": "src/splash/register.js",
        "ajax_format": "JSON.stringify",
        "content_type": "application/json",
        "success_handler": "description",
        "failure_handler": "description",
        "status_codes_checked": [200, 400, 401]
      },
      "csrf": {
        "source": "meta tag / hidden input / cookie",
        "conditional": false,
        "condition_details": "if conditional, what guard"
      },
      "test_files": [
        {"file": "tests/integration/test_register.py", "fixture_notes": "uses client fixture with CSRF from meta tag"}
      ],
      "response_codes": [200, 400, 401, 409]
    }
  ]
}
```

---

## Subagent 4: Test Infrastructure

**Role:** Understand the existing test patterns, markers, and fixtures for the affected area so the plan includes correct and sufficient verification steps.

**What to read:**
- Test files in the same directory/marker as the affected code
- `pytest.ini` or `pyproject.toml` for marker definitions
- `Makefile` for available test targets
- Conftest files in the test directory hierarchy
- Any test utility/helper files imported by the tests

**Research checklist:**
- What test markers apply to the affected area?
- What `make` targets are available for running these tests?
- What fixtures are used? (DB setup, client, auth, CSRF tokens)
- What patterns do existing tests follow? (arrange/act/assert structure, naming, parametrize usage)
- Are there both integration and UI tests for the affected endpoints?
- What conftest fixtures exist in the hierarchy?
- Are there any test utility functions or constants used across tests?

**Response `findings` shape:**

```json
{
  "markers": [
    {"name": "splash", "description": "integration tests for auth", "make_target": "make test-marker-parallel m=splash"}
  ],
  "test_files": [
    {
      "file": "tests/integration/splash/test_register.py",
      "marker": "splash",
      "test_count": 12,
      "patterns": "description of test structure and naming"
    }
  ],
  "fixtures": [
    {
      "name": "login_user",
      "file": "tests/conftest.py",
      "description": "what it does and how"
    }
  ],
  "conftest_hierarchy": ["tests/conftest.py", "tests/integration/conftest.py"],
  "test_utilities": [
    {"file": "tests/utils.py", "exports": ["constant_name", "helper_function"]}
  ],
  "coverage_notes": {
    "has_integration_tests": true,
    "has_ui_tests": true,
    "has_js_tests": false,
    "gaps": "description of any obvious test coverage gaps"
  }
}
```

---

## Subagent 5: Schema & Data Shapes (Conditional)

**Role:** Map the current data validation layer — Pydantic schemas, DB models, form classes, and frontend data contracts — so the plan specifies exact field definitions and type annotations.

**Launch condition:** Only launch this subagent when the task involves data validation, model changes, schema migration, or form handling.

**What to read:**
- Pydantic schema files in `backend/schemas/` for the affected area
- SQLAlchemy model files in `backend/models/` for affected tables
- WTForms form classes (if any remain) in the affected module
- Frontend JS that constructs or parses request/response data for affected endpoints
- Any shared constants or enums used in validation

**Research checklist:**
- What Pydantic schemas exist for the affected endpoints? What fields, types, aliases, validators?
- What DB models are involved? What columns, types, constraints, relationships?
- Are there any WTForms classes still in use that might need migration?
- What does the frontend send? (field names, types, format)
- What does the frontend expect back? (response shape, field names)
- Are there cross-field validators (`@model_validator`) that read other fields?
- Is `from_attributes=True` used? Do ORM attribute names match schema field names?
- What constants or enums are used in validation error messages?

**Response `findings` shape:**

```json
{
  "schemas": [
    {
      "file": "backend/schemas/requests/splash/register.py",
      "class": "RegisterRequest",
      "fields": [
        {"name": "username", "type": "str", "alias": null, "validators": ["min_length=3"]},
        {"name": "email", "type": "EmailStr", "alias": null, "validators": []}
      ],
      "model_config": {"from_attributes": false},
      "cross_field_validators": ["description of any @model_validator"]
    }
  ],
  "models": [
    {
      "file": "backend/models/user.py",
      "class": "User",
      "columns": [
        {"name": "username", "type": "String(64)", "nullable": false, "unique": true}
      ],
      "relationships": ["utubs via UTubMembers"]
    }
  ],
  "forms": [
    {
      "file": "backend/src/splash/forms/register_form.py",
      "class": "RegisterForm",
      "status": "active / deprecated / migrated to Pydantic"
    }
  ],
  "frontend_contracts": [
    {
      "endpoint": "/splash/register",
      "request_fields": ["username", "email", "password", "confirmPassword"],
      "response_shape": {"success": "redirect URL", "failure": "errors dict with field keys"}
    }
  ],
  "validation_constants": [
    {"file": "backend/utils/strings/splash_strings.py", "constants": ["USER_FAILURE", "REGISTER_FORM"]}
  ]
}
```
