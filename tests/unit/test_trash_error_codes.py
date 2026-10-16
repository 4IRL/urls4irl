import pytest

from backend.urls.constants import URLErrorCodes
from backend.utubs.constants import UTubErrorCodes

pytestmark = pytest.mark.unit


def test_trash_error_codes_match_frontend_constants():
    """
    GIVEN the Trash error codes the frontend branches on
    WHEN they are read from the backend enums
    THEN they equal the numbers hardcoded in frontend/home/trash/error-codes.ts
    (a renumbering here must be mirrored there)
    """
    assert URLErrorCodes.NOT_IN_TRASH == 11
    assert UTubErrorCodes.NOT_IN_TRASH == 4
    assert URLErrorCodes.URL_ALREADY_IN_DESTINATION == 14
