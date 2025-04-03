class GenericPageLocator:
    ERROR_PAGE_HANDLER = "#ErrorPageHandler"
    ERROR_PAGE_REFRESH_BTN = f"{ERROR_PAGE_HANDLER} .refresh-button"
    NAVBAR_TOGGLER = ".navbar-toggler"
    NAVBAR_DROPDOWN = "#NavbarNavDropdown"


class HomePageLocators(GenericPageLocator):
    """A collector class for main page locators"""

    INVALID_FIELD_SUFFIX = "-error"
    HIDDEN_BTN_CLASS = "hiddenBtn"

    # Navbar
    BUTTON_LOGOUT = "#logout > .nav-bar-inner-item"
    LOGGED_IN_USERNAME_READ = "#userLoggedIn"
    U4I_LOGO = ".navbar-brand"

    # UTub Deck
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

    # Tag Deck
    SUBHEADER_TAG_DECK = "#TagDeckSubheader"
    LIST_TAGS = "#listTags"
    TAG_FILTERS = ".tagFilter"
    BUTTON_UNSELECT_ALL = "#unselectAllTagFilters"
    BUTTON_UTUB_TAG_CREATE = "#utubTagBtnCreate"
    INPUT_UTUB_TAG_CREATE = "#utubTagCreate"
    BUTTON_UTUB_TAG_SUBMIT_CREATE = "#utubTagSubmitBtnCreate"
    BUTTON_UTUB_TAG_CANCEL_CREATE = "#utubTagCancelBtnCreate"
    UNSELECTED = ".unselected"
    SELECTED = ".selected"

    # URL Deck
    WRAP_UTUB_NAME_UPDATE = "#UTubNameUpdateWrap"
    HEADER_URL_DECK = "#URLDeckHeader"
    BUTTON_UTUB_NAME_UPDATE = "#utubNameBtnUpdate"
    INPUT_UTUB_NAME_UPDATE = "#utubNameUpdate"
    BUTTON_UTUB_NAME_SUBMIT_UPDATE = "#utubNameSubmitBtnUpdate"
    WRAP_URL_CREATE = "#createURLWrap"
    BUTTON_UTUB_NAME_CANCEL_UPDATE = "#utubNameCancelBtnUpdate"
    BUTTON_ADD_UTUB_DESC_ON_EMPTY = "#URLDeckSubheaderCreateDescription"

    WRAP_UTUB_DESCRIPTION_UPDATE = "#UTubDescriptionSubheaderWrap"
    SUBHEADER_URL_DECK = "#URLDeckSubheader"
    SUBHEADER_NO_URLS = "#NoURLsSubheader"
    BUTTON_UTUB_DESCRIPTION_UPDATE = "#updateUTubDescriptionBtn"
    INPUT_UTUB_DESCRIPTION_UPDATE = "#utubDescriptionUpdate"
    BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE = "#utubDescriptionSubmitBtnUpdate"
    BUTTON_UTUB_DESCRIPTION_CANCEL_UPDATE = "#utubDescriptionCancelBtnUpdate"

    LIST_URL = "#listURLs"
    ROWS_URLS = ".urlRow"
    ROW_SELECTED_URL = ".urlRow[urlselected='true']"
    ROW_VISIBLE_URL = ".urlRow[filterable='true']"

    BUTTON_CORNER_URL_CREATE = "#urlBtnCreate"
    BUTTON_DECK_URL_CREATE = "#urlBtnDeckCreate"
    INPUT_URL_TITLE_CREATE = "#urlTitleCreate"
    INPUT_URL_STRING_CREATE = "#urlStringCreate"
    BUTTON_URL_SUBMIT_CREATE = "#urlSubmitBtnCreate"
    BUTTON_URL_CANCEL_CREATE = "#urlCancelBtnCreate"

    BUTTON_ACCESS_ALL_URLS = "#accessAllURLsBtn"

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
    INPUT_TAG_CREATE = ".urlTagCreate"
    BUTTON_TAG_SUBMIT_CREATE = ".urlTagSubmitBtnCreate"
    BUTTON_TAG_CANCEL_CREATE = ".urlTagCancelBtnCreate"
    BUTTON_BIG_TAG_CANCEL_CREATE = ".urlTagCancelBigBtnCreate"
    ERROR_TAG_CREATE = ".urlTagCreate-error"

    BUTTON_TAG_DELETE = ".urlTagBtnDelete"

    UPDATE_URL_STRING_WRAP = ".updateUrlStringWrap"
    BUTTON_URL_STRING_UPDATE = ".urlStringBtnUpdate"
    INPUT_URL_STRING_UPDATE = ".urlStringUpdate"
    BUTTON_URL_STRING_SUBMIT_UPDATE = ".urlStringSubmitBtnUpdate"
    BUTTON_URL_STRING_CANCEL_UPDATE = ".urlStringCancelBtnUpdate"
    BUTTON_BIG_URL_STRING_CANCEL_UPDATE = ".urlStringCancelBigBtnUpdate"

    BUTTON_URL_DELETE = ".urlBtnDelete"

    URL_STRING_IN_DATA = "data-url"
    GO_TO_URL_ICON = ".goToUrlIcon"

    # Members Deck
    SUBHEADER_MEMBER_DECK = "#memberDeckSubheader"
    BUTTON_MEMBER_CREATE = "#memberBtnCreate"
    INPUT_MEMBER_CREATE = "#memberCreate"
    BUTTON_MEMBER_CANCEL_CREATE = "#memberCancelBtnCreate"
    BUTTON_MEMBER_SUBMIT_CREATE = "#memberSubmitBtnCreate"
    BUTTON_UTUB_LEAVE = "#memberSelfBtnDelete"
    BUTTON_MEMBER_DELETE = ".memberOtherBtnDelete"
    INPUT_MEMBER_CREATE_ERROR = INPUT_MEMBER_CREATE + INVALID_FIELD_SUFFIX

    SUBHEADER_UTUB = "#MemberDeckSubheader"
    LIST_MEMBERS = "#listMembers"
    BADGES_MEMBERS = ".member"
    BADGE_OWNER = "#UTubOwner > .member"

    # Modal
    HOME_MODAL = "#confirmModal"
    HEADER_MODAL = "#confirmModalTitle"
    BODY_MODAL = "#confirmModalBody"
    BUTTON_MODAL_DISMISS = "#modalDismiss"
    BUTTON_MODAL_REDIRECT = "#modalRedirect"
    BUTTON_MODAL_SUBMIT = "#modalSubmit"
    BUTTON_X_CLOSE = ".btn-close"
    ACCESS_ALL_URL_MODAL = ".accessAllUrlModal"
    DELETE_URL_MODAL = ".deleteUrlModal"

    # Decks
    UTUB_DECK = ".deck#UTubDeck"
    MEMBER_DECK = ".deck#MemberDeck"
    TAG_DECK = ".deck#TagDeck"
    URL_DECK = ".deck#URLDeck"

    # Panels
    MAIN_PANEL = "main#mainPanel"


class SplashPageLocators(GenericPageLocator):
    """A collector class for splash page locators"""

    # Options
    SPLASH_NAVBAR = "#NavbarDropdownsSplash"
    BUTTON_REGISTER = ".btn.to-register"
    BUTTON_LOGIN = ".btn.to-login"

    # Navbar
    NAVBAR_REGISTER = ".nav-bar-inner-item.to-register"
    NAVBAR_LOGIN = ".nav-bar-inner-item.to-login"

    # Common
    INPUT_USERNAME = "#username"
    INPUT_PASSWORD = "#password"
    BUTTON_SUBMIT = "#submit"

    # Register
    INPUT_EMAIL = "#email"
    INPUT_EMAIL_CONFIRM = "#confirmEmail"
    INPUT_PASSWORD_CONFIRM = "#confirmPassword"
    BUTTON_LOGIN_FROM_REGISTER = "#ToLoginFromRegister"
    HEADER_VALIDATE_EMAIL = ".validate-email-title"
    SUBHEADER_INVALID_FEEDBACK = ".invalid-feedback"

    # Login
    BUTTON_REGISTER_FROM_LOGIN = "#ToRegisterFromLogin"

    BUTTON_LOGIN_FROM_FORGOT_PASSWORD = "#ToLoginFromForgotPassword"

    # Modal
    SPLASH_MODAL = "#SplashModal"
    SPLASH_MODAL_ALERT = "#SplashModalAlertBanner"
    BUTTON_X_MODAL_DISMISS = ".close-register-login-modal"
    BUTTON_FORGOT_PASSWORD_MODAL = ".to-forgot-password"

    # Jumbotron
    WELCOME_TEXT = "#splash-major-text"

    # Reset Password
    INPUT_NEW_PASSWORD = "#newPassword"
    INPUT_CONFIRM_NEW_PASSWORD = "#confirmNewPassword"


class ModalLocators:
    """A collector class for general modal locators"""

    ELEMENT_MODAL = ".modal"
    BUTTON_MODAL_DISMISS = ".btn-close"
    BUTTON_X_MODAL_DISMISS = ".btn-close"
