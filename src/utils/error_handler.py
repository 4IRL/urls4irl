from flask import render_template


def handle_404_response(e):
    return render_template("error_pages/404_response.html"), 404
