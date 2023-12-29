from flask import render_template
from src.utils.strings import IDENTIFIERS


def handle_404_response(e):
    return render_template("error_pages/404_response.html", text=IDENTIFIERS.HTML_404), 404
