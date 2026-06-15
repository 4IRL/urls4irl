import re

from flask import url_for
import pytest

from backend.utils.all_routes import ROUTES

pytestmark = pytest.mark.splash

EXPECTED_TILE_COUNT = 3
FEATURE_TILE_LI_PATTERN = re.compile(
    rb'<li class="[^"]*splash-feature-tile[^"]*"[^>]*>', re.IGNORECASE
)
TABINDEX_ATTR_PATTERN = re.compile(rb"tabindex", re.IGNORECASE)


def test_splash_feature_tiles_have_no_tabindex(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (GET)
    THEN exactly three feature tiles render and none are keyboard-focusable
        (no tabindex attribute), keeping the decorative tiles inert
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(
                url_for(ROUTES.SPLASH.SPLASH_PAGE), follow_redirects=True
            )

        assert response.status_code == 200

        tile_open_tags = FEATURE_TILE_LI_PATTERN.findall(response.data)
        assert len(tile_open_tags) == EXPECTED_TILE_COUNT
        assert all(not TABINDEX_ATTR_PATTERN.search(tag) for tag in tile_open_tags)
