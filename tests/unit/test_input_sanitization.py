import pytest

from src.api_common.input_sanitization import sanitize_user_input

pytestmark = pytest.mark.unit

inputs_outputs = {
    # Close-to-html inputs
    "<": "<",
    ">": ">",
    "<Hello>": None,
    "< Hello >": "< Hello >",
    "<|Hello|>": "<|Hello|>",
    "<div>": None,
    "<<div>>": "<>",
    "<<HELLO>>": "<>",
    "<script>alert(1)</script>": None,
    "<IMG SRC=javascript:alert(1)>": None,
    '<img src="safe.png" onerror="x">': None,
    "<script>": None,
    "<<script>>alert(1)<<script>>": "<",
    # Regular Inputs
    "Hello, World!": "Hello, World!",
    "<!DOCTYPE html>": None,
    "<b>Hello</b>": "Hello",
    "<strong>Hello</strong>": "Hello",
    "<p>Hello</p>": "Hello",
    "<p>Hello<br></p>": "Hello",
    "Plain text without tags": "Plain text without tags",
    "42": "42",
    "user@example.com": "user@example.com",
    "u4i_test1@urls4irl.app": "u4i_test1@urls4irl.app",
    "<h1>Hello</h1>": "Hello",
    # Invalid HTML
    '<a href="javascript:alert(1)">Click</a>': "Click",
    '<iframe src="malicious.com"></iframe>': None,
    "<style>body { background: red; }</style>": None,
    "<div><script>alert(1)</script></div>": None,
    '<svg onload="alert(1)">': None,
    "<math><mo>&times;</mo></math>": "×",
    '<a href="http://safe.com">Safe</a>': "Safe",
    '<a href="ftp://dangerous.com">Unsafe</a>': "Unsafe",
    '<img src="evil.jpg">': None,
    "<!-- Comment -->": None,
}


def test_input_sanitization():
    for inpt, out in inputs_outputs.items():
        assert sanitize_user_input(inpt) == out
