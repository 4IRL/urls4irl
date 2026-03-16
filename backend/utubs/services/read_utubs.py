from flask_login import current_user
from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log
from backend.models.utubs import Utubs
from backend.schemas.users import UtubSummaryListSchema
from backend.schemas.utubs import UtubDetailSchema


def get_single_utub_for_user(current_utub: Utubs) -> FlaskResponse:
    utub_schema = UtubDetailSchema.from_utub(current_utub, current_user.id)

    current_utub.set_last_updated()
    db.session.commit()

    safe_add_log(f"Retrieving UTub.id={current_utub.id} from direct route")
    return APIResponse(data=utub_schema, status_code=200).to_response()


def get_all_utubs_of_user() -> FlaskResponse:
    # TODO: Should serialized summary be utubID and utubName
    # instead of id and name?
    safe_add_log(f"Returning UTubs for User={current_user.id}")

    return APIResponse(
        data=UtubSummaryListSchema.from_user(current_user), status_code=200
    ).to_response()
