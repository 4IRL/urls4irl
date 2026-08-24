class GenericPageLocator:
    ERROR_PAGE_HANDLER = "#ErrorPageHandler"
    ERROR_PAGE_REFRESH_BTN = f"{ERROR_PAGE_HANDLER} .refresh-button"
    NAVBAR_TOGGLER = ".navbar-toggler"
    NAVBAR_DROPDOWN = "#NavbarNavDropdown"
    U4I_LOGO = ".navbar-brand"
    SUBHEADER_INVALID_FEEDBACK = ".invalid-feedback"

    # Footer
    PRIVACY_BTN = "#PrivacyBtn"
    TERMS_BTN = "#TermsBtn"
    CONTACT_BTN = "#ContactBtn"

    # Privacy Terms Pages
    PRIVACY_HEADER = "#PrivacyTitle"
    TERMS_HEADER = "#TermsTitle"
    BACK_HOME_BTN = "#backHomeBtn"
    BACK_SPLASH_BTN = "#backToSplashBtn"

    # Contact Us Page
    CONTACT_US_HEADER = "#ContactTitle"
    CONTACT_SUBJECT_INPUT = "#subject"
    CONTACT_CONTENT_INPUT = "#content"
    CONTACT_SUBMIT = "#submit"
    CONTACT_BANNER = "#Banner"
    CONTACT_SUBJECT_ERROR = "#subject-error"
    CONTACT_CONTENT_ERROR = "#content-error"

    # Cookie Banner
    COOKIE_BANNER = "#CookieBanner"
    COOKIE_BANNER_BTN = "#CookieBanner #CookieButton"


class HomePageLocators(GenericPageLocator):
    """A collector class for main page locators"""

    INVALID_FIELD_SUFFIX = "-error"
    EDITABLE_CLASS = "editable"
    TOOLTIP_SUFFIX = "-tooltip"

    # Change-email confirm-outcome banner (Phase 3, DD-9/DD-14). Net-new here:
    # HomePageLocators carried no banner locator before. Same CSS id as the
    # SplashPageLocators one, since home.html's banner markup is an identical
    # copy of splash.html's — rendered on /home for an already-logged-in browser
    # when splash_page() forwards the `email_change_status` param.
    EMAIL_CHANGE_STATUS_BANNER = "#EmailChangeStatusBanner"

    # Navbar
    BUTTON_LOGOUT = "#logout > .nav-bar-inner-item"
    LOGGED_IN_USERNAME_READ = "#userLoggedIn"
    LOGGED_IN_USERNAME_DESKTOP = "#userLoggedInDesktop"
    NAVBAR_ADMIN_METRICS = "#NavbarDropdownsHome #adminMetrics"
    NAVBAR_ADMIN_METRICS_LINK = "#adminMetricsLink"
    NAVBAR_ADMIN_PORTAL = "#NavbarDropdownsHome #adminPortal"
    NAVBAR_ADMIN_PORTAL_LINK = "#adminPortalLink"
    NAVBAR_USER_SETTINGS = "#NavbarDropdownsHome #userSettings"
    NAVBAR_UTUB_DECK = "#NavbarDropdownsHome #toUTubs"
    NAVBAR_URLS_DECK = "#NavbarDropdownsHome #toURLs"
    NAVBAR_MEMBER_DECK = "#NavbarDropdownsHome #toMembers"
    NAVBAR_TAGS_DECK = "#NavbarDropdownsHome #toTags"
    NAVBAR_LOGOUT = "#NavbarDropdownsHome #logout"
    MOBILE_NAVBAR_OPTIONS = (
        LOGGED_IN_USERNAME_READ,
        NAVBAR_UTUB_DECK,
        NAVBAR_URLS_DECK,
        NAVBAR_MEMBER_DECK,
        NAVBAR_TAGS_DECK,
        NAVBAR_LOGOUT,
    )

    # UTub Deck
    HEADER_UTUB_DECK = "#UTubDeckHeader"
    SUBHEADER_UTUB_DECK = "#UTubDeckSubheader"
    LIST_UTUB = "#listUTubs"
    SELECTORS_UTUB = ".UTubSelector"
    SELECTORS_UTUB_NAME = ".UTubName"
    SELECTOR_SELECTED_UTUB = ".UTubSelector.active"

    BUTTON_UTUB_CREATE = "#utubBtnCreate"
    BUTTON_UTUB_DELETE = "#utubBtnDelete"
    INPUT_UTUB_NAME_CREATE = "#utubNameCreate"
    INPUT_UTUB_DESCRIPTION_CREATE = "#utubDescriptionCreate"
    BUTTON_UTUB_SUBMIT_CREATE = "#utubSubmitBtnCreate"
    BUTTON_UTUB_CANCEL_CREATE = "#utubCancelBtnCreate"

    MEMBER_ICON = ".bi-people-fill"
    CO_CREATOR_ICON = ".bi-diamond-half"
    CREATOR_ICON = ".bi-diamond-fill"
    # Padlock shown in a UTub deck selector in place of the member-role icon
    # when the UTub is locked (server-rendered via UTubCard.html, client-rendered
    # via createUTubSelector).
    UTUB_LOCKED_ICON = "svg.utubLockedIcon"

    UTUB_SEARCH_INPUT = "#UTubNameSearch"
    UTUB_SEARCH_WRAP = "#SearchUTubWrap"
    UTUB_SEARCH_NO_RESULTS = "#UTubSearchNoResults"
    # Desktop-only funnel toggle that reveals/hides the UTub name search input.
    BUTTON_UTUB_NAME_FILTER = "#utubNameFilterBtn"
    BUTTON_UTUB_NAME_FILTER_CLOSE = "#utubNameFilterBtnClose"

    URL_OPEN_SEARCH_ICON = "#URLSearchFilterIcon"
    URL_CLOSE_SEARCH_ICON = "#URLSearchFilterIconClose"
    URL_SEARCH_INPUT = "#URLContentSearch"
    URL_SEARCH_WRAP = "#SearchURLWrap"
    URL_SEARCH_NO_RESULTS = "#URLSearchNoResults"
    TAG_FILTER_NO_RESULTS = "#URLTagFilterNoResults"
    TAG_FILTER_ANNOUNCEMENT = "#URLTagFilterAnnouncement"

    # Cross-UTub search mode
    CROSS_SEARCH_TRIGGER = "#toCrossUtubSearch"
    CROSS_SEARCH_MODE = "#crossUtubSearchMode"
    CROSS_SEARCH_INPUT = "#crossUtubSearchInput"
    CROSS_SEARCH_CLEAR_INPUT = "#crossUtubSearchClear"
    CROSS_SEARCH_SUBMIT = "#crossUtubSearchSubmit"
    CROSS_SEARCH_SUBMIT_ICON = "#crossUtubSearchSubmit .crossSearchSubmitIcon"
    CROSS_SEARCH_REFRESH_ICON = "#crossUtubSearchSubmit .crossSearchRefreshIcon"
    CROSS_SEARCH_TRIGGER_OPEN_ICON = "#crossSearchTriggerOpenIcon"
    CROSS_SEARCH_TRIGGER_CLOSE_ICON = "#crossSearchTriggerCloseIcon"
    NAV_RETURN_HOME = "#navReturnHome"
    CROSS_SEARCH_RESULTS = "#crossUtubSearchResults"
    CROSS_SEARCH_GROUP = ".crossSearchGroup"
    CROSS_SEARCH_HIT_CARD = ".crossSearchHitCard"
    CROSS_SEARCH_NO_RESULTS = "#crossUtubSearchNoResults"
    CROSS_SEARCH_FIELD_CONTROLS = "#crossUtubSearchFieldControls"
    CROSS_SEARCH_SETTINGS_BTN = "#crossUtubSearchSettingsBtn"
    CROSS_SEARCH_SETTINGS_MODAL = "#crossUtubSearchSettingsModal"
    CROSS_SEARCH_HISTORY_LIST = "#crossUtubSearchHistoryList"
    CROSS_SEARCH_HISTORY_ROW = ".crossSearchHistoryRow"
    CROSS_SEARCH_HISTORY_DELETE = ".crossSearchHistoryDelete"
    CROSS_SEARCH_HISTORY_CLEAR = "#crossUtubSearchHistoryClear"

    # Tag Deck
    HEADER_TAG_DECK = "#TagDeckHeader"
    HEADER_AND_CARET_TAG_DECK = "#TagDeckHeaderAndCaret"
    TAG_DECK_COUNT = "#TagDeckCount"
    LIST_TAGS = "#listTags"
    TAG_FILTERS = ".tagFilter"
    # Togglable funnel filter on the Tag Deck (mirrors the UTub name filter).
    TAG_SEARCH_INPUT = "#TagNameSearch"
    TAG_SEARCH_WRAP = "#SearchTagWrap"
    # Tag-deck filter "No tags found" message. NOT the URL-deck TAG_FILTER_NO_RESULTS
    # ("#URLTagFilterNoResults") message above, which is the "no URLs match" message.
    TAG_SEARCH_NO_RESULTS = "#TagSearchNoResults"
    BUTTON_TAG_NAME_FILTER = "#tagNameFilterBtn"
    BUTTON_TAG_NAME_FILTER_CLOSE = "#tagNameFilterBtnClose"
    # Zero-tags empty state shown when a selected UTub has no tags.
    TAG_DECK_EMPTY_STATE = "#noTagsEmptyState"
    TAG_COUNT = ".tagAppliedToUrlsCount"
    BUTTON_UNSELECT_ALL = "#unselectAllTagFilters"
    BUTTON_UTUB_TAG_CREATE = "#utubTagBtnCreate"
    INPUT_UTUB_TAG_CREATE = "#utubTagCreate"
    BUTTON_UTUB_TAG_SUBMIT_CREATE = "#utubTagSubmitBtnCreate"
    BUTTON_UTUB_TAG_CANCEL_CREATE = "#utubTagCancelBtnCreate"
    BUTTON_UTUB_TAG_DELETE = ".utubTagBtnDelete"
    UNSELECTED = ".unselected"
    SELECTED = ".selected"
    BUTTON_UPDATE_TAG_BTN_ALL_OPEN = "#utubTagBtnUpdateAllOpen"
    BUTTON_UPDATE_TAG_BTN_ALL_CLOSE = "#utubTagBtnUpdateAllClose"
    WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE = "#utubTagCloseUpdateTagBtnContainer"
    WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS = "#utubTagStandardBtns"
    UTUB_TAG_MENU_WRAP = ".tagMenuWrap"
    UTUB_TAG_COUNT_WRAP = ".tagCountWrap"
    BUTTON_UTUB_TAG_DELETE = ".utubTagBtnDelete"

    # Mobile Tag filter bottom sheet. The handle is the sheet's header/peek lip
    # (first child of #tagDeckSheet) and the single drag target for open + close.
    TAG_SHEET = "#tagDeckSheet"
    TAG_SHEET_HANDLE = "#tagSheetHandle"
    TAG_SHEET_BACKDROP = "#tagSheetBackdrop"
    TAG_SHEET_HANDLE_COUNT = "#tagSheetHandleCount"
    TAG_SHEET_EMPTY = "#tagSheetEmpty"
    TAG_SHEET_OPEN_CLASS = "tag-sheet-open"

    # URL Deck
    WRAP_UTUB_NAME_UPDATE = "#UTubNameUpdateWrap"
    HEADER_URL_DECK = "#URLDeckHeader"
    # Padlock beside the UTub title in the URL deck header; the `hidden` class is
    # removed when a locked UTub is selected. `body.utub-locked` drives the CSS
    # that disables every mutation control while a locked UTub is selected.
    URL_DECK_LOCK_ICON = "#URLDeckLockIcon"
    BODY_LOCKED_CLASS = "utub-locked"
    INPUT_UTUB_NAME_UPDATE = "#utubNameUpdate"
    BUTTON_UTUB_NAME_SUBMIT_UPDATE = "#utubNameSubmitBtnUpdate"
    WRAP_URL_CREATE = "#createURLWrap"
    BUTTON_UTUB_NAME_CANCEL_UPDATE = "#utubNameCancelBtnUpdate"
    BUTTON_ADD_UTUB_DESC_ON_EMPTY = "#URLDeckSubheaderCreateDescription"
    LABEL_NO_DESCRIPTION = "#URLDeckNoDescription"

    PENCIL_ICON_NAME = "#UTubNameUpdateWrap .edit-pencil-icon"
    PENCIL_ICON_DESCRIPTION = "#UTubDescriptionSubheaderWrap .edit-pencil-icon"

    # Consolidated mobile UTub edit-panel controls (coarse-pointer only). One
    # `<button>` in the URL-deck header toolbar opens a panel showing both the
    # UTub name and description forms; the paired close button dismisses it.
    BUTTON_UTUB_EDIT_PANEL_TOGGLE = "#utubEditPanelToggle"
    BUTTON_UTUB_EDIT_PANEL_CLOSE = "#utubEditPanelClose"

    # Transient "Saved ✓" acknowledgment shown next to a kept-open field after a
    # per-field save on the mobile consolidated panel, plus the shared polite
    # aria-live announcer.
    SAVED_TICK_NAME = "#utubNameSavedTick"
    SAVED_TICK_DESCRIPTION = "#utubDescriptionSavedTick"
    FIELD_SAVED_ANNOUNCEMENT = "#fieldSavedAnnouncement"

    WRAP_UTUB_DESCRIPTION_UPDATE = "#UTubDescriptionSubheaderWrap"
    SUBHEADER_URL_DECK = "#URLDeckSubheader"
    SUBHEADER_NO_URLS = "#noURLsSubheader"
    INPUT_UTUB_DESCRIPTION_UPDATE = "#utubDescriptionUpdate"
    BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE = "#utubDescriptionSubmitBtnUpdate"
    BUTTON_UTUB_DESCRIPTION_CANCEL_UPDATE = "#utubDescriptionCancelBtnUpdate"

    LIST_URL = "#listURLs"
    ROWS_URLS = ".urlRow"
    ROW_SELECTED_URL = f"{ROWS_URLS}[urlselected='true']"
    ROW_VISIBLE_URL = f"{ROWS_URLS}[filterable='true']"

    BUTTON_CORNER_URL_CREATE = "#urlBtnCreate"
    BUTTON_DECK_URL_CREATE = "#urlBtnDeckCreate"

    # URL multi-select (bulk-action) mode
    BUTTON_MULTI_SELECT_TOGGLE = "#urlBtnMultiSelect"
    ROW_MULTI_SELECTED = ".urlRow.multiSelected"
    URL_SELECT_CHECKBOX = ".urlSelectCheckbox"
    BULK_ACTION_BAR = "#bulkActionBar"
    # Selection-context region relocated into the URL-deck header (selection-mode
    # IA restructure). The count/hidden-hint/Exit ids are UNCHANGED — only their
    # DOM home moved from the bottom bar into #bulkSelectContext (and the header
    # .button-container for #bulkSelectExit), so bulk-bar.ts's global $(id)
    # lookups keep driving them.
    BULK_SELECT_CONTEXT = "#bulkSelectContext"
    BULK_SELECT_COUNT = "#bulkSelectCount"
    BULK_SELECT_HIDDEN_HINT = "#bulkSelectHiddenHint"
    BULK_SELECT_ALL = "#bulkSelectAll"
    BULK_SELECT_CLEAR = "#bulkSelectClear"
    BULK_SELECT_EXIT = "#bulkSelectExit"
    # Desktop-only selection-context "range strip" (subheader left). Select all /
    # Clear are surfaced here on desktop (the header #bulkSelectAll/#bulkSelectClear
    # are display:none >=992px); Invert is net-new (flips the visible selection).
    # The strip is hidden on mobile — the drawer keeps its own Select All / Clear.
    BULK_SELECT_RANGE_STRIP = "#bulkSelectRangeStrip"
    BULK_RANGE_SELECT_ALL = "#bulkRangeSelectAll"
    BULK_RANGE_INVERT = "#bulkRangeInvert"
    BULK_RANGE_CLEAR = "#bulkRangeClear"
    # Mobile-only on-demand tag-filter glyph (bi-tag) in the header; opens the
    # existing tag-sheet in selection mode. Hidden on desktop (min-width:992px).
    BULK_TAG_FILTER_ICON = "#bulkTagFilterIcon"
    BULK_SELECTION_ANNOUNCEMENT = "#URLBulkSelectionAnnouncement"

    # Bulk multi-URL tag-apply (Phase 2). The "Add tags" action button rendered
    # into #bulkActionButtons by the bulk-action registry, the stable picker mount
    # that hosts the BULK-mode combobox, and the partial-success result banner.
    BUTTON_BULK_ADD_TAGS = '[data-bulk-action-id="bulk-add-tags"]'
    BULK_TAG_PICKER_MOUNT = "#bulkTagPickerMount"
    BULK_TAG_BANNER = "#bulkTagResultBanner"
    # Dedicated Cancel button prepended into the BULK picker's actions row
    # (distinct from the per-URL big-cancel button BUTTON_TAGS_CANCEL_BATCH).
    BUTTON_BULK_TAG_CANCEL = ".urlTagComboboxCancelBtn"

    # Bulk multi-URL copy-to-UTub (Phase 3). The "Copy to UTub" action button
    # rendered into #bulkActionButtons by the bulk-action registry, the stable
    # destination-picker mount (a role="listbox" of role="option" rows), and the
    # result banner. Row selectors resolve by role="option" (not just the
    # .UTubSelector class) so Playwright's ARIA assertions (aria-selected,
    # aria-disabled) read the role directly.
    BUTTON_BULK_COPY_URLS = '[data-bulk-action-id="bulk-copy"]'
    BULK_COPY_PICKER_MOUNT = "#bulkCopyPickerMount"
    # role="listbox" lives on an INNER element (not the mount itself) so the
    # filter input + footer are not invalid listbox children.
    BULK_COPY_PICKER_LISTBOX = "#bulkCopyPickerMount .bulkCopyListbox[role='listbox']"
    # Destination-picker filter box + its no-results message.
    BULK_COPY_FILTER_INPUT = ".bulkCopyFilterInput"
    BULK_COPY_NO_MATCHES = ".bulkCopyNoMatches"
    BULK_COPY_BANNER = "#bulkCopyResultBanner"
    # Shared banner body class (the copy banner reuses .bulkTagBanner markup).
    BULK_COPY_BANNER_BODY = f"{BULK_COPY_BANNER} .bulkTagBannerBody"
    # Destination rows, resolved by role="option" (all rows / enabled-only /
    # enabled-and-visible, the last excluding rows the filter box has hidden).
    BULK_COPY_OPTION = '.UTubSelector[role="option"]'
    BULK_COPY_OPTION_ENABLED = '.UTubSelector[role="option"]:not(.disabled)'
    BULK_COPY_OPTION_VISIBLE = (
        '.UTubSelector[role="option"]:not(.disabled):not(.hidden)'
    )
    # Multi-select: destination rows currently staged (aria-selected="true") —
    # used to count how many destinations are staged (2+ for multi-copy).
    BULK_COPY_OPTION_SELECTED = '.UTubSelector[role="option"][aria-selected="true"]'
    # Per-row trailing affordances (DD-4/DD-12, mutually exclusive): an enabled
    # row shows its role badge; a locked row shows the locked text label instead.
    BULK_COPY_ROLE_BADGE = ".bulkCopyRoleBadge"
    BULK_COPY_LOCKED_LABEL = ".bulkCopyLockedLabel"
    # In-picker footer controls + the all-other-UTubs-locked message.
    BUTTON_BULK_COPY_CANCEL = ".bulkCopyCancelBtn"
    BUTTON_BULK_COPY_CONFIRM = ".bulkCopyConfirmBtn"
    BULK_COPY_PICKER_MSG = ".bulkCopyPickerMsg"
    BULK_COPY_ALL_LOCKED = ".bulkCopyAllLocked"

    # Bulk multi-URL delete-from-UTub (Phase 5). The destructive "Delete" action
    # button rendered into #bulkActionButtons by the bulk-action registry, and the
    # result banner (reusing the shared .bulkTagBanner markup) that survives the
    # action-button rebuild. The confirm reuses the shared #confirmModal
    # (ACTION_CONFIRM_MODAL) rather than an in-deck picker.
    BUTTON_BULK_DELETE_URLS = '[data-bulk-action-id="bulk-delete"]'
    BULK_DELETE_BANNER = "#bulkDeleteResultBanner"
    # Deck-level outcome announcer (subheader live region) used on the
    # deck-empties path, where the bulk-bar banner is torn down by mode exit.
    URL_DECK_OUTCOME_ANNOUNCEMENT = "#URLDeckOutcomeAnnouncement"

    INPUT_URL_TITLE_CREATE = "#urlTitleCreate"
    INPUT_URL_STRING_CREATE = "#urlStringCreate"
    BUTTON_URL_SUBMIT_CREATE = "#urlSubmitBtnCreate"
    BUTTON_URL_CANCEL_CREATE = "#urlCancelBtnCreate"

    # URLs
    URL_TITLE_READ = ".urlTitle"
    URL_STRING_READ = ".urlString"

    URL_TAGS_READ = ".urlTags"
    TAG_BADGES = ".tagBadge"
    TAG_BADGE_NAME_READ = ".tagBadge > span"
    TAG_BADGE_ID_ATTRIB = "data-utub-tag-id"
    URL_BUTTONS_OPTIONS_READ = ".urlOptions"

    BUTTON_URL_TITLE_UPDATE = ".urlTitleBtnUpdate"
    INPUT_URL_TITLE_UPDATE = ".urlTitleUpdate"
    BUTTON_URL_TITLE_SUBMIT_UPDATE = ".urlTitleSubmitBtnUpdate"
    BUTTON_URL_TITLE_CANCEL_UPDATE = ".urlTitleCancelBtnUpdate"

    BUTTON_URL_ACCESS = ".urlBtnAccess"

    BUTTON_TAG_CREATE = ".urlTagBtnCreate"
    BUTTON_BIG_TAG_CANCEL_CREATE = ".urlTagCancelBigBtnCreate"

    # Per-URL tag combobox (replaces the legacy single free-text input). The
    # combobox always submits via the batch endpoint, so the legacy submit/cancel
    # locators below are repointed to the combobox's own submit/cancel buttons
    # and the legacy "input" locator to the combobox text input — this keeps the
    # sibling tags_ui suites (which only use these as add-a-tag setup) driving the
    # current built UI instead of the removed single input.
    INPUT_TAG_COMBOBOX = ".urlTagComboboxInput"
    TAG_COMBOBOX_OPTION = ".urlTagOption"
    TAG_COMBOBOX_OPTION_LABEL = ".urlTagOptionLabel"
    TAG_COMBOBOX_CREATE_NEW = ".urlTagOptionCreateNew"
    TAG_STAGED_CHIP = ".urlTagStagedChip"
    TAG_STAGED_CHIP_REMOVE = ".urlTagStagedChip button"
    BUTTON_TAGS_SUBMIT_BATCH = ".urlTagComboboxSubmitBtn"
    BUTTON_TAGS_CANCEL_BATCH = BUTTON_BIG_TAG_CANCEL_CREATE
    TAG_COMBOBOX_MSG = ".urlTagComboboxMsg"

    INPUT_TAG_CREATE = INPUT_TAG_COMBOBOX
    BUTTON_TAG_SUBMIT_CREATE = BUTTON_TAGS_SUBMIT_BATCH
    BUTTON_TAG_CANCEL_CREATE = BUTTON_TAGS_CANCEL_BATCH
    ERROR_TAG_CREATE = TAG_COMBOBOX_MSG

    # Create-URL-form tag combobox (staging-only). The combobox mounts inside
    # `#createURLWrap` (not inside a URL card), so its selectors are scoped to
    # the create wrap rather than `ROW_SELECTED_URL`. The create-mode combobox
    # does NOT render the batch submit button.
    CREATE_FORM_TAG_COMBOBOX_INPUT = f"{WRAP_URL_CREATE} {INPUT_TAG_COMBOBOX}"
    CREATE_FORM_TAG_COMBOBOX_OPTION = f"{WRAP_URL_CREATE} {TAG_COMBOBOX_OPTION}"
    CREATE_FORM_TAG_COMBOBOX_CREATE_NEW = f"{WRAP_URL_CREATE} {TAG_COMBOBOX_CREATE_NEW}"
    CREATE_FORM_TAG_STAGED_CHIP = f"{WRAP_URL_CREATE} {TAG_STAGED_CHIP}"
    CREATE_FORM_TAG_COMBOBOX_MSG = f"{WRAP_URL_CREATE} {TAG_COMBOBOX_MSG}"

    BUTTON_TAG_DELETE = ".urlTagBtnDelete"

    UPDATE_URL_STRING_WRAP = ".updateUrlStringWrap"
    UPDATE_URL_TITLE_WRAP = ".updateUrlTitleWrap"
    BUTTON_URL_STRING_UPDATE = ".urlStringBtnUpdate"
    INPUT_URL_STRING_UPDATE = ".urlStringUpdate"
    BUTTON_URL_STRING_SUBMIT_UPDATE = ".urlStringSubmitBtnUpdate"
    BUTTON_URL_STRING_CANCEL_UPDATE = ".urlStringCancelBtnUpdate"
    BUTTON_BIG_URL_STRING_CANCEL_UPDATE = ".urlStringCancelBigBtnUpdate"
    # Mobile form-model "Saved ✓" ticks (card-scoped by wrap since cards repeat)
    SAVED_TICK_URL_TITLE = ".updateUrlTitleWrap .field-saved-tick"
    SAVED_TICK_URL_STRING = ".updateUrlStringWrap .field-saved-tick"

    BUTTON_URL_DELETE = ".urlBtnDelete"

    BUTTON_URL_COPY = ".urlBtnCopy"

    URL_STRING_IN_DATA = "href"
    GO_TO_URL_ICON = ".goToUrlIcon"

    # Members Deck
    HEADER_MEMBER_DECK = "#MemberDeckHeader"
    HEADER_AND_CARET_MEMBER_DECK = "#MemberDeckHeaderAndCaret"
    BUTTON_MEMBER_CREATE = "#memberBtnCreate"
    INPUT_MEMBER_CREATE = "#memberCreate"
    BUTTON_MEMBER_CANCEL_CREATE = "#memberCancelBtnCreate"
    BUTTON_MEMBER_SUBMIT_CREATE = "#memberSubmitBtnCreate"
    BUTTON_UTUB_LEAVE = "#memberSelfBtnDelete"
    BUTTON_MEMBER_DELETE = ".memberOtherBtnDelete"
    INPUT_MEMBER_CREATE_ERROR = INPUT_MEMBER_CREATE + INVALID_FIELD_SUFFIX

    LIST_MEMBERS = "#listMembers"
    BADGES_MEMBERS = ".member"
    BADGE_OWNER = "#UTubOwner > .member"

    DISPLAY_MEMBER_WRAP = "#displayMemberWrap"
    MEMBER_SEARCH_INPUT = "#MemberNameSearch"
    MEMBER_SEARCH_WRAP = "#SearchMemberWrap"
    MEMBER_SEARCH_NO_RESULTS = "#MemberSearchNoResults"
    BUTTON_MEMBER_NAME_FILTER = "#memberNameFilterBtn"
    BUTTON_MEMBER_NAME_FILTER_CLOSE = "#memberNameFilterBtnClose"

    # Modal
    HOME_MODAL = "#confirmModal"
    HEADER_MODAL = "#confirmModalTitle"
    BODY_MODAL = "#confirmModalBody"
    BUTTON_MODAL_DISMISS = "#modalDismiss"
    BUTTON_MODAL_REDIRECT = "#modalRedirect"
    BUTTON_MODAL_SUBMIT = "#modalSubmit"
    BUTTON_X_CLOSE = ".btn-close"
    ACCESS_EXTERNAL_URL_MODAL = "#confirmModal.accessExternalURLModal"
    DELETE_URL_MODAL = ".deleteUrlModal"

    # Decks
    UTUB_DECK = ".deck#UTubDeck"
    MEMBER_DECK = ".deck#MemberDeck"
    TAG_DECK = ".deck#TagDeck"
    URL_DECK = ".deck#URLDeck"

    # Panels
    MAIN_PANEL = "main#mainPanel"
    LEFT_PANEL = ".panel#leftPanel"

    # Toggles
    LHS_TOGGLE_SEAM_BTN = "#lhsToggleSeam"
    LHS_TOGGLE_HEADER_BTN = "#lhsToggleHeader"


class SplashPageLocators(GenericPageLocator):
    """A collector class for splash page locators"""

    # Options
    SPLASH_NAVBAR = "#NavbarDropdownsSplash"
    BUTTON_REGISTER = ".btn.to-register"
    BUTTON_LOGIN = ".btn.to-login"

    # Navbar
    NAVBAR_REGISTER = ".nav-bar-inner-item > .to-register"
    NAVBAR_LOGIN = ".nav-bar-inner-item > .to-login"

    # Per-form modal locators
    LOGIN_MODAL = "#LoginModal"
    REGISTER_MODAL = "#RegisterModal"
    REGISTER_CONFIRMATION_MODAL = "#RegisterConfirmationModal"
    FORGOT_PASSWORD_MODAL = "#ForgotPasswordModal"
    EMAIL_VALIDATION_MODAL = "#EmailValidationModal"

    # Change-email confirm-outcome banner (Phase 3, DD-11). Rendered near the
    # hero on splash.html when the `email_change_status` query param maps to a
    # banner. Mirrors the settings LINK_STATUS_BANNER id-selector pattern; the
    # identical id is also added to HomePageLocators for the DD-9 HOME render.
    EMAIL_CHANGE_STATUS_BANNER = "#EmailChangeStatusBanner"

    # Keep SPLASH_MODAL for reset password and expired email validation flows.
    # These flows use a single generic #SplashModal shell that is populated with
    # different form content at runtime (via URL dispatch), unlike the other modals
    # (e.g. ForgotPasswordModal, EmailValidationModal) which are pre-rendered with
    # their own specific IDs and can be targeted directly.
    SPLASH_MODAL = "#SplashModal"

    # Unscoped common selectors (use for reset password / single-modal pages)
    INPUT_USERNAME = "#username"
    INPUT_PASSWORD = "#password"
    INPUT_EMAIL = "#email"
    INPUT_EMAIL_CONFIRM = "#confirmEmail"
    INPUT_PASSWORD_CONFIRM = "#confirmPassword"
    BUTTON_SUBMIT = "#submit"

    # Login modal scoped selectors
    LOGIN_INPUT_USERNAME = f"{LOGIN_MODAL} #username"
    LOGIN_INPUT_PASSWORD = f"{LOGIN_MODAL} #password"
    LOGIN_BUTTON_SUBMIT = f"{LOGIN_MODAL} #submit"
    LOGIN_INVALID_FEEDBACK = f"{LOGIN_MODAL} .invalid-feedback"
    LOGIN_BUTTON_GOOGLE_OAUTH = f"{LOGIN_MODAL} #GoogleOAuthLogin"
    LOGIN_BUTTON_GITHUB_OAUTH = f"{LOGIN_MODAL} #GitHubOAuthLogin"

    # Register modal scoped selectors
    REGISTER_INPUT_USERNAME = f"{REGISTER_MODAL} #username"
    REGISTER_INPUT_PASSWORD = f"{REGISTER_MODAL} #password"
    REGISTER_INPUT_EMAIL = f"{REGISTER_MODAL} #email"
    REGISTER_INPUT_EMAIL_CONFIRM = f"{REGISTER_MODAL} #confirmEmail"
    REGISTER_INPUT_PASSWORD_CONFIRM = f"{REGISTER_MODAL} #confirmPassword"
    REGISTER_BUTTON_SUBMIT = f"{REGISTER_MODAL} #submit"
    REGISTER_INVALID_FEEDBACK = f"{REGISTER_MODAL} .invalid-feedback"
    REGISTER_BTN_CLOSE = f"{REGISTER_MODAL} .btn-close"
    REGISTER_BUTTON_GOOGLE_OAUTH = f"{REGISTER_MODAL} #GoogleOAuthRegister"
    REGISTER_BUTTON_GITHUB_OAUTH = f"{REGISTER_MODAL} #GitHubOAuthRegister"

    # Forgot password modal scoped selectors
    FORGOT_PASSWORD_INPUT_EMAIL = f"{FORGOT_PASSWORD_MODAL} #email"
    FORGOT_PASSWORD_BUTTON_SUBMIT = f"{FORGOT_PASSWORD_MODAL} #submit"
    FORGOT_PASSWORD_INVALID_FEEDBACK = f"{FORGOT_PASSWORD_MODAL} .invalid-feedback"
    FORGOT_PASSWORD_BTN_CLOSE = f"{FORGOT_PASSWORD_MODAL} .btn-close"

    # Email validation modal scoped selectors
    EMAIL_VALIDATION_BUTTON_SUBMIT = f"{EMAIL_VALIDATION_MODAL} #submit"

    # Reset password (uses #SplashModal — only modal on page, no scoping needed)
    RESET_PASSWORD_BUTTON_SUBMIT = f"{SPLASH_MODAL} #submit"
    RESET_PASSWORD_INVALID_FEEDBACK = f"{SPLASH_MODAL} .invalid-feedback"
    # Set by initResetPasswordForm after the submit handler is bound; tests
    # wait on this so they never race the JS bundle finishing initialization.
    RESET_PASSWORD_FORM_READY = f"{SPLASH_MODAL} form[data-form-ready='true']"

    # Register
    BUTTON_LOGIN_FROM_REGISTER = "#ToLoginFromRegister"
    HEADER_VALIDATE_EMAIL = ".validate-email-title"

    # Post-register confirmation modal
    REGISTER_CONFIRMATION_MODAL_ALERT = (
        f"{REGISTER_CONFIRMATION_MODAL} #SplashModalAlertBanner"
    )
    RESEND_REGISTRATION_EMAIL_LINK = "#ResendRegistrationEmail"
    BACK_TO_LOGIN_FROM_CONFIRMATION = "#BackToLoginFromConfirmation"
    HEADER_REGISTER_CONFIRMATION = "#RegisterConfirmationModalLabel"

    # Login
    BUTTON_REGISTER_FROM_LOGIN = "#ToRegisterFromLogin"

    BUTTON_LOGIN_FROM_FORGOT_PASSWORD = "#ToLoginFromForgotPassword"

    # Alert banner (scoped to visible modal via compound selector)
    LOGIN_MODAL_ALERT = f"{LOGIN_MODAL} #SplashModalAlertBanner"
    REGISTER_MODAL_ALERT = f"{REGISTER_MODAL} #SplashModalAlertBanner"
    FORGOT_PASSWORD_MODAL_ALERT = f"{FORGOT_PASSWORD_MODAL} #SplashModalAlertBanner"
    EMAIL_VALIDATION_MODAL_ALERT = f"{EMAIL_VALIDATION_MODAL} #SplashModalAlertBanner"
    SPLASH_MODAL_ALERT = "#SplashModal #SplashModalAlertBanner"

    # Collision confirm-link page (components/splash/oauth_confirm_link.html)
    CONFIRM_LINK_PROMPT = "#SplashModal #ConfirmLinkPrompt"
    CONFIRM_LINK_INPUT_PASSWORD = "#SplashModal #password"
    CONFIRM_LINK_BUTTON_SUBMIT = "#SplashModal #submit"
    # Password-less (OAuth-only) branch: "Continue with <provider>" anchors,
    # one per provider already linked to the colliding local account.
    CONFIRM_LINK_CONTINUE_WITH_GOOGLE = "#SplashModal #ConfirmLinkContinueWithGoogle"
    CONFIRM_LINK_CONTINUE_WITH_GITHUB = "#SplashModal #ConfirmLinkContinueWithGitHub"

    BUTTON_X_MODAL_DISMISS = ".close-register-login-modal"
    BUTTON_FORGOT_PASSWORD_MODAL = ".to-forgot-password"

    # Modal-scoped dismiss buttons
    LOGIN_BTN_CLOSE = f"{LOGIN_MODAL} .btn-close"
    LOGIN_X_MODAL_DISMISS = f"{LOGIN_MODAL} .close-register-login-modal"
    REGISTER_X_MODAL_DISMISS = f"{REGISTER_MODAL} .close-register-login-modal"

    # Anonymous-splash readiness signal. #splashConfig carries
    # data-show-email-validation, which the route sets to "true" only for an
    # authenticated-but-unvalidated user (email-validation modal auto-shows) and
    # "false" for an anonymous visitor. After logout + redirect, the reloaded
    # splash renders this with "false" — a deterministic positive signal that the
    # session is now anonymous, used in place of a stale-element race.
    SPLASH_CONFIG_ANONYMOUS = '#splashConfig[data-show-email-validation="false"]'

    # Hero section
    WELCOME_TEXT = "#splash-major-text"
    SPLASH_HERO = "#splashHero"
    SPLASH_TAGLINE = "#splash-mini-text"

    # Feature tiles
    SPLASH_FEATURES = "#splashFeatures"
    SPLASH_FEATURES_HEADING = "#splashFeaturesHeading"
    SPLASH_FEATURE_TILES = ".splash-feature-tile"

    # Product preview mock
    SPLASH_PRODUCT_PREVIEW = "#splashProductPreview"
    SPLASH_PRODUCT_MOCK = ".splash-product-mock"
    SPLASH_MOCK_UTUB_ROWS = ".mock-utub-row"
    SPLASH_MOCK_UTUB_SELECTED = ".mock-utub-row--selected"
    SPLASH_MOCK_URL_ROWS = ".mock-url-row"
    SPLASH_MOCK_URL_SELECTED = ".mock-url-row--selected"
    SPLASH_MOCK_TAGS = ".mock-tag"
    SPLASH_MOCK_ACTIONS = ".mock-action"
    SPLASH_MOCK_UTUBS_DECK = ".mock-deck--utubs"
    SPLASH_MOCK_URLS_DECK = ".mock-deck--urls"

    # Reset Password
    INPUT_NEW_PASSWORD = "#newPassword"
    INPUT_CONFIRM_NEW_PASSWORD = "#confirmNewPassword"


class ModalLocators:
    """A collector class for general modal locators"""

    ELEMENT_MODAL = ".modal"
    BUTTON_MODAL_DISMISS = ".btn-close"
    BUTTON_X_MODAL_DISMISS = ".btn-close"


class MetricsDashboardLocators(GenericPageLocator):
    """A collector class for admin metrics dashboard locators.

    Selectors mirror the IDs defined in
    `backend/templates/pages/admin_metrics.html` and the included
    `backend/templates/components/admin/metrics_panel.html` partial.
    """

    # Root containers
    DASHBOARD_ROOT = "#MetricsDashboard"
    DASHBOARD_TITLE = "#MetricsDashboardTitle"

    # Last-flush badge + refresh button
    LAST_FLUSH_BADGE = "#MetricsLastFlush"
    REFRESH_NOW_BUTTON = "#MetricsRefreshNowBtn"
    ERROR_BANNER = "#MetricsErrorBanner"

    # Window selector buttons
    WINDOW_DAY_BUTTON = "#MetricsWindowDay"
    WINDOW_WEEK_BUTTON = "#MetricsWindowWeek"
    WINDOW_MONTH_BUTTON = "#MetricsWindowMonth"
    WINDOW_YEAR_BUTTON = "#MetricsWindowYear"

    # Tab buttons
    TAB_API_BUTTON = "#MetricsTabApi"
    TAB_UI_BUTTON = "#MetricsTabUi"
    TAB_DOMAIN_BUTTON = "#MetricsTabDomain"
    TAB_PIPELINE_HEALTH_BUTTON = "#MetricsTabPipelineHealth"
    TAB_FLOWS_BUTTON = "#MetricsTabFlows"
    TAB_GAUGES_BUTTON = "#MetricsTabGauges"
    TAB_LATENCY_BUTTON = "#MetricsTabLatency"

    # Per-section table IDs
    TOP_TABLE_API = "#MetricsTopTableApi"
    TOP_TABLE_UI = "#MetricsTopTableUi"
    TOP_TABLE_DOMAIN = "#MetricsTopTableDomain"

    # Per-section chart IDs
    CHART_API = "#MetricsChartApi"
    CHART_UI = "#MetricsChartUi"
    CHART_DOMAIN = "#MetricsChartDomain"

    # Global summary section (single 4-card grid at top of page)
    SUMMARY_SECTION = "#MetricsSummary"
    SUMMARY_GRID = "#MetricsSummaryGrid"
    SUMMARY_CARDS = "#MetricsSummaryGrid .summary-card"

    # Per-section top-events filter controls (resource dropdown + substring input)
    TOP_RESOURCE_FILTER_API = "#MetricsTopResourceFilter-api"
    TOP_RESOURCE_FILTER_UI = "#MetricsTopResourceFilter-ui"
    TOP_RESOURCE_FILTER_DOMAIN = "#MetricsTopResourceFilter-domain"
    TOP_DEVICE_FILTER_API = "#MetricsTopDeviceFilter-api"
    TOP_DEVICE_FILTER_UI = "#MetricsTopDeviceFilter-ui"
    TOP_DEVICE_FILTER_DOMAIN = "#MetricsTopDeviceFilter-domain"
    TOP_SUBSTRING_FILTER_API = "#MetricsTopSubstringFilter-api"
    TOP_SUBSTRING_FILTER_UI = "#MetricsTopSubstringFilter-ui"
    TOP_SUBSTRING_FILTER_DOMAIN = "#MetricsTopSubstringFilter-domain"

    # Pipeline Health card (always-visible standalone section above the tablist).
    PIPELINE_HEALTH_CARD = "#MetricsPipelineHealth"
    PIPELINE_HEALTH_CHART = "#MetricsPipelineHealthChart"
    PIPELINE_HEALTH_LEGEND = "#MetricsPipelineHealthLegend"
    PIPELINE_HEALTH_LEGEND_SWATCH_FETCH_DESKTOP = (
        "#MetricsPipelineHealthLegend .swatch--fetch-desktop"
    )
    PIPELINE_HEALTH_LEGEND_SWATCH_FETCH_MOBILE = (
        "#MetricsPipelineHealthLegend .swatch--fetch-mobile"
    )
    PIPELINE_HEALTH_LEGEND_SWATCH_BEACON_DESKTOP = (
        "#MetricsPipelineHealthLegend .swatch--beacon-desktop"
    )
    PIPELINE_HEALTH_LEGEND_SWATCH_BEACON_MOBILE = (
        "#MetricsPipelineHealthLegend .swatch--beacon-mobile"
    )
    PIPELINE_HEALTH_BAR_FETCH_DESKTOP = (
        "#MetricsPipelineHealthChart .MetricsPipelineHealthBar--fetch-desktop"
    )
    PIPELINE_HEALTH_BAR_FETCH_MOBILE = (
        "#MetricsPipelineHealthChart .MetricsPipelineHealthBar--fetch-mobile"
    )
    PIPELINE_HEALTH_BAR_BEACON_DESKTOP = (
        "#MetricsPipelineHealthChart .MetricsPipelineHealthBar--beacon-desktop"
    )
    PIPELINE_HEALTH_BAR_BEACON_MOBILE = (
        "#MetricsPipelineHealthChart .MetricsPipelineHealthBar--beacon-mobile"
    )
    PIPELINE_HEALTH_EMPTY_STATE = "#MetricsPipelineHealthChart .MetricsEmptyState"

    # Flows tab (conversion funnels)
    FLOWS_PANEL = "#MetricsPanelFlows"
    FLOWS_GRID = "#MetricsFlowGrid"
    FLOWS_CARD = "#MetricsFlowGrid .flow-card"
    FLOWS_FUNNEL_STEP = "#MetricsFlowGrid .flow-card .funnel-step"
    FLOWS_CAUSE_PILL = "#MetricsFlowGrid .flow-card .cause-pill"
    FLOWS_CARD_EMPTY = "#MetricsFlowGrid .flow-card .flow-card-empty"

    # Gauges tab (2-column table; click a row to show that gauge's trend chart)
    GAUGES_PANEL = "#MetricsPanelGauges"
    GAUGES_GRID = "#MetricsGaugeGrid"
    GAUGES_TABLE = "#MetricsGaugeGrid .gauge-table"
    GAUGES_ROW = "#MetricsGaugeGrid .gauge-row"
    GAUGES_ROW_SUPPRESSED = "#MetricsGaugeGrid .gauge-row--suppressed"
    GAUGES_ROW_SELECTED = "#MetricsGaugeGrid .gauge-row--selected"
    GAUGES_DETAIL_PROMPT = "#MetricsGaugeGrid .gauge-detail-prompt"
    GAUGES_DETAIL_CHART = "#MetricsGaugeGrid .gauge-detail svg.gauge-chart"
    GAUGES_PANEL_EMPTY_STATE = "#MetricsGaugeGrid .MetricsEmptyState"

    # Backend Performance / Latency tab (per-endpoint percentile table; click a
    # row to show that endpoint's multi-series latency-over-time chart).
    LATENCY_PANEL = "#MetricsPanelLatency"
    LATENCY_TABLE = "#MetricsLatencyTable"
    LATENCY_ROW = "#MetricsLatencyTable tbody tr.latency-row"
    LATENCY_ROW_SELECTED = "#MetricsLatencyTable tbody tr.latency-row--selected"
    LATENCY_EMPTY_ROW = "#MetricsLatencyTable tbody tr.MetricsLatencyEmptyRow"
    LATENCY_DETAIL_CONTAINER = "#MetricsLatencyChartContainer"
    LATENCY_DETAIL_PROMPT = "#MetricsLatencyChartContainer .latency-detail-prompt"
    LATENCY_DETAIL_CHART = "#MetricsLatencyChartContainer svg.latency-chart"
    LATENCY_DETAIL_CHART_LINE = (
        "#MetricsLatencyChartContainer svg.latency-chart polyline"
    )
    LATENCY_DETAIL_CHART_EMPTY_STATE = (
        "#MetricsLatencyChartContainer svg.latency-chart .MetricsEmptyState"
    )
    LATENCY_APPROXIMATE_NOTE = "#MetricsLatencyGrid .latency-approximate-note"
    LATENCY_DAILY_RESOLUTION_NOTE = "#MetricsLatencyGrid .latency-daily-note"


class AdminPortalLocators(GenericPageLocator):
    """A collector class for admin portal landing page locators.

    Selectors mirror the IDs defined in
    `backend/templates/admin_portal/index.html` and
    `backend/templates/admin_portal/_nav.html`.
    """

    # Page-level containers
    PORTAL_TITLE = "#AdminPortalTitle"
    PORTAL_SUBTITLE = "#AdminPortalSubtitle"
    QUICK_LINKS = "#AdminQuickLinks"

    # Navigation shell
    NAV = "#AdminNav"
    NAV_DASHBOARD = "#AdminNavDashboard"
    NAV_HEALTH = "#AdminNavHealth"
    NAV_SYSTEM_OPS = "#AdminNavSystemOps"
    NAV_DB_BROWSER = "#AdminNavDbBrowser"
    NAV_USER_ACTIONS = "#AdminNavUsers"
    NAV_UTUB_ACTIONS = "#AdminNavUtubActions"
    NAV_AUDIT_LOG = "#AdminNavAuditLog"
    NAV_METRICS = "#AdminNavMetrics"

    # Health dashboard page
    HEALTH_TITLE = "#AdminHealthTitle"
    HEALTH_SNAPSHOT_REGION = "#AdminHealthSnapshot"
    HEALTH_GRID = "#AdminHealthGrid"
    HEALTH_DATABASE_CARD = "#AdminHealthDatabase"
    HEALTH_DB_CONNECTIONS = "#AdminHealthDbConnections"
    HEALTH_FLUSH_LAG = "#AdminHealthFlushLag"
    HEALTH_SLOWEST_ENDPOINT = "#AdminHealthSlowestEndpoint"
    HEALTH_ERROR_RATE = "#AdminHealthErrorRate"
    HEALTH_BUSIEST_ENDPOINT = "#AdminHealthBusiestEndpoint"
    HEALTH_SYSTEM_RESOURCES = "#AdminHealthSystemResources"
    HEALTH_CPU_LOAD = "#AdminHealthCpuLoad"
    HEALTH_MEMORY = "#AdminHealthMemory"
    HEALTH_CAPTURED_AT = "#AdminHealthCapturedAt"

    # Ops actions (health page) + shared admin-action modal elements
    OPS_SECTION = "#AdminOpsSection"
    OPS_VERIFY_TABLES_BTN = "#AdminOpsVerifyTablesBtn"
    OPS_METRICS_FLUSH_BTN = "#AdminOpsMetricsFlushBtn"
    OPS_BACKUP_TRIGGER_BTN = "#AdminOpsBackupTriggerBtn"
    OPS_CARD_DESC = ".admin-ops-card-desc"
    HEALTH_BACKUP_CARD = "#AdminHealthBackup"
    # Non-reloading actions render their result inline, immediately after the
    # triggering button (button-scoped via the adjacent-sibling combinator).
    ACTION_INLINE_RESULT = ".admin-action-inline-result"
    OPS_VERIFY_TABLES_RESULT = "#AdminOpsVerifyTablesBtn + .admin-action-inline-result"
    ACTION_CONFIRM_MODAL = "#confirmModal"
    ACTION_MODAL_TITLE = "#confirmModalTitle"
    ACTION_MODAL_SUBMIT = "#modalSubmit"
    ACTION_REASON_INPUT = "#AdminActionReasonInput"

    # Users search page
    USERS_TITLE = "#AdminUsersTitle"
    USER_SEARCH_INPUT = "#AdminUserSearchInput"
    USER_SEARCH_RESULTS = "#AdminUserSearchResults"
    USER_SEARCH_TABLE = "#AdminUserSearchTable"
    USER_SEARCH_ROW = "tr.admin-user-row"
    USER_SEARCH_EMPTY = "#AdminUserSearchEmpty"

    # UTub Actions list page (reuses the DB browser's table service)
    UTUB_TABLE_GRID = "#AdminUtubTableGrid"
    UTUB_TABLE_SEARCH = "#AdminUtubTableSearch"
    UTUB_ROW_LINK = "#AdminUtubTableGrid .admin-db-row-link"
    UTUB_CLICKABLE_ROW = "#AdminUtubTableGrid tbody tr.admin-clickable-row"
    UTUB_TABLE_EMPTY = "#AdminUtubTableEmpty"

    # UTub detail page (aggregated moderation surface)
    UTUB_DETAIL_TITLE = "#AdminUtubDetailTitle"
    UTUB_DETAIL_BREADCRUMB_ROOT = "#AdminUtubDetailBreadcrumb .admin-breadcrumb-root"
    UTUB_DETAIL_MEMBERS_HEADING = "#AdminUtubDetailMembersHeading"
    UTUB_DETAIL_URLS_HEADING = "#AdminUtubDetailUrlsHeading"
    UTUB_DETAIL_MEMBERS_TABLE = "#AdminUtubDetailMembersTable"
    UTUB_DETAIL_URLS_TABLE = "#AdminUtubDetailUrlsTable"
    UTUB_DETAIL_TAGS_PANEL = "#AdminUtubDetailTagsPanel"
    UTUB_DETAIL_TAGS_TABLE = "#AdminUtubDetailTagsTable"
    UTUB_DETAIL_NO_TAGS = "#AdminUtubDetailNoTags"
    UTUB_DETAIL_MEMBERS_SEARCH = "#AdminUtubDetailMembersSearch"
    UTUB_DETAIL_URLS_SEARCH = "#AdminUtubDetailUrlsSearch"
    UTUB_DETAIL_TAGS_SEARCH = "#AdminUtubDetailTagsSearch"
    UTUB_DETAIL_MEMBERS_PAGINATION = "#AdminUtubDetailMembersPagination"
    UTUB_DETAIL_URLS_PAGINATION = "#AdminUtubDetailUrlsPagination"
    UTUB_DETAIL_LOCKED_BADGE = ".admin-locked-badge"
    # Moderation controls on the UTub-detail page (page-agnostic, scoped by
    # data-admin-action value shared across the admin-actions controller).
    UTUB_DETAIL_MOD_LOCK_BTN = '[data-admin-action="utub-lock"]'
    UTUB_DETAIL_MOD_UNLOCK_BTN = '[data-admin-action="utub-unlock"]'
    UTUB_DETAIL_MOD_DELETE_BTN = '[data-admin-action="utub-delete"]'
    UTUB_DETAIL_MOD_MEMBER_REMOVE_BTN = '[data-admin-action="member-remove"]'
    UTUB_DETAIL_MOD_URL_DELETE_BTN = '[data-admin-action="url-delete"]'
    UTUB_DETAIL_MOD_URL_PURGE_BTN = '[data-admin-action="url-purge"]'
    UTUB_DETAIL_MOD_UTUB_TAG_DELETE_BTN = '[data-admin-action="utub-tag-delete"]'

    # User detail page
    USER_DETAIL_TITLE = "#AdminUserDetailTitle"
    USER_DETAIL_BREADCRUMB_ROOT = "#AdminUserDetailBreadcrumb .admin-breadcrumb-root"
    USER_DETAIL_USERNAME = "#AdminUserDetailUsername"
    # Read-only UTub memberships list (moderation buttons relocated to UTub-detail)
    USER_DETAIL_MEMBERSHIPS_TABLE = "#AdminUserMembershipsTable"
    USER_DETAIL_LOCKED_BADGE = ".admin-locked-badge"

    # User-detail info rows
    USER_DETAIL_EMAIL_VALIDATED = "#AdminUserDetailEmailValidated"
    # User-detail Suspended row and account-lifecycle action panel
    USER_DETAIL_SUSPENDED = "#AdminUserDetailSuspended"
    USER_DETAIL_ACCOUNT_ACTIONS = "#AdminUserAccountActions"
    USER_DETAIL_ACCOUNT_ACTIONS_HEADING = "#AdminUserAccountActionsHeading"
    USER_DETAIL_SELF_ACTIONS_NOTE = "#AdminUserSelfActionsNote"
    USER_DETAIL_ACCOUNT_SUSPEND_BTN = '[data-admin-action="user-suspend"]'
    USER_DETAIL_ACCOUNT_UNSUSPEND_BTN = '[data-admin-action="user-unsuspend"]'
    USER_DETAIL_ACCOUNT_KILL_SESSIONS_BTN = '[data-admin-action="user-kill-sessions"]'
    USER_DETAIL_ACCOUNT_FORCE_RESET_BTN = '[data-admin-action="user-force-reset"]'
    USER_DETAIL_ACCOUNT_FORCE_RESET_NA = "#AdminUserForceResetNA"
    USER_DETAIL_ACCOUNT_KILL_SESSIONS_RESULT = (
        '[data-admin-action="user-kill-sessions"] + .admin-action-inline-result'
    )
    USER_DETAIL_ACCOUNT_FORCE_RESET_RESULT = (
        '[data-admin-action="user-force-reset"] + .admin-action-inline-result'
    )
    # Account data actions (erase / OAuth unlink / email verification)
    USER_DETAIL_ERASED = "#AdminUserDetailErased"
    USER_DETAIL_ACCOUNT_ERASE_BTN = '[data-admin-action="user-erase"]'
    USER_DETAIL_ACCOUNT_ERASED_NA = "#AdminUserErasedNA"
    USER_DETAIL_ACCOUNT_EMAIL_VERIFY_BTN = '[data-admin-action="user-email-verify"]'
    USER_DETAIL_ACCOUNT_EMAIL_VERIFIED_NA = "#AdminUserEmailVerifiedNA"
    USER_DETAIL_ACCOUNT_EMAIL_RESEND_BTN = '[data-admin-action="user-email-resend"]'
    # OAuth identities panel
    USER_DETAIL_OAUTH_PANEL = "#AdminUserOauthIdentities"
    USER_DETAIL_OAUTH_TABLE = "#AdminUserOauthTable"
    USER_DETAIL_OAUTH_UNLINK_BTN = '[data-admin-action="oauth-unlink"]'
    USER_DETAIL_OAUTH_UNLINK_NA = "#AdminUserUnlinkNA"
    USER_DETAIL_NO_OAUTH = "#AdminUserNoOauthIdentities"

    # Admin-action modal alert banner (reason-required / server-error messages)
    ACTION_MODAL_ALERT_BANNER = "#HomeModalAlertBanner"

    # Audit log page
    AUDIT_LOG_TITLE = "#AdminAuditLogTitle"
    AUDIT_FILTER_ACTION = "#AdminAuditFilterAction"
    AUDIT_LOG_RESULTS = "#AdminAuditLogResults"
    AUDIT_LOG_TABLE = "#AdminAuditLogTable"
    AUDIT_LOG_ROW = "tr.admin-audit-row"
    AUDIT_METADATA_DETAILS = "details.admin-audit-metadata"
    AUDIT_LOG_EMPTY = "#AdminAuditLogEmpty"

    # DB browser pages
    DB_BROWSER_TITLE = "#AdminDbBrowserTitle"
    DB_TABLES = "#AdminDbTables"
    DB_TABLE_CARD = ".admin-quick-link-card"
    DB_TABLE_GRID = "#AdminDbTableGrid"
    DB_TABLE_EMPTY = "#AdminDbTableEmpty"
    DB_ROW_DETAIL = "#AdminDbRowDetail"
    DB_TABLE_SEARCH = "#AdminDbTableSearch"
    DB_SORT_LINK = ".admin-db-sort-link"


class SettingsPageLocators(GenericPageLocator):
    """A collector class for user settings page locators.

    Selectors mirror the IDs defined in
    `backend/templates/pages/settings.html` (the ARIA tablist + four
    placeholder tabpanels).
    """

    PAGE_ROOT = "#SettingsPage"
    TABLIST = "#SettingsTablist"

    # Tab buttons
    TAB_ACCOUNT_BUTTON = "#SettingsTabAccount"
    TAB_STATS_BUTTON = "#SettingsTabStats"
    TAB_PRIVACY_DATA_BUTTON = "#SettingsTabPrivacyData"
    TAB_UI_SETTINGS_BUTTON = "#SettingsTabUiSettings"

    # Tab panels
    PANEL_ACCOUNT = "#SettingsPanelAccount"
    PANEL_STATS = "#SettingsPanelStats"
    PANEL_PRIVACY_DATA = "#SettingsPanelPrivacyData"
    PANEL_UI_SETTINGS = "#SettingsPanelUiSettings"

    # Account-info panel cards (Account tab). Each value locator targets the
    # `data-account-info="…"` card's `.SettingsStatValue`, mirroring the
    # four-card grid in backend/templates/pages/settings.html.
    ACCOUNT_INFO_USERNAME_VALUE = (
        '#SettingsPanelAccount [data-account-info="username"] .SettingsStatValue'
    )
    ACCOUNT_INFO_EMAIL_VALUE = (
        '#SettingsPanelAccount [data-account-info="email"] .SettingsStatValue'
    )
    ACCOUNT_INFO_MEMBER_SINCE = (
        '#SettingsPanelAccount [data-account-info="member-since"] .SettingsStatValue'
    )
    ACCOUNT_INFO_EMAIL_STATUS = (
        '#SettingsPanelAccount [data-account-info="email-verified"] .SettingsStatValue'
    )

    # Change-username form (Account tab). Mirrors the ids rendered in
    # backend/templates/pages/settings.html and the data-* contract in
    # frontend/settings/change-username.ts.
    # The form now lives inside a collapsible <details> that defaults to closed;
    # click the summary to reveal the input/button before interacting.
    CHANGE_USERNAME_SUMMARY = (
        "#SettingsPanelAccount .SettingsChangeUsername .SettingsDisclosureSummary"
    )
    CHANGE_USERNAME_DETAILS = "#SettingsPanelAccount .SettingsChangeUsername"
    CHANGE_USERNAME_INPUT = "#SettingsNewUsername"
    CHANGE_USERNAME_BTN = "#SettingsChangeUsernameBtn"
    USERNAME_STATUS = "#SettingsUsernameStatus"
    USERNAME_INVALID_FEEDBACK = "#SettingsNewUsername ~ .invalid-feedback"
    # Navbar "Logged in as <username>" label; a successful rename refreshes it in
    # place (desktop-inline copy, visible above 992px).
    NAV_LOGGED_IN_AS_USERNAME = "#userLoggedInDesktop .navLoggedInAsUsername"

    # Change-password form (Account tab). Mirrors the ids rendered (gated by
    # `connected_accounts_has_password`) in backend/templates/pages/settings.html
    # and the data-* contract in frontend/settings/change-password.ts. The
    # section wrapper is always present; the OAuth-only note replaces the form
    # for password-less accounts.
    CHANGE_PASSWORD_SECTION = "#SettingsPanelAccount .SettingsChangePassword"
    # For password accounts the section is a collapsible <details> defaulting to
    # closed; click the summary to reveal the fields. (OAuth-only accounts render
    # a plain note in its place — no summary.)
    CHANGE_PASSWORD_SUMMARY = (
        "#SettingsPanelAccount .SettingsChangePassword .SettingsDisclosureSummary"
    )
    CHANGE_PASSWORD_CURRENT_INPUT = "#SettingsCurrentPassword"
    CHANGE_PASSWORD_NEW_INPUT = "#SettingsNewPassword"
    CHANGE_PASSWORD_CONFIRM_INPUT = "#SettingsConfirmNewPassword"
    CHANGE_PASSWORD_BTN = "#SettingsChangePasswordBtn"
    PASSWORD_STATUS = "#SettingsPasswordStatus"
    CHANGE_PASSWORD_OAUTH_NOTE = ".SettingsChangePasswordOAuthNote"

    # Change-email form (Account tab, Phase 3). Mirrors the ids rendered (gated
    # by `connected_accounts_has_password`) in backend/templates/pages/settings.html
    # and the data-* contract in frontend/settings/change-email.ts. For password
    # accounts it is a collapsible <details> defaulting to closed; OAuth-only
    # accounts render a plain <div> note (SettingsChangeEmailOAuthNote) with no
    # <details>/<summary> (DD-7). CHANGE_EMAIL_DETAILS is scoped to the <details>
    # element so it counts 0 for the OAuth-only plain-div fallback.
    CHANGE_EMAIL_DETAILS = "#SettingsPanelAccount details.SettingsChangeEmail"
    CHANGE_EMAIL_SUMMARY = (
        "#SettingsPanelAccount .SettingsChangeEmail .SettingsDisclosureSummary"
    )
    CHANGE_EMAIL_NEW_INPUT = "#SettingsNewEmail"
    CHANGE_EMAIL_CONFIRM_INPUT = "#SettingsConfirmNewEmail"
    CHANGE_EMAIL_CURRENT_PASSWORD_INPUT = "#SettingsChangeEmailCurrentPassword"
    CHANGE_EMAIL_BTN = "#SettingsChangeEmailBtn"
    EMAIL_STATUS = "#SettingsEmailStatus"
    # Field-error feedback nodes injected by change-email.ts's showFieldError()
    # as a sibling of the offending input (mirrors USERNAME_INVALID_FEEDBACK).
    EMAIL_INVALID_FEEDBACK = "#SettingsNewEmail ~ .invalid-feedback"
    CHANGE_EMAIL_CONFIRM_INVALID_FEEDBACK = (
        "#SettingsConfirmNewEmail ~ .invalid-feedback"
    )
    CHANGE_EMAIL_OAUTH_NOTE = ".SettingsChangeEmailOAuthNote"
    # In-form pending-change warning (DD-16) + account-info pending note (DD-6),
    # both server-rendered only when `account_pending_email` is set.
    CHANGE_EMAIL_PENDING_WARNING = ".SettingsChangeEmailPendingWarning"
    ACCOUNT_PENDING_EMAIL_NOTE = (
        '#SettingsPanelAccount [data-account-info="email"] '
        ".SettingsAccountPendingEmailNote"
    )

    # Stats panel cards (Stats tab). Each value locator targets the
    # `data-stat="…"` card's `.SettingsStatValue`, mirroring the template's
    # six-card grid in backend/templates/pages/settings.html.
    STAT_UTUBS_CREATED = (
        '#SettingsPanelStats [data-stat="utubs-created"] .SettingsStatValue'
    )
    STAT_MEMBER_OF = '#SettingsPanelStats [data-stat="member-of"] .SettingsStatValue'
    STAT_URLS_ADDED = '#SettingsPanelStats [data-stat="urls-added"] .SettingsStatValue'
    STAT_TAGS_CREATED = (
        '#SettingsPanelStats [data-stat="tags-created"] .SettingsStatValue'
    )
    STAT_TAGS_APPLIED = (
        '#SettingsPanelStats [data-stat="tags-applied"] .SettingsStatValue'
    )
    STAT_MEMBER_SINCE = (
        '#SettingsPanelStats [data-stat="member-since"] .SettingsStatValue'
    )

    # Cross-page locator: #userSettingsLink is rendered in the navbar on
    # /home (hidden on /settings). Placed here because
    # test_settings_nav_link_present_on_home lives in the settings_ui suite.
    SETTINGS_NAV_LINK = "#userSettingsLink"

    # Display tab (Phase 6). The theme segmented control + four view-pref
    # <select>s server-rendered in the `#SettingsPanelUiSettings` tabpanel of
    # backend/templates/pages/settings.html, plus the data-* contract read by
    # frontend/settings/display-preferences.ts. The panel/tab locators
    # (TAB_UI_SETTINGS_BUTTON / PANEL_UI_SETTINGS) already exist above.
    THEME_CONTROL = "#SettingsThemeControl"
    THEME_RADIO_LIGHT = f'{THEME_CONTROL} [role="radio"][data-theme-value="light"]'
    THEME_RADIO_DARK = f'{THEME_CONTROL} [role="radio"][data-theme-value="dark"]'
    THEME_RADIO_SYSTEM = f'{THEME_CONTROL} [role="radio"][data-theme-value="system"]'
    DEFAULT_VIEW_SELECT = "#SettingsDefaultViewSelect"
    DEFAULT_SORT_SELECT = "#SettingsDefaultSortSelect"
    DENSITY_SELECT = "#SettingsDensitySelect"
    DATE_FORMAT_SELECT = "#SettingsDateFormatSelect"
    # Success toast (write target for the instant-apply "Preferences saved"
    # message) and the panel-local error region.
    GLOBAL_STATUS_TOAST = "#SettingsGlobalStatusToast"
    UI_SETTINGS_STATUS = "#SettingsUiSettingsStatus"
    # The <html> root carrying the app-wide, server-stamped theme
    # (data-theme="{{ user_theme }}") — the pre-paint delivery this suite
    # asserts round-trips through the DB.
    HTML_ROOT = "html"

    # Connected Accounts section (Account tab). Mirrors
    # backend/templates/pages/settings.html:18-59 and the data-* contract
    # documented in frontend/settings/connected-accounts.ts.
    CONNECTED_ACCOUNTS_ROOT = "#SettingsConnectedAccounts"
    CONNECTED_ACCOUNTS_TITLE = f"{CONNECTED_ACCOUNTS_ROOT} .ConnectedAccountsTitle"
    LINK_STATUS_BANNER = "#SettingsLinkStatusBanner"
    ROW_GOOGLE = "#ConnectedAccountRowGoogle"
    ROW_GITHUB = "#ConnectedAccountRowGitHub"
    ROW_NAME = ".ConnectedAccountName"
    ROW_STATUS = ".ConnectedAccountStatus"
    ROW_LAST_METHOD_NOTE = ".ConnectedAccountLastMethodNote"
    ROW_LINK_BTN = ".ConnectedAccountLinkBtn"
    ROW_UNLINK_BTN = ".ConnectedAccountUnlinkBtn"
    ROW_PASSWORD_CONFIRM = ".ConnectedAccountPasswordConfirm"
    ROW_PASSWORD_INPUT = ".ConnectedAccountPasswordInput"
    ROW_PASSWORD_INPUT_GOOGLE = "#ConnectedAccountPasswordGoogle"
    ROW_PASSWORD_INPUT_GITHUB = "#ConnectedAccountPasswordGitHub"
    ROW_PASSWORD_CONTINUE_BTN = ".ConnectedAccountPasswordContinueBtn"
    ROW_PASSWORD_CANCEL_BTN = ".ConnectedAccountPasswordCancelBtn"

    # Account danger zone (Account tab, Phase 4) — self-service delete — plus the
    # non-destructive "Log out everywhere" security control that lives in the
    # account panel's security area (near `#SettingsConnectedAccounts`), NOT in the
    # Danger Zone. Mirrors the ids rendered in the `.SettingsDangerZone` block and
    # the `#SettingsLogoutEverywhere` block of backend/templates/pages/settings.html
    # plus the bespoke dark modals in its `{% block modal_extender %}`, and the
    # data-* contract documented in frontend/settings/account-removal.ts. The delete
    # re-auth password input bases on CHANGE_EMAIL_CURRENT_PASSWORD_INPUT's naming
    # convention; the re-auth button (`#SettingsDeleteReauthBtn`) renders only for
    # OAuth-only accounts (server-gated by `connected_accounts_has_password`), where
    # the password input + password-path submit button are absent.
    DANGER_ZONE = "#SettingsPanelAccount .SettingsDangerZone"
    DELETE_TRIGGER = "#SettingsDeleteBtn"

    # Export-my-data control (Privacy & Data tab). Non-destructive read: the
    # button triggers a fetch→Blob JSON download and the status region is an
    # aria-live alert. Mirrors the ids in the `#SettingsExportData` card of
    # backend/templates/pages/settings.html.
    EXPORT_DATA_BTN = "#SettingsExportDataBtn"
    EXPORT_STATUS = "#SettingsExportStatus"

    # Log out everywhere control + confirm modal (non-destructive, no re-auth: D-1).
    LOGOUT_EVERYWHERE_TRIGGER = "#SettingsLogoutEverywhereBtn"
    LOGOUT_EVERYWHERE_MODAL = "#SettingsLogoutEverywhereModal"
    LOGOUT_EVERYWHERE_SUBMIT_BTN = "#SettingsLogoutEverywhereSubmitBtn"
    LOGOUT_EVERYWHERE_ERROR = "#SettingsLogoutEverywhereError"
    LOGOUT_EVERYWHERE_CANCEL_BTN = (
        "#SettingsLogoutEverywhereModal .modal-footer .btn-secondary"
    )

    # Delete modal (irreversible erasure) — adds typed-username confirmation.
    DELETE_MODAL = "#SettingsDeleteModal"
    DELETE_CONFIRM_USERNAME_INPUT = "#SettingsDeleteConfirmUsername"
    DELETE_CURRENT_PASSWORD_INPUT = "#SettingsDeleteCurrentPassword"
    DELETE_REAUTH_BTN = "#SettingsDeleteReauthBtn"
    DELETE_SUBMIT_BTN = "#SettingsDeleteSubmitBtn"
    DELETE_ERROR = "#SettingsDeleteError"
    DELETE_CANCEL_BTN = "#SettingsDeleteModal .modal-footer .btn-secondary"
    DELETE_PASSWORD_INVALID_FEEDBACK = (
        "#SettingsDeleteCurrentPassword ~ .invalid-feedback"
    )
