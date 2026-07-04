# Google OAuth reject-message copy. Rendered server-side via
# `backend/templates/components/splash/oauth_reject.html` (which reads
# `oauth_reject_message`) and asserted against by
# `tests/integration/splash/test_oauth_google.py` and
# `tests/functional/splash_ui/test_oauth_google_ui.py` — no TypeScript
# consumer exists for these strings, so they are not part of the
# generate_strings_js()/APP_CONFIG.strings bridge.
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
