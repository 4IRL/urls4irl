import pytest

from src.utils.input_sanitization import sanitize_user_input

pytestmark = pytest.mark.unit

inputs_outputs = {
    # Close-to-html inputs
    "<": "<",
    ">": ">",
    "<Hello>": "",
    "< Hello >": "< Hello >",
    "<|Hello|>": "<|Hello|>",
    "<div>": "",
    "<<div>>": "<>",
    "<<HELLO>>": "<>",
    "<script>alert(1)</script>": "",
    "<IMG SRC=javascript:alert(1)>": "",
    '<img src="safe.png" onerror="x">': "",
    "<script>": "",
    "<<script>>alert(1)<<script>>": "<",

    # Regular Inputs
    "Hello, World!": "Hello, World!",
    "<!DOCTYPE html>": "",
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
    '<iframe src="malicious.com"></iframe>': "",
    '<style>body { background: red; }</style>': "",
    '<div><script>alert(1)</script></div>': "",
    '<svg onload="alert(1)">': "",
    '<math><mo>&times;</mo></math>': "×",
    '<a href="http://safe.com">Safe</a>': "Safe",
    '<a href="ftp://dangerous.com">Unsafe</a>': "Unsafe",
    '<img src="evil.jpg">': "",
    '<!-- Comment -->': ""
}

def test_input_sanitization():
    for inpt, out in inputs_outputs.items():
        assert sanitize_user_input(inpt) == out
