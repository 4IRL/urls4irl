"""
Contains database models for URLS4IRL.

Users.
TODO: UTubs.
TODO: URLs
TODO: tags
"""
from datetime import datetime
from urls4irl import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    email_confirm = db.Column(db.Boolean, default=False)
    password = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    #TODO Relationship to the utub they made
    #TODO Relationship to the URL they added
    #TODO Relationship to the URL tag they added

    def __repr__(self):
        return f"User: {self.username}, Email: {self.email}, Password: {self.password}"
