from __future__ import annotations

import datetime
import decimal
import enum
import json
from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.orm import ColumnProperty

from backend import db

# Imported for its side effect: backend/models/__init__.py imports every model
# module, so the mapper registry iterated below is fully populated even in
# testing mode (where create_app skips the migration-time import).
import backend.models  # noqa: F401

_TABLE_GRID_LIMIT: int = 50
_CELL_TRUNCATE_LENGTH: int = 120
_NULL_PLACEHOLDER: str = "—"
_TRUNCATION_SUFFIX: str = "…"
_PK_SEGMENT_SEPARATOR: str = ","

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
    display_name: str
    row_count: int


@dataclass(frozen=True)
class TableRow:
    """One row of a table grid: its PK URL segment plus formatted cells."""

    pk_segment: str
    cells: list[str]


@dataclass(frozen=True)
class TablePage:
    """One page of a table grid, mirroring the offset/limit pagination of
    ``UserSearchPage`` / ``AuditLogPage``."""

    table_name: str
    column_keys: list[str]
    rows: list[TableRow]
    total_count: int
    limit: int
    offset: int

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
            display_name=model_class.__tablename__,
            row_count=db.session.query(model_class).count(),
        )
        for model_class in _iter_model_classes()
    ]


def get_table_page(
    *,
    table_name: str,
    limit: int = _TABLE_GRID_LIMIT,
    offset: int = 0,
) -> TablePage | None:
    """One page of ``table_name``'s rows, or ``None`` for an unknown table.

    Rows are ordered by primary key for stable pagination; sensitive columns
    are excluded from ``column_keys`` and every cell is truncated to the grid
    display length.
    """
    model_class = _model_by_table_name().get(table_name)
    if model_class is None:
        return None

    visible_columns = _visible_columns(model_class)
    column_keys = [column.key for column in visible_columns]
    total_count = db.session.query(model_class).count()
    records = (
        db.session.query(model_class)
        .order_by(*inspect(model_class).primary_key)
        .limit(limit)
        .offset(offset)
        .all()
    )
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
