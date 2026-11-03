# GARC Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.1.0] — 2026-04-15 — Initial Release

This is the first public release of GARC. Core operations for Gmail, Calendar,
Drive, Sheets, Tasks, and People are functional end-to-end. Several enterprise
features are deferred to v0.2 (see Known Limitations in README).

### Added

**CLI entrypoint**
- `bin/garc` — Main CLI with full command dispatch (gmail / calendar / drive / sheets / task / people / memory / ingress / daemon / agent / approve / auth / bootstrap / setup / status / heartbeat)

**Google Workspace operations**
- `lib/gmail.sh` + `scripts/garc-gmail-helper.py` — send / reply / search / read / inbox / draft / labels / profile
- `lib/calendar.sh` + `scripts/garc-calendar-helper.py` — today / week / list / create / delete / freebusy
- `lib/drive.sh` + `scripts/garc-drive-helper.py` — list / search / upload / download / create-doc / share / info
- `lib/sheets.sh` + `scripts/garc-sheets-helper.py` — info / read / append / update / search / clear
- `lib/task.sh` + `scripts/garc-tasks-helper.py` — list / create / done / show / update / delete / clear-completed / tasklists
- `lib/people.sh` + `scripts/garc-people-helper.py` — lookup / directory / list / contacts

**Agent runtime**
- `lib/bootstrap.sh` — Disclosure chain loading from Google Drive (SOUL.md → USER.md → MEMORY.md → RULES.md → HEARTBEAT.md)
- `lib/memory.sh` — Google Sheets memory sync (pull / push / search)
- `lib/agent.sh` — Agent registry via Google Sheets (list / register / show)
- `lib/approve.sh` — Execution gate and approval flow (gate / list / act / create)
- `lib/heartbeat.sh` — System state logging to Google Sheets
- `lib/ingress.sh` — Queue/ingress system with JSONL local cache (enqueue / list / run-once / done / fail / stats)
- `lib/daemon.sh` — Gmail polling daemon with macOS launchd support (start / stop / status / poll-once / install)
- `lib/kg.sh` — Knowledge graph via Google Drive Docs

**Auth & config**
- `scripts/garc-auth-helper.py` — OAuth2 scope inference + token management
- `scripts/garc-core.py` — Shared auth, retry, and utilities
- `scripts/garc-setup.py` — One-shot workspace provisioner (garc setup all)
- `config/scope-map.json` — 42 task types × Google OAuth scopes × keyword patterns
- `config/gate-policy.json` — Execution gate policies (none / preview / approval)
- `config/config.env.example` — Configuration template
- `agents.yaml` — Default agent declarations (main / crm-agent / doc-agent / expense-processor)

**Claude Code bridge**
- `scripts/garc-ingress-helper.py` — Task type inference + Claude Code execution prompt builder
- `.claude/skills/garc-runtime/SKILL.md` — Claude Code skill definition

**Documentation**
- `README.md` — Quickstart, usage, prerequisites, known limitations, roadmap
- `README.ja.md` — Japanese translation
- `docs/quickstart.md` — 15-minute setup guide
- `docs/google-cloud-setup.md` — Google Cloud Console step-by-step
- `docs/garc-architecture.md` — Full architecture reference
- `docs/garc-vs-larc.md` — GARC vs LARC comparison
- `docs/gws-api-alignment.md` — GWS API command mappings

### Known Limitations (v0.1.0)

- Google Chat integration not implemented — Gmail used as fallback for notifications
- Service Account / Domain-wide Delegation not supported — user OAuth only
- No audit log
- `garc auth revoke` not implemented
- Editing existing Google Docs body not implemented
- Google Forms → auto-enqueue pipeline not implemented
- macOS only for daemon install (launchd); Linux systemd not yet supported
- Single Google Workspace organization only

---

## [0.2.0] — 2026-04-15 — Enterprise Hardening + Workflow Expansion

All 17 findings from the v0.1.0 operational readiness audit have been resolved.

### Fixed (P0 — Blockers)

- **agent register**: upsert by `agent_id` — re-running no longer creates duplicate rows
- **daemon poll-once**: extracted `_gmail_poll_cycle` for synchronous single-cycle execution; `sleep 5 / kill` timeout removed
- **requests warnings**: suppressed `urllib3` / `googleapiclient` `DeprecationWarning` on Python 3.12+; `requests` added to `requirements.txt`

### Fixed (P1 — Operational risks)

- **OAuth refresh**: `RefreshError` (revoked token) now deletes the stale token file and falls through to a new OAuth flow; scope coverage verified before returning cached credentials
- **ingress stale-reset**: new `garc ingress stale-reset [--timeout N]` resets `in_progress` items stuck longer than N minutes back to `pending`
- **Sheets empty rows**: `garc sheets trim-sheet` and `garc sheets clean-all` use `batchUpdate deleteDimension` to remove trailing empty rows
- **Approval notification**: `garc ingress run-once` on approval-gated items sends a Gmail notification to `GARC_APPROVAL_EMAIL`; `GARC_AUTO_CONFIRM` env var added

### Added (P2 — Enterprise features)

- **Google Chat**: `scripts/garc-chat-helper.py` + `garc send chat send/list-spaces/list-messages`
- **Service Account / DWD**: `garc auth service-account verify`, `GARC_IMPERSONATE_EMAIL`, `--type service-account` flag on `garc auth login`
- **Audit log**: `audit` tab in Sheets; `garc audit list [--agent] [--since]`; async audit hook in `bin/garc`
- **`garc auth revoke`**: POST to Google revoke endpoint + deletes local token file
- **Google Docs editing**: `_doc_insert_text` + `append_doc` properly calls `batchUpdate insertText`; `garc drive append-doc <doc_id> --content` added
- **KG improvements**: Drive file listing pagination fixed; shell injection in `kg.sh` eliminated; `garc-kg-query.py` extracted as a proper CLI tool

### Added (P3 — Roadmap)

- **Multi-tenant profiles**: `lib/profile.sh` — `garc profile list/use/add/show/remove/current`; `bin/garc` auto-loads `~/.garc/profiles/<name>/config.env` and token when `GARC_PROFILE` is set
- **Google Forms pipeline**: `garc-forms-helper.py` + `lib/forms.sh` — `garc forms list/responses/watch`; polls Forms for new responses and enqueues them via `garc ingress`
- **Linux systemd support**: `_daemon_install_service` detects OS (Darwin → launchd plist, Linux → `.service` + `.timer` units); `--system` flag for system-wide install
- **Python version gate**: `pyproject.toml` (`python_requires = ">=3.10,<3.13"`); startup check in `bin/garc`; `garc doctor` diagnostics command

---

## Unreleased

### Added

- **Google Forms draft CRUD**: `garc forms get`, `garc forms create` (unpublished draft via `forms.create?unpublished=true`), `garc forms update` (title, description, items through `forms.batchUpdate`). These commands never call `forms.setPublishSettings`.
- **Human-GO publish**: `garc forms publish <id> --go` is the only path that changes `publishState` (`isPublished` / `isAcceptingResponses`). Without `--go` the command exits 2 and does not call the API. `--confirm` is not a substitute. Documented as a human-GO-only operation.
- **Forms scopes and enablement**: `forms.body`, `forms.body.readonly`, and `forms.responses.readonly` on the scope map, gate policy (`publish_form` = approval), and runtime scope lists. `garc setup check`, `garc status`, and `garc bootstrap` probe Forms API enablement (`forms.googleapis.com`).
- **Docs paragraph insert**: `garc drive insert-doc` inserts a paragraph after a heading, at a body index, or at the end via `documents.batchUpdate` `insertText`. End-of-body raw append remains `garc drive append-doc` (already present).

### v0.3 — Stability (planned)
- GCP Secret Manager integration for credential management
- Agent-to-agent approval chains
- `garc kg` — Sheets-backed persistent index (vs local JSON cache)
- GitHub Actions CI matrix (Python 3.10 / 3.11 / 3.12)
