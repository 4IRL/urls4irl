from src.utubs.forms import UTubForm, UTubDescriptionForm, UTubNewNameForm
from src.utils.strings.form_strs import UTUB_FORM


def build_form_errors(
    form: UTubDescriptionForm | UTubForm | UTubNewNameForm,
) -> dict[str, list[str]]:
    errors = {}
    if isinstance(form, UTubDescriptionForm):
        if form.description.errors:
            errors[UTUB_FORM.UTUB_DESCRIPTION] = form.description.errors

    elif isinstance(form, UTubForm):
        if form.name.errors:
            errors[UTUB_FORM.UTUB_NAME] = form.name.errors
        if form.description.errors:
            errors[UTUB_FORM.UTUB_DESCRIPTION] = form.description.errors

    elif isinstance(form, UTubNewNameForm):
        if form.name.errors:
            errors[UTUB_FORM.UTUB_NAME] = form.name.errors

    return errors
