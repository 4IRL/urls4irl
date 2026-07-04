import threading
from time import sleep
from typing import Generator, Optional, Tuple

from flask import Flask
from flask.testing import FlaskCliRunner
from playwright.sync_api import Browser, Page, sync_playwright
import pytest
from redis import Redis
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options
from sqlalchemy import create_engine, text

from backend import create_app, db
from backend.cli.mock_constants import MOCK_TEST_URL_STRINGS
from backend.config import (
    ConfigTest,
    ConfigTestUI,
    IS_DOCKER,
    POSTGRES_TEST_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    TEST_DB_URI,
    TEST_REDIS_URI,
)
from backend.models.email_validations import Email_Validations
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.users import Users
from backend.utils.db_uri_builder import build_db_uri
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.db_utils import add_mock_urls
from tests.functional.playwright_utils import (
    PageBundle,
    add_cookie_banner_cookie as add_playwright_cookie_banner_cookie,
)
from tests.functional.selenium_utils import (
    ChromeRemoteWebDriver,
    add_cookie_banner_cookie,
    wait_for_page_complete_and_dom_stable,
)
from tests.functional.ui_test_setup import (
    clear_db,
    find_open_port,
    hide_logs_for_app,
    ping_server,
    run_app,
)
from tests.functional.urls_ui.selenium_utils import ClipboardMockHelper

# Redis ships with 16 databases (indices 0-15) by default per the default redis.conf
REDIS_DEFAULT_MAX_DATABASES = 16

# Canonical desktop viewport for the shared session-scoped Chrome driver. Defined
# once here so build_driver and the per-test teardown agree on a single size,
# preventing a test that resizes the shared window from polluting later tests.
DESKTOP_VIEWPORT_WIDTH_PX = 1920
DESKTOP_VIEWPORT_HEIGHT_PX = 1080


def _get_worker_num(worker_id: str) -> Optional[int]:
    """Returns None for 'master' (non-parallel), else the integer worker number."""
    if worker_id == "master":
        return None
    return int(worker_id.replace("gw", ""))


@pytest.fixture(scope="session")
def worker_db_uri(worker_id: str) -> Generator[str, None, None]:
    """Provides a per-worker database URI, creating and dropping a worker-specific DB."""
    if worker_id == "master":
        yield TEST_DB_URI
        return

    assert POSTGRES_TEST_DB, "POSTGRES_TEST_DB must be set for parallel UI tests"
    worker_db_name = f"{POSTGRES_TEST_DB}_{worker_id}"
    db_host = "test-db" if IS_DOCKER else "localhost"

    admin_uri = build_db_uri(
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database="postgres",
        database_host=db_host,
    )
    worker_uri = build_db_uri(
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=worker_db_name,
        database_host=db_host,
    )

    def _drop_worker_db(conn) -> None:
        conn.execute(
            text(
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{worker_db_name}' AND pid <> pg_backend_pid()"
            )
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{worker_db_name}"'))

    engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        _drop_worker_db(conn)
        conn.execute(text(f'CREATE DATABASE "{worker_db_name}"'))
    engine.dispose()

    yield worker_uri

    engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        _drop_worker_db(conn)
    engine.dispose()


@pytest.fixture(scope="session")
def worker_redis_uri(worker_id: str) -> str:
    """Returns a per-worker Redis URI using a unique DB index."""
    if not TEST_REDIS_URI or TEST_REDIS_URI == "memory://":
        return TEST_REDIS_URI
    if worker_id == "master":
        return TEST_REDIS_URI
    base, db_str = TEST_REDIS_URI.rsplit("/", 1)
    base_db = int(db_str) if db_str.isdigit() else 0
    db_index = base_db + 1 + _get_worker_num(worker_id)

    probe = Redis.from_url(f"{base}/0")
    try:
        max_dbs = int(
            probe.config_get("databases").get("databases", REDIS_DEFAULT_MAX_DATABASES)
        )
    finally:
        probe.close()

    if db_index >= max_dbs:
        raise ValueError(
            f"Redis DB index {db_index} is out of range for worker '{worker_id}'. "
            f"Redis only has {max_dbs} databases (0-{max_dbs - 1}). "
            f"TEST_REDIS_URI base DB is {base_db}. "
            f"Either increase Redis 'databases' config or lower the base DB index."
        )

    return f"{base}/{db_index}"


@pytest.fixture(scope="session")
def worker_config(
    worker_db_uri: str, worker_redis_uri: str, provide_port: int
) -> ConfigTestUI:
    """Returns a ConfigTestUI instance configured for this worker's DB and Redis.

    `OAUTH_SELF_BASE_URL` must be set here, at config-construction time, rather
    than inside `run_app()` — Authlib's `OAuth` registry caches a "google"
    client the first time ANY `create_app(worker_config)` call registers it
    (see `authlib.integrations.base_client.registry.BaseOAuth.create_client`),
    and `build_app`/`provide_app`/`parallelize_app` each independently call
    `create_app(worker_config)`. Setting it on the shared config object before
    any of those fixtures run guarantees the fake OAuth provider's absolute
    base URL wins regardless of which fixture happens to resolve first.
    """
    config = ConfigTestUI()
    config.SQLALCHEMY_DATABASE_URI = worker_db_uri
    config.SQLALCHEMY_BINDS = {"test": worker_db_uri}
    if worker_redis_uri and worker_redis_uri != "memory://":
        config.SESSION_TYPE = "redis"
        config.SESSION_REDIS = Redis.from_url(worker_redis_uri)
    config.OAUTH_SELF_BASE_URL = f"http://127.0.0.1:{provide_port}"
    return config


# CLI commands
@pytest.fixture(scope="session")
def turn_off_headless(request):
    return request.config.getoption("--show_browser")


@pytest.fixture(scope="session")
def debug_strings(request):
    return request.config.getoption("--DS")


@pytest.fixture(scope="session")
def flask_logs(request):
    return request.config.getoption("--FL")


@pytest.fixture(scope="session")
def build_app(
    worker_config: ConfigTestUI,
    ignore_deprecation_warning,
) -> Generator[Tuple[Flask, ConfigTestUI], None, None]:
    app_for_test = create_app(worker_config)  # type: ignore
    assert app_for_test is not None

    hide_logs_for_app(app_for_test)
    app_for_test.logger.propagate = True

    with app_for_test.app_context():
        db.init_app(app_for_test)
        db.create_all()

    yield app_for_test, worker_config

    with app_for_test.app_context():
        db.drop_all()


@pytest.fixture(scope="session")
def provide_config(worker_config: ConfigTestUI) -> Generator[ConfigTestUI, None, None]:
    yield worker_config


@pytest.fixture(scope="session")
def provide_port(worker_id: str, flask_logs: bool) -> int:
    start_port = 10000 + (_get_worker_num(worker_id) or 0) * 1000
    open_port = find_open_port(start_port=start_port)
    if flask_logs:
        print(f"\nFound an open port: {open_port}")
    sleep(2)
    return open_port


@pytest.fixture(scope="session")
def parallelize_app(provide_port, flask_logs, worker_config: ConfigTestUI):
    """
    Starts a parallel process, runs Flask app
    """
    open_port = provide_port
    thread = threading.Thread(
        target=run_app,
        args=(
            open_port,
            flask_logs,
            worker_config,
        ),
        daemon=True,
    )
    thread.start()
    sleep(5)


@pytest.fixture(scope="session")
def provide_app(worker_config: ConfigTestUI) -> Generator[Flask, None, None]:
    app = create_app(worker_config)  # type: ignore
    assert app
    hide_logs_for_app(app)
    yield app


@pytest.fixture(scope="session")
def build_driver(
    provide_port: int, parallelize_app, turn_off_headless
) -> Generator[WebDriver, None, None]:
    """
    Given the Flask app running in parallel, this function gets the browser ready for manipulation and pings server to ensure Flask app is running in parallel.
    """
    config = ConfigTest()
    open_port = provide_port
    options = Options()
    options.add_argument("--disable-notifications")

    if not turn_off_headless:
        options.add_argument("--headless=new")

    if config.DOCKER:
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        driver = ChromeRemoteWebDriver(
            command_executor=config.TEST_SELENIUM_URI, options=options
        )
        url = UI_TEST_STRINGS.DOCKER_BASE_URL
    else:
        driver = webdriver.Chrome(options=options)
        url = UI_TEST_STRINGS.BASE_URL

    driver.set_window_size(
        width=DESKTOP_VIEWPORT_WIDTH_PX, height=DESKTOP_VIEWPORT_HEIGHT_PX
    )

    ping_server(url + str(open_port))

    yield driver

    # Teardown: Quit the browser after tests
    try:
        driver.quit()
    except Exception:
        pass


@pytest.fixture(scope="session")
def playwright_instance():
    """Session-scoped Playwright process. Session scope is required — a new
    Playwright driver process per test would exhaust ports under n=8 load."""
    instance = sync_playwright().start()
    yield instance
    instance.stop()


@pytest.fixture(scope="session")
def build_page_browser(
    playwright_instance, provide_port: int, parallelize_app, turn_off_headless
) -> Generator[Browser, None, None]:
    """Playwright twin of `build_driver`: connects to the containerized
    browser-server in Docker mode, else launches a local chromium. Forms a
    parallel, non-coupled chain — never a dependency of (or for) the
    Selenium `build_driver` fixture family.
    """
    config = ConfigTest()
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )

    ping_server(base_url + str(provide_port))

    if config.DOCKER:
        if not config.TEST_PLAYWRIGHT_URI:
            raise RuntimeError(
                "PLAYWRIGHT_WS_URL env var is not set; cannot connect to the "
                "Playwright browser server in Docker mode"
            )
        browser = playwright_instance.chromium.connect(config.TEST_PLAYWRIGHT_URI)
    else:
        browser = playwright_instance.chromium.launch(headless=not turn_off_headless)

    yield browser

    try:
        browser.close()
    except Exception:
        pass


@pytest.fixture
def page_without_cookie_banner_cookie(
    build_page_browser: Browser,
    provide_port: int,
    provide_config: ConfigTest,
    runner: Tuple[Flask, FlaskCliRunner],
    debug_strings,
) -> Generator[PageBundle, None, None]:
    """Playwright twin of `browser_without_cookie_banner_cookie`: clears the
    DB and yields a fresh, auto-isolated context+page per test. No manual
    cookie/tab/viewport cleanup is needed — the context is closed after each
    test, unlike the shared session-scoped Selenium driver.
    """
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL
        if provide_config.DOCKER
        else UI_TEST_STRINGS.BASE_URL
    ) + str(provide_port)

    context = build_page_browser.new_context(
        viewport={
            "width": DESKTOP_VIEWPORT_WIDTH_PX,
            "height": DESKTOP_VIEWPORT_HEIGHT_PX,
        }
    )
    context.set_default_timeout(10_000)
    context.set_default_navigation_timeout(30_000)

    clear_db(runner, debug_strings)

    page: Page = context.new_page()

    yield PageBundle(page=page, context=context, base_url=base_url)

    context.close()


@pytest.fixture
def page(
    page_without_cookie_banner_cookie: PageBundle,
) -> Generator[Page, None, None]:
    """Desktop Playwright page with the cookie-banner consent cookie set."""
    bundle = page_without_cookie_banner_cookie
    add_playwright_cookie_banner_cookie(
        context=bundle.context, base_url=bundle.base_url
    )
    yield bundle.page


@pytest.fixture
def page_mobile_portrait_without_cookie_banner_cookie(
    build_page_browser: Browser,
    provide_port: int,
    provide_config: ConfigTest,
    runner: Tuple[Flask, FlaskCliRunner],
    debug_strings,
) -> Generator[PageBundle, None, None]:
    """Mobile-portrait Playwright context: Playwright-native touch/mobile
    emulation replaces the Selenium `execute_cdp_cmd` touch + coarse-pointer
    media emulation.
    """
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL
        if provide_config.DOCKER
        else UI_TEST_STRINGS.BASE_URL
    ) + str(provide_port)

    context = build_page_browser.new_context(
        viewport={"width": 420, "height": 900},
        has_touch=True,
        is_mobile=True,
    )
    context.set_default_timeout(10_000)
    context.set_default_navigation_timeout(30_000)

    clear_db(runner, debug_strings)

    page: Page = context.new_page()

    yield PageBundle(page=page, context=context, base_url=base_url)

    context.close()


@pytest.fixture
def page_mobile_portrait(
    page_mobile_portrait_without_cookie_banner_cookie: PageBundle,
) -> Generator[Page, None, None]:
    """Mobile-portrait Playwright page with the cookie-banner cookie set."""
    bundle = page_mobile_portrait_without_cookie_banner_cookie
    add_playwright_cookie_banner_cookie(
        context=bundle.context, base_url=bundle.base_url
    )
    yield bundle.page


@pytest.fixture
def build_driver_mobile_portrait(
    provide_port: int, parallelize_app, turn_off_headless
) -> Generator[WebDriver, None, None]:
    """
    Given the Flask app running in parallel, this function gets the browser ready for manipulation and pings server to ensure Flask app is running in parallel.
    """
    config = ConfigTest()
    open_port = provide_port
    options = Options()
    options.add_argument("--disable-notifications")

    if not turn_off_headless:
        options.add_argument("--headless=new")

    if config.DOCKER:
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        driver = ChromeRemoteWebDriver(
            command_executor=config.TEST_SELENIUM_URI, options=options
        )
        url = UI_TEST_STRINGS.DOCKER_BASE_URL
    else:
        driver = webdriver.Chrome(options=options)
        url = UI_TEST_STRINGS.BASE_URL

    driver.set_window_size(width=420, height=900)

    # Emulate a coarse-pointer touch device. Touch emulation is required for
    # `(any-pointer: coarse)` / `(pointer: coarse)` to match — without it,
    # `Emulation.setEmulatedMedia` silently no-ops for the pointer feature.
    driver.execute_cdp_cmd(
        "Emulation.setTouchEmulationEnabled",
        {"enabled": True, "maxTouchPoints": 5},
    )

    driver.execute_cdp_cmd(
        "Emulation.setEmulatedMedia",
        {
            "features": [
                {"name": "any-pointer", "value": "coarse"},
                {"name": "pointer", "value": "coarse"},
                {"name": "hover", "value": "none"},
                {"name": "any-hover", "value": "none"},
            ],
        },
    )

    ping_server(url + str(open_port))

    yield driver

    # Teardown: Quit the browser after tests
    try:
        driver.quit()
    except Exception:
        pass


@pytest.fixture
def browser_without_cookie_banner_cookie(
    provide_port: int,
    provide_config: ConfigTest,
    build_driver: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    debug_strings,
):
    """
    This fixture clears cookies, accesses the U4I site and supplies driver for use by the test. A new instance is invoked per test.
    """
    open_port = provide_port
    url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL
        if provide_config.DOCKER
        else UI_TEST_STRINGS.BASE_URL
    )
    driver = build_driver

    driver.get(url + str(open_port) + "/")
    wait_for_page_complete_and_dom_stable(driver)

    init_handle = driver.current_window_handle

    clear_db(runner, debug_strings)

    # Return the driver object to be used in the test functions
    yield driver

    # Clean up any additional tabs that may have been opened during tests
    for handle in driver.window_handles:
        if handle != init_handle:
            driver.switch_to.window(handle)
            driver.close()

    # Return to the initial tab, clear cookies while still on app domain,
    # then navigate to about:blank to release renderer state
    driver.switch_to.window(init_handle)
    driver.delete_all_cookies()
    driver.get("about:blank")

    # Restore the canonical desktop window size so a test that resized the
    # shared session-scoped driver cannot pollute later desktop tests.
    driver.set_window_size(
        width=DESKTOP_VIEWPORT_WIDTH_PX, height=DESKTOP_VIEWPORT_HEIGHT_PX
    )


@pytest.fixture
def browser(
    browser_without_cookie_banner_cookie: WebDriver,
):
    """
    This fixture adds the consent cookie before all tests
    """
    browser = browser_without_cookie_banner_cookie
    add_cookie_banner_cookie(browser)

    yield browser


@pytest.fixture
def browser_mobile_portrait_without_cookie_banner_cookie(
    provide_port: int,
    provide_config: ConfigTest,
    build_driver_mobile_portrait: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    debug_strings,
):
    """
    This fixture clears cookies, accesses the U4I site and supplies driver for use by the test. A new instance is invoked per test.
    """
    open_port = provide_port
    url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL
        if provide_config.DOCKER
        else UI_TEST_STRINGS.BASE_URL
    )
    driver = build_driver_mobile_portrait

    driver.get(url + str(open_port) + "/")
    driver.delete_all_cookies()
    driver.get(url + str(open_port) + "/")
    wait_for_page_complete_and_dom_stable(driver)

    init_handle = driver.current_window_handle

    clear_db(runner, debug_strings)

    # Return the driver object to be used in the test functions
    yield driver

    # Clean up any additional tabs that may have been opened during tests
    for handle in driver.window_handles:
        if handle != init_handle:
            driver.switch_to.window(handle)
            driver.close()

    # Return to the initial tab, clear cookies while still on app domain,
    # then navigate to about:blank to release renderer state
    driver.switch_to.window(init_handle)
    driver.delete_all_cookies()
    driver.get("about:blank")


@pytest.fixture
def browser_mobile_portrait(
    browser_mobile_portrait_without_cookie_banner_cookie: WebDriver,
):
    """
    This fixture clears cookies, accesses the U4I site and supplies driver for use by the test. A new instance is invoked per test.
    """
    browser = browser_mobile_portrait_without_cookie_banner_cookie
    add_cookie_banner_cookie(browser)

    yield browser


@pytest.fixture
def create_test_users(runner, debug_strings):
    """
    Assumes nothing created. Creates users
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "users"])

    if debug_strings:
        print("\nusers created")


@pytest.fixture
def create_user_unconfirmed_email(
    runner: Tuple[Flask, FlaskCliRunner], debug_strings
) -> str:
    """
    Assumes nothing created. Creates an a user with an unconfirmed email

    Returns:
        (str): URL to validate the User's email
    """
    app, _ = runner

    with app.app_context():
        new_user = Users(
            username=UI_TEST_STRINGS.TEST_USERNAME_1,
            email=UI_TEST_STRINGS.TEST_PASSWORD_1,
            plaintext_password=UI_TEST_STRINGS.TEST_PASSWORD_1,
        )

        new_email_validation = Email_Validations(
            validation_token=new_user.get_email_validation_token()
        )
        new_email_validation.is_validated = False
        new_user.email_confirm = new_email_validation

        db.session.add(new_user)
        db.session.commit()
        return f"/validate/{new_email_validation.validation_token}"


@pytest.fixture
def create_user_resetting_password(
    runner: Tuple[Flask, FlaskCliRunner], debug_strings
) -> str:
    """
    Assumes nothing created. Creates an a user with an unconfirmed email

    Returns:
        (str): URL to validate the User's email
    """
    app, _ = runner

    with app.app_context():
        new_user = Users(
            username=UI_TEST_STRINGS.TEST_USERNAME_1,
            email=UI_TEST_STRINGS.TEST_PASSWORD_1,
            plaintext_password=UI_TEST_STRINGS.TEST_PASSWORD_1,
        )

        new_user.email_validated = True

        new_password_reset = Forgot_Passwords(
            reset_token=new_user.get_password_reset_token()
        )

        new_user.forgot_password = new_password_reset
        db.session.add(new_user)
        db.session.commit()
        return f"/reset-password/{new_password_reset.reset_token}"


@pytest.fixture
def create_test_utubs(runner: Tuple[Flask, FlaskCliRunner], debug_strings):
    """
    Assumes users created. Creates sample UTubs, each user owns one.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "utubs"])

    if debug_strings:
        print("\nusers and utubs created")


@pytest.fixture
def create_test_utubmembers(runner, debug_strings):
    """
    Assumes users created, and each own one UTub. Creates all users as members of each UTub.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "utubmembers"])

    if debug_strings:
        print("\nusers, utubs, and members created")


@pytest.fixture
def create_test_urls(runner, debug_strings):
    """
    Assumes users created, each own one UTub, and all users are members of each UTub. Creates URLs in each UTub.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "urls"])

    if debug_strings:
        print("\nusers, utubs, members, and urls created")


@pytest.fixture
def create_test_access_urls(runner, debug_strings):
    """
    Assumes users created, each own one UTub, and all users are members of each UTub. Creates URLs in each UTub.
    """
    _, cli_runner = runner
    add_mock_urls(cli_runner, MOCK_TEST_URL_STRINGS)

    if debug_strings:
        print("\nusers, utubs, members, and acces urls created")


@pytest.fixture
def create_test_tags(runner, debug_strings):
    """
    Assumes users created, each own one UTub, all users are members of each UTub, and URLs added to each UTub. Creates all tags on all URLs.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "tags"])

    if debug_strings:
        print("\nusers, utubs, members, urls, and tags created")


@pytest.fixture(scope="function")
def clipboard_mock(browser):
    """Pytest fixture that sets up clipboard mock for headless testing"""
    mock_helper = ClipboardMockHelper(browser)

    yield mock_helper
    mock_helper.cleanup_mock()
