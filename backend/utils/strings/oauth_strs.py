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
