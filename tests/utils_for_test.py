import re
from logging import LogRecord

import sqlalchemy

from src.config import ConfigTest
from src.models.utub_url_tags import Utub_Url_Tags


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


def trim_and_parse_logs(logs: list[LogRecord]) -> list[str]:
    """
    Remove first and last logs for an endpoint's logs as they do not contain unique data to test for

    Request: GET /home                                      # Not being tested for
    [BEGIN] Returning user's UTubs on home page load [END]  # Being tested for
    Response: 200 completed in 109.63ms                     # Not being tested for

    Args:
        logs (list[LogRecord]): Raw LogRecords for a request

    Returns:
        list[str]: Log messages that aren't the first or last log
    """
    return [
        record.getMessage()
        for idx, record in enumerate(logs)
        if idx not in (0, len(logs) - 1)
    ]


def is_string_in_logs(needle: str, log_records: list[LogRecord]) -> bool:
    logs = trim_and_parse_logs(log_records)
    return any([needle in haystack for haystack in logs])


def is_string_in_logs_regex(needle: str, log_records: list[LogRecord]) -> bool:
    logs = trim_and_parse_logs(log_records)
    return any([re.match(needle, haystack) is not None for haystack in logs])


def count_tag_instances_in_utub(utub_id: int, utub_tag_id: int) -> int:
    return Utub_Url_Tags.query.filter(
        Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_tag_id == utub_tag_id
    ).count()
