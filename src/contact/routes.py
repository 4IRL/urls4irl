from flask import (
    Blueprint,
)

from src import limiter
from src.api_common.responses import FlaskResponse
from src.contact.contact_us import load_contact_us_page, validate_and_contact
from src.contact.forms import ContactForm
from src.utils.constants import provide_config_for_constants

contact = Blueprint("contact", __name__)


@contact.context_processor
def provide_constants():
    return provide_config_for_constants()


@contact.route("/contact", methods=["GET", "POST"])
@limiter.limit("5 per hour, 10 per day", methods=["POST"])
def contact_us() -> str | FlaskResponse:
    contact_form: ContactForm = ContactForm()

    if contact_form.validate_on_submit():
        return validate_and_contact(contact_form)

    return load_contact_us_page(contact_form)
