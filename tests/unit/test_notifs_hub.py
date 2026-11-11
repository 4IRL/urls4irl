"""Unit tests for scripts/notifs_hub.py, the stdlib hub heartbeat client."""

from __future__ import annotations

import email.message
import io
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from scripts import notifs_hub
from tests.unit.stdlib_only_utils import assert_module_is_stdlib_only

pytestmark = pytest.mark.unit

_KEY = "dak_supersecretkey"
_CLIENT_ID = "client-id-value"
_CLIENT_SECRET = "client-secret-value"
_BASE_URL = "https://hub.example.test"
_ENV_NAMES = ("PRODUCTION", "NOTIFS_BASE_URL", "NOTIFS_KEY_DIR", "NOTIFICATION_URL")


def _write_key_dir(key_dir: Path, *, key: str = _KEY) -> None:
    key_dir.mkdir(exist_ok=True)
    (key_dir / "delivery_key").write_text(key + "\n")
    (key_dir / "access_client_id").write_text(_CLIENT_ID + "\n")
    (key_dir / "access_client_secret").write_text(_CLIENT_SECRET + "\n")


def _ok_response(status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        notifs_hub, "CONTAINER_ENVIRONMENT_FILE", str(tmp_path / "no-dump")
    )


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    key_dir = tmp_path / "notifs"
    _write_key_dir(key_dir)
    monkeypatch.setenv("PRODUCTION", "true")
    monkeypatch.setenv("NOTIFS_BASE_URL", _BASE_URL)
    monkeypatch.setenv("NOTIFS_KEY_DIR", str(key_dir))
    return key_dir


@pytest.fixture
def urlopen(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock(return_value=_ok_response())
    monkeypatch.setattr("urllib.request.OpenerDirector.open", mock)
    return mock


def _sent_request(urlopen_mock: MagicMock) -> Any:
    return urlopen_mock.call_args.args[0]


def test_ping_success_url_headers_and_log(
    configured: Path, urlopen: MagicMock, capsys: pytest.CaptureFixture[str]
):
    """
    GIVEN a configured production environment
    WHEN a success ping is sent
    THEN it POSTs the success URL with the three auth headers and logs ok.
    """
    assert notifs_hub.ping("daily_backup") is True
    request = _sent_request(urlopen)
    assert request.full_url == f"{_BASE_URL}/v1/heartbeats/urls4irl/daily_backup"
    assert request.get_method() == "POST"
    assert request.data == b""
    assert request.get_header("Cf-access-client-id") == _CLIENT_ID
    assert request.get_header("Cf-access-client-secret") == _CLIENT_SECRET
    assert request.get_header("Authorization") == f"Bearer {_KEY}"
    err = capsys.readouterr().err
    assert (
        "notifs_hub lane=heartbeat check=daily_backup path=hub kind=success outcome=ok"
        in err
    )


def test_ping_fail_url(configured: Path, urlopen: MagicMock, capsys):
    """
    GIVEN a configured production environment
    WHEN a fail ping is sent
    THEN the URL ends in /fail and the log kind is fail.
    """
    assert notifs_hub.ping("daily_backup", fail=True) is True
    assert _sent_request(urlopen).full_url.endswith("/daily_backup/fail")
    assert "kind=fail outcome=ok" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        (
            urllib.error.HTTPError(_BASE_URL, 401, "Unauthorized", {}, None),  # type: ignore[arg-type]
            "http_401",
        ),
        (
            urllib.error.HTTPError(_BASE_URL, 404, "Not Found", {}, None),  # type: ignore[arg-type]
            "http_404",
        ),
        (urllib.error.URLError("connection refused"), "error"),
        (urllib.error.URLError(TimeoutError("timed out")), "timeout"),
        (TimeoutError("timed out"), "timeout"),
        (OSError("boom"), "error"),
        (ValueError("bad header"), "error"),
    ],
)
def test_ping_failures_return_false_and_log(
    configured: Path, urlopen: MagicMock, capsys, error: Exception, outcome: str
):
    """
    GIVEN urlopen raising a transport or HTTP error
    WHEN a ping is sent
    THEN it returns False, never raises, and logs the outcome.
    """
    urlopen.side_effect = error
    assert notifs_hub.ping("metrics_flush") is False
    assert f"outcome={outcome}" in capsys.readouterr().err


def test_ping_non_200_success_status_is_false(
    configured: Path, urlopen: MagicMock, capsys
):
    """
    GIVEN the hub answering 204
    WHEN a ping is sent
    THEN only 200 counts as success.
    """
    urlopen.return_value = _ok_response(204)
    assert notifs_hub.ping("metrics_flush") is False
    assert "outcome=http_204" in capsys.readouterr().err


def test_key_is_reread_on_every_call(configured: Path, urlopen: MagicMock):
    """
    GIVEN two pings with the delivery key rewritten between them
    WHEN the second ping is sent
    THEN it carries the new bearer.
    """
    notifs_hub.ping("metrics_flush")
    assert _sent_request(urlopen).get_header("Authorization") == f"Bearer {_KEY}"
    (configured / "delivery_key").write_text("dak_rotated\n")
    notifs_hub.ping("metrics_flush")
    assert _sent_request(urlopen).get_header("Authorization") == "Bearer dak_rotated"


@pytest.mark.parametrize("missing", ["directory", "delivery_key", "empty_secret"])
def test_missing_key_material_gives_missing_key(
    configured: Path, urlopen: MagicMock, capsys, missing: str
):
    """
    GIVEN a missing directory, a missing file, or an empty file
    WHEN a ping is sent
    THEN the outcome is missing_key with zero requests.
    """
    if missing == "directory":
        for child in configured.iterdir():
            child.unlink()
        configured.rmdir()
    elif missing == "delivery_key":
        (configured / "delivery_key").unlink()
    else:
        (configured / "access_client_secret").write_text("\n")
    assert notifs_hub.ping("metrics_flush") is False
    urlopen.assert_not_called()
    assert "outcome=missing_key" in capsys.readouterr().err


@pytest.mark.parametrize("value", [None, "false", "TRUE", "1", ""])
def test_production_gate_is_exact_true(
    configured: Path,
    urlopen: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    value: str | None,
):
    """
    GIVEN PRODUCTION not exactly "true", all key files and NOTIFICATION_URL present
    WHEN a ping is sent
    THEN zero requests are made and one skip line is logged.
    """
    monkeypatch.setenv("NOTIFICATION_URL", "https://discord.example.test/hook")
    if value is None:
        monkeypatch.delenv("PRODUCTION")
    else:
        monkeypatch.setenv("PRODUCTION", value)
    assert notifs_hub.ping("metrics_flush") is False
    urlopen.assert_not_called()
    err = capsys.readouterr().err
    assert err.count("outcome=skip") == 1


def test_env_resolves_from_dump_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, urlopen: MagicMock
):
    """
    GIVEN PRODUCTION, NOTIFS_BASE_URL and NOTIFS_KEY_DIR only in the env dump
    WHEN a ping is sent
    THEN the key is read and the request is made.
    """
    key_dir = tmp_path / "notifs"
    _write_key_dir(key_dir)
    dump = tmp_path / "container_environment"
    dump.write_text(
        f"PRODUCTION=true\nNOTIFS_BASE_URL={_BASE_URL}\nNOTIFS_KEY_DIR={key_dir}\n"
    )
    monkeypatch.setattr(notifs_hub, "CONTAINER_ENVIRONMENT_FILE", str(dump))
    assert notifs_hub.ping("metrics_flush") is True
    assert _sent_request(urlopen).full_url.startswith(_BASE_URL)


def test_trailing_slash_base_url_is_normalised(
    configured: Path, urlopen: MagicMock, monkeypatch: pytest.MonkeyPatch
):
    """
    GIVEN NOTIFS_BASE_URL with a trailing slash
    WHEN a ping is sent
    THEN the request URL has no doubled slash.
    """
    monkeypatch.setenv("NOTIFS_BASE_URL", f"{_BASE_URL}/")
    assert notifs_hub.ping("daily_backup") is True
    assert (
        _sent_request(urlopen).full_url
        == f"{_BASE_URL}/v1/heartbeats/urls4irl/daily_backup"
    )


def test_env_dump_skips_comments_blanks_and_malformed_lines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, urlopen: MagicMock
):
    """
    GIVEN a dump with comments, blank lines and lines without '=' around the real entries
    WHEN a ping is sent
    THEN the real entries are still resolved and the request is made.
    """
    key_dir = tmp_path / "notifs"
    _write_key_dir(key_dir)
    dump = tmp_path / "container_environment"
    dump.write_text(
        "# a comment\n"
        "\n"
        "   \n"
        "not-an-assignment\n"
        "PRODUCTION=true\n"
        "# NOTIFS_BASE_URL=https://commented.example.test\n"
        f"NOTIFS_BASE_URL={_BASE_URL}\n"
        "=novalue-key\n"
        f"NOTIFS_KEY_DIR={key_dir}\n"
    )
    monkeypatch.setattr(notifs_hub, "CONTAINER_ENVIRONMENT_FILE", str(dump))
    assert notifs_hub.ping("metrics_flush") is True
    assert _sent_request(urlopen).full_url.startswith(_BASE_URL)


def test_empty_env_value_overrides_the_dump(
    configured: Path,
    urlopen: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
):
    """
    GIVEN NOTIFS_BASE_URL set to "" in the environment and a real value in the dump
    WHEN a ping is sent
    THEN the empty env value wins (the dump is not consulted) and no request is made.
    """
    dump = tmp_path / "container_environment"
    dump.write_text(f"NOTIFS_BASE_URL={_BASE_URL}\n")
    monkeypatch.setattr(notifs_hub, "CONTAINER_ENVIRONMENT_FILE", str(dump))
    monkeypatch.setenv("NOTIFS_BASE_URL", "")
    assert notifs_hub.ping("metrics_flush") is False
    urlopen.assert_not_called()
    assert "outcome=error" in capsys.readouterr().err


def test_unset_base_url_is_error_without_request(
    configured: Path, urlopen: MagicMock, monkeypatch: pytest.MonkeyPatch, capsys
):
    """
    GIVEN key files present but NOTIFS_BASE_URL unset
    WHEN a ping is sent
    THEN the outcome is error with zero requests.
    """
    monkeypatch.delenv("NOTIFS_BASE_URL")
    assert notifs_hub.ping("metrics_flush") is False
    urlopen.assert_not_called()
    assert "outcome=error" in capsys.readouterr().err


@pytest.mark.parametrize(
    "base_url",
    ["http://hub.example.test", "ftp://hub.example.test", "hub.example.test"],
)
def test_non_https_base_url_is_error_without_request(
    configured: Path,
    urlopen: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    base_url: str,
):
    """
    GIVEN a NOTIFS_BASE_URL that is not https
    WHEN a ping is sent
    THEN the outcome is error with zero requests and no secret in the log.
    """
    monkeypatch.setenv("NOTIFS_BASE_URL", base_url)
    assert notifs_hub.ping("metrics_flush") is False
    urlopen.assert_not_called()
    err = capsys.readouterr().err
    assert "outcome=error" in err
    assert "must use https" in err
    assert _KEY not in err
    assert _CLIENT_SECRET not in err


def test_uppercase_https_scheme_is_accepted(
    configured: Path, urlopen: MagicMock, monkeypatch: pytest.MonkeyPatch
):
    """
    GIVEN a NOTIFS_BASE_URL whose scheme is upper case HTTPS
    WHEN a ping is sent
    THEN the request is made.
    """
    monkeypatch.setenv("NOTIFS_BASE_URL", "HTTPS://hub.example.test")
    assert notifs_hub.ping("metrics_flush") is True
    urlopen.assert_called_once()


def test_ping_builds_its_opener_with_the_redirect_refusing_handler(
    configured: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    GIVEN a configured production environment
    WHEN a ping is sent
    THEN the opener is built with the redirect-refusing handler.
    """
    opener = MagicMock()
    opener.open.return_value = _ok_response()
    build_opener = MagicMock(return_value=opener)
    monkeypatch.setattr("urllib.request.build_opener", build_opener)
    assert notifs_hub.ping("metrics_flush") is True
    build_opener.assert_called_once_with(notifs_hub._RefuseRedirects)


class _RedirectingHttpsHandler(urllib.request.HTTPSHandler):
    """Answers every https request with a 302 and records the URLs it was asked for.

    Subclasses HTTPSHandler so ``build_opener`` replaces the real one (no network).
    """

    def __init__(self) -> None:
        super().__init__()
        self.requested: list[str] = []

    def https_open(self, request: urllib.request.Request) -> urllib.response.addinfourl:
        self.requested.append(request.full_url)
        message = email.message.Message()
        message["Location"] = "https://login.example.test/cdn-cgi/access/login"
        response = urllib.response.addinfourl(
            io.BytesIO(b""), message, request.full_url, 302
        )
        response.msg = "Found"  # type: ignore[attr-defined]
        return response


def test_redirect_is_refused_and_never_followed():
    """
    GIVEN a hub answering 302 to another host
    WHEN a request goes through the redirect-refusing opener
    THEN an HTTPError 302 is raised and only the original URL was requested.
    """
    handler = _RedirectingHttpsHandler()
    opener = urllib.request.build_opener(notifs_hub._RefuseRedirects, handler)
    request = urllib.request.Request(f"{_BASE_URL}/v1/heartbeats/urls4irl/x", data=b"")
    with pytest.raises(urllib.error.HTTPError) as raised:
        opener.open(request, timeout=1)
    assert raised.value.code == 302
    assert handler.requested == [f"{_BASE_URL}/v1/heartbeats/urls4irl/x"]


def test_ping_logs_a_redirect_as_http_302(configured: Path, urlopen: MagicMock, capsys):
    """
    GIVEN the opener raising the HTTPError a refused redirect produces
    WHEN a ping is sent
    THEN it returns False and logs outcome=http_302.
    """
    urlopen.side_effect = urllib.error.HTTPError(_BASE_URL, 302, "Found", {}, None)  # type: ignore[arg-type]
    assert notifs_hub.ping("metrics_flush") is False
    assert "outcome=http_302" in capsys.readouterr().err


def test_nothing_configured_is_missing_key(
    monkeypatch: pytest.MonkeyPatch, urlopen: MagicMock, capsys
):
    """
    GIVEN PRODUCTION=true with NOTIFS_BASE_URL and NOTIFS_KEY_DIR both unset
    WHEN a ping is sent
    THEN the outcome is missing_key (pins the check order) with zero requests.
    """
    monkeypatch.setenv("PRODUCTION", "true")
    assert notifs_hub.ping("metrics_flush") is False
    urlopen.assert_not_called()
    assert "outcome=missing_key" in capsys.readouterr().err


def test_safe_ping_swallows_exception_from_ping(
    configured: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """
    GIVEN ping raising an unexpected exception
    WHEN safe_ping is called
    THEN it returns False and logs error with the secret masked.
    """

    def _boom(*args: Any, **kwargs: Any) -> bool:
        raise RuntimeError(f"leaked {_KEY}")

    monkeypatch.setattr(notifs_hub, "ping", _boom)
    assert notifs_hub.safe_ping("metrics_flush") is False
    err = capsys.readouterr().err
    assert "outcome=error" in err
    assert _KEY not in err


def test_logs_never_contain_key_or_secret(configured: Path, urlopen: MagicMock, capsys):
    """
    GIVEN transport errors whose text embeds the key and the Access secret
    WHEN pings fail
    THEN neither value reaches stderr.
    """
    urlopen.side_effect = urllib.error.URLError(f"bad {_KEY} and {_CLIENT_SECRET}")
    notifs_hub.ping("metrics_flush")
    urlopen.side_effect = OSError(f"{_CLIENT_SECRET}{_KEY}")
    notifs_hub.ping("metrics_flush", fail=True)
    err = capsys.readouterr().err
    assert err.count("outcome=error") == 2
    assert _KEY not in err
    assert _CLIENT_SECRET not in err


@pytest.mark.parametrize("scenario", ["ok", "skip", "http", "unconfigured"])
def test_cli_always_exits_zero(
    configured: Path,
    urlopen: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
):
    """
    GIVEN each ping outcome
    WHEN the CLI runs
    THEN it exits 0.
    """
    if scenario == "skip":
        monkeypatch.delenv("PRODUCTION")
    elif scenario == "http":
        urlopen.side_effect = urllib.error.HTTPError(
            _BASE_URL,
            500,
            "err",
            {},
            None,  # type: ignore[arg-type]
        )
    elif scenario == "unconfigured":
        monkeypatch.delenv("NOTIFS_KEY_DIR")
    assert notifs_hub.main(["ping", "metrics_flush", "--fail"]) == 0


def test_cli_exits_zero_on_bad_arguments():
    """
    GIVEN no check name
    WHEN the CLI runs
    THEN it still exits 0.
    """
    assert notifs_hub.main(["ping"]) == 0


def test_module_is_stdlib_only():
    """
    GIVEN scripts/notifs_hub.py
    WHEN it is loaded without the project root on sys.path
    THEN no third-party or project module is imported.
    """
    assert_module_is_stdlib_only(
        Path(notifs_hub.__file__),
        ("requests", "redis", "flask", "backend", "yaml", "sqlalchemy"),
    )
