class MainPageLocators:
    """A class for main page locators. All main page locators should come here"""

    # Navbar
    BUTTON_LOGOUT = "#logout > .nav-bar-inner-item"
    LOGGED_IN_USERNAME_READ = "#userLoggedIn"

    # UTub Deck
    BUTTON_UTUB_CREATE = "#utubBtnCreate"
    BUTTON_UTUB_DELETE = "#utubBtnDelete"
    INPUT_UTUB_NAME_CREATE = "#utubNameCreate"
    INPUT_UTUB_DESCRIPTION_CREATE = "#utubDescriptionCreate"
    BUTTON_UTUB_SUBMIT_CREATE = "#utubSubmitBtnCreate"
    BUTTON_UTUB_CANCEL = "#utubCancelBtnCreate"

    SUBHEADER_UTUB_DECK = "#UTubDeckSubheader"
    LIST_UTUB = "#listUTubs"
    SELECTORS_UTUB = ".UTubSelector"
    SELECTOR_SELECTED_UTUB = ".UTubSelector.active"

    # Tag Deck
    SUBHEADER_TAG_DECK = "#TagDeckSubheader"
    ROWS_TAGS = ".tagFilter"
    ERROR_TAG_CREATE = ".urlTagCreate-error"

    BUTTON_TAG_DELETE = ".urlTagBtnDelete"

    # URL Deck
    HEADER_URL_DECK = "#URLDeckHeader"
    BUTTON_UTUB_NAME_UPDATE = "#utubNameBtnUpdate"
    SUBHEADER_URL_DECK = "#URLDeckSubheader"
    SUBHEADER_NO_URLS = "#NoURLsSubheader"
    BUTTON_UTUB_DESCRIPTION_UPDATE = "#updateUTubDescriptionBtn"
    LIST_URL = "#listURLs"
    ROWS_URLS = ".urlRow"
    ROW_SELECTED_URL = ".urlRow[urlselected='true']"

    BUTTON_URL_CREATE = "#urlBtnCreate"
    INPUT_URL_TITLE_CREATE = "#urlTitleCreate"
    INPUT_URL_STRING_CREATE = "#urlStringCreate"
    BUTTON_URL_SUBMIT_CREATE = "#urlSubmitBtnCreate"

    BUTTON_ACCESS_ALL_URLS = "#accessAllURLsBtn"

    # URLs
    URL_TITLE_READ = ".urlTitle"
    URL_STRING_READ = ".urlString"

    URL_TAG_BADGES_READ = ".tagBadge"

    URL_TAGS_READ = ".urlTags"
    URL_BUTTONS_OPTIONS_READ = ".urlOptions"

    BUTTON_URL_TITLE_UPDATE = ".urlTitleBtnUpdate"
    INPUT_URL_TITLE_UPDATE = ".urlTitleUpdate"
    BUTTON_URL_TITLE_SUBMIT_UPDATE = ".urlTitleSubmitBtnUpdate"

    BUTTON_URL_ACCESS = ".urlBtnAccess"

    BUTTON_TAG_CREATE = ".urlTagBtnCreate"
    INPUT_TAG_CREATE = ".urlTagCreate"
    BUTTON_TAG_SUBMIT_CREATE = ".urlTagSubmitBtnCreate"

    BUTTON_URL_STRING_UPDATE = ".urlStringBtnUpdate"
    INPUT_URL_STRING_UPDATE = ".urlStringUpdate"
    BUTTON_URL_STRING_SUBMIT_UPDATE = ".urlStringSubmitBtnUpdate"

    BUTTON_URL_DELETE = ".urlBtnDelete"

    # Members Deck
    SUBHEADER_MEMBER_DECK = "#memberDeckSubheader"
    BUTTON_MEMBER_CREATE = "#memberBtnCreate"
    INPUT_MEMBER_CREATE = "#memberCreate"
    BUTTON_MEMBER_SUBMIT_CREATE = "#memberSubmitBtnCreate"
    BUTTON_UTUB_LEAVE = "#memberSelfBtnDelete"
    BUTTON_MEMBER_DELETE = ".memberOtherBtnDelete"

    SUBHEADER_UTUB = "#MemberDeckSubheader"
    LIST_MEMBERS = "#listMembers"
    BADGES_MEMBERS = ".member"
    BADGE_OWNER = "#UTubOwner > .member"

    # Modal
    HEADER_MODAL = "#confirmModalTitle"
    BODY_MODAL = "#confirmModalBody"
    BUTTON_MODAL_DISMISS = "#modalDismiss"
    BUTTON_MODAL_REDIRECT = "#modalRedirect"
    BUTTON_MODAL_SUBMIT = "#modalSubmit"


class SplashPageLocators:
    """A class for main page locators. All main page locators should come here"""

    # Options
    BUTTON_REGISTER = ".to-register"
    BUTTON_LOGIN = ".to-login"

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

    # Modal
    HEADER_MODAL = "#SplashModalAlertBanner"
