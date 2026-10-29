import json
import re
from pathlib import Path

import pytest

from backend.config import ConfigTest
from backend.extensions.url_validation.constants import (
    AUTHORITY_URL_SCHEMES,
    CORE_SCHEMES,
    DEV_URLS,
    OTHER_VALID_SCHEMES,
    TRACKING_QUERY_PARAM_PREFIXES,
    TRACKING_QUERY_PARAMS,
    WEB_SCHEMES_FOR_TRACKING_STRIP,
)
from backend.metrics.dimension_models import get_all_dimension_keys
from backend.metrics.events import DeviceType
from backend.metrics.flow_limits import FLOW_LIMITS_FOR_FRONTEND
from backend.utils.constants import (
    generate_constants_js,
    generate_strings_js,
    provide_config_for_constants,
)
from backend.utils.strings import url_strs, utub_strs
from backend.utils.strings.admin_metrics_strs import ADMIN_METRICS_STRINGS
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.json_strs import NOT_AUTHORIZED
from backend.utils.strings.trash_strs import TRASH_UI
from tests.utils_for_test import create_secondary_app

pytestmark = pytest.mark.unit

FLOW_LIMIT_KEYS_JSON = (
    Path(__file__).resolve().parents[2] / "backend" / "metrics" / "flow_limit_keys.json"
)


def _read_flow_limit_keys() -> dict[str, int]:
    return json.loads(FLOW_LIMIT_KEYS_JSON.read_text(encoding="utf-8"))


def test_flow_limit_keys_json_matches_module():
    """The shared limits JSON equals FLOW_LIMITS_FOR_FRONTEND (keys and values) and is key-sorted."""
    shared = _read_flow_limit_keys()
    assert shared == FLOW_LIMITS_FOR_FRONTEND
    assert list(shared) == sorted(shared)


def test_generate_constants_js_includes_flow_limits():
    constants = generate_constants_js()
    for key, value in _read_flow_limit_keys().items():
        assert constants[key] == value


def test_provide_config_for_constants_carries_flow_limits():
    app = create_secondary_app(ConfigTest)
    with app.test_request_context():
        constants = provide_config_for_constants(anonymous=True)["CONFIG"]["constants"]
    for key, value in _read_flow_limit_keys().items():
        assert constants[key] == value
    assert constants["METRIC_FLOWS_MAX_STEPS"] == 8


def test_metrics_config_envs_exist():
    """Every metrics-related env-name constant is registered on CONFIG_ENVS."""
    expected_metrics_keys = (
        "METRICS_ENABLED",
        "METRICS_FLUSH_INTERVAL_SECONDS",
        "METRICS_BUCKET_SECONDS",
        "METRICS_REDIS_URI",
        "METRICS_BATCH_NONCE_TTL_SECONDS",
    )
    for metrics_key in expected_metrics_keys:
        assert hasattr(CONFIG_ENVS, metrics_key), (
            f"CONFIG_ENVS is missing metrics key: {metrics_key}"
        )
        assert getattr(CONFIG_ENVS, metrics_key) == metrics_key


def test_generate_constants_js_includes_dimension_keys():
    constants = generate_constants_js()
    assert constants["DIMENSION_KEYS"] == list(get_all_dimension_keys())


def test_generate_constants_js_includes_tracking_blocklist():
    """The client blocklist mirrors the server's, so a blocklist edit cannot desync it."""
    constants = generate_constants_js()
    assert set(constants["TRACKING_QUERY_PARAMS"]) == TRACKING_QUERY_PARAMS
    assert constants["TRACKING_QUERY_PARAMS"] == sorted(TRACKING_QUERY_PARAMS)
    assert constants["TRACKING_QUERY_PARAM_PREFIXES"] == list(
        TRACKING_QUERY_PARAM_PREFIXES
    )
    assert set(constants["TRACKING_STRIP_SCHEMES"]) == WEB_SCHEMES_FOR_TRACKING_STRIP


def test_generate_constants_js_includes_url_scheme_whitelist():
    """The scheme selector's options are the backend whitelist, deterministically ordered."""
    constants = generate_constants_js()
    whitelist = CORE_SCHEMES | OTHER_VALID_SCHEMES
    url_schemes = constants["URL_SCHEMES"]

    assert isinstance(url_schemes, list)
    assert all(isinstance(scheme, str) for scheme in url_schemes)
    assert len(url_schemes) == len(whitelist)
    assert set(url_schemes) == whitelist
    assert len(set(url_schemes)) == len(url_schemes)
    assert url_schemes[:2] == ["https", "http"]
    assert constants["URL_DEFAULT_SCHEME"] == "https"


def test_generate_constants_js_url_scheme_order_matches_contract():
    """
    GIVEN the backend scheme whitelist (core and other valid schemes)
    WHEN generate_constants_js() builds URL_SCHEMES
    THEN https and http come first, then the remaining core schemes, then the
        other valid schemes, each group alphabetical
    """
    expected_order = [
        "https",
        "http",
        *sorted(CORE_SCHEMES - {"https", "http"}),
        *sorted(OTHER_VALID_SCHEMES),
    ]

    assert generate_constants_js()["URL_SCHEMES"] == expected_order


def _read_test_setup_list(key: str) -> list[str]:
    """Return the string entries of a `key: [...]` list in the vitest APP_CONFIG mock."""
    test_setup = Path(__file__).resolve().parents[2] / "frontend" / "test-setup.ts"
    if not test_setup.is_file():
        # The local `web` container mounts only frontend/types, not the TS sources;
        # CI and host runs check out the whole tree, so the guard still runs there.
        pytest.skip("frontend/test-setup.ts is not available in this environment")
    source = test_setup.read_text(encoding="utf-8")
    list_match = re.search(rf"\b{key}:\s*\[(.*?)\]", source, re.DOTALL)
    assert list_match, f"frontend/test-setup.ts has no `{key}: [...]` list"
    return re.findall(r'"([^"]+)"', list_match.group(1))


def test_frontend_test_mock_scheme_lists_match_backend():
    """
    GIVEN the hand-maintained URL scheme lists in frontend/test-setup.ts
    WHEN they are compared with the backend constants
    THEN each mock list is a subset of its backend counterpart and no mock
        opaque scheme is an authority scheme on the backend
    """
    whitelist = CORE_SCHEMES | OTHER_VALID_SCHEMES
    mock_schemes = _read_test_setup_list("URL_SCHEMES")
    mock_authority = _read_test_setup_list("URL_AUTHORITY_SCHEMES")
    mock_dev_hosts = _read_test_setup_list("URL_DEV_HOSTS")

    drifted_schemes = set(mock_schemes) - whitelist
    drifted_authority = set(mock_authority) - AUTHORITY_URL_SCHEMES
    drifted_dev_hosts = set(mock_dev_hosts) - set(DEV_URLS)
    reclassified_opaque = (set(mock_schemes) - set(mock_authority)) & (
        AUTHORITY_URL_SCHEMES
    )

    assert not drifted_schemes, (
        f"test-setup.ts URL_SCHEMES drifted from the backend whitelist: {sorted(drifted_schemes)}"
    )
    assert not drifted_authority, (
        f"test-setup.ts URL_AUTHORITY_SCHEMES drifted from the backend: {sorted(drifted_authority)}"
    )
    assert not drifted_dev_hosts, (
        f"test-setup.ts URL_DEV_HOSTS drifted from the backend: {sorted(drifted_dev_hosts)}"
    )
    assert not reclassified_opaque, (
        f"test-setup.ts treats these backend authority schemes as opaque: {sorted(reclassified_opaque)}"
    )


def test_generate_constants_js_includes_url_authority_schemes():
    constants = generate_constants_js()
    whitelist = CORE_SCHEMES | OTHER_VALID_SCHEMES
    assert set(constants["URL_AUTHORITY_SCHEMES"]) == AUTHORITY_URL_SCHEMES
    assert set(constants["URL_AUTHORITY_SCHEMES"]) <= whitelist


def test_generate_constants_js_includes_url_dev_hosts():
    constants = generate_constants_js()
    assert constants["URL_DEV_HOSTS"] == list(DEV_URLS)


def test_generate_constants_js_url_scheme_hints_shape():
    constants = generate_constants_js()
    whitelist = CORE_SCHEMES | OTHER_VALID_SCHEMES
    hints = constants["URL_SCHEME_HINTS"]

    assert isinstance(hints, dict)
    assert hints
    assert set(hints) <= whitelist
    assert all(isinstance(hint, str) and hint for hint in hints.values())


def test_generate_strings_js_includes_url_scheme_selector_strings():
    """Every selector label is read by TS (the selector DOM is built in JS), so all are bridged."""
    strings = generate_strings_js()
    expected_keys = (
        "URL_SCHEME_TOGGLE_LABEL",
        "URL_SCHEME_FILTER_LABEL",
        "URL_SCHEME_NO_MATCHES",
        "URL_SCHEME_MATCH_ONE",
        "URL_SCHEME_MATCH_MANY",
        "URL_SCHEME_SET_ANNOUNCE",
        "URL_SCHEME_HELPER_WILL_SAVE_AS",
        "URL_SCHEME_HELPER_DEFAULT",
        "URL_SCHEME_HELPER_TYPE_HINT",
    )
    for key in expected_keys:
        assert key in strings, f"generate_strings_js() is missing {key}"
        assert strings[key]

    assert "{count}" in strings["URL_SCHEME_MATCH_MANY"]
    assert "{scheme}" in strings["URL_SCHEME_SET_ANNOUNCE"]


METRIC_FLOW_BRIDGED_KEYS = (
    "METRICS_FLOWS_COUNT",
    "METRICS_FLOWS_COUNT_BUILTIN_ONLY",
    "METRICS_FLOWS_COUNT_LOADING",
    "METRICS_FLOWS_ZERO_CUSTOM_HINT",
    "METRICS_FLOW_BADGE_BUILTIN",
    "METRICS_FLOW_BADGE_CUSTOM",
    "METRICS_FLOW_CUSTOM_SUFFIX",
    "METRICS_FLOW_DELETE_LABEL",
    "METRICS_FLOW_DELETE_PROMPT",
    "METRICS_FLOW_DELETE_CONFIRM",
    "METRICS_FLOW_DELETE_CANCEL",
    "METRICS_FLOW_DELETING",
    "METRICS_FLOW_DELETED",
    "METRICS_FLOW_ALREADY_DELETED",
    "METRICS_FLOW_DELETE_FAILED",
    "METRICS_FLOW_RATE_LIMITED",
    "METRICS_FLOW_NEEDS_ATTENTION",
    "METRICS_FLOW_NEEDS_ATTENTION_STEP",
    "METRICS_FLOW_NEEDS_ATTENTION_HELP",
    "METRICS_FLOW_LOADING_LABEL",
    "METRICS_FLOW_LOAD_FAILED",
    "METRICS_FLOW_RETRY",
    "METRICS_FLOWS_LIST_FAILED",
    "METRICS_FLOWS_LIST_RETRYING",
    "METRICS_FLOW_DELETE_LOCKED",
)


def test_generate_strings_js_includes_metric_flow_strings():
    """Every METRICS_FLOW* key the Flows grid TS reads is bridged to the frontend."""
    strings = generate_strings_js()
    for key in METRIC_FLOW_BRIDGED_KEYS:
        assert key in strings, f"generate_strings_js() is missing {key}"
        assert strings[key] == getattr(ADMIN_METRICS_STRINGS, key)

    # The heading is rendered by Jinja only, so it has no TS bridge entry.
    assert "METRICS_FLOWS_HEADING" not in strings
    assert "{builtin}" in strings["METRICS_FLOWS_COUNT"]
    assert "{name}" in strings["METRICS_FLOW_DELETE_PROMPT"]


def test_generate_strings_js_includes_trash_ui_strings():
    """Every TRASH_UI constant is read by TS, so each is bridged with a TRASH_ prefix."""
    strings = generate_strings_js()
    for name, value in vars(TRASH_UI).items():
        if name.startswith("_") or not isinstance(value, str):
            continue
        key = name if name.startswith("TRASH_") else f"TRASH_{name}"
        assert key in strings, f"generate_strings_js() is missing {key}"
        assert strings[key] == value

    assert "{n}" in strings["TRASH_DAYS_LEFT"]
    assert "{utub}" in strings["TRASH_FROM_UTUB"]
    assert strings["TRASH_VIEW"] == "trash"
    assert strings["TRASH_ORIGIN_UNAVAILABLE"] == TRASH_UI.ORIGIN_UNAVAILABLE

    for plural_key in (
        "TRASH_EMPTIED",
        "TRASH_EMPTY_SKIPPED_LOCKED",
        "TRASH_CONFIRM_PURGE_UTUB_BODY",
        "TRASH_CONFIRM_EMPTY_URLS_BODY",
        "TRASH_CONFIRM_EMPTY_UTUBS_BODY",
    ):
        assert "{n}" in strings[plural_key]
        assert "{n}" not in strings[f"{plural_key}_ONE"]
        assert "1" in strings[f"{plural_key}_ONE"]


def test_generate_strings_js_includes_tag_drop_strings():
    """The drop hints and outcome banners are read by TS, so each is bridged."""
    strings = generate_strings_js()
    for key in (
        "TAG_DROP_HINT_ADD",
        "TAG_DROP_HINT_HAS",
        "TAG_DROP_ADDED",
        "TAG_DROP_NOOP",
        "TAG_DROP_FAILED",
    ):
        assert key in strings, f"generate_strings_js() is missing {key}"
        assert strings[key]

    assert "{tag}" in strings["TAG_DROP_ADDED"]
    assert "{title}" in strings["TAG_DROP_ADDED"]
    assert "{tag}" in strings["TAG_DROP_NOOP"]
    assert "{title}" in strings["TAG_DROP_NOOP"]


def test_generate_strings_js_includes_mobile_panel_announcements():
    """Each mobile panel's screen-reader announcement is bridged unchanged."""
    strings = generate_strings_js()
    expected = {
        "MOBILE_PANEL_ANNOUNCEMENT_UTUBS": utub_strs.MOBILE_PANEL_ANNOUNCEMENT_UTUBS,
        "MOBILE_PANEL_ANNOUNCEMENT_URLS": utub_strs.MOBILE_PANEL_ANNOUNCEMENT_URLS,
        "MOBILE_PANEL_ANNOUNCEMENT_MEMBERS": utub_strs.MOBILE_PANEL_ANNOUNCEMENT_MEMBERS,
        "MOBILE_PANEL_ANNOUNCEMENT_TRASH": utub_strs.MOBILE_PANEL_ANNOUNCEMENT_TRASH,
    }
    for key, value in expected.items():
        assert strings[key] == value
    assert strings["MOBILE_PANEL_ANNOUNCEMENT_TRASH"] == "Now showing Trash"


def test_generate_strings_js_includes_panel_settings_strings():
    """The panel settings shell writes these from TS, so each is bridged unchanged."""
    strings = generate_strings_js()
    expected = {
        "NOT_AUTHORIZED": NOT_AUTHORIZED,
        "PANEL_SETTINGS_SAVING": utub_strs.PANEL_SETTINGS_SAVING,
        "PANEL_SETTINGS_SAVED": utub_strs.PANEL_SETTINGS_SAVED,
        "PANEL_SETTINGS_REVERTED": utub_strs.PANEL_SETTINGS_REVERTED,
        "PANEL_SETTINGS_SAVE_FAILED": utub_strs.PANEL_SETTINGS_SAVE_FAILED,
        "PANEL_SETTINGS_CLOSED": utub_strs.PANEL_SETTINGS_CLOSED,
        "PANEL_SETTINGS_UTUB_LOCKED": utub_strs.PANEL_SETTINGS_UTUB_LOCKED,
        "PANEL_SETTINGS_MANAGERS_ONLY": utub_strs.PANEL_SETTINGS_MANAGERS_ONLY,
        "PANEL_SETTINGS_SCOPE_UTUB": utub_strs.PANEL_SETTINGS_SCOPE_UTUB,
        "PANEL_SETTINGS_SCOPE_USER": utub_strs.PANEL_SETTINGS_SCOPE_USER,
        "PANEL_SETTINGS_EMPTY": utub_strs.PANEL_SETTINGS_EMPTY,
        "URLS_SETTINGS_SECTION_TITLE": utub_strs.URLS_SETTINGS_SECTION_TITLE,
        "URLS_SETTINGS_DEFAULT_SCHEME_LABEL": utub_strs.URLS_SETTINGS_DEFAULT_SCHEME_LABEL,
        "URLS_SETTINGS_DEFAULT_SCHEME_DESC": utub_strs.URLS_SETTINGS_DEFAULT_SCHEME_DESC,
        "URLS_SETTINGS_HIDE_LABEL": utub_strs.URLS_SETTINGS_HIDE_LABEL,
        "URLS_SETTINGS_HIDE_DESC": utub_strs.URLS_SETTINGS_HIDE_DESC,
        "URLS_SETTINGS_HIDE_REQUIRES_HTTPS": utub_strs.URLS_SETTINGS_HIDE_REQUIRES_HTTPS,
        "URLS_SETTINGS_SELECTOR_RESTORED": utub_strs.URLS_SETTINGS_SELECTOR_RESTORED,
        "URLS_SETTINGS_ALLOW_SHORT_LINKS_LABEL": utub_strs.URLS_SETTINGS_ALLOW_SHORT_LINKS_LABEL,
        "URLS_SETTINGS_ALLOW_SHORT_LINKS_DESC": utub_strs.URLS_SETTINGS_ALLOW_SHORT_LINKS_DESC,
        "URLS_SETTINGS_SHORT_LINKS_OFF_NOTICE": utub_strs.URLS_SETTINGS_SHORT_LINKS_OFF_NOTICE,
        "URLS_SETTINGS_SHORT_LINKS_ON_NOTICE": utub_strs.URLS_SETTINGS_SHORT_LINKS_ON_NOTICE,
        "URLS_PERSONAL_SETTINGS_SECTION_TITLE": utub_strs.URLS_PERSONAL_SETTINGS_SECTION_TITLE,
        "URLS_PERSONAL_SETTINGS_SORT_LABEL": utub_strs.URLS_PERSONAL_SETTINGS_SORT_LABEL,
        "URLS_PERSONAL_SETTINGS_VIEW_LABEL": utub_strs.URLS_PERSONAL_SETTINGS_VIEW_LABEL,
        "URLS_PERSONAL_SETTINGS_DENSITY_LABEL": utub_strs.URLS_PERSONAL_SETTINGS_DENSITY_LABEL,
        "URLS_PERSONAL_SETTINGS_DENSITY_DESC": utub_strs.URLS_PERSONAL_SETTINGS_DENSITY_DESC,
        "URLS_PERSONAL_SETTINGS_DEFAULT_OPTION_PREFIX": utub_strs.URLS_PERSONAL_SETTINGS_DEFAULT_OPTION_PREFIX,
        "URLS_PERSONAL_SETTINGS_SORT_OPTION_NEWEST": utub_strs.URLS_PERSONAL_SETTINGS_SORT_OPTION_NEWEST,
        "URLS_PERSONAL_SETTINGS_SORT_OPTION_OLDEST": utub_strs.URLS_PERSONAL_SETTINGS_SORT_OPTION_OLDEST,
        "URLS_PERSONAL_SETTINGS_SORT_OPTION_TITLE_AZ": utub_strs.URLS_PERSONAL_SETTINGS_SORT_OPTION_TITLE_AZ,
        "URLS_PERSONAL_SETTINGS_VIEW_OPTION_LIST": utub_strs.URLS_PERSONAL_SETTINGS_VIEW_OPTION_LIST,
        "URLS_PERSONAL_SETTINGS_VIEW_OPTION_TITLE_LINE": utub_strs.URLS_PERSONAL_SETTINGS_VIEW_OPTION_TITLE_LINE,
        "URLS_PERSONAL_SETTINGS_VIEW_OPTION_URL_LINE": utub_strs.URLS_PERSONAL_SETTINGS_VIEW_OPTION_URL_LINE,
        "URLS_PERSONAL_SETTINGS_VIEW_OPTION_CARDS": utub_strs.URLS_PERSONAL_SETTINGS_VIEW_OPTION_CARDS,
        "URLS_PERSONAL_SETTINGS_VIEW_OPTION_CARDS_SMALL_SCREEN": utub_strs.URLS_PERSONAL_SETTINGS_VIEW_OPTION_CARDS_SMALL_SCREEN,
        "URLS_PERSONAL_SETTINGS_DENSITY_VIEW_HINT": utub_strs.URLS_PERSONAL_SETTINGS_DENSITY_VIEW_HINT,
        "URLS_PERSONAL_SETTINGS_DENSITY_OPTION_COMFORTABLE": utub_strs.URLS_PERSONAL_SETTINGS_DENSITY_OPTION_COMFORTABLE,
        "URLS_PERSONAL_SETTINGS_DENSITY_OPTION_COMPACT": utub_strs.URLS_PERSONAL_SETTINGS_DENSITY_OPTION_COMPACT,
        "URLS_PERSONAL_SETTINGS_HIDE_COPY_LABEL": utub_strs.URLS_PERSONAL_SETTINGS_HIDE_COPY_LABEL,
        "URLS_PERSONAL_SETTINGS_HIDE_COPY_DESC": utub_strs.URLS_PERSONAL_SETTINGS_HIDE_COPY_DESC,
        "URLS_PERSONAL_SETTINGS_HIDE_SHORT_LINK_LABEL": utub_strs.URLS_PERSONAL_SETTINGS_HIDE_SHORT_LINK_LABEL,
        "URLS_PERSONAL_SETTINGS_HIDE_SHORT_LINK_DESC": utub_strs.URLS_PERSONAL_SETTINGS_HIDE_SHORT_LINK_DESC,
        "URLS_PERSONAL_SETTINGS_HIDE_DATE_LABEL": utub_strs.URLS_PERSONAL_SETTINGS_HIDE_DATE_LABEL,
        "URLS_PERSONAL_SETTINGS_HIDE_DATE_DESC": utub_strs.URLS_PERSONAL_SETTINGS_HIDE_DATE_DESC,
        "URLS_PERSONAL_SETTINGS_DISABLE_SWIPE_LABEL": utub_strs.URLS_PERSONAL_SETTINGS_DISABLE_SWIPE_LABEL,
        "URLS_PERSONAL_SETTINGS_DISABLE_SWIPE_DESC": utub_strs.URLS_PERSONAL_SETTINGS_DISABLE_SWIPE_DESC,
        "URLS_PERSONAL_SETTINGS_SHORT_LINKS_OFF_HINT": utub_strs.URLS_PERSONAL_SETTINGS_SHORT_LINKS_OFF_HINT,
        "URLS_PERSONAL_SETTINGS_COPY_HIDDEN_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_COPY_HIDDEN_NOTICE,
        "URLS_PERSONAL_SETTINGS_COPY_SHOWN_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_COPY_SHOWN_NOTICE,
        "URLS_PERSONAL_SETTINGS_SHORT_LINK_HIDDEN_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_SHORT_LINK_HIDDEN_NOTICE,
        "URLS_PERSONAL_SETTINGS_SHORT_LINK_SHOWN_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_SHORT_LINK_SHOWN_NOTICE,
        "URLS_PERSONAL_SETTINGS_DATE_HIDDEN_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_DATE_HIDDEN_NOTICE,
        "URLS_PERSONAL_SETTINGS_DATE_SHOWN_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_DATE_SHOWN_NOTICE,
        "URLS_PERSONAL_SETTINGS_SWIPE_OFF_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_SWIPE_OFF_NOTICE,
        "URLS_PERSONAL_SETTINGS_SWIPE_ON_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_SWIPE_ON_NOTICE,
        "URLS_PERSONAL_SETTINGS_SORT_ORDER_PENDING_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_SORT_ORDER_PENDING_NOTICE,
        "URLS_PERSONAL_SETTINGS_SORT_SET_NOTICE_PREFIX": utub_strs.URLS_PERSONAL_SETTINGS_SORT_SET_NOTICE_PREFIX,
        "URLS_PERSONAL_SETTINGS_SORT_DEFAULT_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_SORT_DEFAULT_NOTICE,
        "URLS_PERSONAL_SETTINGS_VIEW_SET_NOTICE_PREFIX": utub_strs.URLS_PERSONAL_SETTINGS_VIEW_SET_NOTICE_PREFIX,
        "URLS_PERSONAL_SETTINGS_VIEW_DEFAULT_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_VIEW_DEFAULT_NOTICE,
        "URLS_PERSONAL_SETTINGS_DENSITY_SET_NOTICE_PREFIX": utub_strs.URLS_PERSONAL_SETTINGS_DENSITY_SET_NOTICE_PREFIX,
        "URLS_PERSONAL_SETTINGS_DENSITY_DEFAULT_NOTICE": utub_strs.URLS_PERSONAL_SETTINGS_DENSITY_DEFAULT_NOTICE,
    }
    for key, value in expected.items():
        assert key in strings, f"generate_strings_js() is missing {key}"
        assert strings[key] == value
        assert value


def test_generate_strings_js_includes_delete_undo_strings():
    """The delete Undo toast is built in TS, so each of its strings is bridged unchanged."""
    strings = generate_strings_js()
    expected = {
        "URL_MOVED_TO_TRASH": url_strs.URL_MOVED_TO_TRASH,
        "URL_MOVED_TO_TRASH_ONE": url_strs.URL_MOVED_TO_TRASH_ONE,
        "URL_DELETE_HIDDEN_DETAIL": url_strs.URL_DELETE_HIDDEN_DETAIL,
        "URL_DELETE_HIDDEN_DETAIL_ONE": url_strs.URL_DELETE_HIDDEN_DETAIL_ONE,
        "URL_UNDO_RESTORED": url_strs.URL_UNDO_RESTORED,
        "URL_UNDO_RESTORED_SOME": url_strs.URL_UNDO_RESTORED_SOME,
        "URL_UNDO_LOST_TAGS": url_strs.URL_UNDO_LOST_TAGS,
        "URL_UNDO_LOST_TAGS_ONE": url_strs.URL_UNDO_LOST_TAGS_ONE,
        "URL_UNDO_NOT_IN_TRASH": url_strs.URL_UNDO_NOT_IN_TRASH,
        "URL_UNDO_NOT_IN_TRASH_ONE": url_strs.URL_UNDO_NOT_IN_TRASH_ONE,
        "URL_UNDO_DESTINATION_REQUIRED": url_strs.URL_UNDO_DESTINATION_REQUIRED,
        "URL_UNDO_DESTINATION_REQUIRED_ONE": url_strs.URL_UNDO_DESTINATION_REQUIRED_ONE,
        "URL_UNDO_DELETE_ARIA": url_strs.URL_UNDO_DELETE_ARIA,
        "URL_UNDO_DELETE_ARIA_ONE": url_strs.URL_UNDO_DELETE_ARIA_ONE,
    }
    assert len(expected) == 14
    for key, value in expected.items():
        assert key in strings, f"generate_strings_js() is missing {key}"
        assert strings[key] == value

    assert "{n}" in strings["URL_MOVED_TO_TRASH"]
    assert "{n}" not in strings["URL_MOVED_TO_TRASH_ONE"]
    assert "{restored}" in strings["URL_UNDO_RESTORED_SOME"]
    assert "{total}" in strings["URL_UNDO_RESTORED_SOME"]


def test_generate_constants_js_device_type_shape():
    """`generate_constants_js()["DEVICE_TYPE"]` mirrors the `DeviceType` enum exactly.

    Any renumbering of `DeviceType` or change to the dict comprehension in
    `constants.py` trips this test, preventing silent divergence from the
    `test-setup.ts` mock (which hardcodes `{MOBILE: 1, DESKTOP: 2}`).
    """
    constants = generate_constants_js()
    assert constants["DEVICE_TYPE"] == {
        member.name: member.value for member in DeviceType
    }
