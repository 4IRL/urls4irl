import os
import threading
from time import sleep
from typing import Generator, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from playwright.sync_api import Browser, Page, sync_playwright
from redis import Redis

from backend import create_app, db
from backend.cli.mock_constants import MOCK_TEST_URL_STRINGS
from backend.config import ConfigTest, ConfigTestUI
from backend.models.email_validations import Email_Validations
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.users import Users
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from scripts import testrun_resources
from tests.functional.db_utils import add_mock_urls
from tests.functional.failure_artifacts import (
    ArtifactSettings,
    load_settings,
    recorded_context,
)
from tests.functional.playwright_utils import (
    PageBundle,
)
from tests.functional.playwright_utils import (
    add_cookie_banner_cookie as add_playwright_cookie_banner_cookie,
)
from tests.functional.third_party_stubs import stub_third_party_requests
from tests.functional.ui_test_setup import (
    clear_db,
    connect_to_browser_server,
    find_open_port,
    hide_logs_for_app,
    ping_server,
    run_app,
)
from tests.functional.urls_ui.playwright_utils import ClipboardMockHelper

# Canonical desktop viewport for Playwright desktop contexts.
DESKTOP_VIEWPORT_WIDTH_PX = 1920
DESKTOP_VIEWPORT_HEIGHT_PX = 1080

# `worker_db_uri` and `worker_redis_uri` are inherited from the root
# `tests/conftest.py`: per-run databases and leased Redis indices.


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
        # Isolate the enforcement Redis too (rate-limit / lockout counters),
        # matching integration `build_app`, so concurrent UI runs never share
        # dev DB 0.
        config.REDIS_URI = worker_redis_uri
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
def provide_port(worker_id: str, testrun_uid: str, flask_logs: bool) -> int:
    start_port = testrun_resources.port_probe_start(
        testrun_uid, testrun_resources.worker_index(worker_id)
    )
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
def playwright_instance():
    """Session-scoped Playwright process. Session scope is required — a new
    Playwright driver process per test would exhaust ports under
    `U4I_N_UI`-worker load."""
    instance = sync_playwright().start()
    yield instance
    instance.stop()


@pytest.fixture(scope="session")
def build_page_browser(
    playwright_instance, provide_port: int, parallelize_app, turn_off_headless
) -> Generator[Browser, None, None]:
    """Session-scoped browser: connects to the containerized browser-server
    in Docker mode, else launches a local chromium.
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
        browser = connect_to_browser_server(
            playwright_instance.chromium, config.TEST_PLAYWRIGHT_URI
        )
    else:
        browser = playwright_instance.chromium.launch(headless=not turn_off_headless)

    yield browser

    try:
        browser.close()
    except Exception:
        pass


@pytest.fixture(scope="session")
def failure_artifact_settings(pytestconfig: pytest.Config) -> ArtifactSettings:
    return load_settings(environ=os.environ, rootpath=pytestconfig.rootpath)


@pytest.fixture
def page_without_cookie_banner_cookie(
    build_page_browser: Browser,
    provide_port: int,
    provide_config: ConfigTest,
    runner: Tuple[Flask, FlaskCliRunner],
    debug_strings,
    request: pytest.FixtureRequest,
    worker_id: str,
    failure_artifact_settings: ArtifactSettings,
) -> Generator[PageBundle, None, None]:
    """Clears the DB and yields a fresh, auto-isolated context+page per
    test. No manual cookie/tab/viewport cleanup is needed — the context is
    closed after each test. A failing test (setup or call phase) leaves its
    trace/screenshots/logs under tmp/test-artifacts/ (`recorded_context`).
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
    try:
        with recorded_context(
            context=context,
            request=request,
            settings=failure_artifact_settings,
            worker_id=worker_id,
        ):
            context.set_default_timeout(10_000)
            context.set_default_navigation_timeout(30_000)
            stub_third_party_requests(context=context)

            page: Page = context.new_page()
            page.goto(base_url + "/")

            clear_db(runner, debug_strings)

            yield PageBundle(page=page, context=context, base_url=base_url)
    finally:
        context.close()


@pytest.fixture
def page(
    page_without_cookie_banner_cookie: PageBundle,
) -> Generator[Page, None, None]:
    """Desktop Playwright page with the cookie-banner consent cookie set.

    Reloads after installing the consent cookie so the already-rendered
    splash page drops its banner (mirrors the Selenium fixture's refresh) —
    tests start on the splash page with no banner overlay.
    """
    bundle = page_without_cookie_banner_cookie
    add_playwright_cookie_banner_cookie(
        context=bundle.context, base_url=bundle.base_url
    )
    bundle.page.reload()
    yield bundle.page


@pytest.fixture
def page_mobile_portrait_without_cookie_banner_cookie(
    build_page_browser: Browser,
    provide_port: int,
    provide_config: ConfigTest,
    runner: Tuple[Flask, FlaskCliRunner],
    debug_strings,
    request: pytest.FixtureRequest,
    worker_id: str,
    failure_artifact_settings: ArtifactSettings,
) -> Generator[PageBundle, None, None]:
    """Mobile-portrait Playwright context: Playwright-native touch/mobile
    emulation replaces the Selenium `execute_cdp_cmd` touch + coarse-pointer
    media emulation. Failure artifacts as in `page_without_cookie_banner_cookie`.
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
    try:
        with recorded_context(
            context=context,
            request=request,
            settings=failure_artifact_settings,
            worker_id=worker_id,
        ):
            context.set_default_timeout(10_000)
            context.set_default_navigation_timeout(30_000)
            stub_third_party_requests(context=context)

            page: Page = context.new_page()
            page.goto(base_url + "/")

            clear_db(runner, debug_strings)

            yield PageBundle(page=page, context=context, base_url=base_url)
    finally:
        context.close()


@pytest.fixture
def page_mobile_portrait(
    page_mobile_portrait_without_cookie_banner_cookie: PageBundle,
) -> Generator[Page, None, None]:
    """Mobile-portrait Playwright page with the cookie-banner cookie set.

    Reloads after installing the consent cookie so the already-rendered
    splash page drops its banner (mirrors the Selenium fixture's refresh).
    """
    bundle = page_mobile_portrait_without_cookie_banner_cookie
    add_playwright_cookie_banner_cookie(
        context=bundle.context, base_url=bundle.base_url
    )
    bundle.page.reload()
    yield bundle.page


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
def clipboard_mock(page: Page):
    """Pytest fixture that sets up the clipboard mock for headless testing"""
    mock_helper = ClipboardMockHelper(page)

    yield mock_helper
    mock_helper.cleanup_mock()
