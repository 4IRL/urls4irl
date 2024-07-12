class MainPageLocators:
    """A class for main page locators. All main page locators should come here"""

    # Navbar
    BUTTON_LOGOUT = "#Logout"
    OUTPUT_LOGGED_IN_USERNAME = "#userLoggedIn"

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

    # URL Deck
    SUBHEADER_URL_DECK = "#URLDeckSubheader"
    BUTTON_UTUB_UPDATE = "#utubNameBtnUpdate"
    BUTTON_URL_CREATE = "#urlBtnCreate"
    SUBHEADER_UTUB_DESCRIPTION = "#UTubDescriptionDeckSubheader"
    BUTTON_UTUB_DESCRIPTION_UPDATE = "#editUTubDescriptionBtn"

    # Members Deck
    SUBHEADER_MEMBER_DECK = "#memberDeckSubheader"
    BUTTON_MEMBER_CREATE = "#memberBtnCreate"
    INPUT_MEMBER_CREATE = "#memberCreate"
    BUTTON_MEMBER_SUBMIT_CREATE = "#memberSubmitBtnCreate"
    BUTTON_UTUB_LEAVE = "#memberSelfBtnDelete"
    BUTTON_MEMBER_DELETE = ".memberOtherBtnDelete"

    SUBHEADER_UTUB = "#MemberDeckSubheader"
    BADGES_MEMBERS = ".member"

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
