from itertools import islice
from flask import abort, current_app, render_template, request
from flask_login import current_user
from sqlalchemy.exc import DataError

from src.app_logger import warning_log
from src.models.utub_members import Utub_Members
from src.models.utubs import Utubs
from src.utils.strings.config_strs import CONFIG_ENVS
from src.utils.strings.model_strs import MODELS
from src.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM


def render_home_page() -> str:
    utub_details = current_user.serialized_on_initial_load

    return render_template(
        "home.html",
        utubs_for_this_user=utub_details[MODELS.UTUBS],
        is_prod_or_testing=current_app.config.get(CONFIG_ENVS.TESTING_OR_PROD, True),
    )


def validate_query_param_is_utub_id() -> bool:
    """
    Validates if a query param for this request is UTubID.

    Returns:
        (bool): If query param is "UTubID"
    """
    # Count total number of query param keys/values, even for repeats
    query_param_pairs = list(islice(request.args.items(multi=True), 2))

    if len(query_param_pairs) != 1 or UTUB_ID_QUERY_PARAM not in request.args.keys():
        log_msg = (
            "Too many query parameters"
            if len(query_param_pairs) != 1
            else "Does not contain 'UTubID' as a query parameter"
        )
        log_msg = f"User={current_user.id} | " + log_msg
        warning_log(log_msg)
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
