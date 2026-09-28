"""Host-port resolution for a spoke stack, run by `make` before every stack start.

Each checkout's compose project ("spoke") publishes `web` and `vite` on host
ports that must not collide with another spoke or any other host listener.
Rather than keeping a ledger, this probes reality on every start and caches
the answer in a gitignored env file, so a spoke keeps its URL across
`down`/`up`. Stdlib only: it runs on the host under bare mise python.

Resolution, per service:
1. An explicit port (`--web-port`/`--vite-port`, fed from U4I_WEB_PORT /
   U4I_VITE_PORT) wins; if something else holds it, fail, naming the holder.
   An explicit port is cached like any other, so it sticks after the variable
   is unset while it stays free; delete docker/.ports.generated.env to
   re-resolve from scratch.
2. Else the cached port is kept while it is free or published by this project.
3. Else walk upward from the preferred port (the base for the primary clone,
   base + crc32(slug) % 99 + 1 for a worktree) to the first free one, within
   base..base+199.

"Free" means no other compose project publishes it (`docker ps --filter
publish=<port>`) and a test bind on 0.0.0.0 (SO_REUSEADDR on) succeeds
(non-Docker listeners).
A port this project already publishes counts as free even though the bind
fails. Subcommands (see `main`): `resolve` writes the file, `show` prints it.
"""

from __future__ import annotations

import argparse
import errno
import os
import socket
import subprocess
import sys
import tempfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

WEB_BASE_PORT: int = 8659
VITE_BASE_PORT: int = 5173
# A worktree prefers base + 1..99, leaving the base port to the primary clone.
WORKTREE_OFFSET_SPAN: int = 99
# Candidates walked per service: base..base+199.
PORT_RANGE_SIZE: int = 200
DOCKER_PS_TIMEOUT_SECONDS: int = 30
COMPOSE_PROJECT_LABEL: str = "com.docker.compose.project"
HOST_PROCESS_HOLDER: str = "a host process"
UNLABELLED_CONTAINER_HOLDER: str = "a container outside any compose project"

OwnerFn = Callable[[int], str | None]
BindableFn = Callable[[int], bool]


class PortUnavailable(RuntimeError):
    """No usable port: an explicit port is held, or the whole range is."""


class DockerPsError(RuntimeError):
    """`docker ps` could not answer, so a port's owner is unknown."""


@dataclass(frozen=True)
class Service:
    name: str
    base_port: int
    env_key: str
    url_template: str


SERVICES: tuple[Service, ...] = (
    Service("web", WEB_BASE_PORT, "U4I_WEB_PORT", "http://127.0.0.1:{port}/"),
    Service("vite", VITE_BASE_PORT, "U4I_VITE_PORT", "http://localhost:{port}"),
)


@dataclass(frozen=True)
class Resolution:
    port: int
    note: str | None


# --- real probes ---------------------------------------------------------------


def docker_port_owner(port: int) -> str | None:
    """The compose project of a running container publishing `port`, else None.

    A container outside any compose project reports a generic holder name. Any
    `docker ps` failure raises: an unknown owner must never read as "free".
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"publish={port}",
                "--format",
                f'{{{{.Label "{COMPOSE_PROJECT_LABEL}"}}}}',
            ],
            capture_output=True,
            text=True,
            timeout=DOCKER_PS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as timed_out:
        raise DockerPsError(
            f"docker ps timed out after {DOCKER_PS_TIMEOUT_SECONDS}s"
        ) from timed_out
    except OSError as launch_error:
        raise DockerPsError(str(launch_error)) from launch_error
    if result.returncode != 0:
        raise DockerPsError(
            result.stderr.strip() or f"docker ps exited {result.returncode}"
        )
    holders = result.stdout.splitlines()
    if not holders:
        return None
    return next((holder for holder in holders if holder), UNLABELLED_CONTAINER_HOLDER)


def port_is_bindable(port: int) -> bool:
    """Whether a fresh TCP socket can bind 0.0.0.0:`port`.

    Only EADDRINUSE means "held"; any other bind error (e.g. EACCES on a
    privileged port) propagates so `main` reports its real message.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        # SO_REUSEADDR on, so a TIME_WAIT leftover from this spoke's own previous run (after `make down`) doesn't
        # read as "held" and move the URL. Linux still refuses the bind while any socket LISTENs on the port
        # (Docker's proxy also binds with SO_REUSEADDR).
        probe_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe_socket.bind(("0.0.0.0", port))
        except OSError as bind_error:
            if bind_error.errno == errno.EADDRINUSE:
                return False
            raise
    return True


# --- resolution ------------------------------------------------------------------


def preferred_port(base_port: int, slug: str, primary: bool) -> int:
    if primary:
        return base_port
    return base_port + zlib.crc32(slug.encode()) % WORKTREE_OFFSET_SPAN + 1


def _holder(
    port: int, project: str, owner_fn: OwnerFn, bindable_fn: BindableFn
) -> str | None:
    """Who holds `port` against this project, or None when it is usable."""
    owner = owner_fn(port)
    if owner == project:
        return None
    if owner is not None:
        return owner
    return None if bindable_fn(port) else HOST_PROCESS_HOLDER


def resolve_service(
    service: Service,
    project: str,
    slug: str,
    primary: bool,
    explicit_port: int | None,
    cached_port: int | None,
    claimed: set[int],
    owner_fn: OwnerFn,
    bindable_fn: BindableFn,
) -> Resolution:
    """Pick `service`'s host port; `claimed` holds ports given to (or explicitly set for) another service."""

    def holder_of(port: int) -> str | None:
        if port in claimed:
            return f"this spoke's other service ({port} is claimed by it)"
        return _holder(port, project, owner_fn, bindable_fn)

    if explicit_port is not None:
        holder = holder_of(explicit_port)
        if holder is not None:
            raise PortUnavailable(
                f"{service.env_key}={explicit_port} is held by {holder}; "
                f"free it or choose another {service.env_key}"
            )
        return Resolution(explicit_port, None)

    first_rejected: tuple[int, str] | None = None
    if cached_port is not None:
        holder = holder_of(cached_port)
        if holder is None:
            return Resolution(cached_port, None)
        first_rejected = (cached_port, holder)

    start = preferred_port(service.base_port, slug, primary)
    holders: list[tuple[int, str]] = []
    for candidate in range(start, service.base_port + PORT_RANGE_SIZE):
        holder = holder_of(candidate)
        if holder is None:
            note = None
            if first_rejected is None and holders:
                first_rejected = holders[0]
            if first_rejected is not None:
                rejected_port, rejected_holder = first_rejected
                note = (
                    f"{rejected_port} was held by {rejected_holder}; using {candidate}"
                )
            return Resolution(candidate, note)
        holders.append((candidate, holder))
    listing = ", ".join(f"{port}={holder}" for port, holder in holders)
    raise PortUnavailable(
        f"no free {service.name} port in {start}..{service.base_port + PORT_RANGE_SIZE - 1} "
        f"(held: {listing}); set {service.env_key}=<port> to pick one explicitly"
    )


# --- cache file --------------------------------------------------------------------


def read_cache(path: Path) -> dict[str, int]:
    """Cached ports by env key. A missing or malformed entry is simply absent: it's a cache."""
    if not path.exists():
        return {}
    cached: dict[str, int] = {}
    for line in path.read_text().splitlines():
        key, separator, raw_value = line.partition("=")
        if separator and raw_value.isascii() and raw_value.isdecimal():
            port = int(raw_value)
            if 0 < port < 65536:
                cached[key.strip()] = port
    return cached


def render_cache(ports: dict[str, int]) -> str:
    return "".join(
        f"{service.env_key}={ports[service.env_key]}\n" for service in SERVICES
    )


def _write_atomically(path: Path, content: str) -> None:
    """Write via a same-directory temp file + os.replace, so compose never reads a partial file.

    The file keeps NamedTemporaryFile's owner-only 0600 mode: only host-side
    make/compose (running as this user) read it.
    """
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)
        os.replace(temp_path, path)
    except BaseException:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def _urls_line(ports: dict[str, int]) -> str:
    return "  ".join(
        f"{service.name}: {service.url_template.format(port=ports[service.env_key])}"
        for service in SERVICES
    )


# --- subcommands -------------------------------------------------------------------


def _resolve(
    args: argparse.Namespace, owner_fn: OwnerFn, bindable_fn: BindableFn
) -> int:
    cached = read_cache(args.output)
    explicit = {"U4I_WEB_PORT": args.web_port, "U4I_VITE_PORT": args.vite_port}
    ports: dict[str, int] = {}
    notes: list[str] = []
    for service in SERVICES:
        explicit_port = explicit[service.env_key]
        # An auto-resolved service also avoids every other service's explicit port, so an explicit vite port equal
        # to web's cached/preferred port moves web instead of failing vite. Two equal explicit ports still fail
        # (on the later service).
        claimed = set(ports.values())
        if explicit_port is None:
            claimed |= {
                port
                for env_key, port in explicit.items()
                if env_key != service.env_key and port is not None
            }
        resolution = resolve_service(
            service,
            project=args.project,
            slug=args.slug,
            primary=args.primary,
            explicit_port=explicit_port,
            cached_port=cached.get(service.env_key),
            claimed=claimed,
            owner_fn=owner_fn,
            bindable_fn=bindable_fn,
        )
        ports[service.env_key] = resolution.port
        if resolution.note is not None:
            notes.append(f"{service.name}: {resolution.note}")
    _write_atomically(args.output, render_cache(ports))
    for note in notes:
        print(note)
    print(_urls_line(ports))
    return 0


def _show(output: Path) -> int:
    cached = read_cache(output)
    if not all(service.env_key in cached for service in SERVICES):
        print("ports:          not resolved yet — run make up")
        return 0
    print(f"ports:          {_urls_line(cached)}")
    return 0


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as bad_value:
        raise argparse.ArgumentTypeError(
            f"expected a port number, got {value!r}"
        ) from bad_value
    if not 0 < port < 65536:
        raise argparse.ArgumentTypeError(f"port {port} is outside 1..65535")
    return port


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spoke_ports",
        description="Resolve collision-free host ports for this spoke's web and vite.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    resolve_parser = subcommands.add_parser(
        "resolve", help="probe, pick and cache this spoke's host ports"
    )
    resolve_parser.add_argument("--project", required=True)
    resolve_parser.add_argument("--slug", required=True)
    resolve_parser.add_argument("--primary", action="store_true")
    resolve_parser.add_argument("--web-port", type=_port)
    resolve_parser.add_argument("--vite-port", type=_port)
    resolve_parser.add_argument("--output", type=Path, required=True)

    show_parser = subcommands.add_parser("show", help="print the cached ports")
    show_parser.add_argument("--output", type=Path, required=True)
    return parser


def main(
    argv: list[str],
    owner_fn: OwnerFn = docker_port_owner,
    bindable_fn: BindableFn = port_is_bindable,
) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "show":
            return _show(args.output)
        return _resolve(args, owner_fn, bindable_fn)
    except PortUnavailable as unavailable:
        print(f"spoke ports: {unavailable}", file=sys.stderr)
        return 1
    except DockerPsError as docker_error:
        print(f"spoke ports: docker ps failed — {docker_error}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as file_error:
        print(f"spoke ports: {file_error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
