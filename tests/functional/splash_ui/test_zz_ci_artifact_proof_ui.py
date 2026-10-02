import pytest
from playwright.sync_api import Page

pytestmark = pytest.mark.splash_ui


def test_ci_artifact_proof(page: Page) -> None:
    """Temporary failing test to prove CI uploads UI failure artifacts."""
    assert False, "ci-artifact-proof"
