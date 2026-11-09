from typing import AbstractSet, Tuple
from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.urls import UtubUrlSchema
from backend.utils.all_routes import ROUTES
from backend.utils.strings.form_strs import URL_FORM
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utubs.services.trash_predicates import count_trash_rows_for_user
from tests.integration.trash.trash_helpers import (
    AJAX_HEADERS,
    FIRST_USER_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    THIRD_USER_ID,
    assert_not_in_trash_response,
    get_row_state,
    get_trash_url_ids,
    login_as_user,
    post_restore,
    post_restore_urls,
    row_exists,
)
from tests.utils_for_test import (
    HideListSeed,
    get_utub_url_id,
    remove_member,
    trash_utub,
    trash_utub_url,
)

pytestmark = pytest.mark.trash

THIRD_UTUB_ID = 3


def _purge(client: FlaskClient, csrf_token: str, utub_url_id: int):
    return client.delete(
        url_for(ROUTES.URLS.PURGE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=utub_url_id),
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def _empty_urls_tab(client: FlaskClient, csrf_token: str):
    listed_at = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS).json[
        MODELS.LISTED_AT
    ]
    return client.post(
        url_for(ROUTES.UTUBS.EMPTY_TRASH),
        json={"scope": "urls", "listedAt": listed_at},
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def _trash_count(app: Flask, user_id: int) -> int:
    with app.app_context():
        return count_trash_rows_for_user(user_id=user_id)


def _orphan_and_trash_url_two(app: Flask) -> int:
    """User 2 adds URL 2 (fixture), is removed from UTub 1, and the row is trashed."""
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
    trash_utub_url(app, row_id, deleted_by=1)
    return row_id


def test_plain_member_lists_and_counts_orphaned_trashed_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a trashed URL in UTub 1 has left the UTub
    WHEN plain member user 3 reads the Trash list and the Trash count
    THEN the orphaned URL is listed and counted
    """
    client, _, _, app = login_third_user_without_register
    row_id = _orphan_and_trash_url_two(app)

    assert get_trash_url_ids(client) == [row_id]
    assert _trash_count(app, THIRD_USER_ID) == 1


def test_plain_member_restores_orphaned_url_and_adder_is_kept(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a trashed URL in UTub 1 has left the UTub
    WHEN plain member user 3 restores it in place
    THEN it is 200, live again, and still records user 2 as its adder (still orphaned)
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = _orphan_and_trash_url_two(app)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    after = get_row_state(app, row_id)
    assert after["deleted_at"] is None
    assert after["user_id"] == SECOND_USER_ID


def test_plain_member_purges_orphaned_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a trashed URL in UTub 1 has left the UTub
    WHEN plain member user 3 deletes it forever
    THEN it is 200 and the row is gone
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = _orphan_and_trash_url_two(app)

    response = _purge(client, csrf_token, row_id)

    assert response.status_code == 200
    assert not row_exists(app, row_id)


def test_empty_trash_includes_orphaned_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a trashed URL in UTub 1 has left the UTub
    WHEN plain member user 3 empties the URLs tab
    THEN the orphaned row is purged
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = _orphan_and_trash_url_two(app)

    hidden_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, hidden_row_id, deleted_by=1)

    response = _empty_urls_tab(client, csrf_token)

    assert response.status_code == 200
    assert not row_exists(app, row_id)
    assert row_exists(app, hidden_row_id)


def test_trashed_url_of_current_member_stays_hidden_from_plain_member(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 is still a member of UTub 1 and their URL is trashed
    WHEN plain member user 3 reads, counts, restores and purges it
    THEN it is invisible and non-actionable, exactly as before the orphan rule
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    before = get_row_state(app, row_id)

    assert get_trash_url_ids(client) == []
    assert _trash_count(app, THIRD_USER_ID) == 0
    restore_response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)
    assert_not_in_trash_response(restore_response)
    assert_not_in_trash_response(_purge(client, csrf_token, row_id))
    assert get_row_state(app, row_id) == before


def test_orphaned_url_in_trashed_utub_stays_creator_only(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 (an URL's adder) has left UTub 1 and the whole UTub is trashed
    WHEN plain member user 3 lists, counts, restores and purges that URL
    THEN nothing is visible or actionable: the orphan rule is live-UTub only
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=1)
    before = get_row_state(app, row_id)

    assert get_trash_url_ids(client) == []
    assert _trash_count(app, THIRD_USER_ID) == 0
    restore_response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)
    assert_not_in_trash_response(restore_response)
    assert_not_in_trash_response(_purge(client, csrf_token, row_id))
    assert get_row_state(app, row_id) == before


def test_bulk_in_place_restore_of_orphaned_url_is_deletable_by_plain_member(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a trashed URL in UTub 1 has left the UTub
    WHEN plain member user 3 bulk-restores it in place
    THEN the restored card is deletable by user 3 and still names user 2 as its adder
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = _orphan_and_trash_url_two(app)

    response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [row_id])

    assert response.status_code == 200
    restored = response.json[MODELS.RESTORED]
    assert [card[MODELS.UTUB_URL_ID] for card in restored] == [row_id]
    assert restored[0][MODELS.CAN_DELETE] is True
    assert restored[0][MODELS.ADDED_BY] == SECOND_USER_ID


def test_destination_restore_of_orphaned_url_credits_the_restorer(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a URL has left UTub 1 and UTub 3, and UTub 1 is trashed
    WHEN creator user 1 restores that URL into UTub 3
    THEN the card credits user 1 (not the departed adder) and is deletable
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
    remove_member(app, THIRD_UTUB_ID, SECOND_USER_ID)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)

    response = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": THIRD_UTUB_ID}
    )

    assert response.status_code == 200
    card = response.json[MODELS.URL]
    assert card[MODELS.UTUB_URL_ID] == row_id
    assert card[MODELS.ADDED_BY] == FIRST_USER_ID
    assert card[MODELS.ADDED_BY] != SECOND_USER_ID
    assert card[MODELS.CAN_DELETE] is True


def test_readded_member_is_adder_again_and_their_trashed_url_is_hidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 3 added URL 3, left UTub 1 and was re-added to it, and a manager then
        trashed URL 3
    WHEN plain member user 2 reads the Trash list
    THEN URL 3 is absent, because user 3 is a member (the adder) again
    """
    client, csrf_token, _, app = login_second_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 3)
    remove_member(app, FIRST_UTUB_ID, THIRD_USER_ID)
    with app.app_context():
        db.session.add(
            Utub_Members(
                utub_id=FIRST_UTUB_ID,
                user_id=THIRD_USER_ID,
                member_role=Member_Role.MEMBER,
            )
        )
        db.session.commit()

    delete_response = client.delete(
        url_for(ROUTES.URLS.DELETE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=row_id),
        headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )
    edit_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE, utub_id=FIRST_UTUB_ID, utub_url_id=row_id
        ),
        json={URL_FORM.URL_TITLE: "Not allowed"},
        headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )
    assert delete_response.status_code == 403
    assert edit_response.status_code == 403

    trash_utub_url(app, row_id, deleted_by=1)

    assert get_trash_url_ids(client) == []
    assert _trash_count(app, SECOND_USER_ID) == 0


def _create_trashed_source_utub_with_url(app: Flask, creator_id: int) -> int:
    """Create a trashed UTub owned by ``creator_id`` holding one URL they added.

    Returns the URL's ``Utub_Urls`` id. Used as the origin of a destination restore.
    """
    with app.app_context():
        utub = Utubs(name="Source UTub", utub_creator=creator_id, utub_description="")
        membership = Utub_Members(member_role=Member_Role.CREATOR)
        membership.to_user = Users.query.get(creator_id)
        utub.members.append(membership)
        db.session.add(utub)
        db.session.commit()
        url = Urls(
            normalized_url="https://hide-list-source.example.com",
            current_user_id=creator_id,
        )
        db.session.add(url)
        db.session.commit()
        utub_url = Utub_Urls()
        utub_url.user_id = creator_id
        utub_url.url_title = "Source URL"
        utub_url.url_id = url.id
        utub_url.utub_id = utub.id
        db.session.add(utub_url)
        db.session.commit()
        source_utub_id, utub_url_id = utub.id, utub_url.id
    trash_utub(app, source_utub_id, deleted_by=creator_id)
    return utub_url_id


def _restore_as_hidden_list_plain_member(
    app: Flask, seed: HideListSeed, site: str
) -> tuple[list[int | None], str, list[AbstractSet[int] | None]]:
    """Run one restore site as plain member A in the hidden-list UTub.

    Spies on ``UtubUrlSchema.from_orm_url``. Returns the adder ids in the response,
    the raw response body and the ``visible_member_ids`` argument of every call.
    """
    member_a = seed.member_a_id
    own_row = seed.utub_url_ids[member_a]
    former_row = seed.utub_url_ids[seed.former_member_id]
    if site == "destination":
        source_row = _create_trashed_source_utub_with_url(app, member_a)
        source_utub_id = get_row_state(app, source_row)["utub_id"]
    else:
        trash_utub_url(app, own_row, deleted_by=seed.owner_id)
        trash_utub_url(app, former_row, deleted_by=seed.owner_id)

    with mock.patch.object(
        UtubUrlSchema, "from_orm_url", wraps=UtubUrlSchema.from_orm_url
    ) as spy:
        with login_as_user(app, member_a) as (client, csrf_token):
            if site == "destination":
                response = post_restore(
                    client,
                    csrf_token,
                    source_utub_id,
                    source_row,
                    {"destUtubId": seed.utub_id},
                )
                assert response.status_code == 200
                adders = [response.json[MODELS.URL][MODELS.ADDED_BY]]
            elif site == "in_place":
                adders = []
                for row_id in (own_row, former_row):
                    response = post_restore(client, csrf_token, seed.utub_id, row_id)
                    assert response.status_code == 200
                    adders.append(response.json[MODELS.URL][MODELS.ADDED_BY])
            else:
                response = post_restore_urls(
                    client, csrf_token, seed.utub_id, [own_row, former_row]
                )
                assert response.status_code == 200
                adders = [
                    card[MODELS.ADDED_BY] for card in response.json[MODELS.RESTORED]
                ]
    visible_args = [call.kwargs["visible_member_ids"] for call in spy.call_args_list]
    return adders, response.get_data(as_text=True), visible_args


@pytest.mark.parametrize(
    "site, expected_adders",
    [
        pytest.param("in_place", ["member_a_id", "former_member_id"], id="in_place"),
        pytest.param("bulk", ["member_a_id", "former_member_id"], id="bulk"),
        pytest.param("destination", ["member_a_id"], id="destination"),
    ],
)
def test_plain_member_restore_in_hidden_list_utub_never_echoes_a_hidden_member(
    app: Flask, seed_hide_list, site: str, expected_adders: list[str]
):
    """
    GIVEN a UTub with the member list hidden, where plain member A restores URLs
        (their own and a former member's) in place, in bulk or into it as destination
    WHEN the response is built
    THEN every adder is A's own id or the former member's id, no hidden member's
        id or username appears, and the site passed a visible-id set that excludes
        the hidden plain member B to the serializer
    """
    seed = seed_hide_list(True)

    adders, body, visible_args = _restore_as_hidden_list_plain_member(app, seed, site)

    assert adders == [getattr(seed, name) for name in expected_adders]
    assert seed.usernames[seed.member_b_id] not in body
    assert visible_args
    for visible_ids in visible_args:
        assert visible_ids is not None
        assert seed.member_b_id not in visible_ids
        assert visible_ids == {seed.owner_id, seed.co_owner_id, seed.member_a_id}


def test_trash_list_hides_deleter_of_orphan_row_from_plain_member(
    app: Flask, seed_hide_list
):
    """
    GIVEN a hidden-list UTub where the former member's URL (an orphan) and plain
        member A's own URL were trashed by hidden plain member B
    WHEN plain member A reads the Trash list
    THEN both rows are listed with a null deleter id and username, no username of B
        appears anywhere, the former member's name and A's own name are kept, and
        A's own id is never masked
    """
    seed = seed_hide_list(True)
    own_row = seed.utub_url_ids[seed.member_a_id]
    former_row = seed.utub_url_ids[seed.former_member_id]
    trash_utub_url(app, own_row, deleted_by=seed.member_b_id)
    trash_utub_url(app, former_row, deleted_by=seed.member_b_id)

    with login_as_user(app, seed.member_a_id) as (client, _):
        response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)

    assert response.status_code == 200
    rows = {item[MODELS.UTUB_URL_ID]: item for item in response.json[MODELS.URLS]}
    assert set(rows) == {own_row, former_row}
    for item in rows.values():
        assert item[MODELS.DELETED_BY] is None
        assert item[MODELS.DELETED_BY_USERNAME] is None
    assert rows[own_row][MODELS.ADDED_BY] == seed.member_a_id
    assert rows[own_row][MODELS.ADDED_BY_USERNAME] == seed.usernames[seed.member_a_id]
    assert rows[former_row][MODELS.ADDED_BY] == seed.former_member_id
    body = response.get_data(as_text=True)
    assert seed.usernames[seed.member_b_id] not in body


def test_trash_list_keeps_visible_deleter_names_for_plain_member(
    app: Flask, seed_hide_list
):
    """
    GIVEN a hidden-list UTub where the owner and A themself trashed A's two URLs
    WHEN plain member A reads the Trash list
    THEN the owner (visible) and A (the viewer) keep their ids and usernames
    """
    seed = seed_hide_list(True)
    own_row = seed.utub_url_ids[seed.member_a_id]
    former_row = seed.utub_url_ids[seed.former_member_id]
    trash_utub_url(app, own_row, deleted_by=seed.owner_id)
    trash_utub_url(app, former_row, deleted_by=seed.member_a_id)

    with login_as_user(app, seed.member_a_id) as (client, _):
        response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)

    rows = {item[MODELS.UTUB_URL_ID]: item for item in response.json[MODELS.URLS]}
    assert rows[own_row][MODELS.DELETED_BY] == seed.owner_id
    assert rows[own_row][MODELS.DELETED_BY_USERNAME] == seed.usernames[seed.owner_id]
    assert rows[former_row][MODELS.DELETED_BY] == seed.member_a_id
    assert (
        rows[former_row][MODELS.DELETED_BY_USERNAME] == seed.usernames[seed.member_a_id]
    )


@pytest.mark.parametrize("hide_member_list", [True, False, None])
def test_owner_trash_list_is_unchanged_by_hide_setting(
    app: Flask, seed_hide_list, hide_member_list: bool | None
):
    """
    GIVEN the owner trashed hidden-list-UTub URLs added by plain members A and B
        (B deleted one of them first)
    WHEN the owner reads the Trash list with the setting on, off or absent
    THEN every adder and deleter id and username is present
    """
    seed = seed_hide_list(hide_member_list)
    row_a = seed.utub_url_ids[seed.member_a_id]
    row_b = seed.utub_url_ids[seed.member_b_id]
    trash_utub_url(app, row_a, deleted_by=seed.member_b_id)
    trash_utub_url(app, row_b, deleted_by=seed.owner_id)

    with login_as_user(app, seed.owner_id) as (client, _):
        response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)

    rows = {item[MODELS.UTUB_URL_ID]: item for item in response.json[MODELS.URLS]}
    assert rows[row_a][MODELS.ADDED_BY] == seed.member_a_id
    assert rows[row_a][MODELS.ADDED_BY_USERNAME] == seed.usernames[seed.member_a_id]
    assert rows[row_a][MODELS.DELETED_BY] == seed.member_b_id
    assert rows[row_a][MODELS.DELETED_BY_USERNAME] == seed.usernames[seed.member_b_id]
    assert rows[row_b][MODELS.ADDED_BY] == seed.member_b_id
    assert rows[row_b][MODELS.DELETED_BY] == seed.owner_id


def test_trash_masking_is_per_utub(app: Flask, seed_hide_list):
    """
    GIVEN plain member A, who is in a hidden-list UTub (B hidden) and in a second
        UTub with no hide setting where B is a visible member, and B trashed A's
        URL in each
    WHEN A reads the Trash list
    THEN B is masked as the deleter only in the hidden-list UTub
    """
    seed = seed_hide_list(True)
    second_seed_row = _create_second_visible_utub(app, seed)
    first_row = seed.utub_url_ids[seed.member_a_id]
    trash_utub_url(app, first_row, deleted_by=seed.member_b_id)
    trash_utub_url(app, second_seed_row, deleted_by=seed.member_b_id)

    with login_as_user(app, seed.member_a_id) as (client, _):
        response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)

    rows = {item[MODELS.UTUB_URL_ID]: item for item in response.json[MODELS.URLS]}
    assert rows[first_row][MODELS.DELETED_BY] is None
    assert rows[first_row][MODELS.DELETED_BY_USERNAME] is None
    assert rows[second_seed_row][MODELS.DELETED_BY] == seed.member_b_id
    assert (
        rows[second_seed_row][MODELS.DELETED_BY_USERNAME]
        == seed.usernames[seed.member_b_id]
    )


def _create_second_visible_utub(app: Flask, seed: HideListSeed) -> int:
    """Create a UTub owned by the seed owner with plain members A and B and no stored
    settings, holding one URL added by A. Returns that URL's ``Utub_Urls`` id."""
    with app.app_context():
        utub = Utubs(
            name="Visible UTub", utub_creator=seed.owner_id, utub_description=""
        )
        for user_id, role in (
            (seed.owner_id, Member_Role.CREATOR),
            (seed.member_a_id, Member_Role.MEMBER),
            (seed.member_b_id, Member_Role.MEMBER),
        ):
            membership = Utub_Members(member_role=role)
            membership.to_user = Users.query.get(user_id)
            utub.members.append(membership)
        db.session.add(utub)
        db.session.commit()
        url = Urls(
            normalized_url="https://visible-utub.example.com",
            current_user_id=seed.member_a_id,
        )
        db.session.add(url)
        db.session.commit()
        utub_url = Utub_Urls()
        utub_url.user_id = seed.member_a_id
        utub_url.url_title = "Visible UTub URL"
        utub_url.url_id = url.id
        utub_url.utub_id = utub.id
        db.session.add(utub_url)
        db.session.commit()
        return utub_url.id
