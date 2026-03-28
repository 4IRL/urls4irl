# Push Review: refactor/splash-modal-prerender

## Review 1
Generated: 2026-03-27
Comparison: origin/main...HEAD
Verdict: **PUSHED WITH MINOR FINDINGS**

### Results by Reviewer

#### 1. Safety & Security — PASS
No security vulnerabilities found. Route redirects use internal named routes only, boolean template variable is server-derived, no secrets or injection vectors.

#### 2. Correctness — PASS
- **Minor:** `wait_for_modal_hidden` in `tests/functional/selenium_utils.py` uses a lambda with `modal.get_attribute('class')` without catching `StaleElementReferenceException`. Could produce opaque failures if element goes stale during wait.
- **Minor:** `emailValidationModalOpener` and the validate-button click handler in `handleUserHasAccountNotEmailValidated` duplicate the same three-step sequence (switchModal / logoutOnExit / initEmailValidationForm). Future changes risk divergence.

#### 3. Simplicity & Conciseness — PASS
- **Minor (skill files only):** Plan-reviewer SKILL.md launches parallel fix subagents that could conflict writing the same file; plan-creator research-prompts.md has an invalid JSON comment in a template block; plan-reviewer references AskUserQuestion without a fallback. All are `.claude/` skill documentation, not application code.

#### 4. Test Coverage — PASS
- **Minor:** `emailValidationModalOpener` has no JS unit test covering its composition (switchModal + initEmailValidationForm + logoutOnExit binding).
- **Minor:** The `show.bs.modal` cleanup handlers added to all four form init functions have no JS unit tests asserting form reset behavior.
- **Minor:** The new 429 HTML response branch in `handleForgotPasswordFailure` and `handleResetPasswordFailure` has no dedicated test.

#### 5. Completeness & Cleanup — PASS
No debug artifacts, commented-out code, TODOs, stubs, or accidental temp files.

#### 6. Consistency & Style — PASS
- **Minor:** All four `show.bs.modal` handlers use `$modal.find('#SplashModalAlertBanner').addClass('d-none')` instead of the project-standard `hideSplashModalAlertBanner($modal)` utility. Inconsistent CSS class management (d-none vs custom banner classes).

#### 7. Integration Risk — PASS
No breaking API, schema, or cross-module risks. GET route redirect changes are consistent throughout routes, templates, and tests.

### To-Do: Required Changes

- [x] **Replace `d-none` with `hideSplashModalAlertBanner($modal)`** — `frontend/splash/email-validation-form.js`, `frontend/splash/forgot-password-form.js`, `frontend/splash/login-form.js`, `frontend/splash/register-form.js` — Each `show.bs.modal` handler uses `.addClass('d-none')` to hide the alert banner; replace with the project-standard `hideSplashModalAlertBanner($modal)` call for consistent CSS class management
- [x] **Guard `wait_for_modal_hidden` against stale elements** — `tests/functional/selenium_utils.py` — Wrap the lambda body in `try/except StaleElementReferenceException` returning `False` on staleness, so it times out gracefully rather than raising an opaque exception
- [x] **Extract shared email-validation modal opener logic** — `frontend/splash/init.js` — The validate-button click handler in `handleUserHasAccountNotEmailValidated` duplicates the same sequence as `emailValidationModalOpener`; call `emailValidationModalOpener` from the click handler instead
- [x] **Add JS unit test for `emailValidationModalOpener`** — `frontend/splash/__tests__/init.test.js` — Test that `emailValidationModalOpener('#RegisterModal')` calls `switchModal` with correct selectors, calls `initEmailValidationForm`, and registers `hide.bs.modal` logout binding
- [x] **Add JS unit tests for `show.bs.modal` reset handlers** — `frontend/splash/__tests__/init.test.js` (or per-form test files) — Test that triggering `show.bs.modal` on each modal removes `.invalid-feedback`, removes `.is-invalid`, and hides the alert banner
- [x] **Add JS unit test for 429 HTML response in forgot-password and reset-password** — `frontend/splash/__tests__/forgot-password-form.test.js`, `frontend/splash/__tests__/reset-password-form.test.js` — Mock an xhr with `status=429` and `Content-Type: text/html`, verify `showNewPageOnAJAXHTMLResponse` is called

## Review 2
Generated: 2026-03-27 16:45
Comparison: origin/refactor/splash-modal-prerender...HEAD
Verdict: **PUSHED WITH MINOR FINDINGS**

### Results by Reviewer

#### 1. Safety & Security — PASS
No security vulnerabilities found. Removed GET redirect routes reduce attack surface. No secrets, injection vectors, or OWASP issues.

#### 2. Correctness — PASS (after fix)
- **Fixed:** Duplicate `wait_for_modal_hidden` definition in `selenium_utils.py` (lines 594 and 622). First copy lacked `StaleElementReferenceException` guard. Removed in commit b865a04.

#### 3. Simplicity & Conciseness — PASS
- **Minor:** `const modalElement = $modal[0]` in `reset-password-form.js:68` is a single-use variable; could be inlined.
- **Minor:** The 3-line `show.bs.modal` reset block (remove `.invalid-feedback`, remove `.is-invalid`, `hideSplashModalAlertBanner`) is copy-pasted in login, register, and forgot-password form inits. Could be extracted to a shared helper.

#### 4. Test Coverage — PASS
All review 1 test coverage items were addressed. Minor: `initSplash` auto-show email validation branch has no JS unit test (covered by UI/Selenium tests).

#### 5. Completeness & Cleanup — PASS
No debug artifacts, TODOs, stubs, or accidental files.

#### 6. Consistency & Style — PASS (after fix)
- **Fixed:** Duplicate `wait_for_modal_hidden` removed.
- **Minor:** `FORGOT_PASSWORD_PAGE` constant name implies a GET page but now resolves to POST-only handler. No functional impact.

#### 7. Integration Risk — PASS
No breaking changes. All callers of refactored JS functions updated. Removed GET routes have same URL paths as remaining POST routes.

### To-Do: Required Changes

- [x] **Remove duplicate `wait_for_modal_hidden` definition** — `tests/functional/selenium_utils.py` — First copy (line 594-603) lacks `StaleElementReferenceException` guard and is silently overridden by second definition (line 622-638). Remove the first copy. *(Fixed in commit b865a04)*
- [ ] **Inline single-use `modalElement` variable** — `frontend/splash/reset-password-form.js:68-69` — Replace `const modalElement = $modal[0]; bootstrap.Modal.getOrCreateInstance(modalElement).hide()` with `bootstrap.Modal.getOrCreateInstance($modal[0]).hide()`
- [ ] **Consider extracting shared show.bs.modal reset handler** — `frontend/splash/login-form.js`, `register-form.js`, `forgot-password-form.js` — The identical 3-line block could be a `resetFormState($modal)` helper, but this is optional given the simplicity
