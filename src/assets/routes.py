from flask import Blueprint, send_from_directory, current_app
import os

assets_bp = Blueprint("assets", __name__, url_prefix="/assets")


@assets_bp.route("/<path:filename>")
def serve_bundled_assets(filename: str):
    return send_from_directory(os.path.join(current_app.root_path, "gen"), filename)
