"""
Contains database models for URLS4IRL.

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

class Utub_Urls(db.Model):
    """
    Represents the Many-to-Many relationship between UTubs and the shared URLs.
    A new entry is created in the URLs table if it is not already added in there. This table
    indicates which UTubs contain which URLs, as well as any notes/description for that UTub specific URL.

    https://stackoverflow.com/questions/52920701/many-to-many-with-three-tables-relating-with-each-other-sqlalchemy
    """
    __tablename__ = "UtubUrls"

    utub_id = db.Column(db.Integer, db.ForeignKey('Utub.id'), primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('Urls.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('User.id'), primary_key=True)          
    url_notes = db.Column(db.String(140), default='')
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user_that_added_url = db.relationship("User", back_populates="utub_urls")
    url_in_utub = db.relationship("URLS")
    utub = db.relationship("Utub", back_populates="utub_urls")

    @property
    def serialized(self):
        """Returns serialized object."""
        return {
            "url": self.url_in_utub.serialized,
            "added_by": self.user_that_added_url.serialized,
            "notes": self.url_notes
        }


class Url_Tags(db.Model):
    """
    Represents the Many-to-Many relationship between tags, UTubs, and URLs.
    This table indicates which URLs in a specified UTub contain a specified tag.

    https://stackoverflow.com/questions/52920701/many-to-many-with-three-tables-relating-with-each-other-sqlalchemy
    """
    __tablename__ = "UrlTags"

    utub_id = db.Column(db.Integer, db.ForeignKey('Utub.id'), primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('Urls.id'), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('Tags.id'), primary_key=True)          
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tag_item = db.relationship("Tags")
    tagged_url = db.relationship("URLS", back_populates="url_tags")
    utub_containing_this_tag = db.relationship("Utub", back_populates="utub_url_tags")

    @property
    def serialized(self):
        """Returns serialized object."""
        return {
            'tag': self.tag_item.serialized,
            'tagged_url': self.tagged_url.serialized
        }


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
    utub_urls = db.relationship("Utub_Urls", back_populates="user_that_added_url")
    
    @property
    def serialized(self):
        """Return object in serialized form."""
        return {
            'id': self.id,
            'username': self.username,
        }

    def __repr__(self):
        return f"User: {self.username}, Email: {self.email}, Password: {self.password}"

class Utub(db.Model):
    """Class represents a UTub. A UTub is created by a specific user, but has read-edit access given to other users depending on who it
    is shared with. The UTub contains a set of URL's and their associated tags."""

    __tablename__ = 'Utub'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False) # Note that multiple UTubs can have the same name, maybe verify this per user?
    utub_creator = db.Column(db.Integer, db.ForeignKey('User.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    users = db.relationship('User', secondary=utub_users, lazy='subquery', backref=db.backref('users'))
    utub_url_tags = db.relationship("Url_Tags", back_populates="utub_containing_this_tag", cascade='all, delete')
    utub_urls = db.relationship('Utub_Urls', back_populates="utub", cascade='all, delete')

    @property
    def serialized(self):
        """Return object in serialized form."""
        urls_serialized = [url.serialized for url in self.utub_urls]
        for url in urls_serialized:
            url['tags'] = []
            for tag in self.utub_url_tags:
                if tag.serialized['tagged_url']['id'] == url['url']['id']:
                    url['tags'].append(tag.serialized['tag'])
        return {
            'id': self.id,
            'name': self.name,
            'creator': self.utub_creator,
            'created_at': self.created_at.strftime("%m/%d/%Y %H:%M:%S"),
            'users': [user.serialized for user in self.users],
            'urls': urls_serialized
        }


class URLS(db.Model):
    """Class represents a URL. A URL is added by a single user, but can be used generically across multiple UTubs if it's already
    stored in the server. """

    __tablename__ = 'Urls'
    id = db.Column(db.Integer, primary_key=True)
    url_string = db.Column(db.String(2000), nullable=False) # Note that multiple UTubs can have the same URL
    created_by = db.Column(db.Integer, db.ForeignKey('User.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    url_tags = db.relationship("Url_Tags", back_populates="tagged_url")

    @property
    def serialized(self):
        """Returns object in serialized form."""
        return {
            'id': self.id,
            'url': self.url_string
        }

class Tags(db.Model):
    """Class represents a tag, more specifically a tag for a URL. A tag is added by a single user, but can be used as a tag for any URL. """

    __tablename__ = 'Tags'
    id = db.Column(db.Integer, primary_key=True)
    tag_string = db.Column(db.String(30), nullable=False) # Note that multiple URLs can have the same tag
    created_by = db.Column(db.Integer, db.ForeignKey('User.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def serialized(self):
        """Returns serialized object."""
        return {
            'id': self.id,
            'tag': self.tag_string
        }
