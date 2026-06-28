"""strip tracking query params from existing urls

One-time backfill that re-strips every "Urls"."urlString", removing the known
marketing/advertising tracking query params (the same set the runtime validator
strips at create/update time). Rows that collapse onto the same stripped string
are merged: their "UtubUrls" associations are repointed onto a single survivor
"Urls" row, and when two associations land in the same UTub the dropped
association's tags are merged onto the survivor before the duplicate association
is deleted.

The strip function and the tracking-param constants are inlined (NOT imported
from backend.extensions...) so this migration stays self-contained at any future
point in code history, even if the validator is renamed, moved, or its blocklist
changes — mirroring 0538b281d033_backfill_device_type.

Revision ID: 681906a2f237
Revises: 1253bb6a734e
Create Date: 2026-06-27 19:02:54.904159

"""

import ada_url
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "681906a2f237"
down_revision = "1253bb6a734e"
branch_labels = None
depends_on = None

# Frozen copies of backend.extensions.url_validation.constants — intentionally
# duplicated (not imported) so this migration reproduces exactly the stripping
# behavior in effect when it was written, regardless of later edits to the live
# blocklist. Lowercase exact-name matches.
_TRACKING_QUERY_PARAMS: frozenset[str] = frozenset(
    {
        "gclid",
        "gclsrc",
        "dclid",
        "gbraid",
        "wbraid",
        "gad_source",
        "gad_campaignid",
        "fbclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "_hsenc",
        "_hsmi",
        "__hssc",
        "__hstc",
        "__hsfp",
        "hsctatracking",
        "igshid",
        "ttclid",
        "twclid",
        "yclid",
        "mkt_tok",
        "s_kwcid",
        "vero_id",
        "oly_anon_id",
        "oly_enc_id",
        "wickedid",
    }
)
_TRACKING_QUERY_PARAM_PREFIXES: tuple[str, ...] = ("utm_",)
_WEB_SCHEMES_FOR_TRACKING_STRIP: frozenset[str] = frozenset({"http", "https"})


def _is_tracking_param(param_name: str) -> bool:
    """Return True if a query-param name is a known tracking param.

    Case-insensitive; matches both the exact-name blocklist and the open-ended
    prefix families (e.g. the utm_* family).

    Examples:
        "utm_source" -> True
        "GCLID"      -> True
        "q"          -> False
    """
    lowered = param_name.lower()
    return lowered in _TRACKING_QUERY_PARAMS or lowered.startswith(
        _TRACKING_QUERY_PARAM_PREFIXES
    )


def _strip_tracking_params(url_string: str) -> str:
    """Strip known tracking query params from a URL string.

    Only http/https URLs are touched (so mailto:/magnet:/etc. are never mangled).
    Non-tracking params and their original order/repeats are preserved. If no
    tracking params are present the original string is returned untouched so the
    original query encoding is not re-serialized. Best-effort: any parse failure
    returns the input unchanged so a single malformed legacy row cannot abort the
    whole migration.

    Examples:
        "https://x.com/p?utm_source=g&q=1&fbclid=z" -> "https://x.com/p?q=1"
        "https://x.com/p?utm_source=g&fbclid=z"     -> "https://x.com/p"
        "mailto:a@b.com?subject=hi"                 -> unchanged
    """
    try:
        parsed = ada_url.URL(url_string)
    except Exception:
        return url_string

    scheme = parsed.protocol.rstrip(":").lower()
    if scheme not in _WEB_SCHEMES_FOR_TRACKING_STRIP:
        return url_string

    search = parsed.search
    if not search:
        return url_string

    params = ada_url.URLSearchParams(search.lstrip("?"))
    tracking_keys = [key for key, _ in params.items() if _is_tracking_param(key)]
    if not tracking_keys:
        return url_string

    for key in tracking_keys:
        params.delete(key)

    new_search = str(params)
    return ada_url.replace_url(url_string, search=new_search)


def upgrade():
    connection = op.get_bind()

    # 1. Load all Urls rows and group them by their stripped canonical form.
    url_rows = connection.execute(
        text('SELECT "id", "urlString" FROM "Urls"')
    ).fetchall()

    groups: dict[str, list[tuple[int, str]]] = {}
    for url_id, url_string in url_rows:
        stripped = _strip_tracking_params(url_string)
        groups.setdefault(stripped, []).append((url_id, url_string))

    for stripped, members in groups.items():
        # 2. Pick the survivor: prefer a row whose current urlString already
        #    equals the stripped form; otherwise the lowest id.
        survivor_id = None
        for url_id, url_string in members:
            if url_string == stripped:
                survivor_id = url_id
                break
        if survivor_id is None:
            survivor_id = min(url_id for url_id, _ in members)

        # 3. Merge every non-survivor row onto the survivor.
        for dup_id, _dup_string in members:
            if dup_id == survivor_id:
                continue

            dup_associations = connection.execute(
                text('SELECT "id", "utubID" FROM "UtubUrls" WHERE "urlID" = :dup_id'),
                {"dup_id": dup_id},
            ).fetchall()

            for utub_url_id, utub_id in dup_associations:
                survivor_assoc_row = connection.execute(
                    text(
                        'SELECT "id" FROM "UtubUrls" '
                        'WHERE "utubID" = :utub_id AND "urlID" = :survivor_id'
                    ),
                    {"utub_id": utub_id, "survivor_id": survivor_id},
                ).first()

                if survivor_assoc_row is None:
                    # Survivor not yet in this UTub: repoint the association.
                    # Safe under unique_url_per_utub since no (utub, survivor) row exists.
                    connection.execute(
                        text(
                            'UPDATE "UtubUrls" SET "urlID" = :survivor_id WHERE "id" = :utub_url_id'
                        ),
                        {"survivor_id": survivor_id, "utub_url_id": utub_url_id},
                    )
                else:
                    # Within-UTub collision: merge tags onto the survivor's
                    # association, then drop the duplicate association.
                    survivor_uu_id = survivor_assoc_row[0]

                    dup_tag_rows = connection.execute(
                        text(
                            'SELECT "id", "utubTagID" FROM "UtubUrlTags" '
                            'WHERE "utubUrlID" = :utub_url_id'
                        ),
                        {"utub_url_id": utub_url_id},
                    ).fetchall()

                    for tagrow_id, utub_tag_id in dup_tag_rows:
                        survivor_has_tag = connection.execute(
                            text(
                                'SELECT "id" FROM "UtubUrlTags" '
                                'WHERE "utubUrlID" = :survivor_uu_id '
                                'AND "utubTagID" = :utub_tag_id'
                            ),
                            {
                                "survivor_uu_id": survivor_uu_id,
                                "utub_tag_id": utub_tag_id,
                            },
                        ).first()

                        if survivor_has_tag is None:
                            # Repoint the tag association onto the survivor.
                            connection.execute(
                                text(
                                    'UPDATE "UtubUrlTags" '
                                    'SET "utubUrlID" = :survivor_uu_id WHERE "id" = :tagrow_id'
                                ),
                                {
                                    "survivor_uu_id": survivor_uu_id,
                                    "tagrow_id": tagrow_id,
                                },
                            )
                        else:
                            # Survivor already carries this tag: de-dupe defensively
                            # (no DB unique constraint on (utubUrlID, utubTagID)).
                            connection.execute(
                                text(
                                    'DELETE FROM "UtubUrlTags" WHERE "id" = :tagrow_id'
                                ),
                                {"tagrow_id": tagrow_id},
                            )

                    connection.execute(
                        text('DELETE FROM "UtubUrls" WHERE "id" = :utub_url_id'),
                        {"utub_url_id": utub_url_id},
                    )

            # Delete the now-orphaned duplicate Urls row.
            connection.execute(
                text('DELETE FROM "Urls" WHERE "id" = :dup_id'),
                {"dup_id": dup_id},
            )

        # 4. Rewrite the survivor's urlString to the stripped form if it differs.
        #    Safe: no exact-match row existed (else it would have been the survivor).
        #    Idempotent: when already stripped this UPDATE affects 0 changed rows.
        survivor_current = next(
            url_string for url_id, url_string in members if url_id == survivor_id
        )
        if survivor_current != stripped:
            connection.execute(
                text(
                    'UPDATE "Urls" SET "urlString" = :stripped WHERE "id" = :survivor_id'
                ),
                {"stripped": stripped, "survivor_id": survivor_id},
            )
        # createdBy / createdAt are never touched — only urlString changes.


def downgrade():
    # Irreversible by design. Stripping is lossy (the removed tracking params are
    # gone) and the row/tag merges cannot be un-merged — a merged survivor cannot
    # be split back into the distinct pre-strip rows. Leaving as a no-op is the
    # only safe choice; mirrors 0538b281d033_backfill_device_type.
    pass
