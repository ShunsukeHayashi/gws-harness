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

## Unreleased

### v0.2 — Enterprise hardening (planned)
- Google Chat API (`garc chat send`)
- Service Account + Domain-wide Delegation (`garc auth login --service-account`)
- Audit log (`garc audit log`)
- `garc auth revoke`

### v0.3 — Workflow expansion (planned)
- Google Docs body editing
- Google Forms → ingress pipeline
- Linux systemd daemon support
- GCP Secret Manager integration

### v0.4 — Multi-agent (planned)
- Cross-agent task delegation
- Agent-to-agent approval chains
- Multi-organization support
