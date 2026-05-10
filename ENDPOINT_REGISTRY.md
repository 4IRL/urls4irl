# Endpoint Registry

Cross-layer navigation map for every route in the application. Each entry traces:
**Route → Handler → Service → Template → JS Module → Tests**

Last updated: 2026-04-04

---

## Splash Blueprint

Base path: `/splash` (registered without url_prefix in some routes — paths shown as served)

### GET /

| Layer          | Location                                                                         |
| -------------- | -------------------------------------------------------------------------------- |
| **Handler**    | `backend/splash/routes.py:splash_page`                                           |
| **Decorators** | None                                                                             |
| **Service**    | `render_template()` direct                                                       |
| **Template**   | `pages/splash.html`                                                              |
| **JS Module**  | `frontend/splash/init.ts`                                                        |
| **Tests**      | `tests/integration/splash/test_login_register_home_screen.py` (marker: `splash`) |

### POST /login

| Layer          | Location                                                                                                                                                                                                                                                                                            |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/splash/routes.py:login`                                                                                                                                                                                                                                                                    |
| **Decorators** | `@no_authenticated_users_allowed`, `@api_route(request_schema=LoginRequest, response_schema=LoginRedirectResponseSchema, ajax_required=False, tags=["auth"], description="Log in to an existing account", status_codes={200: LoginRedirectResponseSchema, 400: ErrorResponse, 401: ErrorResponse})` |
| **Service**    | `backend/splash/services/login.py:login_user_to_u4i`                                                                                                                                                                                                                                                |
| **Schema**     | `backend/schemas/requests/splash/login.py:LoginRequest`                                                                                                                                                                                                                                             |
| **JS Module**  | `frontend/splash/login-form.ts` — `JSON.stringify`, `application/json`                                                                                                                                                                                                                              |
| **CSRF**       | Meta tag `<meta name="csrf-token">` via `components/head/meta.html`                                                                                                                                                                                                                                 |
| **Tests**      | `tests/integration/splash/test_login_user.py` (marker: `splash`), `tests/integration/splash/test_invalid_json_body.py` (marker: `splash`), `tests/functional/splash_ui/test_login_user_ui.py` (marker: `splash_ui`)                                                                                 |

### POST /register

| Layer          | Location                                                                                                                                                                                                                                                                                   |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Handler**    | `backend/splash/routes.py:register_user`                                                                                                                                                                                                                                                   |
| **Decorators** | `@no_authenticated_users_allowed`, `@api_route(request_schema=RegisterRequest, response_schema=RegisterResponseSchema, ajax_required=False, tags=["auth"], description="Register a new user account", status_codes={201: RegisterResponseSchema, 400: ErrorResponse, 401: ErrorResponse})` |
| **Service**    | `backend/splash/services/register.py:register_new_user`                                                                                                                                                                                                                                    |
| **Schema**     | `backend/schemas/requests/splash/register.py:RegisterRequest`                                                                                                                                                                                                                              |
| **JS Module**  | `frontend/splash/register-form.ts` — `JSON.stringify`, `application/json`                                                                                                                                                                                                                  |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                                   |
| **Tests**      | `tests/integration/splash/test_register_user.py` (marker: `splash`), `tests/integration/splash/test_invalid_json_body.py` (marker: `splash`), `tests/functional/splash_ui/test_register_user_ui.py` (marker: `splash_ui`), `tests/unit/schemas/test_splash_schemas.py` (marker: `unit`)    |

### GET /confirm-email

| Layer          | Location                                                                                                                                             |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/splash/routes.py:confirm_email_after_register`                                                                                              |
| **Decorators** | None                                                                                                                                                 |
| **Service**    | Redirects: authenticated+validated users to home, all others to splash page                                                                          |
| **Template**   | None (redirect only)                                                                                                                                 |
| **Tests**      | `tests/integration/splash/test_email_validation.py` (marker: `splash`), `tests/functional/splash_ui/test_validate_email_ui.py` (marker: `splash_ui`) |

### POST /send-validation-email

| Layer          | Location                                                                                                                                                                                                                                                                        |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/splash/routes.py:send_validation_email`                                                                                                                                                                                                                                |
| **Decorators** | `@api_route(response_schema=EmailValidationResponseSchema, ajax_required=False, tags=["auth"], description="Send an email validation link to the current user", status_codes={200: EmailValidationResponseSchema, 400: ErrorResponse, 404: ErrorResponse, 429: ErrorResponse})` |
| **Service**    | `backend/splash/services/email_validation.py:send_validation_email_to_user`                                                                                                                                                                                                     |
| **JS Module**  | `frontend/splash/email-validation-form.ts` — form serialize                                                                                                                                                                                                                     |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                        |
| **Tests**      | `tests/integration/splash/test_email_validation.py` (marker: `splash`), `tests/functional/splash_ui/test_validate_email_ui.py` (marker: `splash_ui`)                                                                                                                            |

### GET /validate/expired

| Layer          | Location                                                                                                                                             |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/splash/routes.py:validate_email_expired`                                                                                                    |
| **Decorators** | None                                                                                                                                                 |
| **Service**    | DB query + `login_user()`                                                                                                                            |
| **Template**   | `pages/splash.html` (with `email_token_is_expired=True`)                                                                                             |
| **JS Module**  | `frontend/splash/email-validation-form.ts`                                                                                                           |
| **Tests**      | `tests/integration/splash/test_email_validation.py` (marker: `splash`), `tests/functional/splash_ui/test_validate_email_ui.py` (marker: `splash_ui`) |

### GET /validate/\<token\>

| Layer          | Location                                                               |
| -------------- | ---------------------------------------------------------------------- |
| **Handler**    | `backend/splash/routes.py:validate_email`                              |
| **Decorators** | None                                                                   |
| **Service**    | `backend/splash/services/email_validation.py:validate_email_for_user`  |
| **Template**   | Redirect (no template)                                                 |
| **Tests**      | `tests/integration/splash/test_email_validation.py` (marker: `splash`) |

### POST /forgot-password

| Layer          | Location                                                                                                                                                                                                                                                                                 |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/splash/routes.py:forgot_password`                                                                                                                                                                                                                                               |
| **Decorators** | `@no_authenticated_users_allowed`, `@api_route(request_schema=ForgotPasswordRequest, response_schema=ForgotPasswordResponseSchema, ajax_required=False, tags=["auth"], description="Send a password reset email", status_codes={200: ForgotPasswordResponseSchema, 400: ErrorResponse})` |
| **Service**    | `backend/splash/services/forgot_password.py:send_forgot_password_email_to_user`                                                                                                                                                                                                          |
| **Schema**     | `backend/schemas/requests/splash/forgot_password.py:ForgotPasswordRequest`                                                                                                                                                                                                               |
| **JS Module**  | `frontend/splash/forgot-password-form.ts` — `JSON.stringify`, `application/json`                                                                                                                                                                                                         |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                                 |
| **Tests**      | `tests/integration/splash/test_forgot_password.py` (marker: `splash`), `tests/integration/splash/test_invalid_json_body.py` (marker: `splash`), `tests/functional/splash_ui/test_forgot_password_ui.py` (marker: `splash_ui`)                                                            |

### GET /reset-password/\<token\>

| Layer          | Location                                                                                                                                           |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/splash/routes.py:reset_password_page`                                                                                                     |
| **Decorators** | None                                                                                                                                               |
| **Service**    | `backend/splash/services/reset_password.py:get_reset_password_page`                                                                                |
| **Template**   | `components/splash/reset_password.html`                                                                                                            |
| **JS Module**  | `frontend/splash/reset-password-form.ts`                                                                                                           |
| **Tests**      | `tests/integration/splash/test_reset_password.py` (marker: `splash`), `tests/functional/splash_ui/test_reset_password_ui.py` (marker: `splash_ui`) |

### POST /reset-password/\<token\>

| Layer          | Location                                                                                                                                                                                                                                                                            |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/splash/routes.py:reset_password`                                                                                                                                                                                                                                           |
| **Decorators** | `@api_route(request_schema=ResetPasswordRequest, response_schema=ResetPasswordResponseSchema, ajax_required=False, tags=["auth"], description="Reset a user password with a valid token", status_codes={200: ResetPasswordResponseSchema, 400: ErrorResponse, 404: ErrorResponse})` |
| **Service**    | `backend/splash/services/reset_password.py:reset_password_for_user`                                                                                                                                                                                                                 |
| **Schema**     | `backend/schemas/requests/splash/reset_password.py:ResetPasswordRequest`                                                                                                                                                                                                            |
| **JS Module**  | `frontend/splash/reset-password-form.ts` — `JSON.stringify`, `application/json`                                                                                                                                                                                                     |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                            |
| **Tests**      | `tests/integration/splash/test_reset_password.py` (marker: `splash`), `tests/integration/splash/test_invalid_json_body.py` (marker: `splash`), `tests/functional/splash_ui/test_reset_password_ui.py` (marker: `splash_ui`)                                                         |

---

## UTubs Blueprint

Base path: `/utubs` (some routes served at `/home`)

### GET /home

| Layer          | Location                                                                                                                           |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/utubs/routes.py:home`                                                                                                     |
| **Decorators** | `@email_validation_required`                                                                                                       |
| **Service**    | `backend/utubs/services/home_page.py:render_home_page`                                                                             |
| **Template**   | `pages/home.html`                                                                                                                  |
| **JS Module**  | `frontend/home/` (entire module tree)                                                                                              |
| **Tests**      | `tests/integration/utubs/test_get_home_route.py` (marker: `utubs`), `tests/functional/home_ui/test_home_ui.py` (marker: `home_ui`) |

### POST /utubs

| Layer          | Location                                                                                                                                                                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/utubs/routes.py:create_utub`                                                                                                                                                                                                       |
| **Decorators** | `@email_validation_required`, `@api_route(request_schema=CreateUTubRequest, response_schema=UtubCreatedResponseSchema, tags=["utubs"], description="Create a new UTub", status_codes={200: UtubCreatedResponseSchema, 400: ErrorResponse})` |
| **Service**    | `backend/utubs/services/create_utub.py:create_new_utub`                                                                                                                                                                                     |
| **Schema**     | `backend/schemas/requests/utubs/create_utub.py:CreateUTubRequest`                                                                                                                                                                           |
| **JS Module**  | `frontend/home/utubs/create.js` — `JSON.stringify`, `application/json`                                                                                                                                                                      |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                    |
| **Tests**      | `tests/integration/utubs/test_add_utub_route.py` (marker: `utubs`), `tests/functional/utubs_ui/test_create_utub_ui.py` (marker: `utubs_ui`)                                                                                                 |

### GET /utubs/\<utub_id\>

| Layer          | Location                                                                                                                                                                                             |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/utubs/routes.py:get_single_utub`                                                                                                                                                            |
| **Decorators** | `@utub_membership_required`, `@api_route(response_schema=UtubDetailSchema, tags=["utubs"], description="Retrieve data for a single UTub", status_codes={200: UtubDetailSchema, 404: ErrorResponse})` |
| **Schema**     | `backend/schemas/utubs.py:UtubDetailSchema` — `currentUser: int` (integer, not string), `createdAt: str` (ISO 8601 datetime via `field_serializer`)                                                  |
| **Service**    | `backend/utubs/services/get_utub.py:get_single_utub_for_user`                                                                                                                                        |
| **JS Module**  | `frontend/home/utubs/selectors.js`                                                                                                                                                                   |
| **Tests**      | `tests/integration/utubs/test_get_detailed_utub_info.py` (marker: `utubs`), `tests/functional/utubs_ui/test_select_utub_ui.py` (marker: `utubs_ui`)                                                  |

### GET /utubs

| Layer          | Location                                                                                                                                                                                                         |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/utubs/routes.py:get_utubs`                                                                                                                                                                              |
| **Decorators** | `@email_validation_required`, `@api_route(response_schema=UtubSummaryListSchema, tags=["utubs"], description="Retrieve a summary of all UTubs for the current user", status_codes={200: UtubSummaryListSchema})` |
| **Service**    | `backend/utubs/services/get_utub.py:get_all_utubs_of_user`                                                                                                                                                       |
| **JS Module**  | `frontend/home/utubs/selectors.js`                                                                                                                                                                               |
| **Tests**      | `tests/integration/utubs/test_get_utubs_summary_route.py` (marker: `utubs`)                                                                                                                                      |

### PATCH /utubs/\<utub_id\>/name

| Layer          | Location                                                                                                                                                                                                                                                                                     |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/utubs/routes.py:update_utub_name`                                                                                                                                                                                                                                                   |
| **Decorators** | `@utub_creator_required`, `@api_route(request_schema=UpdateUTubNameRequest, response_schema=UtubNameUpdatedResponseSchema, tags=["utubs"], description="Update a UTub name", status_codes={200: UtubNameUpdatedResponseSchema, 400: ErrorResponse, 403: ErrorResponse, 404: ErrorResponse})` |
| **Service**    | `backend/utubs/services/update_utub.py:update_utub_name_if_new`                                                                                                                                                                                                                              |
| **Schema**     | `backend/schemas/requests/utubs/update_utub.py:UpdateUTubNameRequest`                                                                                                                                                                                                                        |
| **JS Module**  | `frontend/home/urls/update-name.ts` — `JSON.stringify`, `application/json`                                                                                                                                                                                                                   |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                                     |
| **Tests**      | `tests/integration/utubs/test_update_utub_name_route.py` (marker: `utubs`), `tests/functional/utubs_ui/test_update_utub_name_ui.py` (marker: `utubs_ui`)                                                                                                                                     |

### PATCH /utubs/\<utub_id\>/description

| Layer          | Location                                                                                                                                                                                                                                                                                                   |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/utubs/routes.py:update_utub_desc`                                                                                                                                                                                                                                                                 |
| **Decorators** | `@utub_creator_required`, `@api_route(request_schema=UpdateUTubDescriptionRequest, response_schema=UtubDescUpdatedResponseSchema, tags=["utubs"], description="Update a UTub description", status_codes={200: UtubDescUpdatedResponseSchema, 400: ErrorResponse, 403: ErrorResponse, 404: ErrorResponse})` |
| **Service**    | `backend/utubs/services/update_utub.py:update_utub_desc_if_new`                                                                                                                                                                                                                                            |
| **Schema**     | `backend/schemas/requests/utubs/update_utub.py:UpdateUTubDescriptionRequest`                                                                                                                                                                                                                               |
| **JS Module**  | `frontend/home/urls/update-description.ts` — `JSON.stringify`, `application/json`                                                                                                                                                                                                                          |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                                                   |
| **Tests**      | `tests/integration/utubs/test_update_utub_desc_route.py` (marker: `utubs`), `tests/functional/utubs_ui/test_update_utub_description_ui.py` (marker: `utubs_ui`)                                                                                                                                            |

### DELETE /utubs/\<utub_id\>

| Layer          | Location                                                                                                                                                                                                              |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/utubs/routes.py:delete_utub`                                                                                                                                                                                 |
| **Decorators** | `@utub_creator_required`, `@api_route(response_schema=UtubDeletedResponseSchema, tags=["utubs"], description="Delete a UTub", status_codes={200: UtubDeletedResponseSchema, 403: ErrorResponse, 404: ErrorResponse})` |
| **Service**    | `backend/utubs/services/delete_utub.py:delete_utub_for_user`                                                                                                                                                          |
| **JS Module**  | `frontend/home/utubs/delete.js`                                                                                                                                                                                       |
| **CSRF**       | Meta tag                                                                                                                                                                                                              |
| **Tests**      | `tests/integration/utubs/test_delete_utub_route.py` (marker: `utubs`), `tests/functional/utubs_ui/test_delete_utub_ui.py` (marker: `utubs_ui`)                                                                        |

---

## URLs Blueprint

Base path: `/utubs/<utub_id>/urls`

### POST /utubs/\<utub_id\>/urls

| Layer          | Location                                                                                                                                                                                                                                                                         |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/urls/routes.py:create_url`                                                                                                                                                                                                                                              |
| **Decorators** | `@utub_membership_required`, `@api_route(request_schema=CreateURLRequest, response_schema=UrlCreatedResponseSchema, tags=["urls"], description="Add a URL to a UTub", status_codes={200: UrlCreatedResponseSchema, 400: ErrorResponse, 404: ErrorResponse, 409: ErrorResponse})` |
| **Service**    | `backend/urls/services/create_url.py:create_url_in_utub`                                                                                                                                                                                                                         |
| **Schema**     | `backend/schemas/requests/urls/create_url.py:CreateURLRequest`, response: `UrlCreatedResponseSchema` embeds `UrlCreatedItemSchema` (subclass of `UtubUrlDeleteSchema` with title override for distinct OpenAPI component naming)                                                 |
| **JS Module**  | `frontend/home/urls/cards/create.ts` — `JSON.stringify`, `application/json`, 35s timeout                                                                                                                                                                                         |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                         |
| **Tests**      | `tests/integration/urls/test_add_url_to_utub_route.py` (marker: `urls`), `tests/functional/urls_ui/test_create_url_ui.py` (marker: `create_urls_ui`)                                                                                                                             |

### GET /utubs/\<utub_id\>/urls/\<utub_url_id\>

| Layer          | Location                                                                                                                                                                                                                        |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/urls/routes.py:get_url`                                                                                                                                                                                                |
| **Decorators** | `@utub_membership_with_valid_url_in_utub_required`, `@api_route(response_schema=UrlReadResponseSchema, tags=["urls"], description="Retrieve a URL from a UTub", status_codes={200: UrlReadResponseSchema, 404: ErrorResponse})` |
| **Service**    | `backend/urls/services/read_urls.py:get_url_in_utub`                                                                                                                                                                            |
| **JS Module**  | `frontend/home/urls/cards/get.ts`, also called from `update-string.ts`, `update-title.ts`, `delete.ts`, `frontend/home/urls/tags/create.ts`, `frontend/home/urls/tags/delete.ts`                                                |
| **Tests**      | `tests/integration/utuburls/test_get_url_in_utub_route.py` (marker: `urls`)                                                                                                                                                     |

### PATCH /utubs/\<utub_id\>/urls/\<utub_url_id\>

| Layer          | Location                                                                                                                                                                                                                                                                                                                  |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/urls/routes.py:update_url`                                                                                                                                                                                                                                                                                       |
| **Decorators** | `@url_adder_or_creator_required`, `@api_route(request_schema=UpdateURLStringRequest, response_schema=UrlUpdatedResponseSchema, tags=["urls"], description="Update a URL string in a UTub", status_codes={200: UrlUpdatedResponseSchema, 400: ErrorResponse, 403: ErrorResponse, 404: ErrorResponse, 409: ErrorResponse})` |
| **Service**    | `backend/urls/services/update_url.py:update_url_in_utub`                                                                                                                                                                                                                                                                  |
| **Schema**     | `backend/schemas/requests/urls/update_url.py:UpdateURLStringRequest`                                                                                                                                                                                                                                                      |
| **JS Module**  | `frontend/home/urls/cards/update-string.ts` — `JSON.stringify`, `application/json`, 35s timeout                                                                                                                                                                                                                           |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                                                                  |
| **Tests**      | `tests/integration/urls/test_update_url_route.py` (marker: `urls`), `tests/functional/urls_ui/test_update_url_ui.py` (marker: `update_urls_ui`)                                                                                                                                                                           |

### PATCH /utubs/\<utub_id\>/urls/\<utub_url_id\>/title

| Layer          | Location                                                                                                                                                                                                                                                                                                      |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/urls/routes.py:update_url_title`                                                                                                                                                                                                                                                                     |
| **Decorators** | `@url_adder_or_creator_required`, `@api_route(request_schema=UpdateURLTitleRequest, response_schema=UrlTitleUpdatedResponseSchema, tags=["urls"], description="Update a URL title in a UTub", status_codes={200: UrlTitleUpdatedResponseSchema, 400: ErrorResponse, 403: ErrorResponse, 404: ErrorResponse})` |
| **Service**    | `backend/urls/services/update_url_title.py:update_url_title_if_new`                                                                                                                                                                                                                                           |
| **Schema**     | `backend/schemas/requests/urls/update_url.py:UpdateURLTitleRequest`                                                                                                                                                                                                                                           |
| **JS Module**  | `frontend/home/urls/cards/update-title.ts` — `JSON.stringify`, `application/json`                                                                                                                                                                                                                             |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                                                      |
| **Tests**      | `tests/integration/urls/test_update_url_title_route.py` (marker: `urls`), `tests/functional/urls_ui/test_update_url_ui.py` (marker: `update_urls_ui`)                                                                                                                                                         |

### DELETE /utubs/\<utub_id\>/urls/\<utub_url_id\>

| Layer          | Location                                                                                                                                                                                                                              |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/urls/routes.py:delete_url`                                                                                                                                                                                                   |
| **Decorators** | `@url_adder_or_creator_required`, `@api_route(response_schema=UrlDeletedResponseSchema, tags=["urls"], description="Delete a URL from a UTub", status_codes={200: UrlDeletedResponseSchema, 403: ErrorResponse, 404: ErrorResponse})` |
| **Service**    | `backend/urls/services/delete_url.py:delete_url_in_utub`                                                                                                                                                                              |
| **JS Module**  | `frontend/home/urls/cards/delete.ts`                                                                                                                                                                                                  |
| **CSRF**       | Meta tag                                                                                                                                                                                                                              |
| **Tests**      | `tests/integration/urls/test_remove_url_from_utub_route.py` (marker: `urls`), `tests/functional/urls_ui/test_delete_url_ui.py` (marker: `urls_ui`)                                                                                    |

---

## Members Blueprint

Base path: `/utubs/<utub_id>/members`

### POST /utubs/\<utub_id\>/members

| Layer          | Location                                                                                                                                                                                                                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/members/routes.py:create_member`                                                                                                                                                                                                                                                   |
| **Decorators** | `@utub_creator_required`, `@api_route(request_schema=AddMemberRequest, response_schema=MemberModifiedResponseSchema, tags=["members"], description="Add a member to a UTub", status_codes={200: MemberModifiedResponseSchema, 400: ErrorResponse, 403: ErrorResponse, 404: ErrorResponse})` |
| **Service**    | `backend/members/services/create_member.py:create_utub_member`                                                                                                                                                                                                                              |
| **Schema**     | `backend/schemas/requests/members/add_member.py:AddMemberRequest`                                                                                                                                                                                                                           |
| **JS Module**  | `frontend/home/members/create.ts` — `JSON.stringify`, `application/json`                                                                                                                                                                                                                    |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                                    |
| **Tests**      | `tests/integration/members/test_add_member_to_utub_route.py` (marker: `members`), `tests/functional/members_ui/test_create_member_ui.py` (marker: `members_ui`)                                                                                                                             |

### DELETE /utubs/\<utub_id\>/members/\<user_id\>

| Layer          | Location                                                                                                                                                                                                                                                           |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Handler**    | `backend/members/routes.py:remove_member`                                                                                                                                                                                                                          |
| **Decorators** | `@utub_membership_required`, `@api_route(response_schema=MemberModifiedResponseSchema, tags=["members"], description="Remove a member from a UTub", status_codes={200: MemberModifiedResponseSchema, 400: ErrorResponse, 403: ErrorResponse, 404: ErrorResponse})` |
| **Service**    | `backend/members/services/remove_member.py:remove_member_or_self_from_utub`                                                                                                                                                                                        |
| **JS Module**  | `frontend/home/members/delete.ts`                                                                                                                                                                                                                                  |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                           |
| **Tests**      | `tests/integration/members/test_remove_member_from_utub_route.py` (marker: `members`), `tests/functional/members_ui/test_delete_member_ui.py` (marker: `members_ui`), `tests/functional/members_ui/test_leave_utub.py` (marker: `members_ui`)                      |

---

## Metrics Blueprint

Base path: `/api/metrics`

### POST /api/metrics

| Layer              | Location                                                                                                                                                                                                                                                                                                                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**        | `backend/metrics/routes.py:ingest`                                                                                                                                                                                                                                                                                                                                                          |
| **Decorators**     | `@csrf.exempt`, `@api_route(request_schema=MetricsIngestRequest, response_schema=MetricsIngestResponseSchema, tags=["metrics"], ajax_required=False, description="Ingest a batch of UI-category metrics events from the browser", status_codes={200: MetricsIngestResponseSchema, 400: ErrorResponse})`, `@limiter.limit("120 per minute, 3000 per hour", methods=["POST"])`                |
| **Service**        | `backend/extensions/metrics/writer.py:record_event` (proxy to `MetricsWriter.record`); `MetricsWriter.reserve_batch` for batch nonce idempotency                                                                                                                                                                                                                                            |
| **Request**        | `backend/schemas/requests/metrics.py:MetricsIngestRequest` (top-level batch + optional `batch_id` and `csrf_token`); per-event shape: `MetricsIngestEvent`                                                                                                                                                                                                                                  |
| **Response**       | `backend/schemas/metrics.py:MetricsIngestResponseSchema`                                                                                                                                                                                                                                                                                                                                    |
| **JS Module**      | `frontend/lib/metrics-client.ts` (forward-link, lands in Phase 4)                                                                                                                                                                                                                                                                                                                           |
| **CSRF**           | Header `X-CSRFToken` (preferred) or JSON body `csrf_token` (sendBeacon fallback); validated manually via `flask_wtf.csrf.validate_csrf`. Missing token → 400; invalid token → 403 (re-raised `CSRFError`).                                                                                                                                                                                  |
| **Tests**          | `tests/integration/system/test_metrics_ingest.py` (marker: `cli`), `tests/integration/system/test_metrics_pipeline_e2e.py` (marker: `cli`), `tests/integration/system/test_metrics_writer.py` (marker: `cli`), `tests/unit/test_metrics_ingest_schema.py` (marker: `unit`), `tests/unit/test_dimension_models.py` (marker: `unit`), `tests/unit/test_parse_counter_key.py` (marker: `unit`) |

#### Forward references (future phases)

- **Phase 4 — `frontend/lib/metrics-client.ts`**: thin browser-side client that batches UI events, attaches the CSRF token (header preferred, body fallback for `navigator.sendBeacon`), and POSTs to `/api/metrics`. Consumes the generated `MetricsIngestRequest` / `MetricsIngestEvent` types from `frontend/types/api.d.ts`. Not yet present in the codebase — file will be added in Phase 4.
- **Phase 6 — `/api/metrics/query/*` (read endpoints)**: future read-side blueprint surfaces (e.g., `GET /api/metrics/query/events`, `GET /api/metrics/query/summary`) for the internal admin dashboard. Will live alongside the ingest route under the same `metrics` blueprint. Not yet present in the codebase — routes/schemas/handlers will be added in Phase 6.

---

## Tags Blueprint — UTub Tags

Base path: `/utubs/<utub_id>/tags`

### POST /utubs/\<utub_id\>/tags

| Layer          | Location                                                                                                                                                                                                                                                                  |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/tags/utub_tag_routes.py:create_utub_tag`                                                                                                                                                                                                                         |
| **Decorators** | `@utub_membership_required`, `@api_route(request_schema=AddTagRequest, response_schema=UtubTagAddedToUtubResponseSchema, tags=["tags"], description="Add a tag to a UTub", status_codes={200: UtubTagAddedToUtubResponseSchema, 400: ErrorResponse, 404: ErrorResponse})` |
| **Service**    | `backend/tags/services/create_utub_tag.py:create_tag_in_utub`                                                                                                                                                                                                             |
| **Schema**     | `backend/schemas/requests/tags/add_tag.py:AddTagRequest`                                                                                                                                                                                                                  |
| **JS Module**  | `frontend/home/tags/create.ts` — `JSON.stringify`, `application/json`                                                                                                                                                                                                     |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                  |
| **Tests**      | `tests/integration/tags/test_add_tags_to_utub_route.py` (marker: `tags`), `tests/functional/tags_ui/test_create_utub_tag_ui.py` (marker: `tags_ui`)                                                                                                                       |

### DELETE /utubs/\<utub_id\>/tags/\<utub_tag_id\>

| Layer          | Location                                                                                                                                                                                                                                        |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/tags/utub_tag_routes.py:delete_utub_tag`                                                                                                                                                                                               |
| **Decorators** | `@utub_membership_with_valid_utub_tag`, `@api_route(response_schema=UtubTagDeletedFromUtubResponseSchema, tags=["tags"], description="Delete a tag from a UTub", status_codes={200: UtubTagDeletedFromUtubResponseSchema, 404: ErrorResponse})` |
| **Service**    | `backend/tags/services/delete_utub_tag.py:delete_utub_tag_from_utub_and_utub_urls`                                                                                                                                                              |
| **JS Module**  | `frontend/home/tags/delete.ts`                                                                                                                                                                                                                  |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                        |
| **Tests**      | `tests/integration/tags/test_delete_tag_from_utub_route.py` (marker: `tags`), `tests/functional/tags_ui/test_delete_utub_tag_ui.py` (marker: `tags_ui`)                                                                                         |

---

## Tags Blueprint — URL Tags

Base path: `/utubs/<utub_id>/urls/<utub_url_id>/tags`

### POST /utubs/\<utub_id\>/urls/\<utub_url_id\>/tags

| Layer          | Location                                                                                                                                                                                                                                                                                          |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/tags/url_tag_routes.py:create_utub_url_tag`                                                                                                                                                                                                                                              |
| **Decorators** | `@utub_membership_with_valid_url_in_utub_required`, `@api_route(request_schema=AddTagRequest, response_schema=UrlTagModifiedResponseSchema, tags=["tags"], description="Add a tag to a URL in a UTub", status_codes={200: UrlTagModifiedResponseSchema, 400: ErrorResponse, 404: ErrorResponse})` |
| **Service**    | `backend/tags/services/create_url_tag.py:add_tag_to_url_if_valid`                                                                                                                                                                                                                                 |
| **Schema**     | `backend/schemas/requests/tags/add_tag.py:AddTagRequest`                                                                                                                                                                                                                                          |
| **JS Module**  | `frontend/home/urls/tags/create.ts` — `JSON.stringify`, `application/json`                                                                                                                                                                                                                        |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                                                                          |
| **Tests**      | `tests/integration/tags/test_add_tag_to_url_route.py` (marker: `tags`), `tests/functional/tags_ui/test_create_tag_ui.py` (marker: `tags_ui`)                                                                                                                                                      |

### DELETE /utubs/\<utub_id\>/urls/\<utub_url_id\>/tags/\<utub_tag_id\>

| Layer          | Location                                                                                                                                                                                                                                |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/tags/url_tag_routes.py:delete_utub_url_tag`                                                                                                                                                                                    |
| **Decorators** | `@utub_membership_with_valid_url_tag`, `@api_route(response_schema=UrlTagModifiedResponseSchema, tags=["tags"], description="Remove a tag from a URL in a UTub", status_codes={200: UrlTagModifiedResponseSchema, 404: ErrorResponse})` |
| **Service**    | `backend/tags/services/delete_url_tag.py:delete_url_tag`                                                                                                                                                                                |
| **JS Module**  | `frontend/home/urls/tags/delete.ts`                                                                                                                                                                                                     |
| **CSRF**       | Meta tag                                                                                                                                                                                                                                |
| **Tests**      | `tests/integration/tags/test_delete_tag_from_url_route.py` (marker: `tags`), `tests/functional/tags_ui/test_delete_tag_ui.py` (marker: `tags_ui`)                                                                                       |

---

## Users Blueprint

### GET /logout

| Layer          | Location                                                                         |
| -------------- | -------------------------------------------------------------------------------- |
| **Handler**    | `backend/users/routes.py:logout`                                                 |
| **Decorators** | None                                                                             |
| **Service**    | `logout_user()`                                                                  |
| **Template**   | Redirect to splash                                                               |
| **JS Module**  | `frontend/splash/email-validation-form.ts`, `frontend/splash/init.ts`            |
| **Tests**      | `tests/integration/splash/test_login_register_home_screen.py` (marker: `splash`) |

### GET /privacy-policy

| Layer          | Location                                                       |
| -------------- | -------------------------------------------------------------- |
| **Handler**    | `backend/users/routes.py:privacy_policy`                       |
| **Decorators** | None                                                           |
| **Service**    | `render_template()` direct                                     |
| **Template**   | `pages/privacy_policy.html` (vars: `is_privacy_or_terms=True`) |
| **Tests**      | None identified                                                |

### GET /terms

| Layer          | Location                                                             |
| -------------- | -------------------------------------------------------------------- |
| **Handler**    | `backend/users/routes.py:terms_and_conditions`                       |
| **Decorators** | None                                                                 |
| **Service**    | `render_template()` direct                                           |
| **Template**   | `pages/terms_and_conditions.html` (vars: `is_privacy_or_terms=True`) |
| **Tests**      | None identified                                                      |

---

## Contact Blueprint

### GET /contact

| Layer        | Location                                                                                   |
| ------------ | ------------------------------------------------------------------------------------------ |
| **Handler**  | `backend/contact/routes.py:contact_us`                                                     |
| **Service**  | `backend/contact/contact_us.py:load_contact_us_page`                                       |
| **Template** | `pages/contact_us.html` (vars: `is_contact_form`)                                          |
| **CSRF**     | Meta tag (`<meta name="csrf-token">`)                                                      |
| **Tests**    | `tests/integration/account_and_support/test_contact_us.py` (marker: `account_and_support`) |

### POST /contact

| Layer          | Location                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Handler**    | `backend/contact/routes.py:submit_contact_us`                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **Decorators** | `@api_route(request_schema=ContactRequest, error_message="Unable to submit contact form.", error_code=ContactErrorCodes.INVALID_FORM_INPUT, response_schema=ContactResponseSchema, ajax_required=False, tags=["contact"], description="Submit a contact form", status_codes={200: ContactResponseSchema, 400: ErrorResponse})`, `@limiter.limit(f"{CONTACT_FORM_CONSTANTS.RATE_LIMIT_PER_HOUR} per hour, {CONTACT_FORM_CONSTANTS.RATE_LIMIT_PER_DAY} per day", methods=["POST"])` |
| **Schema**     | `backend/schemas/requests/contact.py:ContactRequest`                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **Request**    | JSON `{"subject": "...", "content": "..."}`                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| **Response**   | Success: JSON `{"status": "Success", "message": "..."}`, Failure: JSON `{"status": "Failure", "errors": {...}}`                                                                                                                                                                                                                                                                                                                                                                   |
| **Service**    | `backend/contact/contact_us.py:validate_and_contact`                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **Tests**      | `tests/integration/account_and_support/test_contact_us.py` (marker: `account_and_support`)                                                                                                                                                                                                                                                                                                                                                                                        |

---

## System Blueprint

### GET /health

| Layer          | Location                                                                                                                                                                                   |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Handler**    | `backend/system/routes.py:health`                                                                                                                                                          |
| **Decorators** | `@limiter.exempt`, `@api_route(response_schema=HealthResponseSchema, ajax_required=False, tags=["system"], description="Health check endpoint", status_codes={200: HealthResponseSchema})` |
| **Service**    | `APIResponse()` direct                                                                                                                                                                     |
| **Tests**      | None identified                                                                                                                                                                            |

---

## Debug Blueprint (dev only)

### POST /debug

| Layer          | Location                                          |
| -------------- | ------------------------------------------------- |
| **Handler**    | `backend/debug/routes.py:debug_endpoint`          |
| **Decorators** | None                                              |
| **Service**    | `print()` debug                                   |
| **JS Module**  | `frontend/lib/ajax.js:debugCall`                  |
| **Notes**      | Only registered when NOT in testing or production |

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
3. Request parsing & response declaration: `@api_route(request_schema=..., response_schema=..., tags=..., description=..., status_codes=...)`
4. AJAX enforcement: built into `@api_route` (`ajax_required=True` by default; opt out with `ajax_required=False`)
5. OpenAPI metadata: all 24 API routes declare `tags`, `description`, and `status_codes` in their `@api_route` decorators

### Test Markers
| Marker                                                   | Integration tests | UI tests |
| -------------------------------------------------------- | ----------------- | -------- |
| `splash` / `splash_ui`                                   | 7 files           | 7 files  |
| `utubs` / `utubs_ui`                                     | 7 files           | 6 files  |
| `urls` / `create_urls_ui` / `update_urls_ui` / `urls_ui` | 6 files           | 6 files  |
| `members` / `members_ui`                                 | 2 files           | 3 files  |
| `tags` / `tags_ui`                                       | 4 files           | 7 files  |
| `account_and_support`                                    | 1 file            | —        |
| `home_ui`                                                | —                 | 4 files  |
| `mobile_ui`                                              | —                 | 4+ files |
| `unit`                                                   | 18 files          | —        |
| `cli`                                                    | 4 files           | —        |
