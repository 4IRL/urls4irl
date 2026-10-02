# p (profile), c (restart), e (endpoint-info), run (test-artifacts), base and AFFECTED_INT / AFFECTED_UI (affected-markers / test-affected /
# test-agent), U4I_WEB_PORT / U4I_VITE_PORT (spliced into the _ports-resolve recipe) and U4I_TOKEN_DIR / U4I_MEMORY_WAIT /
# U4I_SETTLE_SECONDS (spliced into every budgeted test line) are rejected when they contain a `$`, checked unexpanded via
# $(value …):
# expanding one would run any embedded make function (e.g. $(shell …)). These must stay the first lines: make 4.4+
# exports command-line variables into every $(shell …) environment, so the first $(shell …) below would already
# expand them.
$(if $(findstring $$,$(value p)),$(error p must not contain '$$'))
$(if $(findstring $$,$(value c)),$(error c must not contain '$$'))
$(if $(findstring $$,$(value e)),$(error e must not contain '$$'))
$(if $(findstring $$,$(value run)),$(error run must not contain '$$'))
$(if $(findstring $$,$(value base)),$(error base must not contain '$$'))
# base is also spliced into a single-quoted shell word (--base '$(base)'), so a ' in it is refused as well.
$(if $(findstring ',$(value base)),$(error base must not contain a single quote (it is passed as one single-quoted shell word)))
# A command-line AFFECTED_INT= / AFFECTED_UI= override skips the selector and is spliced into -m '$(AFFECTED_…)'
# on the budgeted pytest lines, so it gets the same $ and ' guards as base. That single-quoted word also sits inside
# the double-quoted $(EXEC_WEB) "…" string, which the host shell parses first, so ", ` and \ are refused as well.
$(if $(findstring $$,$(value AFFECTED_INT)),$(error AFFECTED_INT must not contain '$$'))
$(if $(findstring ',$(value AFFECTED_INT)),$(error AFFECTED_INT must not contain a single quote (it is passed as one single-quoted shell word)))
$(if $(or $(findstring ",$(value AFFECTED_INT)),$(findstring `,$(value AFFECTED_INT)),$(findstring \,$(value AFFECTED_INT))),$(error AFFECTED_INT must not contain a double quote, backtick or backslash (it is spliced into a double-quoted shell string)))
$(if $(findstring $$,$(value AFFECTED_UI)),$(error AFFECTED_UI must not contain '$$'))
$(if $(findstring ',$(value AFFECTED_UI)),$(error AFFECTED_UI must not contain a single quote (it is passed as one single-quoted shell word)))
$(if $(or $(findstring ",$(value AFFECTED_UI)),$(findstring `,$(value AFFECTED_UI)),$(findstring \,$(value AFFECTED_UI))),$(error AFFECTED_UI must not contain a double quote, backtick or backslash (it is spliced into a double-quoted shell string)))
$(if $(findstring $$,$(value U4I_WEB_PORT)),$(error U4I_WEB_PORT must not contain '$$'))
$(if $(findstring $$,$(value U4I_VITE_PORT)),$(error U4I_VITE_PORT must not contain '$$'))
$(if $(findstring $$,$(value U4I_TOKEN_DIR)),$(error U4I_TOKEN_DIR must not contain '$$'))
$(if $(findstring $$,$(value U4I_MEMORY_WAIT)),$(error U4I_MEMORY_WAIT must not contain '$$'))
$(if $(findstring $$,$(value U4I_SETTLE_SECONDS)),$(error U4I_SETTLE_SECONDS must not contain '$$'))

# Host capacity (scripts/capacity.py, `make capacity`): derived worker counts + interlocks + host UID/GID.
CAPACITY_ENV = docker/.capacity.generated.env
CAPACITY = mise exec python -- python scripts/capacity.py
# Host-wide test token budget (scripts/token_budget.py): a counting semaphore of U4I_N_MAX tokens, per user.
TOKEN_BUDGET = mise exec python -- python scripts/token_budget.py
# Spoke host ports (scripts/spoke_ports.py, run by _ports-resolve): U4I_WEB_PORT / U4I_VITE_PORT, cached per checkout.
PORTS_ENV = docker/.ports.generated.env
SPOKE_PORTS = mise exec python -- python scripts/spoke_ports.py
# Endpoint lookup (scripts/endpoint_info.py, make endpoint-info): stdlib only, reads the committed docs/endpoints/endpoint-registry.json.
ENDPOINT_INFO = mise exec python -- python scripts/endpoint_info.py
# UI failure-artifact reader (scripts/failure_artifacts_report.py, make test-artifacts): stdlib only, reads tmp/test-artifacts/.
FAILURE_ARTIFACTS_REPORT = mise exec python -- python scripts/failure_artifacts_report.py
# Diff-scoped test selection (scripts/affected_markers.py, make affected-markers / test-affected / test-agent): stdlib only,
# maps the branch diff against the merge-base with $(base) to pytest markers.
AFFECTED_MARKERS = mise exec python -- python scripts/affected_markers.py
base ?= origin/main
# Recursive `=` so each `wildcard` is evaluated at recipe time, after _capacity-fresh / _ports-resolve have (re)generated
# their file on a first run. `.env` goes first: passing any --env-file disables compose's implicit .env discovery, and a
# missing .env now errors loudly.
COMPOSE_ENV_FILES = --env-file .env $(if $(wildcard $(CAPACITY_ENV)),--env-file $(CAPACITY_ENV)) $(if $(wildcard $(PORTS_ENV)),--env-file $(PORTS_ENV))
COMPOSE = docker compose --project-directory . -p $(U4I_PROJECT) $(COMPOSE_ENV_FILES) -f docker/compose.local.yaml
COMPOSE_BUILT = docker compose --project-directory . -p $(U4I_PROJECT) $(COMPOSE_ENV_FILES) -f docker/compose.local.yaml -f docker/compose.built.yaml
# Recipe-time shell read of one KEY from the capacity file. The keys are never exported into make, so a
# value read back here is never mistaken for a command-line override.
capacity_val = $$(sed -n 's/^$(1)=//p' $(CAPACITY_ENV))
# Tier 3 worktree identity: computed from the checkout dir name, never stored. It names the per-worktree dev DB
# (Phase 5) and, since Phase 7, the spoke compose project and its hub-reachable aliases (web-<slug>, vite-<slug>).
# Host ports are resolved at recipe time (they need Docker); every parse-time $(shell …) here uses only
# git/printf/tr/sed/cut/id, never docker, so the CI dry runs stay Docker-free. One bounded exception: for the
# test-affected / test-agent goals only, the parse-time $(shell …) also runs the host stdlib scripts/affected_markers.py
# via mise exec python (still Docker-free).
U4I_SLUG ?= $(notdir $(CURDIR))
export U4I_SLUG
# Per-worktree dev DB: u4i_dev_<sanitized slug>. Must agree with scripts/testrun_resources.dev_db_name.
$(if $(strip $(U4I_SLUG)),,$(error U4I_SLUG must be non-empty))
# The slug with each ' escaped as '\'' so it can sit inside a single-quoted shell word.
U4I_SLUG_SHELL := $(subst ','\'',$(U4I_SLUG))
U4I_DEV_DB := u4i_dev_$(shell printf '%s' '$(U4I_SLUG_SHELL)' | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_' '_' | cut -c1-55)
export U4I_DEV_DB
# The primary clone is the git common dir's parent (same resolution as `hooks`); every linked worktree shares it.
# The patsubst assumes the common dir is <primary>/.git: a `--separate-git-dir` clone is not detected as primary,
# so run it with U4I_PRIMARY=1. Empty outside a git checkout (worktree-init refuses to run then).
PRIMARY_ROOT := $(patsubst %/.git,%,$(shell git rev-parse --path-format=absolute --git-common-dir 2>/dev/null))
U4I_PRIMARY ?= $(if $(filter $(PRIMARY_ROOT),$(CURDIR)),1)
# DNS-label-safe slug for compose project/alias names: lowercase [a-z0-9-], no leading/trailing dash, at most 40 chars.
U4I_HOST_SLUG := $(shell printf '%s' '$(U4I_SLUG_SHELL)' | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed 's/^-*//' | cut -c1-40 | sed 's/-*$$//')
$(if $(strip $(U4I_HOST_SLUG)),,$(error U4I_SLUG '$(U4I_SLUG)' sanitizes to an empty compose project name))
# Spoke names derive from the checkout's basename only, so two checkouts with the same directory name on one Docker
# host share a compose project and dev DB: keep worktree directory names unique.
U4I_PROJECT := u4i-$(U4I_HOST_SLUG)
# A spoke project inside the hub's u4i-hub-* namespace would own (and `make down` would remove) the hub's containers.
$(if $(filter u4i-hub-%,$(U4I_PROJECT)),$(error U4I_SLUG '$(U4I_SLUG)' gives spoke project $(U4I_PROJECT) inside the per-user hub's u4i-hub-* namespace; rename the checkout or set another U4I_SLUG))
U4I_WEB_HOST := web-$(U4I_HOST_SLUG)
U4I_VITE_HOST := vite-$(U4I_HOST_SLUG)
# Per-user hub (shared Postgres + Playwright) and its external network: per-user so two users' hubs never share DNS names.
U4I_UID := $(shell id -u)
U4I_HUB_PROJECT := u4i-hub-$(U4I_UID)
U4I_SHARED_NET := u4i-shared-$(U4I_UID)
# The token budget's lock dir: per user like the hub, so it is shared by every checkout of that user (created 0700).
U4I_TOKEN_DIR := /tmp/u4i-test-tokens-$(U4I_UID)
# Seconds a run waits for memory while no other run of ours holds tokens (outside pressure) before it exits 1.
U4I_MEMORY_WAIT ?= 600
# Seconds a started wide run keeps the turnstile, so the next starter's live reading includes its ramp-up allocation.
U4I_SETTLE_SECONDS ?= 20
# Both are spliced bare into every budgeted line, so each must be one word of digits and dots (the runner validates the
# number itself): this refuses shell metacharacters and an empty override at parse time, before any recipe runs.
# $(call remove_chars,<chars>,<text>) folds over the word list <chars>, deleting each one from <text> in turn
# (plain $(foreach) cannot chain subst results). Recursive $(call) works on GNU make 3.81 (macOS).
remove_chars = $(if $(1),$(call remove_chars,$(wordlist 2,$(words $(1)),$(1)),$(subst $(firstword $(1)),,$(2))),$(2))
non_numeric_rest = $(call remove_chars,0 1 2 3 4 5 6 7 8 9 .,$(1))
$(foreach seconds_var,U4I_MEMORY_WAIT U4I_SETTLE_SECONDS,$(if $(or $(filter-out 1,$(words $($(seconds_var)))),$(call non_numeric_rest,$($(seconds_var)))),$(error $(seconds_var) must be a non-negative number of seconds (got '$($(seconds_var))'))))
export PRIMARY_ROOT U4I_PRIMARY U4I_HOST_SLUG U4I_PROJECT U4I_WEB_HOST U4I_VITE_HOST U4I_UID U4I_HUB_PROJECT U4I_SHARED_NET
# The per-user hub (docker/compose.hub.yaml: db, cluster-init, playwright) is always defined by the PRIMARY clone's
# files (compose file, .env, capacity file), so spokes on different branches can never recreate it with diverging
# config. Recursive `=` so the capacity-file `wildcard` is evaluated when hub-up's recipe is expanded, i.e. after its
# prerequisites ran (_hub-capacity ensures the file; make expands a whole recipe before running its first line).
PRIMARY_CAPACITY_ENV = $(PRIMARY_ROOT)/$(CAPACITY_ENV)
HUB_COMPOSE = docker compose --project-directory $(PRIMARY_ROOT) --env-file $(PRIMARY_ROOT)/.env $(if $(wildcard $(PRIMARY_CAPACITY_ENV)),--env-file $(PRIMARY_CAPACITY_ENV)) -p $(U4I_HUB_PROJECT) -f $(PRIMARY_ROOT)/docker/compose.hub.yaml
HUB_SERVICES := db playwright
# --no-recreate starts an idle-reaped (exited 0) hub playwright in place: same container, no registry fetch. It never
# picks up an image/config change (that is playwright-rebuild). --wait blocks until its node TCP healthcheck passes.
PLAYWRIGHT_UP = $(HUB_COMPOSE) up -d --wait --no-recreate playwright
# The hub playwright container, running or stopped, selected by compose labels (stack-info, playwright-rebuild).
HUB_PLAYWRIGHT_PS = docker ps -a --filter label=com.docker.compose.project=$(U4I_HUB_PROJECT) --filter label=com.docker.compose.service=playwright
# Non-hub containers attached to the shared network, running or stopped (an exited db-init still pins the network),
# one name per line; none when the network is absent. The hub is excluded by its compose project label, not a name
# prefix a spoke slug could mimic; an unlabelled stray prints as " <name>", so the name is always the last field.
# Used by hub-down (refuses while any remain) and stack-info.
ATTACHED_SPOKES = docker ps -a --filter network=$(U4I_SHARED_NET) --format '{{.Label "com.docker.compose.project"}} {{.Names}}' 2>/dev/null | awk -v hub='$(U4I_HUB_PROJECT)' 'NF && $$1 != hub {print $$NF}'
EXEC_WEB = $(COMPOSE) exec web bash -c
EXEC_WEB_BUILT = $(COMPOSE_BUILT) exec web bash -c
# Budgeted exec: `$(call BUDGETED,<tokens>,$@,<min tokens>) $(EXEC_WEB) "…"` queues until live memory and the token
# budget allow at least <min tokens> (at most <tokens>), then runs the rest of the line holding the granted count,
# which replaces @TOKENS@ in it. It wraps only that one line, never a prerequisite (start-built's rebuild holds no
# tokens). The budget is the PRIMARY clone's U4I_N_MAX, the same authority as the hub. EXEC_WEB itself stays
# unbudgeted: audit/addmock/clear-db and the reset-test-dbs recovery tool share it and must never queue. New flags go
# before `--tokens <N> --label <target> --` (the dry-run tests pin that adjacency).
BUDGETED = $(TOKEN_BUDGET) run --capacity-file $(PRIMARY_CAPACITY_ENV) --lock-dir '$(subst ','\'',$(U4I_TOKEN_DIR))' --hub-project $(U4I_HUB_PROJECT) --memory-wait $(U4I_MEMORY_WAIT) --settle-seconds $(U4I_SETTLE_SECONDS) --min-tokens $(3) --tokens $(1) --label $(2) --
# Worker ceilings for the -parallel targets (--tokens); pytest's -n is @TOKENS@, the count the runner granted, so a
# run holds exactly one token per worker.
N_INT = $(or $(n),$(call capacity_val,U4I_N_INT))
N_UI = $(or $(n),$(call capacity_val,U4I_N_UI))
# Without n= a parallel run is elastic (shrinks to fit live memory, down to 1 worker); an explicit n= is exact and
# waits for memory instead.
MIN_TOKENS = $(if $(n),$(n),1)
# For steps that write into bind-mounted host files (frontend/types): run as the host user so the
# files keep host ownership, with LOG_DIR moved to /tmp since the image's log dir is only writable by the web user.
EXEC_WEB_AS_HOST = $(COMPOSE) exec --user $(shell id -u):$(shell id -g) -e LOG_DIR=/tmp/u4i-cli-logs web bash -c
# Compose profiles (docker/compose.local.yaml): p= picks the optional services layered on web + datastores.
#   (unset) web, db-init, redis, redis-metrics   ·   ui: + vite (hub playwright started too)   ·   full: + workflow
PROFILES := ui full
# The profiled services `up` stops when p narrows (cloudflared is left to tunnel/tunnel-stop). Hub playwright is
# never stopped by a spoke: other spokes may be using it.
OPTIONAL_SERVICES := vite workflow
# p is spliced into command lines, so it is validated at parse time: an invalid p fails every target before any command runs.
$(if $(word 2,$(p)),$(error p takes one profile: one of $(PROFILES)))
$(if $(filter-out $(PROFILES),$(p)),$(error p must be one of: $(PROFILES) (got '$(p)')))
PROFILE_FLAGS = $(if $(p),--profile $(p))
# Lifecycle ops that must reach every service however it was started.
ALL_PROFILES = --profile '*'
# The profile _profile-narrow treats as "currently intended". Set per lifecycle target via a target-specific
# variable below (never read raw $(p) directly), so up-built's own default (ui) and the narrowing check always agree.
NARROW_PROFILE =
# One-off vite container (no long-lived dev server needed): vite is profile-gated, so `exec vite` fails on a default stack.
RUN_VITE = $(COMPOSE) run --rm --no-deps vite
PYTEST = source /code/venv/bin/activate && python -m pytest
FLASK = source /code/venv/bin/activate && flask
MISE = mise exec --
FRONTEND_BIN = frontend/node_modules/.bin
# Recursive `=` so git only runs for the shell targets; `wildcard` drops tracked-but-deleted paths. Paths must not contain spaces.
SHELL_FILES = $(wildcard $(shell git ls-files '*.sh' ':!:.claude/hooks/*' ':!:.claude/worktrees/*' 2>/dev/null))
PYTHON_FILES = $(wildcard $(shell git ls-files '*.py' ':!:migrations/*' ':!:.claude/hooks/*' ':!:.claude/worktrees/*' 2>/dev/null))
NOTIFY_TEST_DEFAULT_MSG = **Daily Backup — SUCCESS**\n✅ 💾 Database\n✅ 📄 Logs\n✅ ☁️ R2 daily\n💤 ☁️ R2 monthly\n✅ ☁️ R2 logs\n\n**Metrics — HEALTHY**\n🟢 📊 Minute Flush · 38s ago\n🟢 📊 Hourly Snapshot · 12m ago

.PHONY: hooks hooks-check setup stack-info worktree-init hub-up hub-down hub-restart playwright-up playwright-rebuild _hub-network _hub-capacity _admit-spoke _require-hub-files logs tools mise-config-check lockfile-check _require-tools _require-mise _require-shell-files _capacity-fresh _logs-owner-fix _test-artifacts-dir _ports-resolve _require-n-fits _profile-narrow _ui-up _require-workflow capacity test-last-failed up down build restart test-integration test-integration-parallel test-functional test-ui-parallel test-js test-js-built test-backup-pipeline test-db-provision test-playwright-lifecycle test-host-static _host-static-run affected-markers test-affected test-agent test-marker test-file test-file-parallel test-file-parallel-built vite-build vite-build-built typecheck lint lint-python lint-frontend lint-shell lint-actions format format-check format-check-python format-check-frontend format-check-shell prune help up-built start-built test-functional-built test-ui-parallel-built test-marker-built test-marker-parallel test-marker-parallel-built generate-types generate-endpoints audit-endpoints endpoint-info test-artifacts clear-db reset-db metrics-watch metrics-snapshot metrics-flush-now metrics-rows metrics-smoke-test metrics-clear-counters metrics-clear-rows metrics-clear-all gauge-sample-now gauge-rows gauge-clear-rows notify-test addmock audit plan-list playwright-unlock tunnel tunnel-stop reset-test-dbs audit-pins

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Stops + removes every OPTIONAL_SERVICES member NARROW_PROFILE does not enable. `--remove-orphans` never touches a
# profile-disabled service (it isn't an orphan), so without this a narrower `up` would leave them running. The enabled
# set comes from compose itself; $(COMPOSE) is correct for up-built too, since compose.built.yaml declares no profiles.
_profile-narrow:
	@enabled="$$($(COMPOSE) $(if $(NARROW_PROFILE),--profile $(NARROW_PROFILE)) config --services)" || exit 1; \
	stale=""; for service in $(OPTIONAL_SERVICES); do printf '%s\n' "$$enabled" | grep -qx "$$service" || stale="$$stale $$service"; done; \
	if [ -n "$$stale" ]; then $(COMPOSE) $(ALL_PROFILES) rm -sfv $$stale; fi

# -V (--renew-anon-volumes): recreate anonymous volumes (vite's /app/node_modules masks, present only when the ui
# profile is active) on every up, so a stale pre-bump node_modules never shadows the freshly built image's pnpm install.
# Named volumes are unaffected.
up: NARROW_PROFILE = $(p)
up: worktree-init _capacity-fresh _logs-owner-fix _test-artifacts-dir _ports-resolve _admit-spoke hub-up $(if $(p),playwright-up) _profile-narrow ## Start the hub, then build and start this spoke's web + datastores; p=ui adds vite (+ hub playwright), p=full also adds workflow (pass d=1 for detached mode)
	$(COMPOSE) $(PROFILE_FLAGS) up --build --remove-orphans -V $(if $(d),-d,)

# A built stack always needs the vite one-shot build (else pages render with no assets), so p defaults to ui here.
# With d=1 it then waits like start-built/tunnel (VITE_BUILD_BARRIER, then a healthy web). Attached mode has no such
# point: its `up` streams logs until Ctrl-C (which stops the stack), and the vite build output is visible in the stream.
up-built: NARROW_PROFILE = $(or $(p),ui)
# Hub playwright: with d=1 it starts last, after a healthy web, for the same idle-clock reason as start-built. Attached
# mode never reaches a trailing line (Ctrl-C stops the stack), so there it stays an early prerequisite.
up-built: worktree-init _capacity-fresh _logs-owner-fix _test-artifacts-dir _ports-resolve _admit-spoke hub-up $(if $(d),,playwright-up) _profile-narrow ## Start the hub + its playwright, then build and start with pre-built Vite assets: web + datastores + vite build; p=full also adds workflow (pass d=1 for detached mode, which waits for the vite build + a healthy web, then starts playwright)
	$(COMPOSE_BUILT) --profile $(NARROW_PROFILE) up --build --remove-orphans -V $(if $(d),-d,)
	$(if $(d),@$(VITE_BUILD_BARRIER))
	$(if $(d),$(COMPOSE_BUILT) --profile $(NARROW_PROFILE) up --wait web)
	$(if $(d),$(PLAYWRIGHT_UP))

# Completion barrier for the built stack's one-shot vite (`vite build`). Nothing depends on it (hub playwright used to,
# and web must not depend on the profiled vite), so `up --wait` cannot include it: once vite exits, even with 0, a
# waiting `up` fails the whole command. `docker compose wait` cannot serve either: once the container has exited it
# fails with "no containers". So targets start the stack detached, block here, then `up --wait web`. `docker wait`
# returns an exited container's code too, but prints it and itself exits 0, so the printed code is compared to 0.
VITE_BUILD_BARRIER = vite_id="$$($(COMPOSE_BUILT) --profile ui ps -a -q vite)"; \
	if [ -z "$$vite_id" ]; then echo "$@: no vite build container found" >&2; exit 1; fi; \
	vite_exit="$$(docker wait $$vite_id)" || exit 1; \
	if [ "$$vite_exit" != 0 ]; then echo "$@: the vite asset build exited $$vite_exit (see: make logs c=vite)" >&2; exit 1; fi

# Hub playwright starts last: its idle clock starts at container start, so a long rebuild + vite build must not eat
# the window before pytest connects. hub-up stays a prerequisite (the spoke needs the hub db).
start-built: worktree-init _capacity-fresh _logs-owner-fix _test-artifacts-dir _ports-resolve _admit-spoke hub-up prune ## Tear down this spoke, rebuild with pre-built assets (ui profile, no workflow), wait for the vite build + a healthy web, then start hub playwright (used by built test targets)
	$(COMPOSE) $(ALL_PROFILES) down
	$(COMPOSE_BUILT) --profile ui up --build --remove-orphans -d
	@$(VITE_BUILD_BARRIER)
	$(COMPOSE_BUILT) --profile ui up --wait web
	$(PLAYWRIGHT_UP)

down: ## Stop this spoke (every profile); the hub keeps running (make hub-down)
	$(COMPOSE) $(ALL_PROFILES) down

build: _capacity-fresh ## Rebuild images without starting (every profile)
	$(COMPOSE) $(ALL_PROFILES) build

restart: ## Restart a spoke service: make restart c=<service> (hub services: make hub-restart)
	$(if $(c),,$(error c=<service> is required, e.g. make restart c=vite))
	$(if $(filter $(HUB_SERVICES),$(c)),$(error $(c) is a hub service — use make hub-restart c=$(c)))
	$(COMPOSE) $(ALL_PROFILES) restart $(c)

# COMPOSE_BUILT (not COMPOSE) so it also reaches the built-mode stack the tunnel target runs.
logs: ## Tail a spoke service's logs: make logs c=<service>
	$(if $(c),,$(error c=<service> is required, e.g. make logs c=cloudflared))
	$(if $(filter $(HUB_SERVICES),$(c)),$(error $(c) is a hub service — its logs are in the hub project: docker compose -p $(U4I_HUB_PROJECT) logs $(c)))
	$(COMPOSE_BUILT) $(ALL_PROFILES) logs $(c)

# Starts the dev UI-test dependencies: hub playwright, then this spoke's web + vite (datastores via depends_on); idempotent
# when already up. web is named because nothing in the spoke depends on it any more (playwright did, before the hub).
# Assumes a dev stack: on an up-built stack use the `-built` test targets instead, else this recreates vite as the dev server.
_ui-up: _capacity-fresh _logs-owner-fix _test-artifacts-dir _ports-resolve _admit-spoke playwright-up
	$(COMPOSE) --profile ui up -d --wait web vite

# The shared per-user network the hub and every spoke join. Idempotent, and race-tolerant when two spokes create it at
# once: a failed create is fine as long as the network then exists.
_hub-network:
	@docker network inspect $(U4I_SHARED_NET) >/dev/null 2>&1 || docker network create $(U4I_SHARED_NET) >/dev/null 2>&1 || docker network inspect $(U4I_SHARED_NET) >/dev/null

# --no-recreate: a spoke never restarts the shared cluster under another spoke, so a change to db's own config (its
# command: args U4I_PG_MAX_CONN / U4I_PG_SHARED_BUFFERS_MB) applies only through hub-down + hub-up. cluster-init is a
# fresh `run --rm` every time, so a changed U4I_PG_TEST_CONN_LIMIT is re-applied by the next `make up` with no teardown.
# cluster-init runs with --no-deps: `run` would otherwise recreate a db whose config diverged, defeating
# `--no-recreate db`. db is already up and healthy by then, and db-provision.sh has its own readiness wait.
# Concurrent hub-ups from two spokes are safe once the hub exists: cluster-init's cluster steps are serialized by a
# Postgres advisory lock in db-provision.sh (the second waits, then re-applies idempotently) and _hub-network is
# race-tolerant. Known residual race, deliberately not engineered around (same stance as _ports-resolve): two spokes'
# simultaneous FIRST-EVER `up -d --no-recreate db` (or playwright) can both try to create the container, and the loser
# fails with a container name conflict. Rerunning `make up` fixes it, since the container then exists.
hub-up: _hub-capacity _hub-network ## Start the per-user hub (Postgres cluster), provisioning cluster-wide roles; idempotent
	$(HUB_COMPOSE) up -d --wait --no-recreate db
	$(HUB_COMPOSE) run --rm --no-deps cluster-init

# Idempotent: restarts an idle-reaped container in place and waits for it to be healthy (see PLAYWRIGHT_UP).
playwright-up: hub-up ## Start the hub's shared Playwright browser server and wait until healthy (restarts an idle-reaped one in place; idempotent)
	$(PLAYWRIGHT_UP)

# Picks up a changed Dockerfile.Playwright / compose playwright config (playwright-up never recreates). Refuses while
# any client is connected, since recreating drops every spoke's in-flight UI workers. Fails closed: only an absent or
# stopped (created/exited/dead) container skips the count. Any other state must give readable connection tables
# (tcp6 is optional: IPv6 may be disabled) and a numeric count, else it refuses. The tables are captured before
# counting because sh has no pipefail: a failed `exec` piped straight into the counter would read as 0 clients.
# Known residual race (not engineered around): another spoke's playwright-up can start and connect between the guard
# and --force-recreate.
playwright-rebuild: _require-hub-files hub-up ## Rebuild the hub Playwright image and recreate it (refuses while any UI run is connected)
	@state="$$($(HUB_PLAYWRIGHT_PS) --format '{{.State}}')" || \
		{ echo "playwright-rebuild: could not query the hub playwright container state — refusing to recreate it" >&2; exit 1; }; \
	case "$$state" in ''|created|exited|dead) exit 0;; esac; \
	tables="$$($(HUB_COMPOSE) exec -T playwright sh -c 'cat /proc/net/tcp && { cat /proc/net/tcp6 2>/dev/null || true; }')" && [ -n "$$tables" ] || \
		{ echo "playwright-rebuild: hub playwright is $$(echo $$state) but its connection tables could not be read — refusing to recreate it" >&2; exit 1; }; \
	active="$$(printf '%s\n' "$$tables" | $(PRIMARY_ROOT)/docker/playwright-entrypoint.sh --count -)"; \
	case "$$active" in ''|*[!0-9]*) echo "playwright-rebuild: could not count UI clients (got '$$active') — refusing to recreate it" >&2; exit 1;; esac; \
	if [ "$$active" -gt 0 ]; then echo "playwright-rebuild: $$active UI client(s) connected — wait for the run(s) to finish" >&2; exit 1; fi
	$(HUB_COMPOSE) build playwright
	$(HUB_COMPOSE) up -d --wait --force-recreate playwright

hub-down: _require-hub-files ## Stop the hub; refuses while any spoke is attached to the shared network
	@attached="$$($(ATTACHED_SPOKES))"; if [ -n "$$attached" ]; then echo "hub-down: spokes still attached: $$(echo $$attached) — run 'make down' in each first" >&2; exit 1; fi
	$(HUB_COMPOSE) $(ALL_PROFILES) down
	@if docker network inspect $(U4I_SHARED_NET) >/dev/null 2>&1; then docker network rm $(U4I_SHARED_NET) >/dev/null; fi

hub-restart: _require-hub-files ## Restart a hub service: make hub-restart c=db|playwright (no health wait; image changes: make playwright-rebuild)
	$(if $(c),,$(error c=<service> is required, e.g. make hub-restart c=playwright))
	$(if $(filter-out $(HUB_SERVICES),$(c)),$(error c must be one of: $(HUB_SERVICES) (got '$(c)')))
	$(HUB_COMPOSE) restart $(c)

# Tunnel never needs workflow: drop any left from a wider session (--remove-orphans ignores profile-disabled services).
# Naming vite on `up` enables its profile. The hub db is needed (web's dev DB); hub playwright is not.
tunnel: worktree-init _capacity-fresh _logs-owner-fix _test-artifacts-dir _ports-resolve _admit-spoke hub-up ## Force the built stack up (mobile-ready assets, no localhost:5173 dependency) + start an on-demand public Cloudflare tunnel and print its URL
	$(COMPOSE_BUILT) $(ALL_PROFILES) rm -sf workflow
	$(COMPOSE_BUILT) up --build --remove-orphans -V -d web vite
	@$(VITE_BUILD_BARRIER)
	$(COMPOSE_BUILT) up --wait web
	$(COMPOSE_BUILT) --profile tunnel up -d --no-recreate cloudflared
	@echo "Waiting for Cloudflare quick-tunnel URL (~5-10s)..."
	@for i in $$(seq 1 30); do \
		url=$$($(COMPOSE_BUILT) logs cloudflared 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1); \
		if [ -n "$$url" ]; then echo "TUNNEL URL: $$url"; exit 0; fi; \
		sleep 1; \
	done; \
	echo "URL not ready yet — check: $(COMPOSE_BUILT) logs cloudflared"

tunnel-stop: ## Stop and remove the Cloudflare tunnel (leaves the rest of the stack running)
	$(COMPOSE) --profile tunnel rm -sf cloudflared

test-integration: _hub-capacity ## Run all integration (non-UI) tests
	$(call BUDGETED,1,$@,1) $(EXEC_WEB) "$(PYTEST) tests/ -m 'not splash_ui and not home_ui and not utubs_ui and not members_ui and not urls_ui and not create_urls_ui and not update_urls_ui and not tags_ui and not mobile_ui and not metrics_ui and not settings_ui and not search_ui and not admin_ui' -v"

test-integration-parallel: _capacity-fresh _require-n-fits _hub-capacity ## Run integration tests in parallel (queues on the host token budget; shrinks to fit live memory unless n= is given): make test-integration-parallel [n=derived: see make capacity]
	$(call BUDGETED,$(N_INT),$@,$(MIN_TOKENS)) $(EXEC_WEB) "$(PYTEST) tests/ -m 'not splash_ui and not home_ui and not utubs_ui and not members_ui and not urls_ui and not create_urls_ui and not update_urls_ui and not tags_ui and not mobile_ui and not metrics_ui and not settings_ui and not search_ui and not admin_ui' -n @TOKENS@ --dist=loadscope -v"

test-functional: _hub-capacity prune _ui-up ## Run all functional (UI/Playwright) tests
	$(call BUDGETED,1,$@,1) $(EXEC_WEB) "$(PYTEST) tests/ -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui or admin_ui' -v"

test-functional-built: _hub-capacity start-built ## Run all functional (UI/Playwright) tests against built assets
	$(call BUDGETED,1,$@,1) $(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui or admin_ui' -v"

test-ui-parallel: _capacity-fresh _require-n-fits _hub-capacity prune _ui-up ## Run UI tests in parallel (queues on the host token budget; shrinks to fit live memory unless n= is given): make test-ui-parallel [n=derived: see make capacity]
	$(call BUDGETED,$(N_UI),$@,$(MIN_TOKENS)) $(EXEC_WEB) "$(PYTEST) -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui or admin_ui' -n @TOKENS@ --dist=loadscope"

test-ui-parallel-built: _capacity-fresh _require-n-fits _hub-capacity start-built ## Run UI tests in parallel against built assets (queues on the host token budget; shrinks to fit live memory unless n= is given): make test-ui-parallel-built [n=derived: see make capacity]
	$(call BUDGETED,$(N_UI),$@,$(MIN_TOKENS)) $(EXEC_WEB_BUILT) "$(PYTEST) -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui or admin_ui' -n @TOKENS@ --dist=loadscope"

test-js: _require-tools ## Run all JS unit tests (vitest) on the host — no stack needed
	$(MISE) $(FRONTEND_BIN)/vitest run --config frontend/vitest.config.ts

test-js-built: test-js ## Alias of test-js (kept for skills/docs; vitest is host-native and mode-independent)

# The three Docker E2E harnesses take no -n, so each holds a flat 1 token around its run line only (never the image
# builds). They use throwaway containers/networks, not the hub: _hub-capacity only ensures the budget's capacity file.
test-backup-pipeline: _hub-capacity ## Build web+workflow images and run the backup pipeline E2E harness locally (queues on the host token budget)
	docker build -f docker/Dockerfile.Local    -t u4i-local-web:test .
	docker build -f docker/Dockerfile.Workflow -t u4i-local-workflow:test .
	chmod +x docker/backup-pipeline-test.sh docker/backup-pipeline-driver.sh
	$(call BUDGETED,1,$@,1) docker/backup-pipeline-test.sh u4i-local-web:test u4i-local-workflow:test

test-db-provision: _hub-capacity ## Run the db-provision.sh E2E harness against a throwaway Postgres container (queues on the host token budget)
	$(call BUDGETED,1,$@,1) docker/db-provision-test.sh

test-playwright-lifecycle: _hub-capacity ## Build the derived Playwright image and run its idle-reap/restart E2E harness (~7 min; queues on the host token budget)
	docker build -f docker/Dockerfile.Playwright -t u4i-playwright:lifecycle-test docker
	$(call BUDGETED,1,$@,1) docker/playwright-lifecycle-test.sh u4i-playwright:lifecycle-test

# Host-only static tests (Makefile dry runs, compose YAML, the playwright entrypoint): they skip inside `web`, which has
# no make and no compose files. They run in the primary clone's gitignored venv/ (created like `hooks` does), into
# which the primary clone's requirements-test.txt (+ prod) pins are (re)installed whenever either file is newer than
# a stamp inside that venv, so a pin bump reaches it too; the stamp is touched only after a successful install.
# psycopg2 is skipped: it builds from source (needs pg_config), and the pinned psycopg2-binary provides the same
# `psycopg2` module the root conftest imports.
HOST_STATIC_TESTS := tests/unit/test_makefile_profiles.py tests/unit/test_compose_hub.py tests/unit/test_compose_profiles.py tests/unit/test_audit_pins.py tests/unit/test_playwright_entrypoint.py
HOST_STATIC_STAMP = $(PRIMARY_ROOT)/venv/.u4i-host-static.stamp
HOST_STATIC_TEST_PINS = $(PRIMARY_ROOT)/requirements/requirements-test.txt
HOST_STATIC_PROD_PINS = $(PRIMARY_ROOT)/requirements/requirements-prod.txt
test-host-static: _require-mise _host-static-run ## Run the host-only static tests (Makefile/compose/entrypoint) in the primary clone's venv: make test-host-static [f=<paths>] [args=<extra-pytest-args>]

# The host-static run itself, shared by test-host-static and test-affected (a host-static diff); carries its own mise guard.
# PYTHONDONTWRITEBYTECODE=1: tests/ and backend/ are bind-mounted into `web`, which runs the same CPython 3.11 and would
# reuse host-written __pycache__ files whose code objects carry host paths (source lookups then hit FileNotFoundError).
_host-static-run: _require-mise
	@test -n "$(PRIMARY_ROOT)" || { echo "test-host-static: not inside a git checkout" >&2; exit 1; }
	@test -x "$(PRIMARY_ROOT)/venv/bin/python" || (cd "$(PRIMARY_ROOT)" && mise exec python -- python -m venv venv) || exit 1
	@test -f "$(HOST_STATIC_TEST_PINS)" -a -f "$(HOST_STATIC_PROD_PINS)" || { echo "test-host-static: missing $(HOST_STATIC_TEST_PINS) or $(HOST_STATIC_PROD_PINS)" >&2; exit 1; }
	@if [ ! -f "$(HOST_STATIC_STAMP)" ] || [ "$(HOST_STATIC_TEST_PINS)" -nt "$(HOST_STATIC_STAMP)" ] || [ "$(HOST_STATIC_PROD_PINS)" -nt "$(HOST_STATIC_STAMP)" ]; then grep -hvE '^(-r |psycopg2==)' "$(HOST_STATIC_TEST_PINS)" "$(HOST_STATIC_PROD_PINS)" | "$(PRIMARY_ROOT)/venv/bin/pip" install --quiet --disable-pip-version-check -r /dev/stdin && touch "$(HOST_STATIC_STAMP)"; fi
	PYTHONDONTWRITEBYTECODE=1 "$(PRIMARY_ROOT)/venv/bin/python" -m pytest $(or $(f),$(HOST_STATIC_TESTS)) -v $(args)

# Diff-scoped selection for test-affected / test-agent, resolved at parse time (the prerequisites depend on it, and a
# $(MAKE) recursion would break the dry-run tests). Guarded by goal so no other target shells out; `:=` runs each
# script call once, and the $(origin …) guard lets only a command-line AFFECTED_INT= / AFFECTED_UI= /
# AFFECTED_HOST_STATIC= skip the script (a stale exported env var does not). $(shell …) captures only stdout, so a
# failing script's stderr message prints on its own; affected_select appends an AFFECTED_MARKERS_FAILED=<exit> sentinel
# to stdout on failure, and affected_check turns it into a hard stop instead of a silently empty selection (works on
# any GNU make, including macOS make 3.81). affected-markers is deliberately absent: its recipe calls the script directly.
affected_select = $(shell $(AFFECTED_MARKERS) $(1) --base '$(base)' || echo "AFFECTED_MARKERS_FAILED=$$?")
affected_check = $(if $(filter AFFECTED_MARKERS_FAILED=%,$(1)),$(error affected_markers.py failed (exit $(patsubst AFFECTED_MARKERS_FAILED=%,%,$(filter AFFECTED_MARKERS_FAILED=%,$(1)))) — see its message above; for an unresolvable base run git fetch origin))
ifneq ($(filter test-affected test-agent,$(MAKECMDGOALS)),)
$(if $(strip $(f)$(args)),$(error f=/args= are not supported by test-affected/test-agent — they select their own scope; use make test-host-static or test-file-parallel for a narrower run))
ifneq ($(origin AFFECTED_INT),command line)
AFFECTED_INT := $(call affected_select,expr --kind integration)
$(call affected_check,$(AFFECTED_INT))
endif
ifneq ($(origin AFFECTED_UI),command line)
AFFECTED_UI := $(call affected_select,expr --kind ui)
$(call affected_check,$(AFFECTED_UI))
endif
ifneq ($(origin AFFECTED_HOST_STATIC),command line)
AFFECTED_HOST_STATIC := $(call affected_select,host-static)
$(call affected_check,$(AFFECTED_HOST_STATIC))
endif
$(if $(findstring @TOKENS@,$(AFFECTED_INT) $(AFFECTED_UI)),$(error AFFECTED_INT and AFFECTED_UI must not contain @TOKENS@ (the token runner replaces it with the granted worker count)))
endif

affected-markers: ## Show which test markers the branch diff affects, and why: make affected-markers [base=<ref>]
	@$(AFFECTED_MARKERS) report --base '$(base)'

# A host-static-only diff (both marker sets empty) touches no Docker/capacity state; _host-static-run goes first so its
# line precedes the budgeted integration then UI lines.
test-affected: $(if $(filter 1,$(AFFECTED_HOST_STATIC)),_host-static-run) $(if $(strip $(AFFECTED_INT)$(AFFECTED_UI)),_capacity-fresh _require-n-fits _hub-capacity) $(if $(strip $(AFFECTED_UI)),prune _ui-up) ## Run only the test markers the branch diff affects (integration, then UI); queues on the host token budget; shrinks to fit live memory unless n= is given: make test-affected [base=<ref>]
	$(if $(strip $(AFFECTED_INT)),$(call BUDGETED,$(N_INT),$@,$(MIN_TOKENS)) $(EXEC_WEB) "$(PYTEST) tests/ -m '$(AFFECTED_INT)' -n @TOKENS@ --dist=loadscope -v")
	$(if $(strip $(AFFECTED_UI)),$(call BUDGETED,$(N_UI),$@,$(MIN_TOKENS)) $(EXEC_WEB) "$(PYTEST) tests/ -m '$(AFFECTED_UI)' -n @TOKENS@ --dist=loadscope -v")
	$(if $(strip $(AFFECTED_INT)$(AFFECTED_UI)$(filter 1,$(AFFECTED_HOST_STATIC))),,@echo "No affected markers — nothing to run")

test-agent: typecheck test-js test-affected ## Agent tier: typecheck + vitest + the affected markers; queues on the host token budget (target <60s on a single-domain diff): make test-agent [base=<ref>]

# Dev-mode lazy start: a *_ui marker, or a path that collects tests/functional (the whole tree included), restarts an
# idle-reaped hub playwright first. The %_ui word match (parentheses stripped) ignores marker-expression semantics
# (m='not admin_ui' still starts it): a harmless extra start, never a failure.
PAREN_OPEN := (
PAREN_CLOSE := )
UI_MARKER_WORDS = $(filter %_ui,$(subst $(PAREN_OPEN), ,$(subst $(PAREN_CLOSE), ,$(m))))
UI_MARKER_START = $(if $(UI_MARKER_WORDS),playwright-up)
# Default -n for the marker-parallel targets: a *_ui marker gets the UI cap (same word match, so m='not admin_ui'
# gets the smaller UI cap too: fewer workers, never a failure).
MARKER_N_KEY = $(if $(UI_MARKER_WORDS),U4I_N_UI,U4I_N_INT)
N_MARKER = $(or $(n),$(call capacity_val,$(MARKER_N_KEY)))
# Non-empty when f collects tests/functional (a functional path, or the whole tree: empty f, tests, tests/, ., ./, with
# or without a leading ./). The substring match errs toward the UI side (an extra start, the smaller cap), never a failure.
UI_PATH_MATCH = $(or $(findstring tests/functional,$(f)),$(filter tests tests/ . ./,$(or $(f),.) $(patsubst ./%,%,$(f))))
UI_PATH_START = $(if $(UI_PATH_MATCH),playwright-up)
# Default -n for the file-parallel targets: a path that collects UI tests gets the UI cap (whole tree included).
PATH_N_KEY = $(if $(UI_PATH_MATCH),U4I_N_UI,U4I_N_INT)
N_PATH = $(or $(n),$(call capacity_val,$(PATH_N_KEY)))
# A free-form f= or args= (both spliced into the pytest line) carrying its own worker count would run more workers
# than the tokens held, so the test-file* goals refuse one at parse time (-n, -n<N>/-nauto, --numprocesses[=N]); n= is
# the only way to set the count. Combined short flags such as -vn4 are not caught: a pattern broad enough to catch
# them would also match --no-header, so they are accepted as a deliberate-bypass residual.
$(if $(filter test-file test-file-parallel test-file-parallel-built,$(MAKECMDGOALS)),$(if $(filter -n -n% --numprocesses --numprocesses=%,$(f) $(args)),$(error args and f must not set -n/--numprocesses (it bypasses the token budget); use make test-file-parallel f=… n=<N>)))
# The token runner replaces every @TOKENS@ in the budgeted line with the granted worker count, so user text spliced into
# that line must never carry it.
$(if $(findstring @TOKENS@,$(f) $(args) $(m)),$(error f, args and m must not contain @TOKENS@ (the token runner replaces it with the granted worker count)))
test-marker: _hub-capacity $(UI_MARKER_START) ## Run tests for a specific marker: make test-marker m=<marker> (a *_ui marker starts hub playwright)
	$(call BUDGETED,1,$@,1) $(EXEC_WEB) "$(PYTEST) tests/ -m '$(m)' -v"

test-marker-built: _hub-capacity start-built ## Run tests for a specific marker against built assets: make test-marker-built m=<marker>
	$(call BUDGETED,1,$@,1) $(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m '$(m)' -v"

test-marker-parallel: _capacity-fresh _require-n-fits _hub-capacity $(UI_MARKER_START) ## Run tests for a specific marker in parallel (queues on the host token budget; shrinks to fit live memory unless n= is given): make test-marker-parallel m=<marker> [n=derived: see make capacity] (a *_ui marker starts hub playwright)
	$(call BUDGETED,$(N_MARKER),$@,$(MIN_TOKENS)) $(EXEC_WEB) "$(PYTEST) tests/ -m '$(m)' -n @TOKENS@ --dist=loadscope -v"

test-marker-parallel-built: _capacity-fresh _require-n-fits _hub-capacity start-built ## Run tests for a specific marker in parallel against built assets (queues on the host token budget; shrinks to fit live memory unless n= is given): make test-marker-parallel-built m=<marker> [n=derived: see make capacity]
	$(call BUDGETED,$(N_MARKER),$@,$(MIN_TOKENS)) $(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m '$(m)' -n @TOKENS@ --dist=loadscope -v"

test-last-failed: _hub-capacity ## Re-run only the tests that failed last run (pytest --lf)
	$(call BUDGETED,1,$@,1) $(EXEC_WEB) "$(PYTEST) tests/ -v --lf"

test-file: _hub-capacity $(UI_PATH_START) ## Run pytest against a specific file or path: make test-file f=<path> [args=<extra-pytest-args>, never -n: use test-file-parallel] (a tests/functional path starts hub playwright)
	$(call BUDGETED,1,$@,1) $(EXEC_WEB) "$(PYTEST) $(f) -v $(args)"

test-file-parallel: _capacity-fresh _require-n-fits _hub-capacity $(UI_PATH_START) ## Run pytest against a specific file or path in parallel (queues on the host token budget; shrinks to fit live memory unless n= is given): make test-file-parallel f=<path> [n=derived: see make capacity] [args=<extra-pytest-args>] (a tests/functional path starts hub playwright)
	$(call BUDGETED,$(N_PATH),$@,$(MIN_TOKENS)) $(EXEC_WEB) "$(PYTEST) $(f) -n @TOKENS@ --dist=loadscope -v $(args)"

test-file-parallel-built: _capacity-fresh _require-n-fits _hub-capacity start-built ## Run pytest against a specific file or path in parallel against built assets (queues on the host token budget; shrinks to fit live memory unless n= is given): make test-file-parallel-built f=<path> [n=derived: see make capacity] [args=<extra-pytest-args>]
	$(call BUDGETED,$(N_PATH),$@,$(MIN_TOKENS)) $(EXEC_WEB_BUILT) "$(PYTEST) $(f) -n @TOKENS@ --dist=loadscope -v $(args)"

vite-build: ## Build Vite to verify no import/syntax errors (one-off vite container)
	$(RUN_VITE) pnpm exec vite build

vite-build-built: ## Rebuild Vite assets in the built stack (one-off vite build container; used when up-built is running and the long-lived dev vite service is absent)
	$(COMPOSE_BUILT) run --rm --no-deps vite pnpm exec vite build

lint: lint-python lint-frontend lint-shell lockfile-check lint-actions audit-pins ## Run all linters (same command CI and pre-commit run)

lint-python: _require-tools ## Lint Python with ruff + single-letter-name check
	$(MISE) ruff check .
	@mise exec python -- python scripts/check_identifier_names.py $(PYTHON_FILES)

lint-frontend: _require-tools ## Lint JS and TS with eslint
	cd frontend && $(MISE) ./node_modules/.bin/eslint "**/*.js" --no-config-lookup --ignore-pattern node_modules
	cd frontend && $(MISE) ./node_modules/.bin/eslint "**/*.ts"

lint-shell: _require-tools _require-shell-files ## Lint shell scripts with shellcheck
	$(MISE) shellcheck --severity=warning -x $(SHELL_FILES)

# The -ignore is an actionlint schema gap, not a repo issue: `command:` under a workflow `services:` entry is valid GitHub Actions syntax (test.yml's redis-metrics) but missing from actionlint's schema.
lint-actions: _require-tools ## Lint GitHub Actions workflows
	$(MISE) actionlint -ignore 'unexpected key "command" for "services" section'

format-check: format-check-python format-check-frontend format-check-shell ## Check formatting (no writes)

format-check-python: _require-tools ## Check Python formatting with ruff
	$(MISE) ruff format --check .

format-check-frontend: _require-tools ## Check JS and TS formatting with prettier
	cd frontend && $(MISE) ./node_modules/.bin/prettier --check "**/*.{ts,js}"

format-check-shell: _require-tools _require-shell-files ## Check shell formatting with shfmt
	$(MISE) shfmt -i 2 -ci -d $(SHELL_FILES)

format: _require-tools _require-shell-files ## Apply all formatters
	$(MISE) ruff format .
	cd frontend && $(MISE) ./node_modules/.bin/prettier --write "**/*.{ts,js}"
	$(MISE) shfmt -i 2 -ci -w $(SHELL_FILES)

typecheck: _require-tools ## Run TypeScript typecheck (app + test + node-side tsconfigs) on the host
	$(MISE) $(FRONTEND_BIN)/tsc --noEmit --project frontend/tsconfig.json
	$(MISE) $(FRONTEND_BIN)/tsc --noEmit --project frontend/tsconfig.test.json
	$(MISE) $(FRONTEND_BIN)/tsc --noEmit --project frontend/tsconfig.node.json

generate-types: ## Generate TypeScript API types from backend OpenAPI spec + per-event dim shapes
	$(EXEC_WEB_AS_HOST) "$(FLASK) openapi generate --output /code/u4i/frontend/types/openapi.json --strict"
	$(RUN_VITE) pnpm exec openapi-typescript frontend/types/openapi.json -o frontend/types/api.d.ts
	$(EXEC_WEB_AS_HOST) "$(FLASK) metrics generate-dim-types --output /code/u4i/frontend/types/metrics-dimensions.d.ts"
	$(EXEC_WEB_AS_HOST) "$(FLASK) metrics generate-dim-values --output /code/u4i/frontend/types/metrics-dim-values.ts"
	$(EXEC_WEB_AS_HOST) "$(FLASK) metrics generate-events --output /code/u4i/frontend/types/metrics-events.ts"
	$(EXEC_WEB_AS_HOST) "$(FLASK) metrics generate-resources --output /code/u4i/frontend/types/metrics-resources.ts"
	$(EXEC_WEB_AS_HOST) "$(FLASK) metrics generate-flows --output /code/u4i/frontend/types/metrics-flows.ts"
	$(RUN_VITE) pnpm exec prettier --write frontend/types/api.d.ts frontend/types/openapi.json frontend/types/metrics-dimensions.d.ts frontend/types/metrics-dim-values.ts frontend/types/metrics-events.ts frontend/types/metrics-resources.ts frontend/types/metrics-flows.ts

generate-endpoints: ## Regenerate docs/endpoints/endpoint-registry.json + ENDPOINT_REGISTRY.md from the live url_map
	$(EXEC_WEB_AS_HOST) "$(FLASK) endpoints generate --output /code/u4i/docs/endpoints/endpoint-registry.json --markdown-output /code/u4i/docs/endpoints/ENDPOINT_REGISTRY.md"

audit-endpoints: ## Audit the committed endpoint registry against the live app (exits non-zero on drift)
	$(EXEC_WEB) "$(FLASK) endpoints audit --strict"

endpoint-info: ## Show what touches a route: make endpoint-info e=<endpoint | rule | 'METHOD /rule'>
	$(if $(e),,$(error e=<route> is required, e.g. make endpoint-info e=utubs.get_single_utub))
	@$(ENDPOINT_INFO) -- '$(subst ','\'',$(e))'

test-artifacts: _require-mise ## Print the latest UI failure-artifact index (run=<id> for an older run)
	@$(FAILURE_ARTIFACTS_REPORT) --root tmp/test-artifacts $(if $(run),--run='$(subst ','\'',$(run))')

audit: ## Run the metrics event coverage audit (exits non-zero if gaps found)
	$(EXEC_WEB) "$(FLASK) metrics audit --strict"

addmock: ## Seed the dev database with all mock data (flask addmock all)
	$(EXEC_WEB) "$(FLASK) addmock all"

clear-db: ## Empty every table in the dev database (same schema, no data) — frees any registered email/username for reuse
	$(EXEC_WEB) "$(FLASK) managedb clear dev"

reset-db: clear-db addmock ## Empty the dev database, then reseed all mock data (seeded users/UTubs restored)

# ttl is spliced into a double-quoted `bash -c` string, so it is validated with make functions only (a shell
# `case` over $(ttl) would itself expand it): stripping every digit (remove_chars, defined at the top) must leave
# nothing, and it must be one word.
REAP_TTL = $(or $(ttl),10)
REAP_TTL_NON_DIGITS = $(strip $(call remove_chars,0 1 2 3 4 5 6 7 8 9,$(REAP_TTL)))

# c (restart / logs / hub-restart) is spliced into compose command lines, so it is validated at parse time as one
# compose service name, via remove_chars; the `$` guard at the top still runs first.
SERVICE_NAME_CHARS := a b c d e f g h i j k l m n o p q r s t u v w x y z 0 1 2 3 4 5 6 7 8 9 _ -
$(if $(c),$(if $(or $(word 2,$(c)),$(strip $(call remove_chars,$(SERVICE_NAME_CHARS),$(c)))),$(error c must be one compose service name ([a-z0-9_-]), got '$(c)')))

reset-test-dbs: ## Drop leaked per-run test databases and orphaned Redis leases (ttl=<minutes>, default 10)
	$(if $(or $(REAP_TTL_NON_DIGITS),$(word 2,$(REAP_TTL))),$(error ttl must be a non-negative integer number of minutes))
	$(EXEC_WEB) "source /code/venv/bin/activate && python -m scripts.testrun_resources reap --ttl-minutes $(REAP_TTL)"

plan-list: ## List every plan (masters + sub-plans) under plans/ with finished/open status
	@.claude/scripts/plan-list.sh

playwright-unlock: ## Kill orphaned Playwright-MCP Chrome holding the profile lock and clear stale Singleton* files
	@.claude/scripts/playwright-unlock.sh

# hooks always targets the MAIN checkout (the git common dir's parent), so the shared hook's INSTALL_PYTHON never
# points at a linked worktree's venv. In the main checkout, that is the repo root itself.
# The venv uses the mise-pinned python (`make tools` installs it first).
hooks: ## Install the shared pre-commit git hook (idempotent; venv + install always in the main checkout, safe to run from any worktree)
	@common_dir=$$(git rev-parse --path-format=absolute --git-common-dir) || exit 1; \
		main=$$(dirname "$$common_dir"); \
		test -x "$$main/venv/bin/pre-commit" || (cd "$$main" && mise exec python -- python -m venv venv) || exit 1; \
		"$$main/venv/bin/pip" install --quiet --disable-pip-version-check \
			$$(grep -E '^pre-commit==' "$$main/requirements/requirements-dev.txt") || exit 1; \
		(cd "$$main" && venv/bin/pre-commit install) || exit 1; \
		"$$main/venv/bin/pre-commit" --version

# --git-path honors linked worktrees (where .git is a file) and core.hooksPath.
hooks-check: ## Report whether the pre-commit hook is installed (exits 1 when missing; worktree-safe)
	@hook_path=$$(git rev-parse --git-path hooks/pre-commit); \
		if test -f "$$hook_path"; then echo "pre-commit hook: INSTALLED"; \
		else echo "pre-commit hook: MISSING — run 'make hooks'"; exit 1; fi

# hub playwright: `-a`, so an idle-reaped container shows as `Exited (0) …` (normal; the next UI target restarts it).
stack-info: _require-mise ## Print this checkout's spoke project, host URLs, hub project, hub db/playwright state and shared network
	@echo "slug:           $(U4I_SLUG)"
	@echo "spoke project:  $(U4I_PROJECT)"
	@echo "web alias:      $(U4I_WEB_HOST)"
	@echo "vite alias:     $(U4I_VITE_HOST)"
	@echo "hub project:    $(U4I_HUB_PROJECT)"
	@echo "shared network: $(U4I_SHARED_NET)"
	@echo "primary clone:  $(if $(U4I_PRIMARY),yes,no)"
	@$(SPOKE_PORTS) show --output $(PORTS_ENV)
	@if docker network inspect $(U4I_SHARED_NET) >/dev/null 2>&1; then \
		if [ -n "$$(docker ps --filter label=com.docker.compose.project=$(U4I_HUB_PROJECT) --filter label=com.docker.compose.service=db --filter status=running -q)" ]; then echo "hub db:         running"; else echo "hub db:         not running"; fi; \
		playwright_status="$$($(HUB_PLAYWRIGHT_PS) --format '{{.Status}}')"; echo "hub playwright: $${playwright_status:-absent}"; \
		attached="$$($(ATTACHED_SPOKES))"; echo "attached to hub: $$(echo $${attached:-none})"; \
	else echo "hub: not running"; fi

# Links one untracked path ($(1)) from the primary clone into this worktree. An existing symlink is kept, a real
# file or dir is never clobbered (warning only), and $(2) runs when the primary lacks the path too. A dangling
# symlink is reported with a removal hint, then $(3) runs (exit 1 for .env; a no-op for secrets).
worktree_link = if [ -L $(1) ] && [ ! -e $(1) ]; then \
		echo "worktree-init: $(1) is a broken symlink to $$(readlink $(1)); remove it (rm $(1)) and rerun 'make worktree-init'" >&2; $(3); \
	elif [ -L $(1) ]; then echo "worktree-init: $(1) already linked"; \
	elif [ -e $(1) ]; then echo "worktree-init: warning: $(1) is a real file or directory here; leaving it" >&2; \
	elif [ -e "$(PRIMARY_ROOT)/$(1)" ]; then ln -s "$(PRIMARY_ROOT)/$(1)" $(1) && echo "worktree-init: linked $(1) -> $(PRIMARY_ROOT)/$(1)"; \
	else $(2); fi

# Held in a variable because its comma would otherwise split the $(if …) below. Dry-run tests match it verbatim.
WORKTREE_INIT_PRIMARY_MSG := worktree-init: primary clone, nothing to link

# The branch is chosen with make's $(if), not a shell `if`, so `make -n` prints only the taken branch. No $(MAKE)
# recursion here, because `make -n` would run a recursive make for real (setup and every stack-start target depend
# on it). The $(error) guard is recipe-level, so it fires only when this target runs.
worktree-init: ## Link .env and secrets/ from the primary clone into this worktree (no-op in the primary clone)
	$(if $(PRIMARY_ROOT),,$(error worktree-init: not inside a git checkout (git rev-parse --git-common-dir failed)))
	$(if $(U4I_PRIMARY),@echo "$(WORKTREE_INIT_PRIMARY_MSG)",@$(call worktree_link,.env,echo "worktree-init: $(PRIMARY_ROOT)/.env is missing; create it in the primary clone first" >&2; exit 1,exit 1))
	$(if $(U4I_PRIMARY),,@$(call worktree_link,secrets,echo "worktree-init: no secrets/ in the primary clone either; skipping (local compose never reads it)",:))

setup: worktree-init ## One-time per clone/worktree: .env/secrets links (worktrees), toolchain, pnpm deps, hooks, capacity (idempotent)
	@$(MAKE) --no-print-directory tools
	@$(MAKE) --no-print-directory hooks
	@$(MAKE) --no-print-directory capacity || echo "⚠ capacity deferred: docker unavailable — 'make up' will generate it"

# .mise.toml is deliberately never `mise trust`ed: a pin-only config (min_version + plain [tools] strings) loads untrusted, and mise's own trust check refuses anything more at runtime.
# mise-config-check (scripts/mise_config_check.py; run by `tools` after `mise install`, and by CI's Format and Lint jobs; uses mise's own python via `mise exec python --`, never a system one): a post-hoc policy lint for contexts where mise's trust check won't fire (CI / trusted clones).
# It keeps .mise.toml to min_version + plain `[tools] name = "version"` pins, and asserts both Dockerfiles' `ARG PNPM_VERSION=` equals the [tools] pnpm pin (one logical pin; images need their own literal). In an untrusted clone, mise's trust error fires first.
# `pnpm install --frozen-lockfile --ignore-scripts`: no dependency install/postinstall scripts run on the host, and a lockfile out of sync with package.json fails instead of being rewritten.
tools: ## Install the pinned host toolchain (.mise.toml) + frontend node_modules; set git blame ignore-revs
	@command -v mise >/dev/null || { echo "mise not installed — see https://mise.jdx.dev/installing-mise.html (Linux: curl https://mise.run | sh; macOS: brew install mise)"; exit 1; }
	@mise install || { echo "make tools: mise install failed (see above). If it says .mise.toml is 'not trusted', the file has more than min_version + plain [tools] pins: remove that config instead of running 'mise trust'."; exit 1; }
	@$(MAKE) --no-print-directory mise-config-check
	cd frontend && $(MISE) pnpm install --frozen-lockfile --ignore-scripts
	git config blame.ignoreRevsFile .git-blame-ignore-revs

# Overrides pass through only when set on the command line or in the environment (never read back from the generated
# file); an unset knob passes no flag, so the recorded (sticky) override is reused, and `=auto` clears it.
capacity: _require-mise ## Derive worker counts + interlocks from docker info (overrides: U4I_N_UI=<n|auto> U4I_N_INT=<n|auto> U4I_MEM_FRACTION=<f|auto>)
	@$(CAPACITY) generate --output $(CAPACITY_ENV) \
		$(if $(and $(filter command line environment,$(origin U4I_N_UI)),$(U4I_N_UI)),--n-ui '$(U4I_N_UI)') \
		$(if $(and $(filter command line environment,$(origin U4I_N_INT)),$(U4I_N_INT)),--n-int '$(U4I_N_INT)') \
		$(if $(and $(filter command line environment,$(origin U4I_MEM_FRACTION)),$(U4I_MEM_FRACTION)),--mem-fraction '$(U4I_MEM_FRACTION)')
	@$(CAPACITY) show --output $(CAPACITY_ENV) --hub-project $(U4I_HUB_PROJECT)

mise-config-check: ## Fail unless .mise.toml is pin-only and the Dockerfiles' ARG PNPM_VERSION matches its pnpm pin
	@mise exec python -- python scripts/mise_config_check.py

audit-pins: ## Fail unless every dependency manifest, image tag, pip install and action ref is exactly pinned (host-only, no stack)
	@mise exec python -- python scripts/audit_pins.py

lockfile-check: ## Fail if an npm lockfile/.npmrc reappears next to pnpm-lock.yaml
	@test -f frontend/pnpm-lock.yaml || { echo "lockfile-check: frontend/pnpm-lock.yaml is missing"; exit 1; }
	@test -f frontend/pnpm-workspace.yaml || { echo "lockfile-check: frontend/pnpm-workspace.yaml is missing"; exit 1; }
	@for npm_file in frontend/package-lock.json frontend/.npmrc; do \
		if test -e "$$npm_file" || test -L "$$npm_file"; then echo "lockfile-check: $$npm_file must not exist (frontend/ is pnpm-only; never run npm install there)"; exit 1; fi; \
	done

# Private prerequisite guards (_require-*) deliberately have no "## desc" so they stay out of 'make help'.
_require-tools:
	@command -v mise >/dev/null && test -x $(FRONTEND_BIN)/prettier || { echo "host lint toolchain missing — run 'make tools'"; exit 1; }

# Capacity only needs mise's python, not the frontend prettier binary _require-tools also demands.
_require-mise:
	@command -v mise >/dev/null || { echo "mise missing — run 'make tools' (or 'make setup')"; exit 1; }

# The hub is always defined by the primary clone's files (HUB_COMPOSE). The $(error) is recipe-level, so it fires only
# when a hub target runs (a `make -n` dry run included), and an empty PRIMARY_ROOT (not a git checkout) fails it too.
_require-hub-files:
	$(if $(wildcard $(PRIMARY_ROOT)/docker/compose.hub.yaml),,$(error the primary clone ($(PRIMARY_ROOT)) must be a git checkout carrying docker/compose.hub.yaml (check out a branch with the hub there)))

# hub-up's prerequisite, never a hub-up recipe line: make expands a whole recipe before running its first line, so
# HUB_COMPOSE's capacity-file `wildcard` would otherwise miss a file created on this same run and drop its --env-file.
_hub-capacity: _require-hub-files _require-mise
	@$(CAPACITY) ensure --output $(PRIMARY_CAPACITY_ENV)

# Runs before every stack/test target: regenerates the capacity file only when missing or its host fingerprint changed.
_capacity-fresh: _require-mise
	@$(CAPACITY) ensure --output $(CAPACITY_ENV)

# Runs before up/up-built/start-built/_ui-up/tunnel: re-owns the app_logs volume's log dir to HOST_UID:HOST_GID (mode 775) when an
# older image or workflow start left it owned by another uid, since web would otherwise crash on its log file. Logic
# (and its unit tests) lives in scripts/capacity.py `logs-owner-fix`; it prints once when it repairs, silent otherwise.
_logs-owner-fix: _capacity-fresh
	@$(CAPACITY) logs-owner-fix --output $(CAPACITY_ENV)

# Runs before up/up-built/start-built/_ui-up/tunnel: pre-creates web's UI failure-artifact bind source
# (tests/functional/failure_artifacts.py) as the host user, since Docker would create a missing one as root and web
# (HOST_UID) could not write into it. A root-owned leftover from before this target existed fails with the fix command
# (the whole tmp/, since Docker's auto-create also leaves a missing parent root-owned). A symlink or file in its place is
# refused rather than followed, so the bind mount never writes artifacts outside the checkout.
_test-artifacts-dir:
	@if [ -L tmp/test-artifacts ] || { [ -e tmp/test-artifacts ] && [ ! -d tmp/test-artifacts ]; }; then echo "tmp/test-artifacts must be a real directory (found a symlink or file): remove it" >&2; exit 1; fi
	@mkdir -p tmp/test-artifacts
	@test -w tmp/test-artifacts || { echo "tmp/test-artifacts is not writable (root-owned from an older Docker auto-create?): sudo chown -R $$(id -u):$$(id -g) tmp" >&2; exit 1; }

# Runs before every stack start: probes Docker + host sockets and (re)writes $(PORTS_ENV) with this spoke's web/vite host
# ports (explicit U4I_WEB_PORT/U4I_VITE_PORT > cached-and-still-free > first free from the preferred port; see
# scripts/spoke_ports.py). Known residual race, deliberately not engineered around: two spokes starting in the same
# second can pick the same free port, and the second `compose up` fails with `port is already allocated`. Rerunning
# `make up` fixes it, since the port is then published by the other project and gets skipped.
_ports-resolve: _require-mise
	@$(SPOKE_PORTS) resolve --project $(U4I_PROJECT) --slug $(U4I_HOST_SLUG) $(if $(U4I_PRIMARY),--primary) $(if $(U4I_WEB_PORT),--web-port '$(subst ','\'',$(U4I_WEB_PORT))') $(if $(U4I_VITE_PORT),--vite-port '$(subst ','\'',$(U4I_VITE_PORT))') --output $(PORTS_ENV)

# Runs before every spoke start (after _ports-resolve, before hub-up / any compose up): refuses spoke N+1 when the hub,
# N+1 idle spokes and one full-width test run would exceed usable memory (U4I_SPOKE_MAX in the PRIMARY clone's capacity
# file; see scripts/capacity.py `admit`). Counts distinct running compose projects on the shared network minus the hub,
# and always admits a spoke that is already running, so re-running `make up` (or start-built's down/up) is never
# refused. A docker failure refuses, never admits. Known residual race, deliberately not engineered around (same stance
# as _ports-resolve): two spokes starting in the same second can both be counted before either starts, so both are admitted.
# "Before hub-up" is serial-make ordering: under make -j they are sibling prerequisites, so the hub may start first, but
# the spoke's own compose up (a recipe line, run after every prerequisite) is still gated.
_admit-spoke: _hub-capacity
	@$(CAPACITY) admit --output $(PRIMARY_CAPACITY_ENV) --project $(U4I_PROJECT) --hub-project $(U4I_HUB_PROJECT) --network $(U4I_SHARED_NET)

# Refuses a corrupt capacity file (the derived U4I_N_UI/U4I_N_INT defaults are spliced into the runner's --tokens) and an
# explicit n that is not a positive integer or exceeds this host's ceiling, before any prune/rebuild/pytest. Depends
# on _capacity-fresh so the file is current before it is read, regardless of -j. Shared by UI and integration
# targets, so it names both knobs.
_require-n-fits: _capacity-fresh
	@for key in U4I_N_UI U4I_N_INT; do \
		val=$$(sed -n "s/^$$key=//p" $(CAPACITY_ENV)); \
		case "$$val" in ''|*[!0-9]*) echo "$$key invalid in $(CAPACITY_ENV) — run 'make capacity'"; exit 1;; esac; \
	done
	@if [ -n "$(n)" ]; then \
		case "$(n)" in *[!0-9]*) echo "n=$(n) is not a positive integer"; exit 1;; esac; \
		if [ "$(n)" -lt 1 ]; then echo "n=$(n) is not a positive integer"; exit 1; fi; \
		max_n=$(call capacity_val,U4I_N_MAX); \
		case "$$max_n" in ''|*[!0-9]*) echo "U4I_N_MAX invalid in $(CAPACITY_ENV) — run 'make capacity'"; exit 1;; esac; \
		if [ "$(n)" -gt "$$max_n" ]; then \
			echo "n=$(n) exceeds this host's capacity ceiling (U4I_N_MAX=$$max_n); raise it with 'make capacity U4I_N_UI=$(n)' (UI targets, *_ui markers, tests/functional paths) or 'make capacity U4I_N_INT=$(n)' (other integration/marker/file targets), then 'make up [p=…] d=1'"; \
			exit 1; \
		fi; \
	fi

# Guards the workflow exec targets. Not an auto-start: workflow writes /app/container_environment during startup and
# only reports healthy after a successful flush (200s start_period), so starting it here would race the recipes' own check.
_require-workflow:
	@$(COMPOSE) $(ALL_PROFILES) ps --status running --services | grep -qx workflow || { echo "workflow is not running — start it with: make up p=full d=1" >&2; exit 1; }

# An empty list would make shfmt read stdin (hang, or pass silently in CI), so fail loudly instead.
_require-shell-files:
	@test -n "$(SHELL_FILES)" || { echo "no shell files found (not a git checkout, or git ls-files failed)"; exit 1; }

prune: ## Prune dangling images, orphaned volumes, and build cache
	docker image prune -f
	docker volume prune -f
	docker builder prune -f

metrics-watch: ## Live tail Redis ops on dedicated redis-metrics container (metrics on by default; see CLAUDE.md)
	$(COMPOSE) exec redis-metrics redis-cli MONITOR

metrics-snapshot: ## Snapshot current metrics:counter:* keys with values
	$(COMPOSE) exec redis-metrics sh -c 'for k in $$(redis-cli --scan --pattern "metrics:counter:*"); do echo "$$k = $$(redis-cli GET $$k)"; done'

metrics-flush-now: _require-workflow ## Trigger an immediate flush worker run (drains Redis -> Postgres)
	$(COMPOSE) exec workflow sh -c 'if [ ! -f /app/container_environment ]; then echo "ERROR: /app/container_environment missing on workflow container. Run make up p=full d=1 first." >&2; exit 1; fi; set -a && . /app/container_environment && set +a && /opt/metrics-venv/bin/python /app/flush_metrics.py'

metrics-rows: ## Show last 25 flushed rows from AnonymousMetrics
	$(HUB_COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$(U4I_DEV_DB)" -c "SELECT \"bucketStart\", \"eventName\", endpoint, method, \"statusCode\", dimensions, count FROM \"AnonymousMetrics\" ORDER BY \"bucketStart\" DESC LIMIT 25;"'

metrics-smoke-test: metrics-snapshot metrics-flush-now metrics-rows ## E2E: snapshot Redis, force flush, dump Postgres rows

metrics-clear-counters: ## Delete pending Redis state (metrics:counter:* and metrics:batch:*); leaves flush lock/sentinel intact
	$(COMPOSE) exec redis-metrics sh -c 'redis-cli --scan --pattern "metrics:counter:*" | xargs -r redis-cli UNLINK; redis-cli --scan --pattern "metrics:batch:*" | xargs -r redis-cli UNLINK'

metrics-clear-rows: ## Truncate AnonymousMetrics in Postgres
	$(HUB_COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$(U4I_DEV_DB)" -c "TRUNCATE TABLE \"AnonymousMetrics\";"'

metrics-clear-all: metrics-clear-counters metrics-clear-rows gauge-clear-rows ## Wipe all metrics data (Redis pending + Postgres flushed + gauges)

gauge-sample-now: _require-workflow ## Trigger an immediate gauge sampler run (writes one AnonymousGauges row per gauge)
	$(COMPOSE) exec workflow sh -c 'if [ ! -f /app/container_environment ]; then echo "ERROR: /app/container_environment missing on workflow container. Run make up p=full d=1 first." >&2; exit 1; fi; set -a && . /app/container_environment && set +a && /opt/metrics-venv/bin/python /app/sample_gauges.py'

gauge-rows: ## Show last 25 sampled rows from AnonymousGauges
	$(HUB_COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$(U4I_DEV_DB)" -c "SELECT \"gaugeName\", \"sampledAt\", \"valueInt\", \"valueFloat\", dimensions FROM \"AnonymousGauges\" ORDER BY \"sampledAt\" DESC LIMIT 25;"'

gauge-clear-rows: ## Truncate AnonymousGauges in Postgres
	$(HUB_COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$(U4I_DEV_DB)" -c "TRUNCATE TABLE \"AnonymousGauges\";"'

notify-test: _require-workflow ## Post a message to the Discord webhook (NOTIFICATION_URL from the environment, else from .env) via restricted_curl in the workflow container (msg optional, defaults to a sample digest): make notify-test [msg="DOCKER: your message"]
	@url="$${NOTIFICATION_URL:-}"; \
	if [ -z "$$url" ] && [ -f .env ]; then \
	  line="$$(grep -E 'NOTIFICATION_URL[[:space:]]*=' .env | grep -v '^[[:space:]]*#' | tail -n1)"; \
	  url="$${line#*=}"; \
	  url="$$(printf '%s' "$$url" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$$//' -e 's/^["'\'']//' -e 's/["'\'']$$//' | tr -d '\r\n')"; \
	fi; \
	if [ -z "$$url" ]; then echo 'Usage: set NOTIFICATION_URL in the environment or .env, then run: make notify-test [msg="DOCKER: your message"]' >&2; echo 'restricted_curl posts the message verbatim (it does NOT prepend "DOCKER: "); include it yourself to match production. No raw " \\ or newlines (restricted_curl does not JSON-escape).' >&2; exit 1; fi; \
	echo "Posting msg to the Discord webhook in NOTIFICATION_URL via the workflow container..."; \
	$(COMPOSE) exec workflow restricted_curl POST "$$url" "$(or $(msg),$(NOTIFY_TEST_DEFAULT_MSG))"
