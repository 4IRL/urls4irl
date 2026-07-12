from __future__ import annotations

import datetime
import decimal
import enum
import json
from dataclasses import dataclass

from sqlalchemy import Enum as SQLEnum, String, inspect, or_
from sqlalchemy.orm import ColumnProperty
from sqlalchemy.sql.elements import ColumnElement

from backend import db
from backend.admin.user_service import LIKE_ESCAPE_CHAR, escape_like_wildcards

# Imported for its side effect: backend/models/__init__.py imports every model
# module, so the mapper registry iterated below is fully populated even in
# testing mode (where create_app skips the migration-time import).
import backend.models  # noqa: F401

_TABLE_GRID_LIMIT: int = 50
_CELL_TRUNCATE_LENGTH: int = 120
_NULL_PLACEHOLDER: str = "—"
_TRUNCATION_SUFFIX: str = "…"
_PK_SEGMENT_SEPARATOR: str = ","
_SORT_DIRECTION_ASC: str = "asc"
_SORT_DIRECTION_DESC: str = "desc"

# Per-model column exclusions for sensitive data. The browser is read-only,
# but password hashes and token/secret columns still must never render in a
# browser page. Keyed by ``model_class.__name__`` → list of ORM attribute keys
# (``column.key``), excluded from BOTH the grid and the row-detail view.
_SENSITIVE_COLUMN_EXCLUSIONS: dict[str, list[str]] = {
    "Users": ["password"],
    "ApiRefreshTokens": ["token"],
    "Forgot_Passwords": ["reset_token"],
    "Email_Validations": ["validation_token"],
    "UserOAuthIdentity": ["provider_subject"],
}


@dataclass(frozen=True)
class TableSummary:
    """One entry on the DB-browser overview: a table and its live row count."""

    table_name: str
    row_count: int


@dataclass(frozen=True)
class TableRow:
    """One row of a table grid: its PK URL segment plus formatted cells."""

    pk_segment: str
    cells: list[str]


@dataclass(frozen=True)
class _PaginationBase:
    """Shared offset/limit pagination state and derived Previous/Next math.

    Base for every admin paginated page (``TablePage`` here and
    ``_DetailTablePage`` in ``backend.admin.routes``) so the four navigation
    properties are defined once. Subclasses add their own row/column fields;
    since all call sites construct these dataclasses with keyword arguments,
    the extra base fields do not affect construction order.
    """

    total_count: int
    offset: int
    limit: int

    @property
    def has_previous(self) -> bool:
        return self.offset > 0

    @property
    def has_next(self) -> bool:
        return self.offset + self.limit < self.total_count

    @property
    def previous_offset(self) -> int:
        return max(self.offset - self.limit, 0)

    @property
    def next_offset(self) -> int:
        return self.offset + self.limit


@dataclass(frozen=True)
class TablePage(_PaginationBase):
    """One page of a table grid, mirroring the offset/limit pagination of
    ``UserSearchPage`` / ``AuditLogPage``."""

    table_name: str
    column_keys: list[str]
    rows: list[TableRow]
    sort_key: str
    direction: str
    query: str


@dataclass(frozen=True)
class RowDetailField:
    """One key/value pair on the row-detail page (value never truncated)."""

    key: str
    value: str


@dataclass(frozen=True)
class RowDetail:
    """The full, untruncated field list for a single row."""

    table_name: str
    pk_segment: str
    fields: list[RowDetailField]


def _iter_model_classes() -> list[type]:
    """Every mapped SQLAlchemy model class, sorted by ``__tablename__``.

    Iterating the registry (rather than a hand-maintained import list)
    guarantees any future model automatically appears in the browser. The
    sort key is ``__tablename__`` because that is the URL path segment used to
    resolve a table.
    """
    model_classes = [
        mapper.class_
        for mapper in db.Model.registry.mappers  # type: ignore[attr-defined]
    ]
    return sorted(model_classes, key=lambda model_class: model_class.__tablename__)


def _model_by_table_name() -> dict[str, type]:
    """Map each ``__tablename__`` to its model class for path resolution.

    Built straight from the mapper registry — the lookup is order-independent,
    so no sort is applied (unlike ``_iter_model_classes()`` used for display).
    """
    return {
        mapper.class_.__tablename__: mapper.class_
        for mapper in db.Model.registry.mappers  # type: ignore[attr-defined]
    }


def _visible_columns(model_class: type) -> list[ColumnProperty]:
    """Ordered column attributes of ``model_class`` minus its sensitive
    exclusions.

    Iterates ``model_class.__table__.columns`` — the true table/DDL order, so
    the primary key (``id``) comes first, matching the grid mock. (The mapper's
    own ``.columns`` collection is ordered by mapper-configuration order, which
    can float mixin/late-bound columns like ``created_at`` ahead of ``id``, so
    it is deliberately not used here.) Each ``Column`` is resolved back to its
    ``ColumnProperty`` whose ``.key`` is the ORM attribute name usable with
    ``getattr``, NOT the physical DB column name.
    """
    mapper = inspect(model_class)
    excluded_keys = _SENSITIVE_COLUMN_EXCLUSIONS.get(model_class.__name__, [])
    visible_columns: list[ColumnProperty] = []
    for column in model_class.__table__.columns:
        column_attr = mapper.get_property_by_column(column)
        if column_attr.key not in excluded_keys:
            visible_columns.append(column_attr)
    return visible_columns


def _primary_key_attr_keys(model_class: type) -> list[str]:
    """ORM attribute names of ``model_class``'s primary-key columns, in PK
    order (a single name for surrogate PKs, several for composite PKs)."""
    mapper = inspect(model_class)
    return [
        mapper.get_property_by_column(pk_column).key for pk_column in mapper.primary_key
    ]


def format_cell_value(value: object, *, truncate: int | None = None) -> str:
    """Render an arbitrary column value as a display-safe string.

    Dispatches by type so JSONB, enums, timezone-aware datetimes, dates, and
    Decimals each render deterministically; everything else falls back to
    ``str``. The returned string is NOT HTML-escaped — Jinja autoescape handles
    that at render time.

    Examples:
        >>> format_cell_value(None)
        '—'
        >>> format_cell_value({"a": 1})
        '{"a": 1}'
        >>> import datetime
        >>> format_cell_value(
        ...     datetime.datetime(2026, 7, 1, 8, 30, tzinfo=datetime.timezone.utc)
        ... )
        '2026-07-01 08:30:00+00:00'
        >>> format_cell_value(datetime.date(2026, 7, 1))
        '2026-07-01'
        >>> import decimal
        >>> format_cell_value(decimal.Decimal("5.20"))
        '5.20'
        >>> format_cell_value("abcdef", truncate=3)
        'abc…'
        >>> format_cell_value("ab", truncate=3)
        'ab'
    """
    if value is None:
        return _NULL_PLACEHOLDER
    if isinstance(value, (dict, list)):
        result = json.dumps(value, default=str, ensure_ascii=False)
    elif isinstance(value, enum.Enum):
        result = str(value.value)
    elif isinstance(value, datetime.datetime):
        result = value.isoformat(sep=" ")
    elif isinstance(value, datetime.date):
        result = value.isoformat()
    elif isinstance(value, decimal.Decimal):
        result = str(value)
    else:
        result = str(value)

    if truncate is not None and len(result) > truncate:
        return result[:truncate] + _TRUNCATION_SUFFIX
    return result


def _row_pk_segment(model_class: type, row: object) -> str:
    """The URL path segment identifying ``row`` — a single value for surrogate
    PKs, the string PK for ``Event_Registry``, or the comma-joined tuple for
    the composite ``Utub_Members`` PK.
    """
    return _PK_SEGMENT_SEPARATOR.join(
        str(getattr(row, pk_attr_key))
        for pk_attr_key in _primary_key_attr_keys(model_class)
    )


def _parse_row_pk(model_class: type, raw_pk: str) -> tuple | object | None:
    """Coerce a raw ``<row_pk>`` URL segment into a value ``db.session.get``
    can consume, or ``None`` when it cannot be reconciled with the PK.

    Returns a single scalar for a one-column PK and a PK-ordered tuple for a
    composite PK. ``None`` is returned when the segment count does not match
    the PK column count or when any part fails to coerce to its column's
    Python type.

    Examples:
        >>> # single int PK "1" → 1 ; composite "3,4" → (3, 4)
        >>> # non-numeric "abc" for an int PK → None
    """
    primary_key_columns = inspect(model_class).primary_key
    raw_parts = raw_pk.split(_PK_SEGMENT_SEPARATOR)
    if len(raw_parts) != len(primary_key_columns):
        return None

    coerced_parts: list[object] = []
    for pk_column, raw_part in zip(primary_key_columns, raw_parts):
        try:
            coerced_parts.append(pk_column.type.python_type(raw_part))
        except (ValueError, TypeError):
            return None

    if len(coerced_parts) == 1:
        return coerced_parts[0]
    return tuple(coerced_parts)


def list_tables() -> list[TableSummary]:
    """A ``TableSummary`` for every mapped model, ordered by table name."""
    return [
        TableSummary(
            table_name=model_class.__tablename__,
            row_count=db.session.query(model_class).count(),
        )
        for model_class in _iter_model_classes()
    ]


def _resolve_sort_attr_key(model_class: type, sort_key: str | None) -> str:
    """The visible-column attribute key to sort on, or the primary key fallback.

    Invalid input is ignored rather than raising: a ``sort_key`` that is
    ``None``, unknown, or a sensitive (hence non-visible) column falls back to
    the first primary-key attribute so ordering is always well-defined.

    Examples:
        >>> # sort_key="username" for Users → "username"
        >>> # sort_key="password" (sensitive) or "nope" (unknown) → "id"
    """
    visible_keys = {column.key for column in _visible_columns(model_class)}
    if sort_key is not None and sort_key in visible_keys:
        return sort_key
    return _primary_key_attr_keys(model_class)[0]


def _build_order_by(
    model_class: type, *, sort_key: str, direction: str
) -> list[ColumnElement]:
    """Order-by clauses: the chosen column then every primary-key column.

    The primary-key columns are always appended ascending so ties on the
    chosen column resolve deterministically (stable pagination). ``direction``
    only descends on an exact ``"desc"``; anything else ascends.
    """
    sort_attr = getattr(model_class, sort_key)
    if direction == _SORT_DIRECTION_DESC:
        primary_clause = sort_attr.desc()
    else:
        primary_clause = sort_attr.asc()
    pk_clauses = [
        getattr(model_class, pk_key) for pk_key in _primary_key_attr_keys(model_class)
    ]
    return [primary_clause, *pk_clauses]


def _is_searchable_string_column(column_attr: ColumnProperty) -> bool:
    """Whether ``column_attr`` maps to a text-like column safe for ILIKE search.

    ``String`` covers the ``VARCHAR``/``TEXT`` family; SQLAlchemy's ``Enum``
    subclasses ``String`` but is a closed set, so it is excluded. Numeric,
    datetime, boolean, and JSON columns are all skipped.
    """
    column_type = column_attr.columns[0].type
    return isinstance(column_type, String) and not isinstance(column_type, SQLEnum)


def _build_search_filter(model_class: type, query: str) -> ColumnElement | None:
    """An OR-of-ILIKE filter over visible string columns, or ``None``.

    Returns ``None`` when the query is blank or the model has no searchable
    string columns, in which case no filter is applied. Wildcards in the query
    are escaped so ``"%"`` matches a literal percent rather than every row.
    """
    stripped_query = query.strip()
    if not stripped_query:
        return None
    string_attrs = [
        getattr(model_class, column.key)
        for column in _visible_columns(model_class)
        if _is_searchable_string_column(column)
    ]
    if not string_attrs:
        return None
    like_pattern = f"%{escape_like_wildcards(stripped_query)}%"
    return or_(
        *(
            string_attr.ilike(like_pattern, escape=LIKE_ESCAPE_CHAR)
            for string_attr in string_attrs
        )
    )


def get_table_page(
    *,
    table_name: str,
    limit: int = _TABLE_GRID_LIMIT,
    offset: int = 0,
    sort_key: str | None = None,
    direction: str = _SORT_DIRECTION_ASC,
    query: str = "",
) -> TablePage | None:
    """One page of ``table_name``'s rows, or ``None`` for an unknown table.

    Rows are ordered by the resolved ``sort_key`` (falling back to the primary
    key for invalid/sensitive/absent input) with a primary-key tiebreaker for
    deterministic pagination. A non-blank ``query`` filters rows by a
    case-insensitive substring match across visible string columns, and
    ``total_count`` reflects that filter. Sensitive columns are excluded from
    ``column_keys`` (so they are neither sortable nor searchable), and every
    cell is truncated to the grid display length.
    """
    model_class = _model_by_table_name().get(table_name)
    if model_class is None:
        return None

    visible_columns = _visible_columns(model_class)
    column_keys = [column.key for column in visible_columns]

    resolved_sort_key = _resolve_sort_attr_key(model_class, sort_key)
    normalized_direction = (
        _SORT_DIRECTION_DESC
        if direction == _SORT_DIRECTION_DESC
        else _SORT_DIRECTION_ASC
    )
    normalized_query = query.strip()
    order_by = _build_order_by(
        model_class, sort_key=resolved_sort_key, direction=normalized_direction
    )

    filtered_query = db.session.query(model_class)
    search_filter = _build_search_filter(model_class, normalized_query)
    if search_filter is not None:
        filtered_query = filtered_query.filter(search_filter)

    total_count = filtered_query.count()
    records = filtered_query.order_by(*order_by).limit(limit).offset(offset).all()
    rows = [
        TableRow(
            pk_segment=_row_pk_segment(model_class, record),
            cells=[
                format_cell_value(
                    getattr(record, column.key), truncate=_CELL_TRUNCATE_LENGTH
                )
                for column in visible_columns
            ],
        )
        for record in records
    ]
    return TablePage(
        table_name=table_name,
        column_keys=column_keys,
        rows=rows,
        total_count=total_count,
        limit=limit,
        offset=offset,
        sort_key=resolved_sort_key,
        direction=normalized_direction,
        query=normalized_query,
    )


def get_row_detail(*, table_name: str, raw_pk: str) -> RowDetail | None:
    """The full field list for one row, or ``None`` when the table is unknown,
    the PK cannot be parsed, or no such row exists.
    """
    model_class = _model_by_table_name().get(table_name)
    if model_class is None:
        return None

    primary_key = _parse_row_pk(model_class, raw_pk)
    if primary_key is None:
        return None

    record = db.session.get(model_class, primary_key)
    if record is None:
        return None

    fields = [
        RowDetailField(
            key=column.key,
            value=format_cell_value(getattr(record, column.key)),
        )
        for column in _visible_columns(model_class)
    ]
    return RowDetail(table_name=table_name, pk_segment=raw_pk, fields=fields)
