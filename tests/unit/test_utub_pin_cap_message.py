import pytest

from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.utubs.constants import MAX_PINNED_UTUBS

pytestmark = pytest.mark.unit


def test_pin_cap_message_names_the_cap():
    """
    GIVEN the pin cap constant
    WHEN the cap-reached message is read
    THEN it embeds the cap number, so the copy cannot drift from the limit
    """
    assert str(MAX_PINNED_UTUBS) in UTUB_FAILURE.UTUB_PINS_CAP_REACHED
