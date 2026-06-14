"""Flow id enum — split from `flows.py` to break an import cycle.

`backend.schemas.requests.metrics` needs `ALL_FLOW_IDS` to build
`FlowIdLiteral`, while `flows.py` needs `FlowFilterCondition` from that same
schema module. Hoisting the `FlowId` StrEnum into this dependency-free leaf
module lets the schema import the ids without importing `flows.py` (which would
be a cycle), and lets `flows.py` re-export `FlowId`/`ALL_FLOW_IDS` so callers
keep a single import surface.
"""

from __future__ import annotations

from enum import StrEnum


class FlowId(StrEnum):
    CREATE_UTUB = "create_utub"
    ADD_URL_TO_UTUB = "add_url_to_utub"
    REGISTER = "register"
    LOGIN = "login"


# Module-level tuple of every FlowId value. Reused by `FlowIdLiteral` in the
# query schema and by `generate_flows_ts()` so the wire contract and the
# codegen surface stay aligned with this source of truth.
ALL_FLOW_IDS: tuple[str, ...] = tuple(member.value for member in FlowId)
