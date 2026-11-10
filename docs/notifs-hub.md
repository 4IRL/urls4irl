# Notifs hub: deploy wiring and heartbeats

urls4irl checks in with the 4irl-notifs hub so a backup, metrics or purge job that fails or silently stops raises an alert on the `urls4irl_ops` Discord destination.

## What the workflow does

`.github/workflows/notifs-exchange.yml` ("Notifs Exchange") runs after every successful "Build and Deploy Production Server" run, or by hand (`workflow_dispatch`, from `main` only). One job, `exchange`, with `id-token: write`:

1. Sparse-checks out `scripts/notifs-resolve-release-sha.sh` from `main` HEAD, then runs it to pick the manifest commit: the deploy's head sha (`workflow_run`), the dispatch `sha` input, or (empty input) the commit of the latest published release tag, dereferencing annotated tags. Anything unresolved fails the job; it never falls back to `main`.
2. Checks out the manifest at that commit (`release/.notifs/manifest.json`).
3. Preflights the host key directory (`notifs-key-write.sh --check`), lints the manifest offline with 4irl-notifs checked out at the same SHA as the action pin, then runs the pinned `notifs-app` action (OIDC exchange, lint, apply).
4. Writes the new key and the Access service token on the host (`notifs-key-write.sh --write`, three stdin lines, atomic), then compares the key's sha256 on the host with the hash read inside `u4i-prod-flask` and `u4i-prod-workflow`.
5. If the action failed (apply error, approval pending) the run still fails visibly at the last step, after the key (when one was minted) is installed.

Runs are serialized by the `notifs-exchange-urls4irl` concurrency group on the job (never cancelling). Bump the 4irl-notifs SHA in the lint checkout and the action `uses:` together; a test enforces one SHA.

## Key directory

`/home/u4i/notifs-key/` on the host: owner = deploy user, group gid `1001`, mode `2750`, files `640`: `delivery_key`, `access_client_id`, `access_client_secret` (one line each). Mounted read-only at `/run/notifs` in `web` and `workflow`; env `NOTIFS_BASE_URL` and `NOTIFS_KEY_DIR=/run/notifs`. The production deploy creates or repairs the directory before anything else; on a fresh or rebuilt host without the workflow image run once: `sudo chgrp 1001 /home/u4i/notifs-key` (the deploy fails naming this command).

## First run and approval

The first exchange files an identity request and the action fails ("pending") until the operator approves it in the hub admin UI. Approve, then re-run: `workflow_dispatch` from `main` (leave `sha` empty for the latest release, or pass a commit). Verify the checks appear in the hub and that a ping returns 200.

## Re-running after a failed write

A key stays valid for 24 hours after the next exchange supersedes it. If the write or the post-write hash check failed, re-run within 24 hours with `workflow_dispatch` from `main`; it mints a fresh key and rewrites the directory.

## Adding or removing a check

Edit `.notifs/manifest.json` (names must equal the names pinged by the scripts: `daily_backup`, `metrics_flush`, `gauge_sample`, `purge_audit_log`, `purge_trash`, `purge_short_links`, `purge_invite_links`; `period` and `grace` are at least `60s`). The next release applies it, or dispatch with an explicit `sha`. The action never prunes: delete a removed check in the admin UI, or run `node scripts/onboard.mjs apply --manifest <path> --target app --prune` from the 4irl-notifs repo.

The manifest is checked out at the release tag's commit while the deploy checks out `main`, so they can differ by the commits between the tag and `main` (and the resolve script itself runs from `main` HEAD through the sparse checkout): a manifest can name checks whose pings are not deployed yet, or the reverse.

`metrics_flush` (1m period, 5m grace) may alert once while `workflow` is recreated on a release; grace is raised only if that actually happens.

## Failure meanings

- 401/403 on the exchange: the OIDC identity binding does not match (workflow path, ref, environment) or `id-token: write` is missing.
- 404 on a ping: the manifest was not applied.
- A check "Waiting" forever: wrong period, or the key is not mounted in `workflow` (see the key directory above).
