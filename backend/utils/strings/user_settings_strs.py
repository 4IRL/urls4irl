class USER_SETTINGS_STRINGS:
    PAGE_TITLE = "Settings"
    TABLIST_ARIA_LABEL = "Settings sections"
    TAB_ACCOUNT = "Account"
    TAB_STATS = "Stats"
    TAB_PRIVACY_DATA = "Privacy & Data"
    TAB_UI_SETTINGS = "Display"
    PLACEHOLDER = "Coming soon"

    # Connected Accounts section (Account tab). Jinja-rendered only; UI tests
    # assert via ui_testing_strs re-exports — no JS string bridge (the inline
    # password-confirm row is server-rendered hidden and only toggled by TS).
    CONNECTED_ACCOUNTS_TITLE = "Connected accounts"
    CONNECTED_ACCOUNTS_HINT = (
        "Sign-in methods connected to your account. You can sign in with any "
        "of them."
    )
    CONNECTED_STATUS_CONNECTED = "Connected as {email}"
    CONNECTED_STATUS_NOT_CONNECTED = "Not connected"
    CONNECTED_STATUS_NOT_CONNECTED_PROOF = (
        "Not connected — you'll confirm with {provider} first"
    )
    CONNECTED_LAST_METHOD_NOTE = (
        "Your only sign-in method — connect another before disconnecting " "this one."
    )
    CONNECT_BUTTON_TEXT = "Connect"
    DISCONNECT_BUTTON_TEXT = "Disconnect"
    CONNECT_CONTINUE_BUTTON_TEXT = "Continue"
    CONNECT_CANCEL_BUTTON_TEXT = "Cancel"

    # Log out everywhere (Account tab, security area — NON-destructive, so it sits
    # outside the danger zone). Reuses the .SettingsRemovalModal dark-modal chrome
    # for its confirm dialog. Jinja-rendered only; heading/button/modal title are
    # re-exported via ui_testing_strs for Python UI assertions — no JS string
    # bridge (the confirm dialog carries no dynamic copy).
    LOGOUT_EVERYWHERE_TITLE = "Log out everywhere"
    LOGOUT_EVERYWHERE_HINT = (
        "Signs you out on every device. You'll need to log back in."
    )
    LOGOUT_EVERYWHERE_BUTTON = "Log out…"
    LOGOUT_EVERYWHERE_MODAL_TITLE = "Log out on all devices?"
    LOGOUT_EVERYWHERE_MODAL_WARNING_LEAD = "This is reversible."
    LOGOUT_EVERYWHERE_MODAL_WARNING_BODY = (
        "Every signed-in device — including this one — is signed out immediately. "
        "Nothing is deleted; just log back in to return."
    )
    LOGOUT_EVERYWHERE_MODAL_CONFIRM_BUTTON = "Log out everywhere"

    # Privacy & Data tab — Export my data (Phase 5). The section title/hint, the
    # export card title/hint, the button label, and the "Sessions" zone label are
    # Jinja-rendered; the button label + section title/hint are re-exported via
    # ui_testing_strs for Python UI assertions. The status/error copy below
    # (PREPARING/STARTED/ERROR + the two cross-panel guard notices) is written into
    # the DOM by data-export.ts / account-removal.ts, so it goes through the full
    # 5-file JS bridge (STRINGS + generate_strings_js + test-setup.ts mock).
    EXPORT_SECTION_TITLE = "Your data"
    EXPORT_SECTION_HINT = "Download everything URLS4IRL stores about you."
    EXPORT_CARD_TITLE = "Export my data"
    EXPORT_CARD_HINT = (
        "Download a JSON file of your UTubs, URLs, tags, and account details."
    )
    EXPORT_BUTTON = "Export"
    EXPORT_SESSIONS_ZONE_LABEL = "Sessions"
    EXPORT_PREPARING = "Preparing your export…"
    EXPORT_STARTED = "Your download is starting."
    EXPORT_ERROR = "Couldn't export your data. Please try again."
    DELETE_BLOCKED_BY_EXPORT = (
        "Wait for your data export to finish before deleting your account."
    )
    EXPORT_BLOCKED_BY_DELETE = (
        "Finish or cancel the account deletion in progress before exporting."
    )

    # Account information section (Account tab). Read-only card labels for the
    # username / email / member-since / email-verified block. Jinja-rendered
    # only; re-exported via ui_testing_strs for Python UI assertions — no JS
    # string bridge (no TypeScript reads them).
    ACCOUNT_INFO_TITLE = "Account information"
    ACCOUNT_INFO_HINT = "Your account details. Join date can't be changed here."
    ACCOUNT_USERNAME_LABEL = "Username"
    ACCOUNT_EMAIL_LABEL = "Email"
    ACCOUNT_MEMBER_SINCE_LABEL = "Member since"
    ACCOUNT_EMAIL_STATUS_LABEL = "Email status"
    ACCOUNT_EMAIL_VERIFIED = "Verified"
    ACCOUNT_EMAIL_UNVERIFIED = "Not verified"

    # Pending email-change indicator (Account-info email card). Two distinct
    # constants render the IDENTICAL sentence from two different templating
    # layers (DD-18): ACCOUNT_PENDING_EMAIL_INITIAL_NOTE is Jinja-only (rendered
    # server-side at initial page load, re-exported via ui_testing_strs for the
    # Python UI test — no JS bridge), while ACCOUNT_PENDING_EMAIL_NOTE goes
    # through the full 5-file JS bridge (DD-6: production TypeScript reads it via
    # APP_CONFIG.strings after a successful ajax submit to patch the card in
    # place). Kept as two names to avoid a duplicate-attribute collision on the
    # shared STRINGS class. If either wording changes, edit BOTH in the same
    # commit — they must stay verbatim-in-sync.
    ACCOUNT_PENDING_EMAIL_INITIAL_NOTE = (
        "Pending change to {email} — check that inbox for the confirmation link."
    )
    ACCOUNT_PENDING_EMAIL_NOTE = (
        "Pending change to {email} — check that inbox for the confirmation link."
    )

    # Change-username form (Account tab). Static Jinja labels re-exported via
    # ui_testing_strs for Python UI assertions — no JS string bridge (the
    # success/error banner text is server-sourced off the response envelope).
    CHANGE_USERNAME_TITLE = "Change username"
    CHANGE_USERNAME_HINT = "Choose a new username. It must be unique."
    CHANGE_USERNAME_LABEL = "New username"
    CHANGE_USERNAME_BUTTON = "Save username"

    # Change-password form (Account tab). Static Jinja labels re-exported via
    # ui_testing_strs for Python UI assertions — no JS string bridge (the
    # success/error banner text is server-sourced off the response envelope).
    # The section is gated for OAuth-only accounts; the note replaces the form.
    CHANGE_PASSWORD_TITLE = "Change password"
    CHANGE_PASSWORD_HINT = (
        "Choose a new password. This signs you out of all other devices."
    )
    CHANGE_PASSWORD_CURRENT_LABEL = "Current password"
    CHANGE_PASSWORD_NEW_LABEL = "New password"
    CHANGE_PASSWORD_CONFIRM_LABEL = "Confirm new password"
    CHANGE_PASSWORD_BUTTON = "Save password"
    CHANGE_PASSWORD_OAUTH_ONLY_NOTE = (
        "Password change isn't available for accounts that sign in with Google "
        "or GitHub."
    )

    # Change-email form (Account tab). Static Jinja labels re-exported via
    # ui_testing_strs for Python UI assertions — no JS string bridge (the
    # success/error banner text is server-sourced off the response envelope; the
    # separately-bridged ACCOUNT_PENDING_EMAIL_NOTE handles the in-place card
    # patch). The section is gated for OAuth-only accounts; the note replaces the
    # form (DD-7). The in-form pending warning (DD-16) is Jinja-only, gated on
    # the same account_pending_email context key as the account-info indicator.
    CHANGE_EMAIL_TITLE = "Change email"
    CHANGE_EMAIL_HINT = (
        "Enter a new email. We'll send a confirmation link there; your current "
        "email stays active until you confirm."
    )
    CHANGE_EMAIL_NEW_LABEL = "New email"
    CHANGE_EMAIL_CONFIRM_LABEL = "Confirm new email"
    CHANGE_EMAIL_PASSWORD_LABEL = "Current password"
    CHANGE_EMAIL_BUTTON = "Send confirmation"
    CHANGE_EMAIL_OAUTH_ONLY_NOTE = (
        "Set an account password first to change your email — email changes "
        "require confirming your current password."
    )
    CHANGE_EMAIL_PENDING_WARNING = (
        "You already have a pending email change in progress. Submitting a new "
        "address replaces it and invalidates the earlier confirmation link."
    )

    # Stats section (Stats tab). Jinja-rendered only; the six card labels are
    # re-exported via ui_testing_strs for Python UI assertions — no JS string
    # bridge (the panel is fully server-rendered, no TypeScript reads them).
    STATS_SECTION_TITLE = "Your activity"
    STATS_SECTION_HINT = "A snapshot of what you've built on URLS4IRL."
    STATS_UTUBS_CREATED = "UTubs created"
    STATS_MEMBER_OF = "Member of"
    STATS_MEMBER_OF_SUB = "others' UTubs"
    STATS_URLS_ADDED = "URLs added"
    STATS_TAGS_CREATED = "Tags created"
    STATS_TAGS_APPLIED = "Tags applied"
    STATS_TAGS_APPLIED_SUB = "all-time"
    STATS_MEMBER_SINCE = "Member since"
    STATS_JOINED_TODAY = "Joined today"

    # Display tab (Phase 6). The panel intro + every pref-row label/description +
    # the theme radio labels + the select option labels are Jinja-rendered; the
    # section intro + theme labels are re-exported via ui_testing_strs for Python
    # UI assertions. Only PREFERENCES_SAVED (the instant-apply success toast) is
    # written into the DOM by display-preferences.ts, so it alone goes through the
    # full 5-file JS bridge (STRINGS + generate_strings_js + test-setup.ts mock).
    UI_SETTINGS_SECTION_INTRO = (
        "Choose how URLS4IRL looks and how your collections are shown. Changes "
        "save instantly and apply everywhere."
    )
    UI_SETTINGS_THEME_LABEL = "Theme"
    UI_SETTINGS_THEME_DESC = (
        "Light, dark, or match your device. Applied before the page paints — no "
        "flash."
    )
    UI_SETTINGS_THEME_LIGHT = "Light"
    UI_SETTINGS_THEME_DARK = "Dark"
    UI_SETTINGS_THEME_SYSTEM = "System"
    UI_SETTINGS_VIEW_LABEL = "Default UTub view"
    UI_SETTINGS_VIEW_DESC = "How the URL deck lays out when you open a collection."
    UI_SETTINGS_VIEW_OPTION_LIST = "List"
    # "View: Compact" / "Density: Compact" disambiguate the two prefs that both
    # carry the literal value "compact" (DD-25).
    UI_SETTINGS_VIEW_OPTION_COMPACT = "View: Compact"
    UI_SETTINGS_VIEW_OPTION_CARDS = "Cards"
    UI_SETTINGS_SORT_LABEL = "Default sort"
    UI_SETTINGS_SORT_DESC = "Ordering applied to URLs on load."
    UI_SETTINGS_SORT_OPTION_NEWEST = "Date added (newest)"
    UI_SETTINGS_SORT_OPTION_OLDEST = "Date added (oldest)"
    UI_SETTINGS_SORT_OPTION_TITLE_AZ = "Title A–Z"
    UI_SETTINGS_DENSITY_LABEL = "Density"
    UI_SETTINGS_DENSITY_DESC = "Row spacing across decks and lists."
    UI_SETTINGS_DENSITY_OPTION_COMFORTABLE = "Comfortable"
    UI_SETTINGS_DENSITY_OPTION_COMPACT = "Density: Compact"
    UI_SETTINGS_DATE_FORMAT_LABEL = "Date format"
    UI_SETTINGS_DATE_FORMAT_DESC = "How dates on your saved URLs are shown."
    UI_SETTINGS_DATE_FORMAT_OPTION_ISO = "ISO (YYYY-MM-DD)"
    UI_SETTINGS_DATE_FORMAT_OPTION_US = "US (MM/DD/YYYY)"
    UI_SETTINGS_DATE_FORMAT_OPTION_EU = "EU (DD/MM/YYYY)"
    PREFERENCES_SAVED = "Preferences saved"

    # Danger zone + account-removal modals (Account tab, Phase 4). Static Jinja
    # labels re-exported via ui_testing_strs for Python UI assertions — no JS
    # string bridge (the success/error banner text is server-sourced off the
    # response envelope; the typed-username gate reads the username from the DOM,
    # not APP_CONFIG). Copy grounded in the danger-zone mockups.
    DANGER_ZONE_TITLE = "Danger zone"
    DANGER_ZONE_HINT = (
        "This action affects your whole account. Deleting is permanent and "
        "cannot be undone."
    )
    DANGER_ZONE_DELETE_CARD_TITLE = "Delete account"
    DANGER_ZONE_DELETE_CARD_BODY = (
        "Permanently erase your account and personal data. This cannot be undone."
    )
    DANGER_ZONE_DELETE_CARD_BUTTON = "Delete…"

    # Shared modal chrome
    MODAL_CANCEL_BUTTON = "Cancel"
    MODAL_CLOSE_ARIA_LABEL = "Close"
    REMOVAL_REAUTH_SECTION_LABEL = "Re-authenticate to confirm it's you"
    REMOVAL_REAUTH_PROVIDER_BUTTON = "Re-authenticate with {provider}"
    REMOVAL_REAUTH_REDIRECT_HINT = "You'll return here to finish after signing in."
    REMOVAL_PASSWORD_PLACEHOLDER = "Current password"

    # Delete modal
    DELETE_MODAL_TITLE = "Delete your account permanently?"
    DELETE_MODAL_WARNING_LEAD = "This can't be undone."
    DELETE_MODAL_WARNING_BODY = (
        "Your account and personal data are erased from URLS4IRL."
    )
    DELETE_MODAL_NOTICE_TRANSFER = (
        "{count} UTub(s) you co-own will transfer to another member."
    )
    DELETE_MODAL_NOTICE_SOLO = (
        "{count} solo UTub(s) (only you) will be permanently deleted."
    )
    DELETE_MODAL_NOTICE_ATTRIBUTION = (
        "URLs and tags you added stay in shared UTubs, attributed to a "
        "“deleted user”."
    )
    DELETE_MODAL_NOTICE_RETENTION = (
        "Backups and audit logs retain some data for up to ~90 days, then "
        "auto-purge."
    )
    DELETE_MODAL_CONFIRM_USERNAME_PREFIX = "Type your username"
    DELETE_MODAL_CONFIRM_USERNAME_SUFFIX = "to confirm"
    DELETE_MODAL_CONFIRM_USERNAME_PLACEHOLDER = "Your username"
    DELETE_MODAL_PASSWORD_LABEL = "Confirm your password"
    DELETE_MODAL_CONFIRM_BUTTON = "Delete my account"
