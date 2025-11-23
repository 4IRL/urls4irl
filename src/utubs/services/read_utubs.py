from flask import Response, jsonify
from flask_login import current_user
from src import db
from src.app_logger import safe_add_log
from src.models.utubs import Utubs


def get_single_utub_for_user(current_utub: Utubs) -> Response:
    utub_data_serialized = current_utub.serialized(current_user.id)

    current_utub.set_last_updated()
    db.session.commit()

    safe_add_log(f"Retrieving UTub.id={current_utub.id} from direct route")
    return jsonify(utub_data_serialized)


def get_all_utubs_of_user() -> Response:
    # TODO: Should serialized summary be utubID and utubName
    # instead of id and name?
    safe_add_log(f"Returning UTubs for User={current_user.id}")
    return jsonify(current_user.serialized_on_initial_load)
