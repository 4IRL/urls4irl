from typing import Tuple

from sqlalchemy import case, func

from src import db
from src.models.utub_url_tags import Utub_Url_Tags
from src.urls.forms import (
    UpdateURLForm,
    UpdateURLTitleForm,
    NewURLForm,
)
from src.utils.strings.model_strs import MODELS


def build_form_errors(
    form: UpdateURLForm | UpdateURLTitleForm | NewURLForm,
) -> dict[str, list[str]]:
    errors = {}
    if isinstance(form, NewURLForm):
        if form.url_string.errors:
            errors[MODELS.URL_STRING] = form.url_string.errors
        if form.url_title.errors:
            errors[MODELS.URL_TITLE] = form.url_title.errors
    elif isinstance(form, UpdateURLForm):
        if form.url_string.errors:
            errors[MODELS.URL_STRING] = form.url_string.errors
    else:
        if form.url_title.errors:
            errors[MODELS.URL_TITLE] = form.url_title.errors
    return errors


def get_utub_url_tag_ids_and_utub_tag_ids_on_utub_url(
    utub_id: int, utub_url_id: int
) -> Tuple[list[int], list[int]]:
    primary_key_and_tag_ids = (
        db.session.query(Utub_Url_Tags)
        .filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == utub_url_id,
        )
        .with_entities(Utub_Url_Tags.id, Utub_Url_Tags.utub_tag_id)
        .all()
    )
    return parse_utub_url_tag_ids_and_utub_tag_ids(primary_key_and_tag_ids)


def parse_utub_url_tag_ids_and_utub_tag_ids(
    primary_key_and_tag_ids: list[Utub_Url_Tags],
) -> Tuple[list[int], list[int]]:
    utub_tag_ids = []
    utub_url_tag_ids = []

    for utub_url_tag_id, utub_tag_id in primary_key_and_tag_ids:
        utub_tag_ids.append(utub_tag_id)
        utub_url_tag_ids.append(utub_url_tag_id)

    return utub_url_tag_ids, utub_tag_ids


def get_utub_url_tag_ids_and_count_in_utub(
    utub_id: int, utub_tag_ids: list[int]
) -> list[tuple[int, int]]:
    tag_ids_and_count_in_utub = (
        db.session.query(
            Utub_Url_Tags.utub_tag_id,
            case([(func.count() > 0, func.count() - 1)], else_=0).label("count"),
        )
        .filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_tag_id.in_(utub_tag_ids),
        )
        .group_by(Utub_Url_Tags.utub_tag_id)
        .all()
    )
    return tag_ids_and_count_in_utub
