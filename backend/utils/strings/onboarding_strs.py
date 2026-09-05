# Strings for the first-time onboarding nudge system. These are read by
# production TypeScript via APP_CONFIG.strings.* (the 5-file APP_CONFIG bridge:
# this module -> constants.py STRINGS -> generate_strings_js() ->
# frontend/test-setup.ts mock -> APP_CONFIG.strings.KEY_NAME), never hardcoded in
# TS. All nudge copy lives here in one domain file, mirroring url_strs.py.
ONBOARDING_CREATE_UTUB_TIP_TITLE = "Start here"
ONBOARDING_CREATE_UTUB_TIP_BODY = "Create your first UTub to begin collecting URLs."
ONBOARDING_ADD_URL_TIP_TITLE = "Add a URL"
ONBOARDING_ADD_URL_TIP_BODY = "Tap here to save your first link to this UTub."
