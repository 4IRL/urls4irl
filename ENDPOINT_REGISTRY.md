# Endpoint Registry

Cross-layer navigation map for every route in the application. Each entry traces:
**Route → Handler → Service → Template → JS Module → Tests**

Last updated: 2026-03-25

---

## Splash Blueprint

Base path: `/splash` (registered without url_prefix in some routes — paths shown as served)

### GET /

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:splash_page` |
| **Decorators** | None |
| **Service** | `render_template()` direct |
| **Template** | `pages/splash.html` |
| **JS Module** | `frontend/splash/init.js` |
| **Tests** | `tests/integration/splash/test_login_register_home_screen.py` (marker: `splash`) |

### GET /login

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:login_page` |
| **Decorators** | `@no_authenticated_users_allowed` |
| **Service** | `render_template()` direct |
| **Template** | `components/splash/login.html` |
| **JS Module** | `frontend/splash/init.js` (loads form), `frontend/splash/login-form.js` (handles submit) |
| **Tests** | `tests/integration/splash/test_login_user.py` (marker: `splash`), `tests/functional/splash_ui/test_login_user_ui.py` (marker: `splash_ui`) |

### POST /login

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:login` |
| **Decorators** | `@no_authenticated_users_allowed`, `@parse_json_body(LoginRequest)` |
| **Service** | `backend/splash/services/login.py:login_user_to_u4i` |
| **Schema** | `backend/schemas/requests/splash/login.py:LoginRequest` |
| **JS Module** | `frontend/splash/login-form.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag `<meta name="csrf-token">` via `components/head/meta.html` |
| **Tests** | `tests/integration/splash/test_login_user.py` (marker: `splash`), `tests/integration/splash/test_invalid_json_body.py` (marker: `splash`), `tests/functional/splash_ui/test_login_user_ui.py` (marker: `splash_ui`) |

### GET /register

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:register_user_page` |
| **Decorators** | `@no_authenticated_users_allowed` |
| **Service** | `render_template()` direct |
| **Template** | `components/splash/register_user.html` |
| **JS Module** | `frontend/splash/init.js` (loads form), `frontend/splash/register-form.js` (handles submit) |
| **Tests** | `tests/integration/splash/test_register_user.py` (marker: `splash`), `tests/functional/splash_ui/test_register_user_ui.py` (marker: `splash_ui`) |

### POST /register

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:register_user` |
| **Decorators** | `@no_authenticated_users_allowed`, `@parse_json_body(RegisterRequest)` |
| **Service** | `backend/splash/services/register.py:register_new_user` |
| **Schema** | `backend/schemas/requests/splash/register.py:RegisterRequest` |
| **JS Module** | `frontend/splash/register-form.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/splash/test_register_user.py` (marker: `splash`), `tests/integration/splash/test_invalid_json_body.py` (marker: `splash`), `tests/functional/splash_ui/test_register_user_ui.py` (marker: `splash_ui`), `tests/unit/schemas/test_splash_schemas.py` (marker: `unit`) |

### GET /confirm-email

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:confirm_email_after_register` |
| **Decorators** | None |
| **Service** | `render_template()` direct |
| **Template** | `components/splash/validate_email.html` |
| **JS Module** | `frontend/splash/init.js` (loads form), `frontend/splash/email-validation-form.js` (handles submit) |
| **Tests** | `tests/integration/splash/test_email_validation.py` (marker: `splash`), `tests/functional/splash_ui/test_validate_email_ui.py` (marker: `splash_ui`) |

### POST /send-validation-email

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:send_validation_email` |
| **Decorators** | None |
| **Service** | `backend/splash/services/email_validation.py:send_validation_email_to_user` |
| **JS Module** | `frontend/splash/email-validation-form.js` — form serialize |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/splash/test_email_validation.py` (marker: `splash`), `tests/functional/splash_ui/test_validate_email_ui.py` (marker: `splash_ui`) |

### GET /validate/expired

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:validate_email_expired` |
| **Decorators** | None |
| **Service** | DB query + `login_user()` |
| **Template** | `pages/splash.html` (with `email_token_is_expired=True`) |
| **JS Module** | `frontend/splash/email-validation-form.js` |
| **Tests** | `tests/integration/splash/test_email_validation.py` (marker: `splash`), `tests/functional/splash_ui/test_validate_email_ui.py` (marker: `splash_ui`) |

### GET /validate/\<token\>

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:validate_email` |
| **Decorators** | None |
| **Service** | `backend/splash/services/email_validation.py:validate_email_for_user` |
| **Template** | Redirect (no template) |
| **Tests** | `tests/integration/splash/test_email_validation.py` (marker: `splash`) |

### GET /forgot-password

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:forgot_password_page` |
| **Decorators** | `@no_authenticated_users_allowed` |
| **Service** | `render_template()` direct |
| **Template** | `components/splash/forgot_password.html` |
| **JS Module** | `frontend/splash/login-form.js` (loads form), `frontend/splash/forgot-password-form.js` (handles submit) |
| **Tests** | `tests/integration/splash/test_forgot_password.py` (marker: `splash`), `tests/functional/splash_ui/test_forgot_password_ui.py` (marker: `splash_ui`) |

### POST /forgot-password

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:forgot_password` |
| **Decorators** | `@no_authenticated_users_allowed`, `@parse_json_body(ForgotPasswordRequest)` |
| **Service** | `backend/splash/services/forgot_password.py:send_forgot_password_email_to_user` |
| **Schema** | `backend/schemas/requests/splash/forgot_password.py:ForgotPasswordRequest` |
| **JS Module** | `frontend/splash/forgot-password-form.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/splash/test_forgot_password.py` (marker: `splash`), `tests/integration/splash/test_invalid_json_body.py` (marker: `splash`), `tests/functional/splash_ui/test_forgot_password_ui.py` (marker: `splash_ui`) |

### GET /reset-password/\<token\>

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:reset_password_page` |
| **Decorators** | None |
| **Service** | `backend/splash/services/reset_password.py:get_reset_password_page` |
| **Template** | `components/splash/reset_password.html` |
| **JS Module** | `frontend/splash/reset-password-form.js` |
| **Tests** | `tests/integration/splash/test_reset_password.py` (marker: `splash`), `tests/functional/splash_ui/test_reset_password_ui.py` (marker: `splash_ui`) |

### POST /reset-password/\<token\>

| Layer | Location |
|---|---|
| **Handler** | `backend/splash/routes.py:reset_password` |
| **Decorators** | `@parse_json_body(ResetPasswordRequest)` |
| **Service** | `backend/splash/services/reset_password.py:reset_password_for_user` |
| **Schema** | `backend/schemas/requests/splash/reset_password.py:ResetPasswordRequest` |
| **JS Module** | `frontend/splash/reset-password-form.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/splash/test_reset_password.py` (marker: `splash`), `tests/integration/splash/test_invalid_json_body.py` (marker: `splash`), `tests/functional/splash_ui/test_reset_password_ui.py` (marker: `splash_ui`) |

---

## UTubs Blueprint

Base path: `/utubs` (some routes served at `/home`)

### GET /home

| Layer | Location |
|---|---|
| **Handler** | `backend/utubs/routes.py:home` |
| **Decorators** | `@email_validation_required` |
| **Service** | `backend/utubs/services/home_page.py:render_home_page` |
| **Template** | `pages/home.html` |
| **JS Module** | `frontend/home/` (entire module tree) |
| **Tests** | `tests/integration/utubs/test_get_home_route.py` (marker: `utubs`), `tests/functional/home_ui/test_home_ui.py` (marker: `home_ui`) |

### POST /utubs

| Layer | Location |
|---|---|
| **Handler** | `backend/utubs/routes.py:create_utub` |
| **Decorators** | `@email_validation_required`, `@parse_json_body(CreateUTubRequest)` |
| **Service** | `backend/utubs/services/create_utub.py:create_new_utub` |
| **Schema** | `backend/schemas/requests/utubs/create_utub.py:CreateUTubRequest` |
| **JS Module** | `frontend/home/utubs/create.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/utubs/test_add_utub_route.py` (marker: `utubs`), `tests/functional/utubs_ui/test_create_utub_ui.py` (marker: `utubs_ui`) |

### GET /utubs/\<utub_id\>

| Layer | Location |
|---|---|
| **Handler** | `backend/utubs/routes.py:get_single_utub` |
| **Decorators** | `@xml_http_request_only`, `@utub_membership_required` |
| **Service** | `backend/utubs/services/get_utub.py:get_single_utub_for_user` |
| **JS Module** | `frontend/home/utubs/selectors.js` |
| **Tests** | `tests/integration/utubs/test_get_detailed_utub_info.py` (marker: `utubs`), `tests/functional/utubs_ui/test_select_utub_ui.py` (marker: `utubs_ui`) |

### GET /utubs

| Layer | Location |
|---|---|
| **Handler** | `backend/utubs/routes.py:get_utubs` |
| **Decorators** | `@xml_http_request_only`, `@email_validation_required` |
| **Service** | `backend/utubs/services/get_utub.py:get_all_utubs_of_user` |
| **JS Module** | `frontend/home/utubs/selectors.js` |
| **Tests** | `tests/integration/utubs/test_get_utubs_summary_route.py` (marker: `utubs`) |

### PATCH /utubs/\<utub_id\>/name

| Layer | Location |
|---|---|
| **Handler** | `backend/utubs/routes.py:update_utub_name` |
| **Decorators** | `@utub_creator_required`, `@parse_json_body(UpdateUTubNameRequest)` |
| **Service** | `backend/utubs/services/update_utub.py:update_utub_name_if_new` |
| **Schema** | `backend/schemas/requests/utubs/update_utub.py:UpdateUTubNameRequest` |
| **JS Module** | `frontend/home/urls/update-name.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/utubs/test_update_utub_name_route.py` (marker: `utubs`), `tests/functional/utubs_ui/test_update_utub_name_ui.py` (marker: `utubs_ui`) |

### PATCH /utubs/\<utub_id\>/description

| Layer | Location |
|---|---|
| **Handler** | `backend/utubs/routes.py:update_utub_desc` |
| **Decorators** | `@utub_creator_required`, `@parse_json_body(UpdateUTubDescriptionRequest)` |
| **Service** | `backend/utubs/services/update_utub.py:update_utub_desc_if_new` |
| **Schema** | `backend/schemas/requests/utubs/update_utub.py:UpdateUTubDescriptionRequest` |
| **JS Module** | `frontend/home/urls/update-description.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/utubs/test_update_utub_desc_route.py` (marker: `utubs`), `tests/functional/utubs_ui/test_update_utub_description_ui.py` (marker: `utubs_ui`) |

### DELETE /utubs/\<utub_id\>

| Layer | Location |
|---|---|
| **Handler** | `backend/utubs/routes.py:delete_utub` |
| **Decorators** | `@utub_creator_required` |
| **Service** | `backend/utubs/services/delete_utub.py:delete_utub_for_user` |
| **JS Module** | `frontend/home/utubs/delete.js` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/utubs/test_delete_utub_route.py` (marker: `utubs`), `tests/functional/utubs_ui/test_delete_utub_ui.py` (marker: `utubs_ui`) |

---

## URLs Blueprint

Base path: `/utubs/<utub_id>/urls`

### POST /utubs/\<utub_id\>/urls

| Layer | Location |
|---|---|
| **Handler** | `backend/urls/routes.py:create_url` |
| **Decorators** | `@utub_membership_required`, `@parse_json_body(CreateURLRequest)` |
| **Service** | `backend/urls/services/create_url.py:create_url_in_utub` |
| **Schema** | `backend/schemas/requests/urls/create_url.py:CreateURLRequest` |
| **JS Module** | `frontend/home/urls/cards/create.js` — `JSON.stringify`, `application/json`, 35s timeout |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/urls/test_add_url_to_utub_route.py` (marker: `urls`), `tests/functional/urls_ui/test_create_url_ui.py` (marker: `create_urls_ui`) |

### GET /utubs/\<utub_id\>/urls/\<utub_url_id\>

| Layer | Location |
|---|---|
| **Handler** | `backend/urls/routes.py:get_url` |
| **Decorators** | `@xml_http_request_only`, `@utub_membership_with_valid_url_in_utub_required` |
| **Service** | `APIResponse()` direct |
| **JS Module** | `frontend/home/urls/cards/get.js`, also called from `update-string.js`, `update-title.js`, `delete.js`, `frontend/home/urls/tags/create.js`, `frontend/home/urls/tags/delete.js` |
| **Tests** | `tests/integration/urls/test_get_url_in_utub_route.py` (marker: `urls`) |

### PATCH /utubs/\<utub_id\>/urls/\<utub_url_id\>

| Layer | Location |
|---|---|
| **Handler** | `backend/urls/routes.py:update_url` |
| **Decorators** | `@utub_membership_with_valid_url_in_utub_required`, `@parse_json_body(UpdateURLStringRequest)` |
| **Service** | `backend/urls/services/update_url.py:update_url_in_utub` |
| **Schema** | `backend/schemas/requests/urls/update_url.py:UpdateURLStringRequest` |
| **JS Module** | `frontend/home/urls/cards/update-string.js` — `JSON.stringify`, `application/json`, 35s timeout |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/urls/test_update_url_route.py` (marker: `urls`), `tests/functional/urls_ui/test_update_url_ui.py` (marker: `update_urls_ui`) |

### PATCH /utubs/\<utub_id\>/urls/\<utub_url_id\>/title

| Layer | Location |
|---|---|
| **Handler** | `backend/urls/routes.py:update_url_title` |
| **Decorators** | `@utub_membership_with_valid_url_in_utub_required`, `@parse_json_body(UpdateURLTitleRequest)` |
| **Service** | `backend/urls/services/update_url_title.py:update_url_title_if_new` |
| **Schema** | `backend/schemas/requests/urls/update_url.py:UpdateURLTitleRequest` |
| **JS Module** | `frontend/home/urls/cards/update-title.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/urls/test_update_url_title_route.py` (marker: `urls`), `tests/functional/urls_ui/test_update_url_ui.py` (marker: `update_urls_ui`) |

### DELETE /utubs/\<utub_id\>/urls/\<utub_url_id\>

| Layer | Location |
|---|---|
| **Handler** | `backend/urls/routes.py:delete_url` |
| **Decorators** | `@utub_membership_with_valid_url_in_utub_required` |
| **Service** | `backend/urls/services/delete_url.py:delete_url_in_utub` |
| **JS Module** | `frontend/home/urls/cards/delete.js` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/urls/test_remove_url_from_utub_route.py` (marker: `urls`), `tests/functional/urls_ui/test_delete_url_ui.py` (marker: `urls_ui`) |

---

## Members Blueprint

Base path: `/utubs/<utub_id>/members`

### POST /utubs/\<utub_id\>/members

| Layer | Location |
|---|---|
| **Handler** | `backend/members/routes.py:create_member` |
| **Decorators** | `@utub_creator_required`, `@parse_json_body(AddMemberRequest)` |
| **Service** | `backend/members/services/create_member.py:create_utub_member` |
| **Schema** | `backend/schemas/requests/members/add_member.py:AddMemberRequest` |
| **JS Module** | `frontend/home/members/create.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/members/test_add_member_to_utub_route.py` (marker: `members`), `tests/functional/members_ui/test_create_member_ui.py` (marker: `members_ui`) |

### DELETE /utubs/\<utub_id\>/members/\<user_id\>

| Layer | Location |
|---|---|
| **Handler** | `backend/members/routes.py:remove_member` |
| **Decorators** | `@utub_membership_required` |
| **Service** | `backend/members/services/remove_member.py:remove_member_or_self_from_utub` |
| **JS Module** | `frontend/home/members/delete.js` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/members/test_remove_member_from_utub_route.py` (marker: `members`), `tests/functional/members_ui/test_delete_member_ui.py` (marker: `members_ui`), `tests/functional/members_ui/test_leave_utub.py` (marker: `members_ui`) |

---

## Tags Blueprint — UTub Tags

Base path: `/utubs/<utub_id>/tags`

### POST /utubs/\<utub_id\>/tags

| Layer | Location |
|---|---|
| **Handler** | `backend/tags/utub_tag_routes.py:create_utub_tag` |
| **Decorators** | `@utub_membership_required`, `@parse_json_body(AddTagRequest)` |
| **Service** | `backend/tags/services/create_utub_tag.py:create_tag_in_utub` |
| **Schema** | `backend/schemas/requests/tags/add_tag.py:AddTagRequest` |
| **JS Module** | `frontend/home/tags/create.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/tags/test_add_tags_to_utub_route.py` (marker: `tags`), `tests/functional/tags_ui/test_create_utub_tag_ui.py` (marker: `tags_ui`) |

### DELETE /utubs/\<utub_id\>/tags/\<utub_tag_id\>

| Layer | Location |
|---|---|
| **Handler** | `backend/tags/utub_tag_routes.py:delete_utub_tag` |
| **Decorators** | `@utub_membership_with_valid_utub_tag` |
| **Service** | `backend/tags/services/delete_utub_tag.py:delete_utub_tag_from_utub_and_utub_urls` |
| **JS Module** | `frontend/home/tags/delete.js` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/tags/test_delete_tag_from_utub_route.py` (marker: `tags`), `tests/functional/tags_ui/test_delete_utub_tag_ui.py` (marker: `tags_ui`) |

---

## Tags Blueprint — URL Tags

Base path: `/utubs/<utub_id>/urls/<utub_url_id>/tags`

### POST /utubs/\<utub_id\>/urls/\<utub_url_id\>/tags

| Layer | Location |
|---|---|
| **Handler** | `backend/tags/url_tag_routes.py:create_utub_url_tag` |
| **Decorators** | `@utub_membership_with_valid_url_in_utub_required`, `@parse_json_body(AddTagRequest)` |
| **Service** | `backend/tags/services/create_url_tag.py:add_tag_to_url_if_valid` |
| **Schema** | `backend/schemas/requests/tags/add_tag.py:AddTagRequest` |
| **JS Module** | `frontend/home/urls/tags/create.js` — `JSON.stringify`, `application/json` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/tags/test_add_tag_to_url_route.py` (marker: `tags`), `tests/functional/tags_ui/test_create_tag_ui.py` (marker: `tags_ui`) |

### DELETE /utubs/\<utub_id\>/urls/\<utub_url_id\>/tags/\<utub_tag_id\>

| Layer | Location |
|---|---|
| **Handler** | `backend/tags/url_tag_routes.py:delete_utub_url_tag` |
| **Decorators** | `@utub_membership_with_valid_url_tag` |
| **Service** | `backend/tags/services/delete_url_tag.py:delete_url_tag` |
| **JS Module** | `frontend/home/urls/tags/delete.js` |
| **CSRF** | Meta tag |
| **Tests** | `tests/integration/tags/test_delete_tag_from_url_route.py` (marker: `tags`), `tests/functional/tags_ui/test_delete_tag_ui.py` (marker: `tags_ui`) |

---

## Users Blueprint

### GET /logout

| Layer | Location |
|---|---|
| **Handler** | `backend/users/routes.py:logout` |
| **Decorators** | None |
| **Service** | `logout_user()` |
| **Template** | Redirect to splash |
| **JS Module** | `frontend/splash/email-validation-form.js`, `frontend/splash/init.js` |
| **Tests** | `tests/integration/splash/test_login_register_home_screen.py` (marker: `splash`) |

### GET /privacy-policy

| Layer | Location |
|---|---|
| **Handler** | `backend/users/routes.py:privacy_policy` |
| **Decorators** | None |
| **Service** | `render_template()` direct |
| **Template** | `pages/privacy_policy.html` (vars: `is_privacy_or_terms=True`) |
| **Tests** | None identified |

### GET /terms

| Layer | Location |
|---|---|
| **Handler** | `backend/users/routes.py:terms_and_conditions` |
| **Decorators** | None |
| **Service** | `render_template()` direct |
| **Template** | `pages/terms_and_conditions.html` (vars: `is_privacy_or_terms=True`) |
| **Tests** | None identified |

---

## Contact Blueprint

### GET/POST /contact

| Layer | Location |
|---|---|
| **Handler** | `backend/contact/routes.py:contact_us` |
| **Decorators** | `@limiter.limit("5 per hour, 10 per day", methods=["POST"])` |
| **Service** | GET: `backend/contact/contact_us.py:load_contact_us_page`, POST: `backend/contact/contact_us.py:validate_and_contact` |
| **Template** | `pages/contact_us.html` (vars: `contact_form`, `is_contact_form`, `contacted`) |
| **CSRF** | WTForms `hidden_tag()` (unique — all other forms use meta tag) |
| **Tests** | `tests/integration/account_and_support/test_contact_us.py` (marker: `account_and_support`) |

---

## System Blueprint

### GET /health

| Layer | Location |
|---|---|
| **Handler** | `backend/system/routes.py:health` |
| **Decorators** | `@limiter.exempt` |
| **Service** | `APIResponse()` direct |
| **Tests** | None identified |

---

## Debug Blueprint (dev only)

### POST /debug

| Layer | Location |
|---|---|
| **Handler** | `backend/debug/routes.py:debug_endpoint` |
| **Decorators** | None |
| **Service** | `print()` debug |
| **JS Module** | `frontend/lib/ajax.js:debugCall` |
| **Notes** | Only registered when NOT in testing or production |

---

## Cross-Cutting Patterns

### CSRF Token Delivery
- **Primary**: Meta tag `<meta name="csrf-token">` in `components/head/meta.html` — used by all JS modules
- **Exception**: Contact form uses WTForms `hidden_tag()`

### AJAX Patterns
- All home page operations use `frontend/lib/ajax.js:ajaxCall` wrapper (jQuery `$.ajax`)
- Data format: `JSON.stringify` with `contentType: "application/json"` for POST/PATCH
- DELETE operations send empty body array `[]`
- Global 429 handler in `ajaxCall()` — replaces page with rate limit HTML
- Default timeout: 1000ms; URL create/update: 35000ms

### Decorator Stack (typical ordering)
1. Auth gate: `@email_validation_required` / `@no_authenticated_users_allowed`
2. Membership: `@utub_membership_required` / `@utub_creator_required` / `@utub_membership_with_valid_*`
3. Request parsing: `@parse_json_body(SchemaClass)`
4. AJAX enforcement: `@xml_http_request_only` (GET-only routes)

### Test Markers
| Marker | Integration tests | UI tests |
|---|---|---|
| `splash` / `splash_ui` | 7 files | 7 files |
| `utubs` / `utubs_ui` | 7 files | 6 files |
| `urls` / `create_urls_ui` / `update_urls_ui` / `urls_ui` | 6 files | 6 files |
| `members` / `members_ui` | 2 files | 3 files |
| `tags` / `tags_ui` | 4 files | 7 files |
| `account_and_support` | 1 file | — |
| `home_ui` | — | 4 files |
| `mobile_ui` | — | 4+ files |
| `unit` | 18 files | — |
| `cli` | 4 files | — |
