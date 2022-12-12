import pytest
from utils_for_test import get_csrf_token
from urls4irl import create_app, db
from urls4irl.config import TestingConfig
from urls4irl.models import User
from models_for_test import valid_user_1
from flask_login import FlaskLoginClient


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

    yield valid_user_1    

@pytest.fixture
def login_first_user(app, register_first_user):
    """ https://flask-login.readthedocs.io/en/latest/#automated-testing """

    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login = User.query.get(1)
        
    with app.test_client(user=user_to_login) as logged_in_client:
        yield logged_in_client, user_to_login
