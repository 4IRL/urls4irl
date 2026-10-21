"""Link lifecycle: address edits and trashing kill a URL's share link, restores never
bring it back, and every path updates the locked row before deleting the link.
"""

from __future__ import annotations

from typing import Any, Callable, Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response
from sqlalchemy import event

from backend import db
from backend.models.short_links import Short_Links
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.utils.all_routes import ROUTES
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    anonymous_client,
    code_from_short_url,
    get_share_page,
    post_mint,
)
from tests.integration.trash.trash_helpers import (
    post_restore,
    post_restore_urls,
)
from tests.utils_for_test import add_short_link, get_utub_url_id, trash_utub_url

pytestmark = pytest.mark.short_links

AJAX_HEADERS = {URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST}
SECOND_UTUB_ID = 2
LOGIN_FIXTURE = Tuple[FlaskClient, str, Users, Flask]


def _csrf(csrf_token: str) -> dict[str, str]:
    return {"X-CSRFToken": csrf_token}


def _patch_url_string(
    client: FlaskClient, csrf_token: str, utub_url_id: int, url_string: str
) -> Response:
    return client.patch(
        url_for(ROUTES.URLS.UPDATE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=utub_url_id),
        json={"urlString": url_string},
        headers=_csrf(csrf_token),
    )


def _patch_url_title(
    client: FlaskClient, csrf_token: str, utub_url_id: int, title: str
) -> Response:
    return client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=FIRST_UTUB_ID,
            utub_url_id=utub_url_id,
        ),
        json={MODELS.URL_TITLE: title},
        headers=_csrf(csrf_token),
    )


def _delete_url(client: FlaskClient, csrf_token: str, utub_url_id: int) -> Response:
    return client.delete(
        url_for(ROUTES.URLS.DELETE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=utub_url_id),
        headers=_csrf(csrf_token),
    )


def _bulk_delete(
    client: FlaskClient, csrf_token: str, utub_url_ids: list[int]
) -> Response:
    return client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={"utubUrlIds": utub_url_ids},
        headers=_csrf(csrf_token),
    )


def _delete_utub(client: FlaskClient, csrf_token: str, utub_id: int) -> Response:
    return client.delete(
        url_for(ROUTES.UTUBS.DELETE_UTUB, utub_id=utub_id),
        headers=_csrf(csrf_token),
    )


def _restore_utub(client: FlaskClient, csrf_token: str, utub_id: int) -> Response:
    return client.post(
        url_for(ROUTES.UTUBS.RESTORE_UTUB, utub_id=utub_id),
        json={},
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def _get_utub(client: FlaskClient, utub_id: int) -> dict[str, Any]:
    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id), headers=AJAX_HEADERS
    )
    assert response.status_code == 200
    return response.json


def _url_string_of(app: Flask, utub_url_id: int) -> str:
    with app.app_context():
        return Utub_Urls.query.get(utub_url_id).standalone_url.url_string


def _link_ids(app: Flask) -> list[int]:
    """The ``utubUrlID`` of every ShortLinks row, sorted.

    Does not use ``short_link_rows``: its ``expunge_all`` would detach the logged-in
    user the harness caches on ``g`` for the rest of the test.
    """
    with app.app_context():
        return sorted(
            utub_url_id for (utub_url_id,) in db.session.query(Short_Links.utub_url_id)
        )


def _assert_no_link_state(item: dict[str, Any]) -> None:
    assert item[MODELS.SHORT_LINK_EXPIRES_AT] is None
    assert item[MODELS.CAN_REVOKE_SHORT_LINK] is False


def _statements_during(send_request: Callable[[], Any]) -> list[str]:
    """Run ``send_request`` and return every SQL statement it executed, normalized."""
    statements: list[str] = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.split()))

    # Listen on the session's live connection, not the Engine class: the harness
    # checks out a long-lived SAVEPOINT connection at fixture setup.
    connection = db.session.connection()
    event.listen(connection, "before_cursor_execute", record_statement)
    try:
        send_request()
    finally:
        event.remove(connection, "before_cursor_execute", record_statement)
    return statements


def _first_index(statements: list[str], matches: Callable[[str], bool]) -> int:
    for index, statement in enumerate(statements):
        if matches(statement):
            return index
    raise AssertionError(f"no matching statement in: {statements}")


def _is_utub_lock(statement: str) -> bool:
    return 'FROM "Utubs"' in statement and "FOR NO KEY UPDATE" in statement


def _is_update_of(table: str, column: str) -> Callable[[str], bool]:
    return lambda statement: (
        statement.startswith(f'UPDATE "{table}" SET') and f'"{column}"' in statement
    )


def _is_link_delete(statement: str) -> bool:
    return statement.startswith('DELETE FROM "ShortLinks"')


def _assert_lock_then_update_then_link_delete(
    statements: list[str], *, table: str, column: str
) -> None:
    """The Utubs lock, then the row UPDATE, then the ShortLinks DELETE."""
    lock_index = _first_index(statements, _is_utub_lock)
    update_index = _first_index(statements, _is_update_of(table, column))
    delete_index = _first_index(statements, _is_link_delete)
    assert lock_index < update_index < delete_index, statements


def test_title_edit_keeps_the_link(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN URL 1 holding a short link
    WHEN only its title is edited
    THEN the link row is untouched
    """
    client, csrf_token, _, app = login_first_user_without_register
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    link_id = add_short_link(app, url_1, minted_by=CREATOR_ID)

    response = _patch_url_title(client, csrf_token, url_1, "A brand new title")

    assert response.status_code == 200
    with app.app_context():
        assert [row.id for row in db.session.query(Short_Links)] == [link_id]


def test_address_edit_deletes_only_that_urls_link(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN URLs 1 and 2 each holding a minted link
    WHEN URL 1's address is edited to a new one
    THEN URL 1's link is deleted (its old code now resolves to the dead-link 404),
        URL 2's link remains, and the lock-then-update-then-delete order holds
    """
    client, csrf_token, _, app = login_first_user_without_register
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    url_2 = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    mint_response = post_mint(client, csrf_token, FIRST_UTUB_ID, url_1)
    assert mint_response.status_code == 200
    old_code = code_from_short_url(mint_response.json["shortUrl"])
    add_short_link(app, url_2, minted_by=CREATOR_ID)

    statements = _statements_during(
        lambda: _patch_url_string(client, csrf_token, url_1, "https://yahoo.com")
    )

    assert _link_ids(app) == [url_2]
    with app.app_context():
        assert (
            db.session.query(Short_Links).filter(Short_Links.code == old_code).count()
            == 0
        )
    # The old code now resolves to the dead-link page.
    assert get_share_page(anonymous_client(app), old_code).status_code == 404
    _assert_lock_then_update_then_link_delete(
        statements, table="UtubUrls", column="urlID"
    )


def test_address_edit_through_revive_leaves_neither_row_with_a_link(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN URL 1 holding a link and URL 3 trashed
    WHEN URL 1's address is edited to URL 3's string (revive-on-edit)
    THEN neither the edited row (now trashed) nor the revived row has a link, the
        revived card reports no link state, and the Utubs lock precedes the trash
        UPDATE which precedes the link DELETE
    """
    client, csrf_token, _, app = login_first_user_without_register
    edited_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trashed_id = get_utub_url_id(app, FIRST_UTUB_ID, 3)
    trash_string = _url_string_of(app, trashed_id)
    add_short_link(app, edited_id, minted_by=CREATOR_ID)
    trash_utub_url(app, trashed_id, deleted_by=CREATOR_ID)

    responses: list[Response] = []
    statements = _statements_during(
        lambda: responses.append(
            _patch_url_string(client, csrf_token, edited_id, trash_string)
        )
    )

    assert responses[0].status_code == 200
    assert responses[0].json[MODELS.REVIVED_FROM_TRASH] is True
    assert _link_ids(app) == []
    _assert_lock_then_update_then_link_delete(
        statements, table="UtubUrls", column="deletedAt"
    )
    utub_json = _get_utub(client, FIRST_UTUB_ID)
    revived_card = next(
        item
        for item in utub_json[MODELS.URLS]
        if item[MODELS.UTUB_URL_ID] == trashed_id
    )
    _assert_no_link_state(revived_card)


def test_single_trash_deletes_the_link(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN URLs 1 and 2 each holding a link
    WHEN URL 1 is trashed
    THEN only URL 1's link is deleted, after the Utubs lock and the trash UPDATE
    """
    client, csrf_token, _, app = login_first_user_without_register
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    url_2 = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    add_short_link(app, url_1, minted_by=CREATOR_ID)
    add_short_link(app, url_2, minted_by=CREATOR_ID)

    responses: list[Response] = []
    statements = _statements_during(
        lambda: responses.append(_delete_url(client, csrf_token, url_1))
    )

    assert responses[0].status_code == 200
    assert _link_ids(app) == [url_2]
    _assert_lock_then_update_then_link_delete(
        statements, table="UtubUrls", column="deletedAt"
    )


def test_bulk_trash_deletes_links_of_trashed_urls_only(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN URLs 1, 2 and 3 each holding a link
    WHEN URLs 1 and 2 are bulk-trashed
    THEN their links are deleted and URL 3's remains, after the Utubs lock and the
        trash UPDATEs
    """
    client, csrf_token, _, app = login_first_user_without_register
    url_ids = [get_utub_url_id(app, FIRST_UTUB_ID, number) for number in (1, 2, 3)]
    for utub_url_id in url_ids:
        add_short_link(app, utub_url_id, minted_by=CREATOR_ID)

    responses: list[Response] = []
    statements = _statements_during(
        lambda: responses.append(_bulk_delete(client, csrf_token, url_ids[:2]))
    )

    assert responses[0].status_code == 200
    assert _link_ids(app) == [url_ids[2]]
    _assert_lock_then_update_then_link_delete(
        statements, table="UtubUrls", column="deletedAt"
    )


def test_utub_trash_deletes_every_link_in_it_only(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN links on all three URLs of UTub 1 and on the URL of UTub 2
    WHEN UTub 1 is trashed
    THEN UTub 1's links are deleted, UTub 2's remains, and the Utubs UPDATE precedes
        the link DELETE
    """
    client, csrf_token, _, app = login_first_user_without_register
    utub_1_url_ids = [
        get_utub_url_id(app, FIRST_UTUB_ID, number) for number in (1, 2, 3)
    ]
    with app.app_context():
        utub_2_url_id: int = (
            Utub_Urls.query.filter(Utub_Urls.utub_id == SECOND_UTUB_ID).first().id
        )
    for utub_url_id in [*utub_1_url_ids, utub_2_url_id]:
        add_short_link(app, utub_url_id, minted_by=CREATOR_ID)

    responses: list[Response] = []
    statements = _statements_during(
        lambda: responses.append(_delete_utub(client, csrf_token, FIRST_UTUB_ID))
    )

    assert responses[0].status_code == 200
    assert _link_ids(app) == [utub_2_url_id]
    _assert_lock_then_update_then_link_delete(
        statements, table="Utubs", column="deletedAt"
    )


def test_restoring_a_trashed_url_brings_no_link_back(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN URLs 1 and 2 with links, trashed together and then restored
    WHEN restored in place (single), in bulk, and to a destination UTub
    THEN every restore response card reports no link state and no row exists
    """
    client, csrf_token, _, app = login_first_user_without_register
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    url_2 = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    url_3 = get_utub_url_id(app, FIRST_UTUB_ID, 3)
    for utub_url_id in (url_1, url_2, url_3):
        add_short_link(app, utub_url_id, minted_by=CREATOR_ID)
    assert _bulk_delete(client, csrf_token, [url_1, url_2, url_3]).status_code == 200
    assert _link_ids(app) == []

    single = post_restore(client, csrf_token, FIRST_UTUB_ID, url_1)
    assert single.status_code == 200
    _assert_no_link_state(single.json[MODELS.URL])

    bulk = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [url_2])
    assert bulk.status_code == 200
    assert [item[MODELS.UTUB_URL_ID] for item in bulk.json[MODELS.RESTORED]] == [url_2]
    for item in bulk.json[MODELS.RESTORED]:
        _assert_no_link_state(item)

    assert _delete_utub(client, csrf_token, FIRST_UTUB_ID).status_code == 200
    destination = post_restore(
        client, csrf_token, FIRST_UTUB_ID, url_3, {"destUtubId": SECOND_UTUB_ID}
    )
    assert destination.status_code == 200
    _assert_no_link_state(destination.json[MODELS.URL])

    assert _link_ids(app) == []


def test_restoring_a_trashed_utub_brings_no_link_back(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN UTub 1 whose URLs held links before the UTub was trashed
    WHEN the UTub is restored and loaded
    THEN no link row exists and every URL card reports no link state, while a member
        can mint a fresh link on one of them
    """
    client, csrf_token, _, app = login_first_user_without_register
    url_ids = [get_utub_url_id(app, FIRST_UTUB_ID, number) for number in (1, 2, 3)]
    for utub_url_id in url_ids:
        add_short_link(app, utub_url_id, minted_by=SECOND_USER_ID)
    assert _delete_utub(client, csrf_token, FIRST_UTUB_ID).status_code == 200

    assert _restore_utub(client, csrf_token, FIRST_UTUB_ID).status_code == 200

    assert _link_ids(app) == []
    for item in _get_utub(client, FIRST_UTUB_ID)[MODELS.URLS]:
        _assert_no_link_state(item)
    assert post_mint(client, csrf_token, FIRST_UTUB_ID, url_ids[0]).status_code == 200
    assert _link_ids(app) == [url_ids[0]]
