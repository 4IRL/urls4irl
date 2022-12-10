"""
Contains database models for URLS4IRL.

# https://docs.sqlalchemy.org/en/14/orm/backref.html
"""
from datetime import datetime
from urls4irl import db, login_manager
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from urls4irl.url_validation import check_request_head, InvalidURLError

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

"""
Represents the Many-to-Many relationship between UTubs and their allowed visitors.
A new entry is created on creation of a UTub for the creator, and whomver the creator decides to add to the UTub.

To query:
https://stackoverflow.com/questions/12593421/sqlalchemy-and-flask-how-to-query-many-to-many-relationship/12594203
"""

class Utub_Users(db.Model):
    __tablename__ = 'UtubUsers'
    utub_id = db.Column(db.Integer, db.ForeignKey('Utub.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('User.id'), primary_key=True)

    to_user = db.relationship('User', back_populates='utubs_is_member_of')
    to_utub = db.relationship('Utub', back_populates='members')

    @property
    def serialized(self):
        return self.to_user.serialized

    @property
    def serialized_on_initial_load(self):
        """Returns the serialized object on initial load for this user, including UTub name and id."""
        return {
            "id": self.to_utub.id,
            "name": self.to_utub.name
        }


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

        # Only return tags for the requested UTub
        url_tags = []
        for tag in self.url_in_utub.url_tags:
            if int(tag.utub_id) == int(self.utub_id):
                url_tags.append(tag.tag_id)

        return {
            "url_id": self.url_in_utub.serialized_for_utub['id'],
            "url_string": self.url_in_utub.serialized_for_utub['url'],
            "url_tags": url_tags,
            "added_by": self.user_that_added_url.serialized['id'],
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
    utubs_is_member_of = db.relationship("Utub_Users", back_populates='to_user')
    
    def __init__(self, username: str, email: str, plaintext_password: str, email_confirm: bool = False ):
        """
        Create new user object per the following parameters

        Args:
            username (str): Username from user input
            email (str): Email from user input
            email_confirm (bool): Whether user's email has been confirmed yet
            plaintext_password (str): Plaintext password to be hashed
        """
        self.username = username
        self.email = email
        self.password = generate_password_hash(plaintext_password)
        self.email_confirm = email_confirm

    def is_password_correct(self, plaintext_password: str) -> bool:
        return check_password_hash(self.password, plaintext_password)

    @property
    def serialized(self):
        """Return object in serialized form."""
        return {
            'id': self.id,
            'username': self.username,
        }

    @property
    def serialized_on_initial_load(self):
        """Returns object in serialized for, with only the utub id and Utub name the user is a member of."""
        utubs_for_user = []
        for utub in self.utubs_is_member_of:
            utubs_for_user.append(utub.serialized_on_initial_load)

        return utubs_for_user

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
    utub_description = db.Column(db.String(500), nullable=True)
    utub_url_tags = db.relationship("Url_Tags", back_populates="utub_containing_this_tag", cascade='all, delete')
    utub_urls = db.relationship('Utub_Urls', back_populates="utub", cascade='all, delete')
    members = db.relationship('Utub_Users', back_populates="to_utub", cascade='all, delete, delete-orphan')

    @property
    def serialized(self):
        """Return object in serialized form."""

        # self.utub_url_tags may contain repeats of tags since same tags can be on multiple URLs
        # Need to pull only the unique ones
        utub_tags = []
        for tag in self.utub_url_tags:
            tag_object = tag.tag_item.serialized
            
            if tag_object not in utub_tags:
                utub_tags.append(tag_object)

        return {
            'id': self.id,
            'name': self.name,
            'created_by': self.utub_creator,
            'created_at': self.created_at.strftime("%m/%d/%Y %H:%M:%S"),
            'description': self.utub_description if self.utub_description is not None else "",
            'members': [member.serialized for member in self.members],
            'urls': [url.serialized for url in self.utub_urls],
            'tags': utub_tags
        }


class URLS(db.Model):
    """Class represents a URL. A URL is added by a single user, but can be used generically across multiple UTubs if it's already
    stored in the server. """

    __tablename__ = 'Urls'
    id = db.Column(db.Integer, primary_key=True)
    url_string = db.Column(db.String(2000), nullable=False, unique=True) # Note that multiple UTubs can have the same URL
    created_by = db.Column(db.Integer, db.ForeignKey('User.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    url_tags = db.relationship("Url_Tags", back_populates="tagged_url")

    def __init__(self, normalized_url: str, current_user_id: int):
        self.url_string = self.verify_url(normalized_url)
        self.created_by = int(current_user_id)

    def verify_url(self, url_to_verify: str) -> str:
        try:
            return check_request_head(url_to_verify)
        
        except InvalidURLError as e:
            raise InvalidURLError from e

    @property
    def serialized(self):
        """Returns object in serialized form."""
        return {
            'id': self.id,
            'url': self.url_string,
            'tags': [tag.tag_item.serialized for tag in self.url_tags]
        }

    @property
    def serialized_for_utub(self):
        return {
            'id': self.id,
            'url': self.url_string,
            'tags': [int(tag.tag_item.serialized['id']) for tag in self.url_tags]
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
            'tag_string': self.tag_string
        }
