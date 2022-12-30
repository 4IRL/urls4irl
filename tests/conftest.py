import pytest
import flask
from flask_login import FlaskLoginClient, current_user

from utils_for_test import get_csrf_token
from urls4irl import create_app, db
from urls4irl.config import TestingConfig
from urls4irl.models import User, Utub, Utub_Users
from models_for_test import (valid_user_1, valid_user_2, valid_user_3, 
                                valid_empty_utub_1)

@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    yield app
    db.drop_all(app=app)

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture
def load_register_page(client):
    """
    Given a Flask client, performs a GET of the register page using "/register"

    Args:
        client (FlaskClient): A Flask client

    Yields:
        (FlaskClient): A Flask client that has just performed a GET on "/register"
        (str): The CSRF token found on the "/register" page
    """
    with client:
        get_register_response = client.get("/register")
        csrf_token_string = get_csrf_token(get_register_response.get_data())
        yield client, csrf_token_string

@pytest.fixture
def load_login_page(client):
    """
    Given a Flask client, performs a GET of the login page using "/login"

    Args:
        client (FlaskClient): A Flask client

    Yields:
        (FlaskClient): A Flask client that has just performed a GET on "/login"
        (str): The CSRF token found on the "/login" page
    """
    with client:
        get_register_response = client.get("/login")
        print(type(client))
        csrf_token_string = get_csrf_token(get_register_response.get_data())
        yield client, csrf_token_string

@pytest.fixture
def register_first_user(app):
    """
    Registers a User model with.
    See 'models_for_test.py' for model information.
    The newly registered User's will have ID == 1

    Args:
        app (Flask): The Flask client for providing an app context

    Yields:
        (dict): The information used to generate the new User model
        (User): The newly generated User model
    """
    # Add a new user for testing
    with app.app_context():
        new_user = User(username=valid_user_1["username"],
                        email=valid_user_1["email"],
                        plaintext_password=valid_user_1["password"])
                    
        db.session.add(new_user)
        db.session.commit()

    yield valid_user_1, new_user    

@pytest.fixture
def register_all_but_first_user(app):
    """
    Registers two User models with unique usernames, emails, passwords, and ID's.
    See 'models_for_test.py' for model information.
    Assumes the first user is already registered.
    The newly registered User's will have ID's 2 and 3

    Args:
        app (Flask): The Flask client for providing an app context

    Yields:
        (tuple): Contains models of all valid registered users
        (Flask): The Flask client for providing an app context
    """
    # Add multiple users for testing
    all_users = (valid_user_2, valid_user_3,)
    with app.app_context():
        for user in all_users:
            new_user = User(username=user["username"],
                            email=user["email"],
                            plaintext_password=user["password"])
                        
            db.session.add(new_user)
            db.session.commit()
        
    yield app, all_users

@pytest.fixture
def register_multiple_users(app):
    """
    Registers three User models with unique usernames, emails, passwords, and ID's.
    See 'models_for_test.py' for model information.
    The registered User's will have ID's 1, 2, and 3

    Args:
        app (Flask): The Flask client for providing an app context

    Yields:
        (tuple): Contains models of all valid registered users
    """
    # Add multiple users for testing
    all_users = (valid_user_1, valid_user_2, valid_user_3,)
    with app.app_context():
        for user in all_users:
            new_user = User(username=user["username"],
                            email=user["email"],
                            plaintext_password=user["password"])
                        
            db.session.add(new_user)
            db.session.commit()
        
    yield all_users

@pytest.fixture
def login_first_user_with_register(app, register_first_user):
    """ 
    After registering a User with ID == 1,logs them in and routes them to "/home"
    https://flask-login.readthedocs.io/en/latest/#automated-testing

    Args:
        app (Flask): The Flask client providing an app context
        register_first_user (pytest fixture): Registers the user with ID == 1

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (str): The CSRF token string
        (User): The User model of currently logged in user
        (Flask): The Flask client for providing an app context
    """

    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login = User.query.get(1)
        
    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app

@pytest.fixture
def login_first_user_without_register(app):
    """ 
    Given a user with ID == 1, logs them in, routes them to "/home",
    https://flask-login.readthedocs.io/en/latest/#automated-testing 

    Args:
        app (Flask): The Flask client providing an app context

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (str): The CSRF token string
        (User): The User model of currently logged in user
        (Flask): The Flask client for providing an app context
    """

    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login = User.query.get(1)
        
    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app

@pytest.fixture
def login_second_user_without_register(app):
    """
    Given a user with ID == 2, logs them in, routes them to "/home",
    https://flask-login.readthedocs.io/en/latest/#automated-testing 

    Args:
        app (Flask): The Flask client providing an app context

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (str): The CSRF token string
        (User): The User model of currently logged in user
        (Flask): The Flask client for providing an app context
    """
    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login = User.query.get(2)
        
    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app

@pytest.fixture
def add_single_utub_as_user_without_logging_in(app, register_first_user):
    """
    Sets up a single UTub in the database, created by the user with ID == 1
    No members are added to this UTub besides the creator

    Args:
        app (Flask): The Flask client providing an app context
        register_first_user (pytest fixture): Registers the user with ID == 1
    """
    first_user_dict, first_user_object = register_first_user
    with app.app_context():
        new_utub = Utub(name=valid_empty_utub_1["name"], 
                utub_creator=1, 
                utub_description=valid_empty_utub_1["utub_description"])
        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = first_user_object
        new_utub.members.append(creator_to_utub)
        db.session.add(new_utub)
        db.session.commit()

@pytest.fixture
def add_single_user_to_utub_without_logging_in(app, register_multiple_users):
    """
    Sets up a single UTub in the database, created by user with ID == 1, and adds
        the user with ID == 2 to the UTub as a member

    Args:
        app (Flask): The Flask client providing an app context
        register_multiple_users (pytest fixture): Registers the users with ID == 1, 2, 3
    """
    with app.app_context():
        creator = User.query.get(1)
        new_utub = Utub(name=valid_empty_utub_1["name"], 
                utub_creator=creator.id, 
                utub_description=valid_empty_utub_1["utub_description"])
        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = creator
        new_utub.members.append(creator_to_utub)

        # Grab and add second user
        user_to_utub = User.query.get(2)
        new_user_for_utub = Utub_Users()
        new_user_for_utub.to_user = user_to_utub
        new_utub.members.append(new_user_for_utub)

        db.session.add(new_utub)
        db.session.commit()

@pytest.fixture
def add_multiple_users_to_utub_without_logging_in(app, register_multiple_users):
    """
    Sets up a single UTub in the database, created by user with ID == 1, and adds
        the other two members to the UTub

    Args:
        app (Flask): The Flask client providing an app context
        register_multiple_users (pytest fixture): Registers the users with ID == 1, 2, 3
    """
    with app.app_context():
        creator = User.query.get(1)
        new_utub = Utub(name=valid_empty_utub_1["name"], 
                utub_creator=creator.id, 
                utub_description=valid_empty_utub_1["utub_description"])
        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = creator
        new_utub.members.append(creator_to_utub)

        # Other users that aren't creators have ID's of 2 and 3 from fixture
        for user_id in (2, 3,):
            user_to_utub = User.query.get(user_id)
            new_user_for_utub = Utub_Users()
            new_user_for_utub.to_user = user_to_utub
            new_utub.members.append(new_user_for_utub)

        db.session.add(new_utub)
        db.session.commit()

@pytest.fixture
def add_single_utub_as_user_after_logging_in(login_first_user_with_register):
    """ 
    After logging in a user with ID == 1, has the user create a UTub and adds the 
        UTub and UTub-User association to the database

    Args:
        login_first_user_with_register (pytest fixture): Registers the user with ID == 1, logs them in,
            and routes to them "/home"

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (int): The ID of the added UTub
        (str): The CSRF token for the current client
        (Flask): The Flask client for providing an app context
    """
    client, csrf_token, valid_user, app = login_first_user_with_register

    with app.app_context():
        new_utub = Utub(name=valid_empty_utub_1["name"], 
                utub_creator=valid_user.id, 
                utub_description=valid_empty_utub_1["utub_description"])

        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = current_user
        new_utub.members.append(creator_to_utub)
        db.session.commit()

        new_utub_id = new_utub.id
    
    yield client, new_utub_id, csrf_token, app

@pytest.fixture
def every_user_makes_a_unique_utub(app, register_multiple_users):
    """ 
    After registering multiple users with ID's 1, 2, 3, has each user make their own unique UTub
    Each UTub has IDs == 1, 2, 3, corresponding with the creator ID

    Args:
        app (Flask): The Flask client providing an app context
        register_multiple_users (pytest fixture): Registers the users with ID == 1, 2, 3
    """
    with app.app_context():
        # Get all other users who aren't logged in
        other_users = User.query.all()
        for other_user in other_users:
            new_utub = Utub(name=valid_empty_utub_1["name"], 
                    utub_creator=other_user.id, 
                    utub_description=valid_empty_utub_1["utub_description"])

            creator_to_utub = Utub_Users()
            creator_to_utub.to_user = other_user
            new_utub.members.append(creator_to_utub)
            db.session.commit()

@pytest.fixture
def every_user_in_every_utub(app, every_user_makes_a_unique_utub):
    """ 
    After registering multiple users with ID's 1, 2, 3, and ensuring each User has their own UTub, 
    then adds all other Users as members to each User's UTubs.
    Each of the three User's has ID == 1, 2, 3

    Args:
        app (Flask): The Flask client providing an app context
        every_user_makes_a_unique_utub (pytest fixture): Has each User make their own UTub
    """
    with app.app_context():
        # Ensure each UTub has only one member
        current_utubs = Utub.query.all()
        current_users = User.query.all()

        for utub in current_utubs:
            current_utub_members = [user.to_user for user in utub.members]

            for user in current_users:
                if user not in current_utub_members:
                    # Found a missing User who should be in a UTub
                    new_utub_user_association = Utub_Users()
                    new_utub_user_association.to_user = user
                    utub.members.append(new_utub_user_association)

        db.session.commit()
