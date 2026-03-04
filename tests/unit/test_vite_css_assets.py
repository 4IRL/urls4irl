import pytest

from backend import _collect_css_from_manifest

pytestmark = pytest.mark.unit


def test_collect_css_entrypoint_not_in_manifest():
    assert _collect_css_from_manifest({}, "frontend/main.js") == []


def test_collect_css_no_css_key():
    manifest = {"frontend/main.js": {"file": "assets/main-abc.js"}}
    assert _collect_css_from_manifest(manifest, "frontend/main.js") == []


def test_collect_css_returns_css_paths():
    manifest = {
        "frontend/main.js": {
            "file": "assets/main-abc.js",
            "css": ["assets/main-abc.css"],
        }
    }
    assert _collect_css_from_manifest(manifest, "frontend/main.js") == [
        "assets/main-abc.css"
    ]


def test_collect_css_traverses_imports():
    manifest = {
        "frontend/main.js": {
            "file": "assets/main-abc.js",
            "css": ["assets/main-abc.css"],
            "imports": ["_shared-chunk.js"],
        },
        "_shared-chunk.js": {
            "file": "assets/_shared-chunk.js",
            "css": ["assets/shared-abc.css"],
        },
    }
    result = _collect_css_from_manifest(manifest, "frontend/main.js")
    assert result == ["assets/main-abc.css", "assets/shared-abc.css"]


def test_collect_css_cycle_guard():
    manifest = {
        "frontend/main.js": {
            "file": "assets/main-abc.js",
            "css": ["assets/main-abc.css"],
            "imports": ["_chunk-a.js"],
        },
        "_chunk-a.js": {
            "file": "assets/_chunk-a.js",
            "css": ["assets/chunk-a.css"],
            "imports": ["frontend/main.js"],  # cycle back
        },
    }
    result = _collect_css_from_manifest(manifest, "frontend/main.js")
    assert "assets/main-abc.css" in result
    assert "assets/chunk-a.css" in result
    assert len(result) == 2  # no duplicates from the cycle
