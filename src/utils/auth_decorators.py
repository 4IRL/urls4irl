from typing import Callable
from flask import abort, g, jsonify, request, session, url_for, redirect
from flask_login import login_required, current_user
from functools import wraps

from src.app_logger import critical_log, warning_log
from src.models.utub_members import Member_Role, Utub_Members
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs
from src.utils.all_routes import ROUTES
from src.utils.request_utils import is_adder_of_utub_url, is_current_utub_creator
from src.utils.strings.email_validation_strs import EMAILS
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.url_validation_strs import URL_VALIDATION
from src.utils.strings.utub_strs import UTUB_FAILURE


def xml_http_request_only(func: Callable) -> Callable:
    """Ensures JSON not viewed in browser by verifying the request is an XMLHTTPRequest"""

    @wraps(func)
    def decorated_view(*args, **kwargs):
        if (
            request.headers.get(URL_VALIDATION.X_REQUESTED_WITH, None)
            != URL_VALIDATION.XMLHTTPREQUEST
        ):
            warning_log(f"User={current_user.id} did not make an AJAX request")
            return redirect(url_for(ROUTES.UTUBS.HOME))
        return func(*args, **kwargs)

    return decorated_view


def email_validation_required(func: Callable) -> Callable:
    @wraps(func)
    @login_required
    def decorated_view(*args, **kwargs):
        is_email_validated: bool | None = session.get(EMAILS.EMAIL_VALIDATED_SESS_KEY)

        if is_email_validated is None:
            session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = current_user.email_validated
            is_email_validated = session[EMAILS.EMAIL_VALIDATED_SESS_KEY]

        if not is_email_validated:
            return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))

        return func(*args, **kwargs)

    return decorated_view


def utub_membership_required(func: Callable) -> Callable:
    @wraps(func)
    @email_validation_required
    def decorated_view(*args, **kwargs):
        utub_id: int | None = kwargs.get("utub_id")
        if utub_id is None:
            abort(404)

        member: Utub_Members = Utub_Members.query.get_or_404((utub_id, current_user.id))
        g.is_creator = member.member_role in (
            Member_Role.CREATOR,
            Member_Role.CO_CREATOR,
        )
        utub: Utubs = Utubs.query.get_or_404(utub_id)
        g.utub_id = utub.id
        kwargs["current_utub"] = utub

        return func(*args, **kwargs)

    return decorated_view


def utub_creator_required(func: Callable):
    @wraps(func)
    @utub_membership_required
    def decorated_view(*args, **kwargs):
        if not is_current_utub_creator():
            utub_id: int = kwargs["utub_id"]
            current_utub: Utubs = kwargs["current_utub"]
            critical_log(
                f"User={current_user.id} not creator: UTub.id={utub_id} | UTub.name={current_utub.name}"
            )
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: UTUB_FAILURE.NOT_AUTHORIZED,
                    }
                ),
                403,
            )
        return func(*args, **kwargs)

    return decorated_view


def utub_membership_with_valid_url_in_utub_required(func: Callable) -> Callable:
    @wraps(func)
    @utub_membership_required
    def decorated_view(*args, **kwargs):
        utub_url_id: int | None = kwargs.get("utub_url_id")
        if utub_url_id is None:
            abort(404)

        current_utub_url: Utub_Urls = Utub_Urls.query.get_or_404(utub_url_id)
        if current_utub_url.utub_id != g.utub_id:
            critical_log(
                f"Invalid UTubURL.id={utub_url_id} for UTub.id={g.utub_id} by UTubUser={current_user.id}"
            )
            abort(404)

        kwargs["current_utub_url"] = current_utub_url
        g.user_added_url = current_utub_url.user_id == current_user.id

        return func(*args, **kwargs)

    return decorated_view


def utub_membership_and_utub_url_creator_required(func: Callable) -> Callable:
    @wraps(func)
    @utub_membership_with_valid_url_in_utub_required
    def decorated_view(*args, **kwargs):
        if not is_adder_of_utub_url():
            abort(404)

        return func(*args, **kwargs)

    return decorated_view


def _verify_and_get_utub_tag(**kwargs) -> Utub_Tags:
    utub_tag_id: int | None = kwargs.get("utub_tag_id")
    if utub_tag_id is None:
        abort(404)

    current_utub_tag: Utub_Tags = Utub_Tags.query.get_or_404(utub_tag_id)
    if current_utub_tag.utub_id != g.utub_id:
        critical_log(
            f"Invalid UTubTag.id={utub_tag_id} for UTub.id={g.utub_id} by UTubUser={current_user.id}"
        )
        abort(404)

    return current_utub_tag


def utub_membership_with_valid_utub_tag(func: Callable) -> Callable:
    @wraps(func)
    @utub_membership_required
    def decorated_view(*args, **kwargs):
        kwargs["current_utub_tag"] = _verify_and_get_utub_tag(**kwargs)

        return func(*args, **kwargs)

    return decorated_view


def utub_membership_with_valid_url_tag(func: Callable) -> Callable:
    @wraps(func)
    @utub_membership_with_valid_url_in_utub_required
    def decorated_view(*args, **kwargs):
        current_utub_tag = _verify_and_get_utub_tag(**kwargs)
        utub_url_id: int | None = kwargs.get("utub_url_id")
        kwargs["current_utub_tag"] = current_utub_tag

        current_url_tag: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == g.utub_id,
            Utub_Url_Tags.utub_url_id == utub_url_id,
            Utub_Url_Tags.utub_tag_id == current_utub_tag.id,
        ).first_or_404()

        if current_url_tag.utub_id != g.utub_id:
            critical_log(
                f"Invalid UTubURLTag.id={current_url_tag.id} for UTub.id={g.utub_id} by UTubUser={current_user.id}"
            )
            abort(404)

        kwargs["current_url_tag"] = current_url_tag

        return func(*args, **kwargs)

    return decorated_view
