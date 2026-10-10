from __future__ import annotations

from typing import Generator

import pytest
from flask import Flask
from redis import Redis

from backend import db
from backend import metrics_writer as app_metrics_writer
from backend.models.urls import Urls
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.strings.config_strs import CONFIG_ENVS


@pytest.fixture
def metrics_enabled_app(
    app: Flask, provide_metrics_redis: Redis | None
) -> Generator[Flask, None, None]:
    """Re-init the module-level `metrics_writer` with `METRICS_ENABLED=True`
    so the after_request middleware writes counters into the per-worker
    metrics Redis DB and the ingest route's CSRF + nonce + dispatch path
    actually exercises Redis.

    Mutates the module-level singleton (the same instance the
    `app.extensions["metrics_writer"]` slot points at) rather than swapping
    in a fresh one — keeps the writer that `record_event(...)` resolves
    through `current_app.extensions` and the writer that the route's
    `from backend import metrics_writer` import binds to identical, so
    `mock.patch.object(app_metrics_writer, ...)` in tests is honored by
    both the route code and the proxy.

    Restores the original config flag and writer state on teardown so the
    fixture is safe under parallel xdist workers.
    """
    if provide_metrics_redis is None:
        pytest.skip("metrics Redis is unavailable in this environment")

    original_metrics_enabled = app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    original_redis = app_metrics_writer._redis
    original_enabled = app_metrics_writer._enabled

    app.config[CONFIG_ENVS.METRICS_ENABLED] = True
    app_metrics_writer.init_app(app)

    yield app

    app.config[CONFIG_ENVS.METRICS_ENABLED] = original_metrics_enabled
    app_metrics_writer._redis = original_redis
    app_metrics_writer._enabled = original_enabled


@pytest.fixture
def add_mixed_delete_permission_urls_in_first_utub(
    app: Flask, add_tags_to_utubs, add_one_url_and_all_users_to_each_utub_no_tags
):
    """
    Seed the FIRST UTub (id 1, created by user 1) with a mix of URLs the acting user
    may or may not delete, plus tags arranged to exercise the bulk-delete tag-count
    recompute (shared-tag aggregate + zero-count backfill).

    Lives in the shared integration conftest because both the URL and tag suites use it.

    Starting from every user being a member of every UTub with UTub 1 holding URL 1
    (added by user 1), this fixture adds:

    - URL 2 into UTub 1, added by MEMBER user 2 (user_id=2)
    - URL 3 into UTub 1, added by MEMBER user 3 (user_id=3)

    So UTub 1 holds three URL rows attributed to users 1, 2, and 3 respectively:

    - The literal creator (user 1) may delete ALL three (creator predicate).
    - A plain member (e.g. user 2) may delete only their own URL (URL 2) and is
      FORBIDDEN from the other two.

    Tags in UTub 1 (three ``Utub_Tags`` seeded by ``add_tags_to_utubs``):

    - ``shared`` tag (first UTub-1 tag) applied to URL 1, URL 2, AND URL 3 — deleting
      URL 1 + URL 2 leaves it on URL 3, so its recomputed count is the aggregate 1,
      not a naive per-URL double-decrement.
    - ``solo`` tag (second UTub-1 tag) applied to URL 1 ONLY — deleting URL 1 empties
      it, so the recompute must return count 0 (present in the map, not omitted).

    Args:
        app (Flask): The Flask client providing an app context
        add_tags_to_utubs (pytest fixture): Seeds UTub tags for every UTub
        add_one_url_and_all_users_to_each_utub_no_tags (pytest fixture): Adds all users
            to all UTubs, each UTub containing a single URL added by its creator
    """
    with app.app_context():
        first_utub: Utubs = Utubs.query.get(1)

        added_url_rows: dict[int, Utub_Urls] = {}
        for url_id_and_adder in (2, 3):
            url: Urls = Urls.query.get(url_id_and_adder)
            new_utub_url = Utub_Urls()
            new_utub_url.standalone_url = url
            new_utub_url.url_id = url.id
            new_utub_url.utub_id = first_utub.id
            new_utub_url.user_id = url_id_and_adder
            new_utub_url.url_title = f"This is {url.url_string}"
            db.session.add(new_utub_url)
            added_url_rows[url_id_and_adder] = new_utub_url

        db.session.flush()

        first_url_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == first_utub.id,
            Utub_Urls.url_id == 1,
        ).first()

        first_utub_tags = (
            Utub_Tags.query.filter(Utub_Tags.utub_id == first_utub.id)
            .order_by(Utub_Tags.id)
            .all()
        )
        shared_tag = first_utub_tags[0]
        solo_tag = first_utub_tags[1]

        # Shared tag on URL 1, URL 2, and URL 3.
        for url_row in (first_url_row, added_url_rows[2], added_url_rows[3]):
            db.session.add(
                Utub_Url_Tags(
                    utub_id=first_utub.id,
                    utub_url_id=url_row.id,
                    utub_tag_id=shared_tag.id,
                    user_id=first_utub.utub_creator,
                )
            )

        # Solo tag on URL 1 only.
        db.session.add(
            Utub_Url_Tags(
                utub_id=first_utub.id,
                utub_url_id=first_url_row.id,
                utub_tag_id=solo_tag.id,
                user_id=first_utub.utub_creator,
            )
        )

        db.session.commit()
