from flask import redirect, url_for, request, render_template, abort, jsonify, Blueprint
from flask_login import current_user

from src.models import Utub
from src.utils.email_validation import email_validation_required

main = Blueprint("main", __name__)


@main.route("/", methods=["GET"])
def splash():
    """Splash page for an unlogged in user."""
    if current_user.is_authenticated:
        if not current_user.email_confirm.is_validated:
            return render_template("splash.html", email_validation_modal=True)
        return redirect(url_for("main.home"))
    return render_template("splash.html")


@main.route("/home", methods=["GET"])
@email_validation_required
def home():
    """
    Splash page for logged in user. Loads and displays all UTubs, and contained URLs.

    Args:
        /home : With no args, this returns all UTubIDs for the given user
        /home?UTubID=[int] = Where the integer value is the associated UTubID
                                that the user clicked on

    Returns:
        - All UTubIDs if no args
        - Requested UTubID if a valid arg

    """
    if not request.args:
        # User got here without any arguments in the URL
        # Therefore, only provide UTub name and UTub ID
        utub_details = jsonify(current_user.serialized_on_initial_load)
        return render_template("home.html", utubs_for_this_user=utub_details.json)

    elif len(request.args) > 1:
        # Too many args in URL
        print("Too many arguments?")
        abort(404)

    else:
        if "UTubID" not in request.args:
            # Wrong argument
            abort(404)

        requested_id = request.args.get("UTubID")

        utub = Utub.query.get_or_404(requested_id)

        if int(current_user.get_id()) not in [
            int(member.user_id) for member in utub.members
        ]:
            # User is not member of the UTub they are requesting
            abort(404)

        utub_data_serialized = utub.serialized

        return jsonify(utub_data_serialized)
