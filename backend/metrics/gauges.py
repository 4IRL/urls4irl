"""Code-side single source of truth for anonymous-metrics *gauge* metadata + SQL.

A *gauge* is a periodically-sampled scalar value (`COUNT` / `AVG` / `MAX`)
computed over a relational table — total users, average URLs per UTub, the
single most-shared URL, etc. Each gauge is one `GaugeDefinition` entry in
`GAUGE_REGISTRY`, and its aggregate SQL is *generated* from that entry by the
pure `build_gauge_sql()` function. A contributor adds a new gauge with exactly
one `GaugeName` member + one `GAUGE_REGISTRY` entry — no hand-written SQL and no
dispatcher edit.

This module is a **pure leaf**: its only imports are the stdlib `enum`,
`dataclasses`, and `typing`. It deliberately imports **no Flask, no SQLAlchemy,
and no `EventName`** so the standalone psycopg2 gauge-sampler (which side-loads
this file by absolute path inside the workflow container — a venv with only
`redis` + `psycopg2`) and the Flask app share the exact same gauge definitions
and SQL generator. Any heavy import here would crash the workflow container.

Adding a new gauge: append a `GaugeName` member, then add an entry here with the
same key. The unit test `tests/unit/test_gauges.py` asserts
`set(GAUGE_REGISTRY) == set(GaugeName)`, so a missing entry fails CI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# k-anonymity floor: a `max_*` distribution gauge is suppressed (NULL) when the
# distinct population grouped over is below this count, so a single outlier
# entity cannot be re-identified from an extreme maximum.
MIN_GAUGE_POPULATION = 5


class GaugeKind(StrEnum):
    VOLUME = "volume"
    DISTRIBUTION_MAX = "distribution_max"
    DISTRIBUTION_AVG = "distribution_avg"
    # Reserved for future event-derived max gauges (e.g. max URL access count).
    # No shipped gauge references this kind yet; it is kept so the deferred
    # event-derived gauges re-land as a one-place registry add once their
    # source events gain a per-entity dimension key.
    EVENT_DERIVED_MAX = "event_derived_max"


class GaugeName(StrEnum):
    # Volume — single scalar COUNT over a table.
    TOTAL_USERS = "total_users"
    TOTAL_UTUBS = "total_utubs"
    TOTAL_URLS = "total_urls"
    TOTAL_TAGS = "total_tags"
    TOTAL_UTUB_URL_ASSOCIATIONS = "total_utub_url_associations"
    # Distribution — MAX / AVG of a per-entity grouped count.
    MAX_URLS_PER_UTUB = "max_urls_per_utub"
    AVG_URLS_PER_UTUB = "avg_urls_per_utub"
    MAX_TAGS_PER_URL = "max_tags_per_url"
    AVG_TAGS_PER_URL = "avg_tags_per_url"
    MAX_TAGS_PER_UTUB = "max_tags_per_utub"
    AVG_TAGS_PER_UTUB = "avg_tags_per_utub"
    MAX_UTUBS_PER_USER = "max_utubs_per_user"
    MAX_MEMBERS_PER_UTUB = "max_members_per_utub"
    AVG_MEMBERS_PER_UTUB = "avg_members_per_utub"
    MAX_UTUBS_PER_URL = "max_utubs_per_url"
    MAX_URLS_PER_USER = "max_urls_per_user"


# Module-level tuple of every GaugeName value. Defined here, in the source
# module, mirroring `ALL_FLOW_IDS` in `flows.py`; available for any consumer
# that needs the closed gauge-name set (the CLI builds `click.Choice` from this).
ALL_GAUGE_NAMES: tuple[str, ...] = tuple(member.value for member in GaugeName)


@dataclass(frozen=True)
class GaugeDefinition:
    """A flat, kind-discriminated spec carrying every fact needed to describe a
    gauge and to generate its aggregate SQL.

    Physical DB identifiers (`table`, `*_column`) are emitted double-quoted in
    the generated SQL. They are closed-set registry constants, never request
    data, so f-string interpolation of them in `build_gauge_sql` is safe.
    """

    kind: GaugeKind
    # 1-line human-readable text for the `/list` response and CLI output.
    description: str
    # Physical table name for VOLUME / DISTRIBUTION gauges (e.g. "Utubs").
    table: str | None = None
    # VOLUME only: None -> COUNT(*), else COUNT(DISTINCT "<distinct_column>").
    distinct_column: str | None = None
    # DISTRIBUTION only: the physical column to GROUP BY (e.g. "utubID").
    group_by_column: str | None = None
    # DISTRIBUTION inner COUNT("<count_column>"); None -> COUNT(*). For
    # UtubMembers-backed gauges use a real column ("userID"/"utubID") — that
    # table has no `id`.
    count_column: str | None = None
    # Reserved for the future EVENT_DERIVED_MAX kind; the AnonymousMetrics
    # eventName to filter on. No shipped gauge sets it (all 16 are relational).
    event_name: str | None = None
    # Reserved for the future EVENT_DERIVED_MAX kind; the JSONB dimension key to
    # group by. No shipped gauge sets it.
    dimension_key: str | None = None


GAUGE_REGISTRY: dict[GaugeName, GaugeDefinition] = {
    # -----------------------------------------------------------------------
    # Volume — total counts
    # -----------------------------------------------------------------------
    GaugeName.TOTAL_USERS: GaugeDefinition(
        kind=GaugeKind.VOLUME,
        description="Total registered users",
        table="Users",
    ),
    GaugeName.TOTAL_UTUBS: GaugeDefinition(
        kind=GaugeKind.VOLUME,
        description="Total UTubs",
        table="Utubs",
    ),
    GaugeName.TOTAL_URLS: GaugeDefinition(
        kind=GaugeKind.VOLUME,
        description="Total unique URLs stored",
        table="Urls",
    ),
    GaugeName.TOTAL_TAGS: GaugeDefinition(
        kind=GaugeKind.VOLUME,
        description="Total distinct tag strings (global vocabulary)",
        table="UtubTags",
        distinct_column="tagString",
    ),
    GaugeName.TOTAL_UTUB_URL_ASSOCIATIONS: GaugeDefinition(
        kind=GaugeKind.VOLUME,
        description="Total URL-in-UTub associations",
        table="UtubUrls",
    ),
    # -----------------------------------------------------------------------
    # Distribution — URLs per UTub
    # -----------------------------------------------------------------------
    GaugeName.MAX_URLS_PER_UTUB: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_MAX,
        description="Most URLs in any single UTub",
        table="UtubUrls",
        group_by_column="utubID",
    ),
    GaugeName.AVG_URLS_PER_UTUB: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_AVG,
        description="Average URLs per UTub",
        table="UtubUrls",
        group_by_column="utubID",
    ),
    # -----------------------------------------------------------------------
    # Distribution — tags per URL
    # -----------------------------------------------------------------------
    GaugeName.MAX_TAGS_PER_URL: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_MAX,
        description="Most tags on any single UTub URL",
        table="UtubUrlTags",
        group_by_column="utubUrlID",
    ),
    GaugeName.AVG_TAGS_PER_URL: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_AVG,
        description="Average tags per UTub URL",
        table="UtubUrlTags",
        group_by_column="utubUrlID",
    ),
    # -----------------------------------------------------------------------
    # Distribution — tags per UTub
    # -----------------------------------------------------------------------
    GaugeName.MAX_TAGS_PER_UTUB: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_MAX,
        description="Most tags in any single UTub",
        table="UtubTags",
        group_by_column="utubID",
    ),
    GaugeName.AVG_TAGS_PER_UTUB: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_AVG,
        description="Average tags per UTub",
        table="UtubTags",
        group_by_column="utubID",
    ),
    # -----------------------------------------------------------------------
    # Distribution — membership (UtubMembers has no `id`; count real columns)
    # -----------------------------------------------------------------------
    GaugeName.MAX_UTUBS_PER_USER: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_MAX,
        description="Most UTubs any single user belongs to",
        table="UtubMembers",
        group_by_column="userID",
        count_column="utubID",
    ),
    GaugeName.MAX_MEMBERS_PER_UTUB: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_MAX,
        description="Most members in any single UTub",
        table="UtubMembers",
        group_by_column="utubID",
        count_column="userID",
    ),
    GaugeName.AVG_MEMBERS_PER_UTUB: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_AVG,
        description="Average members per UTub",
        table="UtubMembers",
        group_by_column="utubID",
        count_column="userID",
    ),
    # -----------------------------------------------------------------------
    # Distribution — relational max gauges replacing the deferred event-derived
    # max-access gauges (see master Deferred table).
    # -----------------------------------------------------------------------
    GaugeName.MAX_UTUBS_PER_URL: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_MAX,
        description="Most UTubs containing any single URL (most-shared URL)",
        table="UtubUrls",
        group_by_column="urlID",
    ),
    GaugeName.MAX_URLS_PER_USER: GaugeDefinition(
        kind=GaugeKind.DISTRIBUTION_MAX,
        description="Most URL associations added by any single member",
        table="UtubUrls",
        group_by_column="userID",
    ),
}


def value_column_for(kind: GaugeKind) -> str:
    """Return the AnonymousGauges value column a gauge of `kind` writes/reads.

    AVG gauges produce a fractional value stored in `valueFloat`; every other
    kind (COUNT / MAX) is an integer stored in `valueInt`. Used by both the
    sampler (which column to populate) and the query service (which to read).

    Examples:
        value_column_for(GaugeKind.DISTRIBUTION_AVG) -> "valueFloat"
        value_column_for(GaugeKind.VOLUME)           -> "valueInt"
        value_column_for(GaugeKind.DISTRIBUTION_MAX) -> "valueInt"
    """
    if kind is GaugeKind.DISTRIBUTION_AVG:
        return "valueFloat"
    return "valueInt"


def _inner_count_expr(count_column: str | None) -> str:
    """Build the inner per-group count expression for a distribution gauge.

    Examples:
        _inner_count_expr(None)       -> "COUNT(*)"
        _inner_count_expr("userID")   -> 'COUNT("userID")'
    """
    if count_column is None:
        return "COUNT(*)"
    return f'COUNT("{count_column}")'


def build_gauge_sql(gauge_name: GaugeName) -> str:
    """Generate the single-row-single-value aggregate SQL for one gauge.

    The SQL shape is selected by the registry entry's `kind`. All interpolated
    identifiers (table / column names) come from the closed-set
    `GAUGE_REGISTRY` constants — never from request data — so f-string
    interpolation is safe and no parameter binding is needed.

    Distribution gauges group only the child table, so a parent entity with
    zero children is absent from the grouped population: AVG / MAX are computed
    over the non-empty population only (e.g. `avg_urls_per_utub` is the average
    among UTubs that have at least one URL, not across all UTubs).

    Examples (by kind):
        VOLUME (COUNT *), TOTAL_UTUBS:
            SELECT COUNT(*) FROM "Utubs"
        VOLUME (COUNT DISTINCT), TOTAL_TAGS:
            SELECT COUNT(DISTINCT "tagString") FROM "UtubTags"
        DISTRIBUTION_AVG, AVG_URLS_PER_UTUB:
            SELECT AVG(c) FROM (SELECT COUNT(*) AS c FROM "UtubUrls" GROUP BY "utubID") s
        DISTRIBUTION_MAX, MAX_URLS_PER_UTUB:
            SELECT CASE WHEN (SELECT COUNT(DISTINCT "utubID") FROM "UtubUrls") < 5
            THEN NULL ELSE (SELECT MAX(c) FROM (SELECT COUNT(*) AS c FROM "UtubUrls"
            GROUP BY "utubID") s) END
        EVENT_DERIVED_MAX (reserved — no shipped gauge uses this branch):
            SELECT CASE WHEN (SELECT COUNT(DISTINCT "dimensions"->>'url_id') FROM
            "AnonymousMetrics" WHERE "eventName" = 'url_accessed') < 5 THEN NULL
            ELSE (SELECT MAX(c) FROM (SELECT SUM("count") AS c FROM "AnonymousMetrics"
            WHERE "eventName" = 'url_accessed' GROUP BY "dimensions"->>'url_id') s) END
    """
    definition = GAUGE_REGISTRY[gauge_name]

    if definition.kind is GaugeKind.VOLUME:
        if definition.distinct_column is None:
            count_expr = "COUNT(*)"
        else:
            count_expr = f'COUNT(DISTINCT "{definition.distinct_column}")'
        return f'SELECT {count_expr} FROM "{definition.table}"'

    if definition.kind is GaugeKind.DISTRIBUTION_AVG:
        inner_count = _inner_count_expr(definition.count_column)
        return (
            f"SELECT AVG(c) FROM (SELECT {inner_count} AS c "
            f'FROM "{definition.table}" GROUP BY "{definition.group_by_column}") s'
        )

    if definition.kind is GaugeKind.DISTRIBUTION_MAX:
        inner_count = _inner_count_expr(definition.count_column)
        population = (
            f'SELECT COUNT(DISTINCT "{definition.group_by_column}") '
            f'FROM "{definition.table}"'
        )
        max_value = (
            f"SELECT MAX(c) FROM (SELECT {inner_count} AS c "
            f'FROM "{definition.table}" GROUP BY "{definition.group_by_column}") s'
        )
        return (
            f"SELECT CASE WHEN ({population}) < {MIN_GAUGE_POPULATION} "
            f"THEN NULL ELSE ({max_value}) END"
        )

    # EVENT_DERIVED_MAX: reserved branch — generated but unexercised in this PR
    # (zero registry entries use this kind). Kept so the deferred event-derived
    # gauges re-land without a generator edit once their source events gain a
    # per-entity dimension key.
    dim_expr = f"\"dimensions\"->>'{definition.dimension_key}'"
    event_filter = (
        f'FROM "AnonymousMetrics" WHERE "eventName" = \'{definition.event_name}\''
    )
    population = f"SELECT COUNT(DISTINCT {dim_expr}) {event_filter}"
    max_value = (
        f'SELECT MAX(c) FROM (SELECT SUM("count") AS c '
        f"{event_filter} GROUP BY {dim_expr}) s"
    )
    return (
        f"SELECT CASE WHEN ({population}) < {MIN_GAUGE_POPULATION} "
        f"THEN NULL ELSE ({max_value}) END"
    )


__all__ = [
    "ALL_GAUGE_NAMES",
    "GAUGE_REGISTRY",
    "MIN_GAUGE_POPULATION",
    "GaugeDefinition",
    "GaugeKind",
    "GaugeName",
    "build_gauge_sql",
    "value_column_for",
]
