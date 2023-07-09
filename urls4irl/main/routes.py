from flask import redirect, url_for, request, render_template, abort, jsonify, Blueprint
from flask_login import current_user, login_required
from urls4irl.models import Utub

main = Blueprint("main", __name__)


@main.route("/")
def splash():
    """Splash page for either an unlogged in user."""
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    return render_template("splash.html")


@main.route("/home", methods=["GET"])
@login_required
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
        return abort(404)

    else:
        if "UTubID" not in request.args:
            # Wrong argument
            return abort(404)

        requested_id = request.args.get("UTubID")

        utub = Utub.query.get_or_404(requested_id)

        if int(current_user.get_id()) not in [
            int(member.user_id) for member in utub.members
        ]:
            # User is not member of the UTub they are requesting
            return abort(403)

        utub_data_serialized = utub.serialized

        return jsonify(utub_data_serialized)
