"""Pick the single most important validation problem of a saved custom flow.

`first_invalid_detail` is pure (no app context; `flow_invalid_response` needs
one for `jsonify`). It orders the validator's error map by the DD-58 rules so
`/flow` and the flow list always show the same message.
"""

import re
from collections.abc import Mapping

from flask import jsonify

from backend.api_common.responses import FlaskResponse
from backend.schemas.metrics import FlowInvalidDetailSchema, FlowInvalidResponseSchema
from backend.utils.strings.metric_flow_strs import FLOW_INVALID_UNKNOWN_STR

__all__ = ["first_invalid_detail", "flow_invalid_response"]

_STEP_PATH = re.compile(r"^steps\.(\d+)(?:\.(.+))?$")
_INDEXED_SUFFIX = re.compile(r"^(dim_filter|drop_breakdown\.dim_filter)\.(\d+)$")

_ROOT_FIELD = "__root__"
_FLOW_LEVEL_RANK: dict[str, int] = {_ROOT_FIELD: 0, "display_name": 1, "steps": 2}
_OTHER_FLOW_LEVEL_RANK = 3

_STEP_FIELD_RANK: dict[str, int] = {
    "stream": 0,
    "event_name": 1,
    "api_endpoint": 2,
    "api_method": 3,
    "label": 4,
    "dim_filter": 5,
    "drop_breakdown": 7,
    "drop_breakdown.event_name": 8,
    "drop_breakdown.dim_filter": 9,
    "drop_breakdown.group_by": 11,
}
_BARE_STEP_RANK = 0
_DIM_FILTER_INDEXED_RANK = 6
_DROP_DIM_FILTER_INDEXED_RANK = 10
_OTHER_STEP_RANK = 12

_SortKey = tuple[int, int, int, int, str]


def _step_suffix_rank(suffix: str | None) -> tuple[int, int]:
    """Return (rank, numeric filter index) for the part after `steps.<i>`."""
    if suffix is None:
        return _BARE_STEP_RANK, 0
    if suffix in _STEP_FIELD_RANK:
        return _STEP_FIELD_RANK[suffix], 0
    indexed = _INDEXED_SUFFIX.match(suffix)
    if indexed is not None:
        rank = (
            _DIM_FILTER_INDEXED_RANK
            if indexed.group(1) == "dim_filter"
            else _DROP_DIM_FILTER_INDEXED_RANK
        )
        return rank, int(indexed.group(2))
    return _OTHER_STEP_RANK, 0


def _sort_key(path: str) -> _SortKey:
    step_match = _STEP_PATH.match(path)
    if step_match is None:
        return 0, _FLOW_LEVEL_RANK.get(path, _OTHER_FLOW_LEVEL_RANK), 0, 0, path
    rank, filter_index = _step_suffix_rank(step_match.group(2))
    return 1, int(step_match.group(1)), rank, filter_index, path


def first_invalid_detail(errors: Mapping[str, list[str]]) -> FlowInvalidDetailSchema:
    """Return the DD-58 first problem; fail closed to a flow-level detail."""
    selectable = [path for path, messages in errors.items() if messages]
    if not selectable:
        return FlowInvalidDetailSchema(
            step_index=None, field=_ROOT_FIELD, reason=FLOW_INVALID_UNKNOWN_STR
        )
    path = min(selectable, key=_sort_key)
    step_match = _STEP_PATH.match(path)
    return FlowInvalidDetailSchema(
        step_index=int(step_match.group(1)) if step_match is not None else None,
        field=path,
        reason=errors[path][0],
    )


def flow_invalid_response(detail: FlowInvalidDetailSchema) -> FlaskResponse:
    """Build the pinned 422 body; `step_index: null` stays present, no `status`."""
    body = FlowInvalidResponseSchema(error="flow_invalid", invalid=detail)
    return jsonify(body.model_dump(mode="json")), 422
