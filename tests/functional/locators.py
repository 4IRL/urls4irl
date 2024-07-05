class MainPageLocators:
    """A class for main page locators. All main page locators should come here"""

    # Navbar
    BUTTON_LOGOUT = "#Logout"
    USERNAME_LOGGED_IN_OUTPUT = "#userLoggedIn"

    # UTub Deck
    BUTTON_UTUB_CREATE = "#createUTubBtn"
    # CREATE_UTUB_BUTTON = "#utubBtnCreate"
    BUTTON_UTUB_DELETE = "#deleteUTubBtn"
    INPUT_UTUB_NAME_CREATE = ".add#utubName"
    # CREATE_UTUB_INPUT = "#utubNameCreate"
    INPUT_UTUB_DESCRIPTION_CREATE = ".add#utubDescription"
    # CREATE_UTUB_INPUT = "#utubDescriptionCreate"
    BUTTON_UTUB_SUBMIT_CREATE = "#submitCreateUTub"
    # BUTTON_UTUB_SUBMIT_CREATE = "#utubSubmitBtnCreate"
    BUTTON_UTUB_CANCEL = "#cancelCreateUTub"
    # BUTTON_UTUB_CANCEL = "#utubCancelBtnCreate"

    SELECTORS_UTUB = "#listUTubs"
    SUBHEADER_UTUB = "#UTubDeckSubheader"
    SELECTOR_SELECTED_UTUB = ".UTubSelector.active"

    # Tag Deck
    SUBHEADER_TAG_DECK = "#TagDeckSubheader"

    # URL Deck
    SUBHEADER_URL_DECK = "#URLDeckSubheader"
    BUTTON_UTUB_UPDATE = "#editUTubNameBtn"
    # BUTTON_UTUB_UPDATE = "#utubNameBtnUpdate"
    BUTTON_URL_CREATE = "#addURLBtn"
    # BUTTON_URL_CREATE = "#urlBtnCreate"
    SUBHEADER_UTUB_DESCRIPTION = "#UTubDescriptionDeckSubheader"
    BUTTON_UTUB_DESCRIPTION_UPDATE = "#editUTubDescriptionBtn"

    # Members Deck
    SUBHEADER_MEMBER_DECK = "#MemberDeckSubheader"
    BUTTON_MEMBER_CREATE = "#addMemberBtn"
    # BUTTON_MEMBER_CREATE = "#memberBtnCreate"
    BUTTON_UTUB_LEAVE = "#leaveUTubBtn"

    # Modal
    HEADER_MODAL = "#confirmModalTitle"
    BODY_MODAL = "#confirmModalBody"
    BUTTON_MODAL_DISMISS = "#modalDismiss"
    BUTTON_MODAL_REDIRECT = "#modalRedirect"
    BUTTON_MODAL_SUBMIT = "#modalSubmit"


class SplashPageLocators:
    """A class for main page locators. All main page locators should come here"""

    REGISTER_OPTION_BUTTON = ".to-register"
    LOGIN_OPTION_BUTTON = ".to-login"
    USERNAME_INPUT = "#username"
    PASSWORD_INPUT = "#password"
    LOGIN_BUTTON = "#submit"
    REGISTER_FROM_LOGIN_BUTTON = "#oRegisterFromLogin"
