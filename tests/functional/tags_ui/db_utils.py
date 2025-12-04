from flask import Flask
from src.models.utub_tags import Utub_Tags


def get_tag_in_utub(app: Flask, tag_id: int) -> Utub_Tags:
    with app.app_context():
        return Utub_Tags.query.get(tag_id)
