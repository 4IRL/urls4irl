import re
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS

pytestmark = pytest.mark.utubs

# gear id -> exact aria-label
EXPECTED_GEARS: Dict[str, str] = {
    "utubBtnSettings": UI_TEST_STRINGS.PANEL_SETTINGS_GEAR_UTUBS,
    "memberBtnSettings": UI_TEST_STRINGS.PANEL_SETTINGS_GEAR_MEMBERS,
    "utubTagBtnSettings": UI_TEST_STRINGS.PANEL_SETTINGS_GEAR_TAGS,
    "urlBtnSettings": UI_TEST_STRINGS.PANEL_SETTINGS_GEAR_URLS,
}

EXPECTED_PANELS: Dict[str, str] = {
    "utubBtnSettings": "utubs",
    "memberBtnSettings": "members",
    "utubTagBtnSettings": "tags",
    "urlBtnSettings": "urls",
}

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta"}


class _HomeMarkupParser(HTMLParser):
    """Records each element's attributes and the ids/classes of its ancestors."""

    def __init__(self) -> None:
        super().__init__()
        # (tag, attrs, ordered child markers) per open element
        self._stack: List[Tuple[str, Dict[str, Optional[str]], List[object]]] = []
        self.elements: Dict[str, Dict[str, Optional[str]]] = {}
        self.ancestors: Dict[str, List[Dict[str, Optional[str]]]] = {}
        self.parents: Dict[str, Dict[str, Optional[str]]] = {}
        self.id_counts: Dict[str, int] = {}
        self._markers: Dict[str, Tuple[List[object], object]] = {}

    def is_last_child(self, element_id: str) -> bool:
        siblings, marker = self._markers[element_id]
        return siblings[-1] is marker

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_map = dict(attrs)
        marker = object()
        if self._stack:
            self._stack[-1][2].append(marker)
        element_id = attr_map.get("id")
        if element_id:
            self.id_counts[element_id] = self.id_counts.get(element_id, 0) + 1
            self.elements[element_id] = attr_map
            self.ancestors[element_id] = [
                ancestor_attrs for _, ancestor_attrs, _ in self._stack
            ]
            if self._stack:
                self.parents[element_id] = self._stack[-1][1]
                self._markers[element_id] = (self._stack[-1][2], marker)
        if tag not in VOID_TAGS:
            self._stack.append((tag, attr_map, []))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break


def _get_home_markup(client: FlaskClient) -> Tuple[_HomeMarkupParser, str]:
    response = client.get(url_for(ROUTES.UTUBS.HOME))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    parser = _HomeMarkupParser()
    parser.feed(html)
    return parser, html


def test_home_page_renders_four_hidden_settings_gears(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user
    WHEN the home page is requested
    THEN all four panel settings gears ship hidden with their exact aria-label,
        dialog semantics and the standard bottom hover tooltip carrying the same label
    """
    client, _, _, _ = login_first_user_without_register
    parser, _ = _get_home_markup(client)

    for gear_id, label in EXPECTED_GEARS.items():
        assert gear_id in parser.elements, f"missing gear #{gear_id}"
        attrs = parser.elements[gear_id]
        assert "panelSettingsGear" in (attrs.get("class") or "").split()
        assert "hidden" in (attrs.get("class") or "").split()
        assert "hidden" not in attrs, "must use the .hidden class, not the attribute"
        assert attrs.get("aria-label") == label
        assert attrs.get("aria-haspopup") == "dialog"
        assert attrs.get("aria-expanded") == "false"
        assert attrs.get("aria-controls") == "panelSettingsPopover"
        assert attrs.get("data-bs-toggle") == "tooltip"
        assert attrs.get("data-bs-placement") == "bottom"
        assert attrs.get("data-bs-trigger") == "hover"
        assert attrs.get("data-bs-title") == label
        assert attrs.get("data-bs-custom-class") == "panelSettingsGear-tooltip"
        assert attrs.get("data-panel") == EXPECTED_PANELS[gear_id]
        assert parser.id_counts[gear_id] == 1


def test_home_page_settings_gears_are_last_child_of_their_container(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user
    WHEN the home page is requested
    THEN each gear sits inside a .button-container within its own deck header, and
        the Tags gear is in #utubTagStandardBtns, not the close/update row
    """
    client, _, _, _ = login_first_user_without_register
    parser, _ = _get_home_markup(client)

    expected_deck = {
        "utubBtnSettings": "UTubDeck",
        "memberBtnSettings": "MemberDeck",
        "utubTagBtnSettings": "TagDeck",
        "urlBtnSettings": "URLDeck",
    }
    for gear_id, deck_id in expected_deck.items():
        parent = parser.parents[gear_id]
        assert "button-container" in (parent.get("class") or "").split()
        ancestor_ids = [ancestor.get("id") for ancestor in parser.ancestors[gear_id]]
        assert deck_id in ancestor_ids

    assert parser.parents["utubTagBtnSettings"].get("id") == "utubTagStandardBtns"
    assert "utubTagCloseUpdateTagBtnContainer" not in [
        ancestor.get("id") for ancestor in parser.ancestors["utubTagBtnSettings"]
    ]

    # The gear is the last direct child of its container.
    for gear_id in EXPECTED_GEARS:
        assert parser.is_last_child(gear_id)


def test_home_page_renders_settings_shell_mount_outside_main(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user
    WHEN the home page is requested
    THEN the settings shell mount is a sibling after </main>, with a hidden dialog
        popover, hidden phase 3 containers and one polite live region
    """
    client, _, _, _ = login_first_user_without_register
    parser, html = _get_home_markup(client)

    assert html.index("</main>") < html.index('id="panelSettingsRoot"')
    assert html.index('id="panelSettingsRoot"') < html.index('id="utubs-data"')
    for element_id in ("panelSettingsRoot", "panelSettingsPopover"):
        assert not any(
            ancestor.get("id") == "mainPanel"
            for ancestor in parser.ancestors[element_id]
        )

    popover = parser.elements["panelSettingsPopover"]
    assert popover.get("role") == "dialog"
    assert popover.get("tabindex") == "-1"
    assert "aria-modal" not in popover
    assert "hidden" not in popover
    for element_id in (
        "panelSettingsPopover",
        "panelSettingsBackdrop",
        "panelSettingsSheet",
    ):
        assert "hidden" in (parser.elements[element_id].get("class") or "").split()

    announcement = parser.elements["PanelSettingsAnnouncement"]
    assert announcement.get("aria-live") == "polite"
    assert html.count('id="PanelSettingsAnnouncement"') == 1


def test_home_page_renders_settings_sheet_dialog_markup(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user
    WHEN the home page is requested
    THEN the hidden mobile settings sheet carries dialog semantics, a named close
        button, an empty title and grabber, header (title, close), body in DOM order
    """
    client, _, _, _ = login_first_user_without_register
    parser, html = _get_home_markup(client)

    sheet = parser.elements["panelSettingsSheet"]
    assert sheet.get("role") == "dialog"
    assert sheet.get("aria-modal") == "true"
    assert sheet.get("aria-labelledby") == "panelSettingsSheetTitle"
    assert sheet.get("tabindex") == "-1"
    # The title is the only accessible-name source.
    assert "aria-label" not in sheet

    backdrop = parser.elements["panelSettingsBackdrop"]
    assert backdrop.get("aria-hidden") == "true"
    for element_id in ("panelSettingsSheet", "panelSettingsBackdrop"):
        classes = (parser.elements[element_id].get("class") or "").split()
        assert "hidden" in classes
        assert "hidden" not in parser.elements[element_id]

    close = parser.elements["panelSettingsSheetClose"]
    assert close.get("type") == "button"
    assert close.get("aria-label") == UI_TEST_STRINGS.PANEL_SETTINGS_CLOSE
    assert UI_TEST_STRINGS.PANEL_SETTINGS_CLOSE == "Close settings"

    grabber = parser.elements["panelSettingsSheetGrabber"]
    assert grabber.get("aria-hidden") == "true"

    # The title is an empty h2 (text is set at open time), read from the raw html.
    assert re.search(r'<h2[^>]*id="panelSettingsSheetTitle"[^>]*>\s*</h2>', html), (
        "title must be an empty h2"
    )

    grabber_at = html.index('id="panelSettingsSheetGrabber"')
    header_at = html.index('id="panelSettingsSheetHeader"')
    title_at = html.index('id="panelSettingsSheetTitle"')
    close_at = html.index('id="panelSettingsSheetClose"')
    body_at = html.index('id="panelSettingsSheetBody"')
    assert grabber_at < header_at < title_at < close_at < body_at
    for child_id in (
        "panelSettingsSheetGrabber",
        "panelSettingsSheetHeader",
        "panelSettingsSheetBody",
    ):
        assert parser.parents[child_id].get("id") == "panelSettingsSheet"
    assert (
        parser.parents["panelSettingsSheetTitle"].get("id")
        == "panelSettingsSheetHeader"
    )
    assert (
        parser.parents["panelSettingsSheetClose"].get("id")
        == "panelSettingsSheetHeader"
    )
