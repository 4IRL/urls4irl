from flask import (
    Blueprint,
    jsonify,
    request,
)
from src.utils.strings.json_strs import STD_JSON_RESPONSE

debug = Blueprint("debug", __name__)


@debug.route("/debug", methods=["POST"])
def debug_endpoint():
    """Logs user out by clearing session details. Returns to login page."""
    print(f"IN DEBUG ENDPOINT: {request.get_json()=}", flush=True)
    return jsonify({STD_JSON_RESPONSE.STATUS: "ok"}), 200
