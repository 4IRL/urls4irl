# OAuth reject-message copy. Rendered server-side via
# `backend/templates/components/splash/oauth_reject.html` (which reads
# `oauth_reject_message`) and asserted against by
# `tests/integration/splash/test_oauth_google.py` /
# `test_oauth_github.py` and their `tests/functional/splash_ui/` UI twins —
# no TypeScript consumer exists for these strings, so they are not part of
# the generate_strings_js()/APP_CONFIG.strings bridge.
#
# GENERIC_FAILURE / EMAIL_COLLISION / CONSENT_DECLINED are provider-neutral
# and shared by every provider's callback; the unverified-email and
# invalid-callback messages name the provider, so each provider carries its
# own wording.
GENERIC_FAILURE_MESSAGE = "Sign-in failed, please try again."
UNVERIFIED_EMAIL_MESSAGE = (
    "Google has not verified this email address — please verify it with "
    "Google and try again."
)
EMAIL_COLLISION_MESSAGE = (
    "Email already registered — log in with your password instead."
)
CONSENT_DECLINED_MESSAGE = "Sign-in was cancelled."
INVALID_CALLBACK_QUERY_MESSAGE = "Invalid Google OAuth callback request."

GITHUB_UNVERIFIED_EMAIL_MESSAGE = (
    "Your GitHub account has no verified primary email address — please "
    "verify your email with GitHub and try again."
)
GITHUB_INVALID_CALLBACK_QUERY_MESSAGE = "Invalid GitHub OAuth callback request."

# Account-linking copy (settings link/unlink endpoints + the collision
# confirm-link page). Same bridge posture as above: rendered server-side or
# returned in JSON message fields, asserted by Python integration/UI tests,
# no TypeScript consumer — so backend constants only. `{provider}` slots take
# `provider_display_name(...)` values ("Google"/"GitHub").
LINK_SUCCESS_MESSAGE = "{provider} connected to your account."
LINK_ALREADY_LINKED_MESSAGE = "{provider} is already connected to your account."
LINK_SUBJECT_OWNED_BY_OTHER_ACCOUNT_MESSAGE = (
    "That {provider} account is already connected to a different account."
)
LINK_FORBIDDEN_MESSAGE = "You can only manage sign-in methods for your own account."
LINK_PASSWORD_REQUIRED_MESSAGE = "Enter your password to connect a new sign-in method."
LINK_INVALID_PASSWORD_MESSAGE = "Incorrect password."
LINK_PROVIDER_NOT_CONFIGURED_MESSAGE = "That sign-in provider is not available."
LINK_INTENT_INVALID_MESSAGE = (
    "This link request has expired or is invalid — start again from Settings."
)
LINK_PROOF_MISMATCH_MESSAGE = (
    "Identity check failed — sign-in did not match a provider already "
    "connected to your account."
)
UNLINK_SUCCESS_MESSAGE = "{provider} disconnected from your account."
UNLINK_NOT_LINKED_MESSAGE = "{provider} is not connected to your account."
UNLINK_LAST_METHOD_MESSAGE = (
    "You can't remove your only sign-in method. Connect another provider " "first."
)

# Collision confirm-link page copy (Jinja-rendered; UI tests assert these via
# ui_testing_strs re-exports).
CONFIRM_LINK_TITLE = "Link to your existing account?"
CONFIRM_LINK_PASSWORD_PROMPT = (
    "An account already exists for {email}. Enter its password to connect "
    "your {provider} sign-in to it."
)
CONFIRM_LINK_OAUTH_ONLY_PROMPT = (
    "An account already exists for {email}. To connect your {provider} "
    "sign-in to it, first sign in with a provider already on that account."
)
CONFIRM_LINK_SUBMIT_TEXT = "Link accounts"
CONFIRM_LINK_CONTINUE_WITH_TEXT = "Continue with {provider}"
CONFIRM_LINK_EXPIRED_MESSAGE = "This link request has expired — sign in again to retry."
CONFIRM_LINK_INVALID_MESSAGE = "Unable to link accounts, please try again."
