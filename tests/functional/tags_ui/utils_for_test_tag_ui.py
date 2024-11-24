# Standard library
import random

# External libraries
from flask import Flask
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

# Internal libraries
from src import db
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.models.utub_url_tags import Utub_Url_Tags
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    wait_then_get_element,
)


def create_tag(browser: WebDriver, selected_url_row: WebElement, tag_string: str = ""):
    """
    Once logged in, with users, UTub, and URLs this function initiates the action to create one tag applied to the selected URL in the selected UTub.
    """

    # Select createTag button
    selected_url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_TAG_CREATE).click()

    create_tag_input = selected_url_row.find_element(
        By.CSS_SELECTOR, MPL.INPUT_TAG_CREATE
    )

    assert create_tag_input.is_displayed()

    if tag_string:
        # Input new tag
        tag_input_field = wait_then_get_element(browser, MPL.INPUT_TAG_CREATE)
        clear_then_send_keys(tag_input_field, tag_string)


def hover_tag_badge(browser: WebDriver, tag_badge: WebElement):

    actions = ActionChains(browser)

    actions.move_to_element(tag_badge)

    # Pause to make sure deleteTag button is visible
    actions.pause(3).perform()
    return actions


def show_delete_tag_button_on_hover(browser: WebDriver, tag_badge: WebElement):
    """
    Args:
        WebDriver open to a selected URL
        Tag badge element to remove from the selected URL

    Returns:
        Boolean confirmation of successful deletion of tag
        WebDriver handoff to member tests
    """
    actions = hover_tag_badge(browser, tag_badge)

    delete_tag_button = tag_badge.find_element(By.CSS_SELECTOR, MPL.BUTTON_TAG_DELETE)

    actions.move_to_element(delete_tag_button).pause(2).perform()

    return delete_tag_button


def delete_tag_from_url_in_utub_random(app: Flask, utub_title: str):
    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == utub_title).first()
        utub_urls: list[Utub_Urls] = utub.utub_urls

        utub_url = random.choice(utub_urls)
        utub_url_id = utub_url.id

        utub_tag: Utub_Url_Tags = random.choice(utub_url.url_tags)
        utub_tag_id = utub_tag.utub_tag_id

        utub_url_tag: Utub_Url_Tags = Utub_Url_Tags.query.get(utub_tag.id)

        db.session.delete(utub_url_tag)
        db.session.commit()

        return utub_url_id, utub_tag_id


def delete_one_tag_from_each_url_in_utub(app: Flask, utub_title: str):
    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == utub_title).first()
        utub_urls: list[Utub_Urls] = utub.utub_urls

        utub_url = random.choice(utub_urls)
        utub_url_id = utub_url.id

        utub_tag: Utub_Url_Tags = random.choice(utub_url.url_tags)
        utub_tag_id = utub_tag.utub_tag_id

        utub_url_tag: Utub_Url_Tags = Utub_Url_Tags.query.get(utub_tag.id)

        db.session.delete(utub_url_tag)
        db.session.commit()

        return utub_url_id, utub_tag_id
