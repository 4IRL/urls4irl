from typing import Tuple

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


def parse_pk_and_tag_ids(primary_key_and_tag_ids: list) -> Tuple[list[int], list[int]]:
    tag_ids = []
    pks = []

    for pk, tag_id in primary_key_and_tag_ids:
        tag_ids.append(tag_id)
        pks.append(pk)

    return pks, tag_ids
