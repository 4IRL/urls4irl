import os

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text

from backend import db, migrate
from backend.cli.mock_constants import MOCK_TRACKING_SEED_URL_PAIRS

pytestmark = pytest.mark.cli

_PRE_STRIP_REVISION = "1253bb6a734e"

# The first two seed pairs collapse onto the same stripped URL and are both
# associated to UTub 1 by _add_tracking_seed_urls — exercising the migration's
# within-UTub collision path (merge associations, merge/de-dupe tags, drop the
# duplicate Urls row). The third collapses onto a distinct stripped URL.
_COLLIDING_TRACKING_URLS = (
    MOCK_TRACKING_SEED_URL_PAIRS[0][0],
    MOCK_TRACKING_SEED_URL_PAIRS[1][0],
)
_COLLIDING_STRIPPED_URL = MOCK_TRACKING_SEED_URL_PAIRS[0][1]
_OTHER_TRACKING_URL = MOCK_TRACKING_SEED_URL_PAIRS[2][0]
_OTHER_STRIPPED_URL = MOCK_TRACKING_SEED_URL_PAIRS[2][1]

_ALL_TRACKING_URLS = tuple(
    tracking_url for tracking_url, _stripped in MOCK_TRACKING_SEED_URL_PAIRS
)
_ALL_STRIPPED_URLS = frozenset(
    stripped for _tracking_url, stripped in MOCK_TRACKING_SEED_URL_PAIRS
)


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    alembic_config.attributes["connection"] = db.engine.connect()
    return alembic_config


def _url_id_for_string(connection, url_string: str) -> int | None:
    return connection.execute(
        text('SELECT "id" FROM "Urls" WHERE "urlString" = :url_string'),
        {"url_string": url_string},
    ).scalar_one_or_none()


def _all_url_strings(connection) -> set[str]:
    return set(
        connection.execute(text('SELECT "urlString" FROM "Urls"')).scalars().all()
    )


def _utub_url_count_for_url(connection, url_id: int) -> int:
    return connection.execute(
        text('SELECT COUNT(*) FROM "UtubUrls" WHERE "urlID" = :url_id'),
        {"url_id": url_id},
    ).scalar_one()


def _utub_ids_for_url(connection, url_id: int) -> list[int]:
    return list(
        connection.execute(
            text('SELECT "utubID" FROM "UtubUrls" WHERE "urlID" = :url_id'),
            {"url_id": url_id},
        )
        .scalars()
        .all()
    )


def _tag_ids_on_association(connection, utub_url_id: int) -> list[int]:
    return list(
        connection.execute(
            text(
                'SELECT "utubTagID" FROM "UtubUrlTags" '
                'WHERE "utubUrlID" = :utub_url_id ORDER BY "utubTagID"'
            ),
            {"utub_url_id": utub_url_id},
        )
        .scalars()
        .all()
    )


def _sole_association_id_for_url(connection, url_id: int) -> int:
    return connection.execute(
        text('SELECT "id" FROM "UtubUrls" WHERE "urlID" = :url_id'),
        {"url_id": url_id},
    ).scalar_one()


def test_strip_tracking_params_upgrade_downgrade_idempotent(runner):
    """
    GIVEN a database upgraded to head and seeded with the full mock dataset —
        including the tracking-laden Urls rows inserted raw by ``flask addmock
        all`` (bypassing the create/update validator), two of which collapse
        onto the same stripped URL within UTub 1
    WHEN the database is downgraded to 1253bb6a734e (the strip migration's
        no-op downgrade leaves tracking URLs intact), then upgraded to head
        (681906a2f237 strips them), then the no-op downgrade is run again,
        and the upgrade is re-applied
    THEN every tracking-laden urlString is stripped to its canonical form, the
        within-UTub colliding rows are merged onto a single survivor Urls row
        with their associations repointed/deduped and tags merged, no orphaned
        Urls rows remain, the downgrade does not raise, and the re-applied
        upgrade is idempotent — confirming the data migration behaves correctly
        in both directions against real seeded data (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"  # Silence alembic logging for this test
    app, cli_runner = runner
    migrate.init_app(app)

    # build_app provisions the schema via db.create_all() (no alembic_version row),
    # so drop the schema and rebuild it via migrations — this gives alembic a real
    # version context to upgrade/downgrade against.
    cli_runner.invoke(args=["managedb", "drop", "test"])

    with app.app_context():
        # Seed at head so addmock all runs against a complete schema (isLocked
        # column exists). The strip migration runs on an empty DB here (no-op).
        # The raw tracking-laden Urls inserted by addmock bypass the validator and
        # are not stripped by the already-applied migration, so they survive at head.
        command.upgrade(_build_alembic_config(), "head")

        # Seed the full mock dataset (users, UTubs, members, urls, tags, metrics)
        # including the raw tracking-laden Urls rows that bypass the validator.
        cli_runner.invoke(args=["addmock", "all"])

        # Downgrade to the pre-strip revision. The strip migration's downgrade is
        # a no-op, so the raw tracking URLs are still present. The isLocked
        # downgrade is reversible (column dropped, data preserved).
        command.downgrade(_build_alembic_config(), _PRE_STRIP_REVISION)

        with db.engine.connect() as connection:
            url_strings_before = _all_url_strings(connection)
            assert all(
                tracking_url in url_strings_before
                for tracking_url in _ALL_TRACKING_URLS
            )

            colliding_url_ids_before = [
                _url_id_for_string(connection, tracking_url)
                for tracking_url in _COLLIDING_TRACKING_URLS
            ]
            assert all(url_id is not None for url_id in colliding_url_ids_before)
            assert len(set(colliding_url_ids_before)) == len(colliding_url_ids_before)

            # Both colliding rows live in the same UTub before the merge.
            colliding_utub_ids = [
                _utub_ids_for_url(connection, url_id)
                for url_id in colliding_url_ids_before
            ]
            assert all(len(utub_ids) == 1 for utub_ids in colliding_utub_ids)
            shared_utub_id = colliding_utub_ids[0][0]
            assert all(utub_ids == [shared_utub_id] for utub_ids in colliding_utub_ids)

            other_url_id_before = _url_id_for_string(connection, _OTHER_TRACKING_URL)
            assert other_url_id_before is not None

        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            url_strings_after = _all_url_strings(connection)

            # Tracking-laden strings are gone; their stripped forms are present.
            for tracking_url in _ALL_TRACKING_URLS:
                assert tracking_url not in url_strings_after
            for stripped_url in _ALL_STRIPPED_URLS:
                assert stripped_url in url_strings_after

            # The two colliding rows merged onto a single survivor Urls row.
            survivor_id = _url_id_for_string(connection, _COLLIDING_STRIPPED_URL)
            assert survivor_id is not None
            assert survivor_id in colliding_url_ids_before

            # The dropped duplicate Urls row is fully orphan-free.
            dropped_id = next(
                url_id for url_id in colliding_url_ids_before if url_id != survivor_id
            )
            assert dropped_id not in set(
                connection.execute(text('SELECT "id" FROM "Urls"')).scalars().all()
            )

            # Survivor carries exactly one association within the shared UTub
            # (the within-UTub duplicate association was deleted, not duplicated).
            assert _utub_url_count_for_url(connection, survivor_id) == 1
            assert _utub_ids_for_url(connection, survivor_id) == [shared_utub_id]

            # The dropped association is gone; nothing references the dropped url.
            assert _utub_url_count_for_url(connection, dropped_id) == 0

            # The merged survivor association carries the merged, de-duped tags.
            survivor_assoc_id = _sole_association_id_for_url(connection, survivor_id)
            survivor_tag_ids = _tag_ids_on_association(connection, survivor_assoc_id)
            assert len(survivor_tag_ids) == len(set(survivor_tag_ids))

            # The third (non-colliding) row stripped in place to its own survivor.
            other_survivor_id = _url_id_for_string(connection, _OTHER_STRIPPED_URL)
            assert other_survivor_id is not None
            assert other_survivor_id == other_url_id_before

        # Downgrade is intentionally a no-op; it must run without raising.
        command.downgrade(_build_alembic_config(), _PRE_STRIP_REVISION)

        with db.engine.connect() as connection:
            url_strings_after_downgrade = _all_url_strings(connection)
            for stripped_url in _ALL_STRIPPED_URLS:
                assert stripped_url in url_strings_after_downgrade
            for tracking_url in _ALL_TRACKING_URLS:
                assert tracking_url not in url_strings_after_downgrade

        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            url_strings_after_reapply = _all_url_strings(connection)
            for stripped_url in _ALL_STRIPPED_URLS:
                assert stripped_url in url_strings_after_reapply
            for tracking_url in _ALL_TRACKING_URLS:
                assert tracking_url not in url_strings_after_reapply

            reapply_survivor_id = _url_id_for_string(
                connection, _COLLIDING_STRIPPED_URL
            )
            assert reapply_survivor_id == survivor_id
            assert _utub_url_count_for_url(connection, reapply_survivor_id) == 1

        # Schema is now fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown (clear_database)
        # operates against the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
