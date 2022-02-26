"""
Contains database models for URLS4IRL.

TODO: tags

# https://docs.sqlalchemy.org/en/14/orm/backref.html
"""
from datetime import datetime
from urls4irl import db, login_manager
from flask_login import UserMixin


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

"""
Represents the Many-to-Many relationship between UTubs and their allowed visitors.
A new entry is created on creation of a UTub for the creator, and whomver the creator decides to add to the UTub.

To query:
https://stackoverflow.com/questions/12593421/sqlalchemy-and-flask-how-to-query-many-to-many-relationship/12594203
"""
utub_users = db.Table('UtubUsers',
    db.Column('utub_id', db.Integer, db.ForeignKey('Utub.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('User.id'), primary_key=True)            
)

class UtubUrls(db.Model):
    """
    Represents the Many-to-Many relationship between UTubs and the shared URLs.
    A new entry is created in the URLs table if it is not already added in there. This table
    indicates which UTubs contain which URLs, as well as any notes/description for that UTub specific URL.
    """
    __tablename__ = "UtubUrls"

    utub_id = db.Column(db.Integer, db.ForeignKey('Utub.id'), primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('Urls.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('User.id'), primary_key=True)          
    url_notes = db.Column(db.String(140), default='')
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class User(db.Model, UserMixin):
    """Class represents a User, with their username, email, and hashed password."""

    __tablename__ = 'User'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    email_confirm = db.Column(db.Boolean, default=False)
    password = db.Column(db.String(166), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    utubs_created = db.relationship('Utub', backref='created_by', lazy=True)
    url_added = db.relationship('URLS', backref='added_to_utub_by', lazy=True)

    #TODO Relationship to the URL tag they added

    def __repr__(self):
        return f"User: {self.username}, Email: {self.email}, Password: {self.password}"


class Utub(db.Model):
    """Class represents a UTub. A UTub is created by a specific user, but has read-edit access given to other users depending on who it
    is shared with. The UTub contains a set of URL's and their associated tags."""

    __tablename__ = 'Utub'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False) # Note that multiple UTubs can have the same name, maybe verify this per user?
    user_id = db.Column(db.Integer, db.ForeignKey('User.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    users = db.relationship('User', secondary=utub_users, lazy='subquery', backref=db.backref('users'))
    urls = db.relationship('URLS', secondary=UtubUrls.__table__, lazy='subquery', backref=db.backref('associated_utubs'))


class URLS(db.Model):
    """Class represents a URL. A URL is added by a single user, but can be used generically across multiple UTubs if it's already
    stored in the server. """

    __tablename__ = 'Urls'
    id = db.Column(db.Integer, primary_key=True)
    url_string = db.Column(db.String(2000), nullable=False) # Note that multiple UTubs can have the same URL
    created_by = db.Column(db.Integer, db.ForeignKey('User.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
