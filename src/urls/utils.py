from src.urls.forms import (
    EditURLForm,
    EditURLTitleForm,
    NewURLForm,
)
from src.utils.strings.model_strs import MODELS


def build_form_errors(
    form: EditURLForm | EditURLTitleForm | NewURLForm,
) -> dict[str, list[str]]:
    errors = {}
    if isinstance(form, NewURLForm):
        if form.url_string.errors:
            errors[MODELS.URL_STRING] = form.url_string.errors
        if form.url_title.errors:
            errors[MODELS.URL_TITLE] = form.url_title.errors
    elif isinstance(form, EditURLForm):
        if form.url_string.errors:
            errors[MODELS.URL_STRING] = form.url_string.errors
    else:
        if form.url_title.errors:
            errors[MODELS.URL_TITLE] = form.url_title.errors
    return errors
