# Standard library
import re

import sqlalchemy

from src.config import ConfigTest


def get_csrf_token(html_page: bytes, meta_tag: bool = False) -> str:
    """
    Reads in the html byte response from a GET of a page, finds the CSRF token using regex, returns it.

    Args:
        html_page (bytes): Byte data of html page
        meta_tag (bool): If it's in a meta tag or not

    Returns:
        str: CSRF from parsed HTML page
    """
    if meta_tag:
        all_html_data = str(
            [val for val in html_page.splitlines() if b'name="csrf-token"' in val][0]
        )
        result = re.search('<meta name="csrf-token" content="(.*)">', all_html_data)
    else:
        all_html_data = str(
            [val for val in html_page.splitlines() if b'name="csrf_token"' in val][0]
        )
        result = re.search(
            '<input id="csrf_token" name="csrf_token" type="hidden" value="(.*)">',
            all_html_data,
        )

    assert result is not None
    return result.group(1)


def clear_database(test_config: ConfigTest):
    engine = sqlalchemy.create_engine(test_config.SQLALCHEMY_DATABASE_URI)
    meta = sqlalchemy.MetaData(engine)
    meta.reflect()
    meta.drop_all()
    meta.create_all()
