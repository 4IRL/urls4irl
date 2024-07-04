class MainPageLocators:
    """A class for main page locators. All main page locators should come here"""

    # Navbar
    LOGOUT_BUTTON = "#Logout"
    USERNAME_LOGGED_IN_OUTPUT = "#userLoggedIn"

    # UTub Deck
    UTUB_DECK_SUBHEADER = "#UTubDeckSubheader"
    CREATE_UTUB_BUTTON = "#createUTubBtn"
    CREATE_UTUB_BUTTON = "#utubBtnCreate"
    CREATE_UTUB_INPUT = ".add#utubName"
    # CREATE_UTUB_INPUT = "#utubNameCreate"
    SUBMIT_UTUB_INPUT = "#utubSubmitBtnCreate"
    CANCEL_UTUB_INPUT = "#cancelCreateUTub"
    UTUB_SELECTORS = "#listUTubs"
    SELECTED_UTUB_SELECTOR = ".UTubSelector.active"
    DELETE_UTUB_BUTTON = "#deleteUTubBtn"

    # Tag Deck
    TAG_DECK_SUBHEADER = "#TagDeckSubheader"

    # URL Deck
    URL_DECK_SUBHEADER = "#URLDeckSubheader"
    EDIT_UTUB_BUTTON = "#editUTubNameBtn"
    # UPDATE_UTUB_BUTTON = "#utubNameBtnUpdate"
    ADD_URL_BUTTON = "#addURLBtn"
    # ADD_URL_BUTTON = "#addURLBtn"

    # UTub Description Deck
    UTUB_DESCRIPTION_DECK_SUBHEADER = "#UTubDescriptionDeckSubheader"
    EDIT_UTUB_DESCRIPTION_BUTTON = "#editUTubDescriptionBtn"

    # Members Deck
    MEMBER_DECK_SUBHEADER = "#MemberDeckSubheader"
    ADD_MEMBER_BUTTON = "#addMemberBtn"


class SplashPageLocators:
    """A class for main page locators. All main page locators should come here"""

    REGISTER_OPTION_BUTTON = ".to-register"
    LOGIN_OPTION_BUTTON = ".to-login"
    USERNAME_INPUT = "#username"
    PASSWORD_INPUT = "#password"
    LOGIN_BUTTON = "#submit"
    REGISTER_FROM_LOGIN_BUTTON = "#oRegisterFromLogin"
