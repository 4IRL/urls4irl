import pytest
from utils_for_test import get_csrf_token
from urls4irl import create_app, db
from urls4irl.config import TestingConfig
from urls4irl.models import User, Utub, Utub_Users
from models_for_test import (valid_user_1, valid_user_2, valid_user_3, 
                                valid_empty_utub_1)
from flask_login import FlaskLoginClient, current_user


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
    with client:
        get_register_response = client.get("/register")
        csrf_token_string = get_csrf_token(get_register_response.get_data())
        yield client, csrf_token_string

@pytest.fixture
def load_login_page(client):
    with client:
        get_register_response = client.get("/login")
        csrf_token_string = get_csrf_token(get_register_response.get_data())
        yield client, csrf_token_string

@pytest.fixture
def register_first_user(app):
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
    """ https://flask-login.readthedocs.io/en/latest/#automated-testing """

    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login = User.query.get(1)
        
    with app.test_client(user=user_to_login) as logged_in_client:
        yield logged_in_client, user_to_login, app

@pytest.fixture
def login_first_user_without_register(app):
    """ https://flask-login.readthedocs.io/en/latest/#automated-testing """

    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login = User.query.get(1)
        
    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app

@pytest.fixture
def login_second_user_without_register(app):
    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login = User.query.get(2)
        
    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app

@pytest.fixture
def logged_in_user_on_home_page(login_first_user_with_register):
    client, user, app = login_first_user_with_register
    get_home_response = client.get("/home")
    csrf_token_string = get_csrf_token(get_home_response.get_data(), meta_tag=True)
    yield client, user, csrf_token_string, app

@pytest.fixture
def add_single_utub_as_user_without_logging_in(app, register_first_user):
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
def add_single_utub_as_user_after_logging_in(logged_in_user_on_home_page):
    client, valid_user, csrf_token, app = logged_in_user_on_home_page

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
def every_user_makes_a_unique_utub(register_multiple_users, app):
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
