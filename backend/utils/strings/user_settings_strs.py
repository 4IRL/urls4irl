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

    # Account information section (Account tab). Read-only card labels for the
    # username / email / member-since / email-verified block. Jinja-rendered
    # only; re-exported via ui_testing_strs for Python UI assertions — no JS
    # string bridge (no TypeScript reads them).
    ACCOUNT_INFO_TITLE = "Account information"
    ACCOUNT_INFO_HINT = (
        "Your account details. Email and join date can't be changed here."
    )
    ACCOUNT_USERNAME_LABEL = "Username"
    ACCOUNT_EMAIL_LABEL = "Email"
    ACCOUNT_MEMBER_SINCE_LABEL = "Member since"
    ACCOUNT_EMAIL_STATUS_LABEL = "Email status"
    ACCOUNT_EMAIL_VERIFIED = "Verified"
    ACCOUNT_EMAIL_UNVERIFIED = "Not verified"

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
