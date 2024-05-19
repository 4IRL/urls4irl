from flask import url_for
import pytest

from selenium import webdriver
from selenium.webdriver.common.by import By

from tests.models_for_test import valid_user_1
from src.models.users import Users
from src.utils.all_routes import ROUTES
from src.utils.strings.splash_form_strs import REGISTER_FORM
from src.utils.strings.email_validation_strs import EMAILS

import constants as const


@pytest.mark.skip(reason="This test is not yet implemented")
def test_add_utub_input_field_shown(app, load_register_page):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """
    client, csrf_token = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token

    response = client.post(
        url_for(ROUTES.UTUBS.HOME), data=valid_user_1, follow_redirects=True
    )

    driver = webdriver.Chrome()
    driver.get(const.BASE_URL)
    driver.implicitly_wait(3)

    addUTubBtn = driver.find_element(By.ID, "createUTubBtn")
    addUTubBtn.click()

    # Here and below in-work 05/15/24

    # Ensure input field opened
    # Ensure all other input fields are hidden

    # Assert user gets shown email validation modal
    assert response.status_code == 201
    # assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data
    assert f"{EMAILS.EMAIL_VALIDATION_MODAL_CALL}".encode() in response.data

    with app.app_context():
        registered_user: Users = Users.query.filter(
            Users.username == valid_user_1[REGISTER_FORM.USERNAME]
        ).first_or_404()
        assert not registered_user.email_confirm.is_validated


@pytest.mark.skip(reason="This test is not yet implemented")
def test_add_utub_name_length_exceeded(app, load_register_page):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """
    client, csrf_token = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token

    response = client.post(
        url_for(ROUTES.UTUBS.HOME), data=valid_user_1, follow_redirects=True
    )

    driver = webdriver.Chrome()
    driver.get(const.BASE_URL)
    driver.implicitly_wait(3)

    addUTubBtn = driver.find_element(By.ID, "createUTubBtn")
    addUTubBtn.click()

    # Here and below in-work 05/15/24

    # Assert user gets shown email validation modal
    assert response.status_code == 201
    # assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data
    assert f"{EMAILS.EMAIL_VALIDATION_MODAL_CALL}".encode() in response.data

    with app.app_context():
        registered_user: Users = Users.query.filter(
            Users.username == valid_user_1[REGISTER_FORM.USERNAME]
        ).first_or_404()
        assert not registered_user.email_confirm.is_validated


@pytest.mark.skip(reason="This test is not yet implemented")
def test_add_utub_name_similar(app, load_register_page):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """
    client, csrf_token = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token

    response = client.post(
        url_for(ROUTES.UTUBS.HOME), data=valid_user_1, follow_redirects=True
    )

    driver = webdriver.Chrome()
    driver.get(const.BASE_URL)
    driver.implicitly_wait(3)

    addUTubBtn = driver.find_element(By.ID, "createUTubBtn")
    addUTubBtn.click()

    # Here and below in-work 05/15/24

    # Assert user gets shown email validation modal
    assert response.status_code == 201
    # assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data
    assert f"{EMAILS.EMAIL_VALIDATION_MODAL_CALL}".encode() in response.data

    with app.app_context():
        registered_user: Users = Users.query.filter(
            Users.username == valid_user_1[REGISTER_FORM.USERNAME]
        ).first_or_404()
        assert not registered_user.email_confirm.is_validated
