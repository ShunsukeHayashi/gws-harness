# GWS Harness — Google Workspace Harness

> The business operations harness for AI agents — built on Google Workspace.

GWS Harness lets Claude Code (or any LLM agent) send emails, manage calendars, read Drive files, write Sheets, and manage tasks — with built-in **execution gates** that prevent accidental or unauthorized actions.

```
You / Claude Code
      ↓
   GWS Harness       ← permission check, queue, context
      ↓
Google Workspace APIs (Gmail · Calendar · Drive · Sheets · Tasks · People)
```

> **Current release: v0.2.0.** All 17 operational readiness findings resolved.
> See [CHANGELOG](CHANGELOG.md) for full details. Known limitations and planned improvements are listed in [Known Limitations](#known-limitations) below.

---

## Prerequisites

> **Complete all steps below before running any `garc` command.**
> Skipping any step will result in authentication or API errors.

### 1. Google Account

A Google account with **Gmail, Drive, Sheets, Calendar, and Tasks** active.
- Personal Gmail accounts work for development and testing.
- Google Workspace (business) accounts work and are the primary target use case.

### 2. Python 3.10+

```bash
python3 --version   # must be 3.10 or higher
```

### 3. Google Cloud Project with APIs enabled

You need a Google Cloud project with the following APIs enabled:

| API | Service name | Used for |
|-----|-------------|----------|
| Google Drive API | `drive.googleapis.com` | File storage, disclosure chain |
| Google Sheets API | `sheets.googleapis.com` | Memory, queue, agent registry |
| Gmail API | `gmail.googleapis.com` | Email send/receive/search |
| Google Calendar API | `calendar-json.googleapis.com` | Event management |
| Google Tasks API | `tasks.googleapis.com` | Task management |
| Google Docs API | `docs.googleapis.com` | Document creation |
| Google People API | `people.googleapis.com` | Contacts, directory search |

Step-by-step setup: [`docs/google-cloud-setup.md`](docs/google-cloud-setup.md)

### 4. OAuth 2.0 Credentials file

1. In [Google Cloud Console](https://console.cloud.google.com/) → **Credentials** → **Create OAuth 2.0 Client ID**
2. Application type: **Desktop app**
3. Download JSON → save as **`~/.garc/credentials.json`**

```bash
mkdir -p ~/.garc
mv ~/Downloads/client_secret_*.json ~/.garc/credentials.json
```

> Without `~/.garc/credentials.json`, all `garc` commands will fail with
> `FileNotFoundError: credentials.json not found`.

---

## Quickstart

### 1. Install

```bash
git clone https://github.com/<owner>/garc-gws-agent-runtime ~/study/garc-gws-agent-runtime
cd ~/study/garc-gws-agent-runtime
pip3 install -r requirements.txt
echo 'export PATH="$HOME/study/garc-gws-agent-runtime/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
garc --version   # → garc 0.1.0
```

### 2. Authenticate

```bash
garc auth login --profile backoffice_agent
# Opens browser → Google login → authorize all scopes
# Writes ~/.garc/token.json
garc auth status
```

### 3. Provision workspace

```bash
garc setup all
# Creates GARC Workspace folder in Google Drive
# Creates Google Sheets with all tabs (memory/agents/queue/heartbeat/approval)
# Uploads disclosure chain templates (SOUL.md / USER.md / MEMORY.md / RULES.md)
# Writes folder/sheet IDs to ~/.garc/config.env
```

### 4. Verify

```bash
garc status
garc bootstrap --agent main
```

---

## Usage

### Gmail

```bash
garc gmail inbox --unread
garc gmail search "from:alice@co.com subject:invoice" --max 10
garc gmail send --to boss@co.com --subject "Weekly report" --body "..."
garc gmail read <message_id>
garc gmail draft --to boss@co.com --subject "Draft" --body "..."
```

### Google Calendar

```bash
garc calendar today
garc calendar week
garc calendar create --summary "Team meeting" \
  --start "2026-04-20T14:00:00" --end "2026-04-20T15:00:00" \
  --attendees alice@co.com bob@co.com --timezone "Asia/Tokyo"
garc calendar freebusy --start 2026-04-20 --end 2026-04-21 --emails alice@co.com
```

### Google Drive

```bash
garc drive list
garc drive search "Q1 report" --type doc
garc drive upload ./report.pdf
garc drive create-doc "Meeting Notes 2026-04-20"
garc drive download --file-id 1xxxxx --output ./local.txt
```

### Google Sheets

```bash
garc sheets info
garc sheets read --range "memory!A:E" --format json
garc sheets append --sheet memory --values '["main","2026-04-20","key decision","manual",""]'
```

### Tasks & Contacts

```bash
garc task list
garc task create "Write Q1 report" --due 2026-04-30
garc task done <task_id>
garc people lookup "Alice Smith"
garc people directory "engineering"
```

### Memory sync

```bash
garc memory pull              # Download from Google Sheets
garc memory push "note text"  # Append to memory tab
garc memory search "keyword"
```

### Queue / Ingress (Claude Code bridge)

```bash
# Enqueue a task
garc ingress enqueue --text "Send weekly report to manager@co.com"

# Show queue
garc ingress list

# Output a Claude-readable execution prompt → Claude Code acts on this
garc ingress run-once

# Mark complete
garc ingress done --queue-id abc12345 --note "Report sent"
```

### Daemon — auto-enqueue from Gmail

```bash
garc daemon start --interval 60    # poll every 60s
garc daemon status
garc daemon stop
garc daemon install                 # install as macOS launchd service
```

### Scope & gate inference

```bash
garc auth suggest "create expense report and send to manager for approval"
# → gate: approval  scopes: spreadsheets + drive.file + gmail.send

garc approve gate create_expense
garc approve list
garc approve act <id> --action approve
```

---

## Architecture

```
~/.garc/
  credentials.json      # OAuth client credentials (Google Cloud Console) ← YOU PROVIDE THIS
  token.json            # OAuth user token (garc auth login generates this)
  config.env            # GARC_DRIVE_FOLDER_ID, GARC_SHEETS_ID, … (garc setup all generates this)
  cache/
    workspace/<agent>/
      SOUL.md / USER.md / MEMORY.md / RULES.md / HEARTBEAT.md
      AGENT_CONTEXT.md   # consolidated bootstrap context
    queue/               # JSONL queue files
    daemon/              # PID files
    logs/                # daemon logs
```

### Execution gates

| Gate | Risk | Behaviour |
|------|------|-----------|
| `none` | Low — reads | Execute immediately |
| `preview` | Medium — external writes | Show plan, confirm first |
| `approval` | High — financial / irreversible | Create approval request, block until approved |

---

## Known Limitations

The following are known gaps in v0.1.0. They are planned for future releases.

| Limitation | Impact | Planned |
|-----------|--------|---------|
| **Google Chat not implemented** | No push notifications to Chat spaces. Gmail is used as fallback for approval notifications | v0.2 |
| **Service Account / Domain-wide Delegation not supported** | Enterprise deployments requiring headless bot identity (not user OAuth) are not yet supported | v0.2 |
| **No audit log** | Operations are not logged to Admin SDK / Google Cloud Logging | v0.2 |
| **`garc auth revoke` not implemented** | Token revocation requires manual deletion of `~/.garc/token.json` | v0.2 |
| **Existing Google Docs editing limited** | `drive create-doc` creates new docs; editing body of existing Docs is not implemented | v0.3 |
| **Google Forms → auto-enqueue not implemented** | Form submissions cannot automatically create queue tasks | v0.3 |
| **Single organization only** | Multi-tenant (multiple Google Workspace domains) is not supported | v0.3+ |
| **macOS only (daemon)** | `daemon install` generates a macOS launchd plist. Linux systemd not yet supported | v0.3 |

---

## Roadmap

### v0.2 — Enterprise hardening
- Google Chat API integration (`garc chat send`)
- Service Account support (`garc auth login --service-account`)
- Audit log (`garc audit log`)
- `garc auth revoke`

### v0.3 — Workflow expansion
- Google Docs body editing
- Google Forms → ingress pipeline
- Linux systemd daemon support
- GCP Secret Manager for credentials

### v0.4 — Multi-agent
- Cross-agent task delegation
- Agent-to-agent approval chains
- Multi-organization support

---

## Repository layout

```
bin/garc                    CLI entrypoint
lib/
  bootstrap.sh              disclosure chain
  gmail.sh / calendar.sh / drive.sh / sheets.sh / task.sh / people.sh
  memory.sh / ingress.sh / daemon.sh / agent.sh / approve.sh
  auth.sh / heartbeat.sh / kg.sh
scripts/
  garc-core.py              shared auth, retry, utilities
  garc-ingress-helper.py    task inference + Claude prompt builder
  garc-gmail-helper.py / garc-calendar-helper.py / garc-drive-helper.py
  garc-sheets-helper.py / garc-tasks-helper.py / garc-people-helper.py
  garc-auth-helper.py       OAuth scope inference engine
  garc-setup.py             workspace provisioner
config/
  scope-map.json            42 task types × OAuth scopes × keyword patterns
  gate-policy.json          gate assignments
  config.env.example
agents.yaml                 agent declarations
docs/
  quickstart.md / google-cloud-setup.md / garc-architecture.md / garc-vs-larc.md
.claude/skills/garc-runtime/SKILL.md   Claude Code skill
```

---

## Relation to LARC

GARC mirrors [LARC](https://github.com/miyabi-lab/larc-openclaw-coding-agent) — the same governance model running on Google Workspace instead of Lark/Feishu.

| LARC (Lark) | GARC (Google Workspace) |
|-------------|------------------------|
| Lark Drive | Google Drive |
| Lark Base | Google Sheets |
| Lark IM / Mail | Gmail |
| Lark Approval | Sheets-based approval flow |
| Lark Calendar | Google Calendar |
| Lark Task | Google Tasks |
| `lark-cli` | Google APIs (Python) |
| OpenClaw agent | Claude Code |

## License

MIT
