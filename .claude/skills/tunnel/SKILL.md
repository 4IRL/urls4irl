---
name: tunnel
description: Start or stop the on-demand public Cloudflare tunnel that exposes the local app for remote testing (e.g. checking the mobile layout from a phone). Use whenever the user asks to start/open/bring up the tunnel, expose the app publicly, get a shareable/remote URL, or test the app remotely/on their phone — AND whenever they ask to stop/kill/shut down/close the tunnel or take the URL down. Handles both directions; infer start vs stop from the user's words.
---

# Tunnel skill

Wraps the `make tunnel` / `make tunnel-stop` targets (defined in the project `Makefile`; backed by the profiled `cloudflared` service in `docker/compose.local.yaml`). Cloudflare quick tunnels are token-free and ephemeral; `make tunnel` forces the **built** stack up first so the served page works on a remote device (no `localhost:5173` dependency).

## Step 0 — Determine intent

From the user's message, decide **start** or **stop**:
- **Start** — "start/open/bring up the tunnel", "expose the app", "remote/public URL", "test on my phone", "let me see it remotely", etc.
- **Stop** — "stop/kill/shut down/close the tunnel", "take the URL down", "done testing", etc.

If genuinely ambiguous, ask via `AskUserQuestion` (start vs stop). Otherwise proceed.

## Start

**MANDATORY — never send a tunnel URL without the credentials block in the same message.** This holds even if `make tunnel` was run directly via Bash instead of through this skill (e.g. mid-conversation, outside a dedicated skill invocation) — the URL and the login block are not separable outputs.

1. Run the start target (synchronous `Bash`, `dangerouslyDisableSandbox: true` — it's a `make`/`docker` command). It rebuilds into built mode (~1–2 min on first run), starts the tunnel, and prints a `TUNNEL URL: https://<random>.trycloudflare.com` line:
   ```
   make tunnel
   ```
2. Read the `TUNNEL URL:` value from stdout. If the loop times out without printing a URL, run `docker compose --project-directory . -f docker/compose.local.yaml -f docker/compose.built.yaml logs cloudflared` (DDS) and report what you find instead of guessing.
3. Print the URL plus the first two seeded test logins in this copy-paste-friendly block (login is by **username**; the seeded mock password equals the user's email):

   ```
   🌐 Tunnel URL: <the URL>

   Test login 1
   username: u4i_test1
   password: u4i_test1@urls4irl.app

   Test login 2
   username: u4i_test2
   password: u4i_test2@urls4irl.app
   ```
4. Remind the user the machine must stay awake while away, and that they can say "stop the tunnel" to take it down.

## Stop

Run the stop target (synchronous `Bash`, `dangerouslyDisableSandbox: true`), then confirm the URL is now dead and the rest of the stack is untouched:
```
make tunnel-stop
```

## Maintenance note

The test credentials above are derived from `flask addmock all` seeding — `USERNAME_BASE` + `EMAIL_SUFFIX` in `backend/cli/mock_constants.py` and `generate_mock_users()` (`plaintext_password=email`) in `backend/cli/mock_data/users.py`. If those constants change, update this skill's printed credentials to match.
