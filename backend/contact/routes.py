from flask import (
    Blueprint,
)

from backend import limiter
from backend.api_common.parse_request import api_route
from backend.api_common.responses import FlaskResponse
from backend.contact.constants import CONTACT_FORM_CONSTANTS
from backend.contact.contact_us import load_contact_us_page, validate_and_contact
from backend.schemas.contact import ContactResponseSchema
from backend.schemas.requests import ContactRequest
from backend.utils.constants import provide_config_for_constants

contact = Blueprint("contact", __name__)


@contact.context_processor
def provide_constants():
    return provide_config_for_constants()


@contact.route("/contact", methods=["GET"])
def contact_us() -> str:
    return load_contact_us_page()


@contact.route("/contact", methods=["POST"])
@api_route(
    request_schema=ContactRequest,
    response_schema=ContactResponseSchema,
    error_message="Unable to submit contact form.",
    error_code=1,
    ajax_required=False,
)
@limiter.limit(
    f"{CONTACT_FORM_CONSTANTS.RATE_LIMIT_PER_HOUR} per hour, {CONTACT_FORM_CONSTANTS.RATE_LIMIT_PER_DAY} per day",
    methods=["POST"],
)
def submit_contact_us(contact_request: ContactRequest) -> FlaskResponse:
    return validate_and_contact(contact_request.subject, contact_request.content)
