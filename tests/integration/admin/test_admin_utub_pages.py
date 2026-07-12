from __future__ import annotations

from typing import Tuple
from urllib.parse import quote, urlsplit

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend import db
from backend.models.audit_log import AuditLog
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.strings.admin_portal_strs import (
    ADMIN_AUDIT_ACTIONS,
    ADMIN_PORTAL_STRINGS,
)

pytestmark = pytest.mark.admin

_ADMIN_UTUBS_URL: str = "/admin/utubs"
_UTUB_ACTIONS_TITLE_BYTES: bytes = ADMIN_PORTAL_STRINGS.UTUB_ACTIONS_TITLE.encode()
_SEARCH_INPUT_ID_BYTES: bytes = b'id="AdminUtubTableSearch"'
_TABLE_GRID_ID_BYTES: bytes = b'id="AdminUtubTableGrid"'
_DETAIL_TITLE_ID_BYTES: bytes = b'id="AdminUtubDetailTitle"'
_DETAIL_MEMBERS_TABLE_ID_BYTES: bytes = b'id="AdminUtubDetailMembersTable"'
_DETAIL_URLS_TABLE_ID_BYTES: bytes = b'id="AdminUtubDetailUrlsTable"'

_ALPHA_UTUB_NAME: str = "AlphaSeededUtub"
_BETA_UTUB_NAME: str = "BetaSeededUtub"
_DETAIL_UTUB_NAME: str = "DetailSeededUtub"
_DETAIL_URL_STRING: str = "https://detail-seeded-example.test/page"
_DETAIL_URL_TITLE: str = "Detail Seeded URL Title"
_DETAIL_TAG_STRING: str = "detail-seeded-tag"
_TAGLESS_UTUB_NAME: str = "TaglessSeededUtub"
_MISSING_UTUB_ID: int = 999999

_DETAIL_TAGS_PANEL_ID_BYTES: bytes = b'id="AdminUtubDetailTagsPanel"'
_DETAIL_TAGS_TABLE_ID_BYTES: bytes = b'id="AdminUtubDetailTagsTable"'
_DETAIL_NO_TAGS_ID_BYTES: bytes = b'id="AdminUtubDetailNoTags"'
_UTUB_TAG_DELETE_ACTION_BYTES: bytes = b'data-admin-action="utub-tag-delete"'

# Must match ``_DETAIL_TABLE_PAGE_SIZE`` in ``backend/admin/routes.py``.
_DETAIL_TABLE_PAGE_SIZE: int = 50
_PAGINATION_UTUB_NAME: str = "PaginationSeededUtub"
_PAGINATION_MEMBER_TOTAL: int = 55
_PAGINATION_URL_TOTAL: int = 60
_MEMBERS_PAGINATION_ID_BYTES: bytes = b'id="AdminUtubDetailMembersPagination"'
_URLS_PAGINATION_ID_BYTES: bytes = b'id="AdminUtubDetailUrlsPagination"'
_URL_DELETE_ACTION_BYTES: bytes = b'data-admin-action="url-delete"'
_MEMBER_REMOVE_ACTION_BYTES: bytes = b'data-admin-action="member-remove"'
_MEMBER_REMOVE_NA_BYTES: bytes = (
    ADMIN_PORTAL_STRINGS.MOD_MEMBER_REMOVE_CREATOR_NA.encode()
)

# In-table server-side filter fixtures.
_SEARCH_UTUB_NAME: str = "SearchSeededUtub"
_SEARCH_MEMBER_USERNAMES: Tuple[str, str, str] = (
    "searchalpha",
    "searchbeta",
    "searchgamma",
)
_SEARCH_URL_A_STRING: str = "https://alpha-site.test/page"
_SEARCH_URL_A_TITLE: str = "Mango Report"
_SEARCH_URL_B_STRING: str = "https://beta-site.test/page"
_SEARCH_URL_B_TITLE: str = "Papaya Report"
_SEARCH_URL_C_STRING: str = "https://gamma-site.test/page"
_SEARCH_URL_C_TITLE: str = "Guava Report"
_SEARCH_TAG_STRINGS: Tuple[str, str, str] = ("crimson", "azure", "emerald")
_NO_MATCH_QUERY: str = "zzzznevermatchesanything"

_NO_SEARCH_RESULTS_BYTES: bytes = ADMIN_PORTAL_STRINGS.DB_NO_SEARCH_RESULTS.encode()
_MEMBERS_NO_RESULTS_ID_BYTES: bytes = b'id="AdminUtubDetailMembersNoResults"'
_URLS_NO_RESULTS_ID_BYTES: bytes = b'id="AdminUtubDetailUrlsNoResults"'
_TAGS_NO_RESULTS_ID_BYTES: bytes = b'id="AdminUtubDetailTagsNoResults"'
_NO_URLS_ID_BYTES: bytes = b'id="AdminUtubDetailNoUrls"'

# Filtered-pagination fixture: enough matching URLs to spill past one page.
_FILTER_PAGINATION_UTUB_NAME: str = "FilterPaginationSeededUtub"
_FILTER_MATCH_TERM: str = "Widget"
_FILTER_MATCH_URL_TOTAL: int = 55
_FILTER_NONMATCH_URL_TOTAL: int = 5


def _count_tag_rows(page_bytes: bytes) -> int:
    """Number of tag rows rendered (one utub-tag-delete button per tag row)."""
    return page_bytes.count(_UTUB_TAG_DELETE_ACTION_BYTES)


def _count_url_rows(page_bytes: bytes) -> int:
    """Number of URL rows rendered (one url-delete button per URL row)."""
    return page_bytes.count(_URL_DELETE_ACTION_BYTES)


def _count_member_rows(page_bytes: bytes) -> int:
    """Number of member rows rendered — non-creator rows carry a member-remove
    button, the creator row carries the remove-N/A span; summing both yields the
    exact rendered row count regardless of which page the creator lands on."""
    return page_bytes.count(_MEMBER_REMOVE_ACTION_BYTES) + page_bytes.count(
        _MEMBER_REMOVE_NA_BYTES
    )


def _seed_utub_with_pagination_content(*, name: str, creator_id: int) -> int:
    """Insert one UTub with ``_PAGINATION_MEMBER_TOTAL`` members (the creator plus
    fresh users) and ``_PAGINATION_URL_TOTAL`` URLs, returning the UTub id — enough
    rows to force both detail-page tables past a single page."""
    new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
    db.session.add(new_utub)
    db.session.flush()
    db.session.add(
        Utub_Members(
            utub_id=new_utub.id,
            user_id=creator_id,
            member_role=Member_Role.CREATOR,
        )
    )
    for member_index in range(_PAGINATION_MEMBER_TOTAL - 1):
        member_user = Users(
            username=f"pageuser{member_index}",
            email=f"pageuser{member_index}@pagination-seeded.test",
            plaintext_password="password123",
        )
        db.session.add(member_user)
        db.session.flush()
        db.session.add(
            Utub_Members(
                utub_id=new_utub.id,
                user_id=member_user.id,
                member_role=Member_Role.MEMBER,
            )
        )
    for url_index in range(_PAGINATION_URL_TOTAL):
        new_url = Urls(
            normalized_url=f"https://pagination-seeded-{url_index}.test/page",
            current_user_id=creator_id,
        )
        db.session.add(new_url)
        db.session.flush()
        db.session.add(
            Utub_Urls(
                utub_id=new_utub.id,
                url_id=new_url.id,
                user_id=creator_id,
                url_title=f"Pagination URL {url_index}",
            )
        )
    db.session.commit()
    return new_utub.id


def _seed_utub(*, name: str, creator_id: int) -> int:
    """Insert one UTub owned by ``creator_id`` and return its id."""
    new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
    db.session.add(new_utub)
    db.session.commit()
    return new_utub.id


def _seed_utub_with_content(*, name: str, creator_id: int) -> int:
    """Insert one UTub owned by ``creator_id`` with the creator as a member and
    a single URL association, returning the UTub id.

    Provides the aggregated detail page with at least one member row, one URL
    row, and one UTub tag (vocabulary) so the members, URLs, and UTub Tags
    tables all render (rather than empty states).
    """
    new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
    db.session.add(new_utub)
    db.session.flush()
    db.session.add(
        Utub_Members(
            utub_id=new_utub.id,
            user_id=creator_id,
            member_role=Member_Role.CREATOR,
        )
    )
    new_url = Urls(normalized_url=_DETAIL_URL_STRING, current_user_id=creator_id)
    db.session.add(new_url)
    db.session.flush()
    new_url_association = Utub_Urls(
        utub_id=new_utub.id,
        url_id=new_url.id,
        user_id=creator_id,
        url_title=_DETAIL_URL_TITLE,
    )
    db.session.add(new_url_association)
    db.session.flush()
    new_tag = Utub_Tags(
        utub_id=new_utub.id,
        tag_string=_DETAIL_TAG_STRING,
        created_by=creator_id,
    )
    db.session.add(new_tag)
    db.session.flush()
    db.session.add(
        Utub_Url_Tags(
            utub_id=new_utub.id,
            utub_url_id=new_url_association.id,
            utub_tag_id=new_tag.id,
        )
    )
    db.session.commit()
    return new_utub.id


def _seed_utub_with_searchable_content(*, name: str, creator_id: int) -> int:
    """Insert one UTub with several distinctly-named members, URLs, and tags so
    each detail-page table has a mix of matching/non-matching rows to filter.

    Members: the creator plus ``_SEARCH_MEMBER_USERNAMES``. URLs: three rows with
    distinct url-strings and titles (so url-string vs title matching can both be
    exercised). Tags: ``_SEARCH_TAG_STRINGS``.
    """
    new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
    db.session.add(new_utub)
    db.session.flush()
    db.session.add(
        Utub_Members(
            utub_id=new_utub.id,
            user_id=creator_id,
            member_role=Member_Role.CREATOR,
        )
    )
    for username in _SEARCH_MEMBER_USERNAMES:
        member_user = Users(
            username=username,
            email=f"{username}@search-seeded.test",
            plaintext_password="password123",
        )
        db.session.add(member_user)
        db.session.flush()
        db.session.add(
            Utub_Members(
                utub_id=new_utub.id,
                user_id=member_user.id,
                member_role=Member_Role.MEMBER,
            )
        )
    for url_string, url_title in (
        (_SEARCH_URL_A_STRING, _SEARCH_URL_A_TITLE),
        (_SEARCH_URL_B_STRING, _SEARCH_URL_B_TITLE),
        (_SEARCH_URL_C_STRING, _SEARCH_URL_C_TITLE),
    ):
        new_url = Urls(normalized_url=url_string, current_user_id=creator_id)
        db.session.add(new_url)
        db.session.flush()
        db.session.add(
            Utub_Urls(
                utub_id=new_utub.id,
                url_id=new_url.id,
                user_id=creator_id,
                url_title=url_title,
            )
        )
    for tag_string in _SEARCH_TAG_STRINGS:
        db.session.add(
            Utub_Tags(
                utub_id=new_utub.id,
                tag_string=tag_string,
                created_by=creator_id,
            )
        )
    db.session.commit()
    return new_utub.id


def _seed_utub_with_filtered_url_pagination(*, name: str, creator_id: int) -> int:
    """Insert one UTub whose URLs split into ``_FILTER_MATCH_URL_TOTAL`` rows
    matching ``_FILTER_MATCH_TERM`` (via both url-string and title) and
    ``_FILTER_NONMATCH_URL_TOTAL`` non-matching rows — enough matches to force the
    filtered URLs table past a single page while proving the filter is applied
    before pagination."""
    new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
    db.session.add(new_utub)
    db.session.flush()
    db.session.add(
        Utub_Members(
            utub_id=new_utub.id,
            user_id=creator_id,
            member_role=Member_Role.CREATOR,
        )
    )
    for match_index in range(_FILTER_MATCH_URL_TOTAL):
        new_url = Urls(
            normalized_url=f"https://widget-seeded-{match_index}.test/page",
            current_user_id=creator_id,
        )
        db.session.add(new_url)
        db.session.flush()
        db.session.add(
            Utub_Urls(
                utub_id=new_utub.id,
                url_id=new_url.id,
                user_id=creator_id,
                url_title=f"{_FILTER_MATCH_TERM} {match_index}",
            )
        )
    for nonmatch_index in range(_FILTER_NONMATCH_URL_TOTAL):
        new_url = Urls(
            normalized_url=f"https://gadget-seeded-{nonmatch_index}.test/page",
            current_user_id=creator_id,
        )
        db.session.add(new_url)
        db.session.flush()
        db.session.add(
            Utub_Urls(
                utub_id=new_utub.id,
                url_id=new_url.id,
                user_id=creator_id,
                url_title=f"Gadget {nonmatch_index}",
            )
        )
    db.session.commit()
    return new_utub.id


# ---------------------------------------------------------------------------
# UTub Actions list page
# ---------------------------------------------------------------------------


def test_admin_utubs_page_renders_grid_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and two seeded UTubs
    WHEN the admin sends GET /admin/utubs
    THEN the response is 200 HTML containing the UTub Actions title, the search
         input id, the table grid id, and a seeded UTub name; and exactly one
         AuditLog row is created with action UTUB_LIST, actor_id == the admin's
         user id, and metadata {"query": "", "result_count": <all UTub count>}.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        _seed_utub(name=_ALPHA_UTUB_NAME, creator_id=admin_user.id)
        _seed_utub(name=_BETA_UTUB_NAME, creator_id=admin_user.id)
        total_utub_count: int = Utubs.query.count()
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0
    assert total_utub_count == 2

    response = client.get(_ADMIN_UTUBS_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _UTUB_ACTIONS_TITLE_BYTES in response.data
    assert _SEARCH_INPUT_ID_BYTES in response.data
    assert _TABLE_GRID_ID_BYTES in response.data
    assert _ALPHA_UTUB_NAME.encode() in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.UTUB_LIST
        assert audit_row.actor_id == admin_user.id
        assert audit_row.target_type is None
        assert audit_row.log_metadata == {
            "query": "",
            "result_count": total_utub_count,
        }


def test_admin_utubs_page_filters_by_query(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and two seeded UTubs with distinct names
    WHEN the admin sends GET /admin/utubs?q=<alpha name>
    THEN the grid contains the alpha UTub name but not the beta one, and
         exactly one AuditLog row is created with metadata.query == the alpha
         name and metadata.result_count == 1.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        _seed_utub(name=_ALPHA_UTUB_NAME, creator_id=admin_user.id)
        _seed_utub(name=_BETA_UTUB_NAME, creator_id=admin_user.id)
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_UTUBS_URL}?q={_ALPHA_UTUB_NAME}")

    assert response.status_code == 200
    assert _ALPHA_UTUB_NAME.encode() in response.data
    assert _BETA_UTUB_NAME.encode() not in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.UTUB_LIST
        assert audit_row.actor_id == admin_user.id
        assert audit_row.log_metadata == {
            "query": _ALPHA_UTUB_NAME,
            "result_count": 1,
        }


# ---------------------------------------------------------------------------
# Access-control: non-admin (403) and anonymous (302)
# ---------------------------------------------------------------------------


def test_admin_utubs_page_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in non-admin user
    WHEN the user sends GET /admin/utubs
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_UTUBS_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_utubs_page_redirects_anonymous_to_splash(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/utubs
    THEN the response is 302 and redirects away from /admin (to the login
         page) with the original path in the ``next`` parameter.
    """
    response = client.get(_ADMIN_UTUBS_URL)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")

    encoded_next = quote(_ADMIN_UTUBS_URL, safe="")
    raw_next = _ADMIN_UTUBS_URL
    assert (
        f"next={encoded_next}" in response.location
        or f"next={raw_next}" in response.location
    )


# ---------------------------------------------------------------------------
# UTub detail page
# ---------------------------------------------------------------------------


def test_admin_utub_detail_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and a seeded UTub with one member and one URL
    WHEN the admin sends GET /admin/utubs/<id>
    THEN the response is 200 HTML containing the UTub name, the detail title id,
         the members-table id with the member's username, the URLs-table id
         with the seeded URL string, and the UTub Tags panel/table with the
         seeded tag string and its utub-tag-delete control;
         and exactly one AuditLog row is created with action UTUB_VIEW,
         target_type "Utub", target_id str(<id>), and actor_id == the admin's
         user id.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        admin_username: str = admin_user.username
        utub_id: int = _seed_utub_with_content(
            name=_DETAIL_UTUB_NAME, creator_id=admin_user.id
        )
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_UTUBS_URL}/{utub_id}")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _DETAIL_TITLE_ID_BYTES in response.data
    assert _DETAIL_UTUB_NAME.encode() in response.data
    assert _DETAIL_MEMBERS_TABLE_ID_BYTES in response.data
    assert admin_username.encode() in response.data
    assert _DETAIL_URLS_TABLE_ID_BYTES in response.data
    assert _DETAIL_URL_STRING.encode() in response.data
    # UTub Tags panel/table + the vocabulary tag string and its delete control.
    assert _DETAIL_TAGS_PANEL_ID_BYTES in response.data
    assert _DETAIL_TAGS_TABLE_ID_BYTES in response.data
    assert _DETAIL_TAG_STRING.encode() in response.data
    assert _UTUB_TAG_DELETE_ACTION_BYTES in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.UTUB_VIEW
        assert audit_row.actor_id == admin_user.id
        assert audit_row.target_type == "Utub"
        assert audit_row.target_id == str(utub_id)


def test_admin_utub_detail_renders_empty_tags_state(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and a seeded UTub with no tags
    WHEN the admin sends GET /admin/utubs/<id>
    THEN the response is 200 HTML that still renders the UTub Tags panel but shows
         the no-tags empty state (and no utub-tag-delete control).
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        utub_id: int = _seed_utub(name=_TAGLESS_UTUB_NAME, creator_id=admin_user.id)

    response = client.get(f"{_ADMIN_UTUBS_URL}/{utub_id}")

    assert response.status_code == 200
    assert _DETAIL_TAGS_PANEL_ID_BYTES in response.data
    assert _DETAIL_NO_TAGS_ID_BYTES in response.data
    assert _DETAIL_TAGS_TABLE_ID_BYTES not in response.data
    assert _UTUB_TAG_DELETE_ACTION_BYTES not in response.data


def test_admin_utub_detail_returns_404_for_missing_id(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and no UTub with the requested id
    WHEN the admin sends GET /admin/utubs/<missing id>
    THEN the response is 404 and no AuditLog row is created.
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        assert Utubs.query.get(_MISSING_UTUB_ID) is None
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_UTUBS_URL}/{_MISSING_UTUB_ID}")

    assert response.status_code == 404

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_utub_detail_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in non-admin user and one seeded UTub
    WHEN the user sends GET /admin/utubs/<id>
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, user, app = login_first_user_with_register

    with app.app_context():
        utub_id: int = _seed_utub(name=_DETAIL_UTUB_NAME, creator_id=user.id)
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_UTUBS_URL}/{utub_id}")

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_utub_detail_redirects_anonymous_to_splash(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/utubs/<id>
    THEN the response is 302 and redirects away from /admin (to the login
         page) with the original path in the ``next`` parameter.
    """
    detail_path = f"{_ADMIN_UTUBS_URL}/1"

    response = client.get(detail_path)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")

    encoded_next = quote(detail_path, safe="")
    assert (
        f"next={encoded_next}" in response.location
        or f"next={detail_path}" in response.location
    )


def test_admin_utub_detail_paginates_members_and_urls(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and a UTub seeded with more members and URLs than
          the detail-table page size
    WHEN the admin opens the detail page (page 1) and then each table's page 2
    THEN page 1 renders exactly page-size rows in each table, both info-panel
         counts show the TOTALS, each table exposes a Next link at the page-size
         offset (and no Previous), page 2 renders the remainder with a Previous
         link, and paginating one table preserves the OTHER table's offset.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        utub_id: int = _seed_utub_with_pagination_content(
            name=_PAGINATION_UTUB_NAME, creator_id=admin_user.id
        )

    remainder_members: int = _PAGINATION_MEMBER_TOTAL - _DETAIL_TABLE_PAGE_SIZE
    remainder_urls: int = _PAGINATION_URL_TOTAL - _DETAIL_TABLE_PAGE_SIZE

    # Page 1 (no offsets) — both tables show exactly a full page.
    page_one = client.get(f"{_ADMIN_UTUBS_URL}/{utub_id}")
    assert page_one.status_code == 200
    page_one_bytes = page_one.data
    assert _MEMBERS_PAGINATION_ID_BYTES in page_one_bytes
    assert _URLS_PAGINATION_ID_BYTES in page_one_bytes
    assert _count_member_rows(page_one_bytes) == _DETAIL_TABLE_PAGE_SIZE
    assert _count_url_rows(page_one_bytes) == _DETAIL_TABLE_PAGE_SIZE
    # Info-panel counts are the TOTALS, not the page length.
    assert f"of {_PAGINATION_MEMBER_TOTAL}".encode() in page_one_bytes
    assert f"of {_PAGINATION_URL_TOTAL}".encode() in page_one_bytes
    # Next links present at page-size offset; no Previous on page 1.
    assert f"members_offset={_DETAIL_TABLE_PAGE_SIZE}".encode() in page_one_bytes
    assert f"urls_offset={_DETAIL_TABLE_PAGE_SIZE}".encode() in page_one_bytes
    assert b">Previous<" not in page_one_bytes

    # URLs page 2 — remainder rows + Previous; members table stays on page 1
    # (its offset preserved at 0).
    urls_page_two = client.get(
        f"{_ADMIN_UTUBS_URL}/{utub_id}?urls_offset={_DETAIL_TABLE_PAGE_SIZE}"
    )
    assert urls_page_two.status_code == 200
    urls_page_two_bytes = urls_page_two.data
    assert _count_url_rows(urls_page_two_bytes) == remainder_urls
    assert _count_member_rows(urls_page_two_bytes) == _DETAIL_TABLE_PAGE_SIZE
    assert b">Previous<" in urls_page_two_bytes
    # URLs Previous link returns to offset 0.
    assert b"urls_offset=0" in urls_page_two_bytes

    # Members page 2 while URLs stay on their page 2 — each link preserves the
    # OTHER table's current offset (urls_offset=50 threaded into members links,
    # members_offset=50 threaded into URL links).
    members_page_two = client.get(
        f"{_ADMIN_UTUBS_URL}/{utub_id}"
        f"?members_offset={_DETAIL_TABLE_PAGE_SIZE}&urls_offset={_DETAIL_TABLE_PAGE_SIZE}"
    )
    assert members_page_two.status_code == 200
    members_page_two_bytes = members_page_two.data
    assert _count_member_rows(members_page_two_bytes) == remainder_members
    assert _count_url_rows(members_page_two_bytes) == remainder_urls
    assert (
        f"members_offset={_DETAIL_TABLE_PAGE_SIZE}".encode() in members_page_two_bytes
    )
    assert f"urls_offset={_DETAIL_TABLE_PAGE_SIZE}".encode() in members_page_two_bytes


# ---------------------------------------------------------------------------
# UTub detail page — in-table server-side filters
# ---------------------------------------------------------------------------


def test_admin_utub_detail_filters_urls_by_query(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and a UTub seeded with three distinct URLs
    WHEN the admin sends GET /admin/utubs/<id>?urls_q=<url-string term> and, in a
         second request, ?urls_q=<title-only term>
    THEN the URL-string query renders only the matching URL row (with the
         filtered "of 1" total and the other URLs absent), and the title-only
         query likewise renders only its matching row — proving both the URL
         string and the title columns are searched, filtered over the full set.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        utub_id: int = _seed_utub_with_searchable_content(
            name=_SEARCH_UTUB_NAME, creator_id=admin_user.id
        )

    # url-string match: "alpha-site" is only in URL A's url string.
    by_url_string = client.get(f"{_ADMIN_UTUBS_URL}/{utub_id}?urls_q=alpha-site")
    assert by_url_string.status_code == 200
    by_url_string_bytes = by_url_string.data
    assert _count_url_rows(by_url_string_bytes) == 1
    assert _SEARCH_URL_A_STRING.encode() in by_url_string_bytes
    assert _SEARCH_URL_B_STRING.encode() not in by_url_string_bytes
    assert _SEARCH_URL_C_STRING.encode() not in by_url_string_bytes
    # Filtered pagination total reflects the FILTERED set, not the true 3.
    assert b"of 1" in by_url_string_bytes
    # Info-panel URL count stays the UNFILTERED total.
    assert b'id="AdminUtubDetailUrlCount">3<' in by_url_string_bytes

    # title-only match: "Papaya" is only in URL B's title, not any url string.
    by_title = client.get(f"{_ADMIN_UTUBS_URL}/{utub_id}?urls_q=Papaya")
    assert by_title.status_code == 200
    by_title_bytes = by_title.data
    assert _count_url_rows(by_title_bytes) == 1
    assert _SEARCH_URL_B_TITLE.encode() in by_title_bytes
    assert _SEARCH_URL_A_STRING.encode() not in by_title_bytes
    assert _SEARCH_URL_C_STRING.encode() not in by_title_bytes


def test_admin_utub_detail_filters_members_by_username(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and a UTub seeded with several distinct members
    WHEN the admin sends GET /admin/utubs/<id>?members_q=<username term>
    THEN only the matching member row renders and the info-panel member count
         stays the UNFILTERED total.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        utub_id: int = _seed_utub_with_searchable_content(
            name=_SEARCH_UTUB_NAME, creator_id=admin_user.id
        )

    response = client.get(
        f"{_ADMIN_UTUBS_URL}/{utub_id}?members_q={_SEARCH_MEMBER_USERNAMES[0]}"
    )

    assert response.status_code == 200
    response_bytes = response.data
    # Only the one matching member row renders (the creator/admin row and the
    # other seeded members are filtered out of the table).
    assert _count_member_rows(response_bytes) == 1
    assert _SEARCH_MEMBER_USERNAMES[0].encode() in response_bytes
    assert _SEARCH_MEMBER_USERNAMES[1].encode() not in response_bytes
    assert _SEARCH_MEMBER_USERNAMES[2].encode() not in response_bytes
    # Info-panel member count stays the UNFILTERED total (creator + 3 seeded).
    assert b'id="AdminUtubDetailMemberCount">4<' in response_bytes


def test_admin_utub_detail_filters_tags_by_text(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and a UTub seeded with several distinct tags
    WHEN the admin sends GET /admin/utubs/<id>?tags_q=<tag term>
    THEN only the matching tag row renders (tags are un-paginated).
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        utub_id: int = _seed_utub_with_searchable_content(
            name=_SEARCH_UTUB_NAME, creator_id=admin_user.id
        )

    response = client.get(
        f"{_ADMIN_UTUBS_URL}/{utub_id}?tags_q={_SEARCH_TAG_STRINGS[0]}"
    )

    assert response.status_code == 200
    response_bytes = response.data
    assert _count_tag_rows(response_bytes) == 1
    assert _SEARCH_TAG_STRINGS[0].encode() in response_bytes
    assert _SEARCH_TAG_STRINGS[1].encode() not in response_bytes
    assert _SEARCH_TAG_STRINGS[2].encode() not in response_bytes


def test_admin_utub_detail_filter_preserves_other_table_state(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and a searchable UTub
    WHEN the admin sends GET /admin/utubs/<id> with one table filtered plus
         another table's query and offset set
    THEN the filter is applied to its own table while every OTHER table's search
         form carries the other queries and the paginated offsets as hidden
         inputs — so submitting one table's search never drops the others'
         state.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        utub_id: int = _seed_utub_with_searchable_content(
            name=_SEARCH_UTUB_NAME, creator_id=admin_user.id
        )

    response = client.get(
        f"{_ADMIN_UTUBS_URL}/{utub_id}"
        f"?members_q={_SEARCH_MEMBER_USERNAMES[0]}"
        f"&tags_q={_SEARCH_TAG_STRINGS[0]}"
        f"&urls_offset={_DETAIL_TABLE_PAGE_SIZE}"
    )

    assert response.status_code == 200
    response_bytes = response.data
    # The members filter is applied (only the one member row).
    assert _count_member_rows(response_bytes) == 1
    # Other tables' search forms preserve the sibling queries...
    assert (
        f'name="members_q" value="{_SEARCH_MEMBER_USERNAMES[0]}"'.encode()
        in response_bytes
    )
    assert f'name="tags_q" value="{_SEARCH_TAG_STRINGS[0]}"'.encode() in response_bytes
    # ...and the other paginated table's offset.
    assert (
        f'name="urls_offset" value="{_DETAIL_TABLE_PAGE_SIZE}"'.encode()
        in response_bytes
    )


def test_admin_utub_detail_filter_no_match_shows_no_results(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and a searchable UTub
    WHEN the admin sends GET /admin/utubs/<id>?urls_q=<term matching nothing>
    THEN the URLs table shows the distinct no-search-results empty state (not the
         unfiltered "no URLs" state) with the shared no-results copy.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        utub_id: int = _seed_utub_with_searchable_content(
            name=_SEARCH_UTUB_NAME, creator_id=admin_user.id
        )

    response = client.get(f"{_ADMIN_UTUBS_URL}/{utub_id}?urls_q={_NO_MATCH_QUERY}")

    assert response.status_code == 200
    response_bytes = response.data
    assert _count_url_rows(response_bytes) == 0
    assert _URLS_NO_RESULTS_ID_BYTES in response_bytes
    assert _NO_SEARCH_RESULTS_BYTES in response_bytes
    # The unfiltered "no URLs at all" state must NOT be shown when a query is set.
    assert _NO_URLS_ID_BYTES not in response_bytes


def test_admin_utub_detail_filtered_urls_paginate(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and a UTub whose URLs split into more matching rows
          than the detail-table page size plus some non-matching rows
    WHEN the admin filters the URLs table and pages through the filtered result
    THEN page 1 shows a full page of matches with the FILTERED total, a Next link
         carrying both the query and the next offset, and page 2 shows exactly the
         filtered remainder (never the non-matching rows).
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        utub_id: int = _seed_utub_with_filtered_url_pagination(
            name=_FILTER_PAGINATION_UTUB_NAME, creator_id=admin_user.id
        )

    remainder: int = _FILTER_MATCH_URL_TOTAL - _DETAIL_TABLE_PAGE_SIZE

    page_one = client.get(f"{_ADMIN_UTUBS_URL}/{utub_id}?urls_q={_FILTER_MATCH_TERM}")
    assert page_one.status_code == 200
    page_one_bytes = page_one.data
    assert _count_url_rows(page_one_bytes) == _DETAIL_TABLE_PAGE_SIZE
    # Filtered total, not the seeded (match + non-match) count.
    assert f"of {_FILTER_MATCH_URL_TOTAL}".encode() in page_one_bytes
    # Next link carries both the query and the next offset.
    assert f"urls_offset={_DETAIL_TABLE_PAGE_SIZE}".encode() in page_one_bytes
    assert f"urls_q={_FILTER_MATCH_TERM}".encode() in page_one_bytes
    assert b">Previous<" not in page_one_bytes

    page_two = client.get(
        f"{_ADMIN_UTUBS_URL}/{utub_id}"
        f"?urls_q={_FILTER_MATCH_TERM}&urls_offset={_DETAIL_TABLE_PAGE_SIZE}"
    )
    assert page_two.status_code == 200
    page_two_bytes = page_two.data
    assert _count_url_rows(page_two_bytes) == remainder
    assert b">Previous<" in page_two_bytes
