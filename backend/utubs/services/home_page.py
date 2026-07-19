from flask import abort, current_app, render_template, request
from flask_login import current_user
from sqlalchemy.exc import DataError

from backend.app_logger import warning_log
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.users import UtubSummaryListSchema
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.utub_strs import (
    MOBILE_PANEL_QUERY_PARAM,
    UTUB_ID_QUERY_PARAM,
)

# The only query params the /home route recognizes: the UTub to preselect and
# the mobile panel to restore (added for the mobile back/forward panel feature).
# Any other param — or a repeated recognized one — is rejected as malformed.
RECOGNIZED_HOME_QUERY_PARAMS = frozenset(
    {UTUB_ID_QUERY_PARAM, MOBILE_PANEL_QUERY_PARAM}
)


def render_home_page() -> str:
    utubs_for_this_user = UtubSummaryListSchema.from_user(current_user).model_dump(
        by_alias=True
    )[MODELS.UTUBS]

    return render_template(
        "pages/home.html",
        utubs_for_this_user=utubs_for_this_user,
        is_prod_or_testing=current_app.config.get(CONFIG_ENVS.TESTING_OR_PROD, True),
    )


def validate_home_query_params() -> bool:
    """
    Validates the /home query params. Only ``UTubID`` and the mobile panel
    param are recognized, each allowed at most once. A repeated recognized
    param or any unrecognized param is rejected.

    Returns:
        (bool): True if every present query param is a recognized, non-repeated
            key; False otherwise.
    """
    query_param_keys = [key for key, _ in request.args.items(multi=True)]

    if len(query_param_keys) != len(set(query_param_keys)):
        warning_log(f"User={current_user.id} | Too many query parameters")
        return False

    unrecognized_keys = [
        key for key in query_param_keys if key not in RECOGNIZED_HOME_QUERY_PARAMS
    ]
    if unrecognized_keys:
        warning_log(
            f"User={current_user.id} | "
            f"Unrecognized query parameter(s): {unrecognized_keys}"
        )
        return False

    return True


def validate_user_is_member_of_utub_on_home_page_with_query_param(utub_id: str) -> bool:
    """
    Given a string query param representing a UTub ID, verify the current user
    in this request is a member of that UTub.

    Args:
        utub_id (str): The ID of the UTub to verify membership for the current user

    Returns:
        (bool): True if current user is member of UTub with ID of the given query param
    """
    try:
        if (
            Utubs.query.get_or_404(int(utub_id)) is None
            or Utub_Members.query.get((int(utub_id), current_user.id)) is None
        ):
            warning_log(f"User={current_user.id} not a member of UTub.id={utub_id}")
            return False

        return True

    except (ValueError, DataError):
        # Handle invalid UTubID passed as query parameter
        warning_log(f"Invalid UTub.id={utub_id} for User={current_user.id}")
        abort(404)
