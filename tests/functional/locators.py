from selenium.webdriver.common.by import By


class MainPageLocators(object):
    """A class for main page locators. All main page locators should come here"""

    # Navbar
    LOGOUT_BUTTON = (By.ID, "Logout")
    USERNAME_LOGGED_IN_OUTPUT = (By.ID, "userLoggedIn")

    # UTub Deck
    UTUB_DECK_SUBHEADER = (By.ID, "UTubDeckSubheader")
    CREATE_UTUB_BUTTON = (By.ID, "createUTubBtn")
    CREATE_UTUB_INPUT = (By.ID, "createUTub")
    SUBMIT_UTUB_INPUT = (By.ID, "submitCreateUTub")
    CANCEL_UTUB_INPUT = (By.ID, "cancelCreateUTub")
    # FIRST_UTUB_SELECTOR = (By.XPATH, "//div[@id='listUTubs']/div[@class='UTubSelector'][1]")
    FIRST_UTUB_SELECTOR = (By.XPATH, "//div[@id='listUTubs']/div[1]")
    SELECTED_UTUB_SELECTOR = (
        By.XPATH,
        "//div[@id='listUTubs']/div[@class='active'][1]",
    )
    DELETE_UTUB_BUTTON = (By.ID, "deleteUTubBtn")

    # Tag Deck
    TAG_DECK_SUBHEADER = (By.ID, "TagDeckSubheader")

    # URL Deck
    URL_DECK_SUBHEADER = (By.ID, "URLDeckSubheader")
    EDIT_UTUB_BUTTON = (By.ID, "editUTubNameBtn")
    ADD_URL_BUTTON = (By.ID, "addURLBtn")

    # UTub Description Deck
    UTUB_DESCRIPTION_DECK_SUBHEADER = (By.ID, "UTubDescriptionDeckSubheader")
    EDIT_UTUB_DESCRIPTION_BUTTON = (By.ID, "editUTubDescriptionBtn")

    # Members Deck
    MEMBER_DECK_SUBHEADER = (By.ID, "MemberDeckSubheader")
    ADD_MEMBER_BUTTON = (By.ID, "addMemberBtn")


class SplashPageLocators(object):
    """A class for main page locators. All main page locators should come here"""

    REGISTER_OPTION_BUTTON = (By.CLASS_NAME, "to-register")
    LOGIN_OPTION_BUTTON = (By.CLASS_NAME, "to-login")
    USERNAME_INPUT = (By.ID, "username")
    PASSWORD_INPUT = (By.ID, "password")
    LOGIN_BUTTON = (By.ID, "submit")
    REGISTER_FROM_LOGIN_BUTTON = (By.ID, "ToRegisterFromLogin")
