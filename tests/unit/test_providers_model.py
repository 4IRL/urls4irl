import pytest

from backend import db
from backend.models.providers import Providers

pytestmark = pytest.mark.unit

_KEY = "gitlab"
_DISPLAY_NAME = "GitLab"


def test_provider_persists_key_and_display_name(app):
    """
    GIVEN no Providers row exists for a given key
    WHEN a Providers row is constructed and committed
    THEN the key and displayName persist as written
    """
    with app.app_context():
        assert Providers.query.get(_KEY) is None

        db.session.add(Providers(key=_KEY, display_name=_DISPLAY_NAME))
        db.session.commit()

        reloaded = Providers.query.get(_KEY)
        assert reloaded is not None
        assert reloaded.key == _KEY
        assert reloaded.display_name == _DISPLAY_NAME


def test_provider_enabled_defaults_to_true_when_omitted(app):
    """
    GIVEN a Providers row constructed without an explicit enabled value
    WHEN the row is committed and reloaded
    THEN enabled defaults to True
    """
    with app.app_context():
        assert Providers.query.get(_KEY) is None

        db.session.add(Providers(key=_KEY, display_name=_DISPLAY_NAME))
        db.session.commit()

        reloaded = Providers.query.get(_KEY)
        assert reloaded.enabled is True
