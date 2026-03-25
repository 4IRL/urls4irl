# Changelog — 03/24/2026

- [HH:MM] code-change: Replaced hardcoded "Please enter a valid email address." literal with INVALID_EMAIL_STR constant in tests/functional/splash_ui/test_forgot_password_ui.py (lines 222, 242) and tests/integration/splash/test_forgot_password.py (line 159)
- [HH:MM] code-change: Renamed camelCase Pydantic fields to snake_case with camelCase aliases in RegisterRequest and ResetPasswordRequest (splash.py); updated field_validator names, info.data keys, routes.py attribute access, and unit test assertion
- [22:45] code-change: Removed ValidateEmailForm FlaskForm — replaced with plain HTML + csrf_token() in validate_email templates, added id="submit" to button
- [22:45] code-change: Fixed relative imports to absolute in tags.py, urls.py, utubs.py schemas
- [22:50] git-commit: Committed 2 changes — PR review fixes (snake_case aliases, ValidateEmailForm removal, test constants) and absolute import fixes
- [22:52] git-push: Pushed 2 commits to origin/refactor/splash-json-migration-from-forms, updated PR #557
- [22:55] ci-monitor: CI run 23528492814 on refactor/splash-json-migration-from-forms — PASSED (all jobs succeeded)
