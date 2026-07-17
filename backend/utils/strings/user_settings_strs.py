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
