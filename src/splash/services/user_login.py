from urllib.parse import parse_qs, urlencode, urlparse
from flask import render_template, request, url_for
from flask_login import current_user, login_user
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import safe_add_log, warning_log
from src.models.users import Users
from src.models.utub_members import Utub_Members
from src.splash.forms import LoginForm
from src.utils.all_routes import ROUTES
from src.utils.strings.user_strs import USER_FAILURE
from src.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM


def handle_invalid_user_login_form_inputs(login_form: LoginForm) -> FlaskResponse | str:
    # Input form errors
    if login_form.errors is not None:
        warning_log("User had form errors on login")
        return APIResponse(
            status_code=400,
            message=USER_FAILURE.UNABLE_TO_LOGIN,
            error_code=2,
            errors=login_form.errors,
        ).to_response()

    return render_template("components/splash/login.html", login_form=login_form)


def login_user_to_u4i(login_form: LoginForm) -> FlaskResponse | str:
    username = login_form.username.data
    user: Users = Users.query.filter(Users.username == username).first()

    login_user(user)  # Can add Remember Me functionality here

    if not user.email_validated:
        warning_log(f"User={user.id} not email validated")
        return APIResponse(
            status_code=401,
            message=USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED,
            error_code=1,
        ).to_response()

    safe_add_log(f"Logging User.id={user.id} in")

    # next query param takes user to the page they wanted to originally before being logged in
    next_page = _verify_and_provide_next_page(request.args.to_dict())
    redirect_url = next_page if next_page else url_for(ROUTES.UTUBS.HOME)

    return APIResponse(
        status_code=200,
        data={"redirect_url": redirect_url},
    ).to_response()


def _verify_and_provide_next_page(request_args: dict[str, str]) -> str:
    url = ""
    if _has_invalid_next_query_param(request_args):
        return url

    rel_url = urlparse(request_args.get("next"))
    if rel_url.path != url_for(ROUTES.UTUBS.HOME):
        return url

    query_params = parse_qs(str(rel_url.query))
    if len(query_params) != 1 or UTUB_ID_QUERY_PARAM not in query_params:
        return url

    utub_id_vals = query_params.get(UTUB_ID_QUERY_PARAM, None)
    if not utub_id_vals or len(utub_id_vals) != 1:
        return url

    utub_id = utub_id_vals[0]

    if not utub_id.isdigit() or int(utub_id) <= 0:
        return url

    if Utub_Members.query.get((int(utub_id), current_user.id)) is None:
        return url

    url = (
        f"{url_for(ROUTES.UTUBS.HOME)}?{urlencode({UTUB_ID_QUERY_PARAM: int(utub_id)})}"
    )
    safe_add_log(f"Routing user to UTub.id={utub_id}")
    return url


def _has_invalid_next_query_param(request_args: dict[str, str]) -> bool:
    return (
        len(request_args) != 1
        or "next" not in request_args
        or not isinstance(request_args.get("next"), str)
    )
