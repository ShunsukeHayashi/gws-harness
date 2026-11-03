---
name: garc-runtime
version: 0.1.0
description: GARC — Google Workspace Agent Runtime. Use when performing office-work tasks on Gmail, Google Drive, Sheets, Calendar, or Tasks through the GARC CLI.
---

# GARC Runtime Skill

## When to use this skill

Use GARC when the user asks you to:
- Send emails, search Gmail, read emails
- Create or update Google Calendar events, check availability
- Read/write Google Drive files, upload/download, create docs
- Read/write Google Sheets data
- Manage Google Tasks
- Check OAuth scope requirements for a GWS task
- Manage the agent memory/context
- Register or manage agents

## Pre-flight checklist

Before any GARC operation:

1. **Check config**
   ```bash
   garc status
   ```
   All items must be ✅. If not, guide through `garc setup all`.

2. **Infer scopes** (for new task types)
   ```bash
   garc auth suggest "<task description>"
   ```
   Note the gate level. Act accordingly.

3. **Check execution gate**
   - `none` → proceed immediately
   - `preview` → show user what will happen, confirm before executing
   - `approval` → create approval request, wait for human approval

---

## Gmail Operations

### Send email
```bash
garc gmail send \
  --to recipient@example.com \
  --subject "Subject here" \
  --body "Body text here" \
  [--cc cc@example.com] \
  [--html]   # for HTML body
```

Gate: **preview** — Always confirm recipient and content with user before sending.

### Search emails
```bash
garc gmail search "from:alice@co.com subject:invoice" --max 10
garc gmail search "after:2026/04/01 has:attachment" --body
```

Gate: **none**

### Read email
```bash
garc gmail read <message_id>
```

### Inbox
```bash
garc gmail inbox --unread --max 20
```

### Draft
```bash
garc gmail draft --to someone@co.com --subject "Draft title" --body "..."
```

---

## Google Calendar Operations

### List events
```bash
garc calendar today               # Today's events
garc calendar week                # This week
garc calendar list --days 14      # Next 14 days
garc calendar list --query "Standup"  # Filter by keyword
```

Gate: **none**

### Create event
```bash
garc calendar create \
  --summary "Team Meeting" \
  --start "2026-04-16T14:00:00" \
  --end "2026-04-16T15:00:00" \
  --description "Weekly sync" \
  --location "Google Meet" \
  --attendees alice@co.com bob@co.com \
  --timezone "Asia/Tokyo"
```

Gate: **preview** — Show user the event details before creating.

### Check free/busy
```bash
garc calendar freebusy \
  --start 2026-04-16 \
  --end 2026-04-17 \
  --emails alice@co.com bob@co.com
```

Gate: **none**

### Quick add (natural language)
```bash
garc calendar quick-add "Lunch with Alice tomorrow at 12:30pm"
```

Gate: **preview**

---

## Google Drive Operations

### List/search
```bash
garc drive list --folder-id 1xxxxx
garc drive search "Q1 report" --type doc
garc drive info <file_id>
```

Gate: **none**

### Download
```bash
garc drive download --file-id 1xxxxx --output ./local_file.txt
garc drive download --folder-id 1xxxxx --filename "SOUL.md" --output ~/.garc/SOUL.md
```

Gate: **none**

### Upload
```bash
garc drive upload ./report.pdf --folder-id 1xxxxx
garc drive upload ./data.csv --folder-id 1xxxxx --convert  # Convert to Google Sheet
```

Gate: **preview**

### Create document / folder
```bash
garc drive create-doc "Meeting Notes 2026-04-15" --folder-id 1xxxxx
garc drive create-folder "Project Alpha" --parent-id 1xxxxx
```

Gate: **preview**

### Append or insert into an existing Doc

```bash
garc drive append-doc <doc_id> --content "追記"
garc drive insert-doc <doc_id> --content "正本: https://docs.google.com/document/d/abc" --after-heading "手順"
garc drive insert-doc <doc_id> --content "末尾の段落" --at end
garc drive insert-doc <doc_id> --content "途中" --index 10
```

Uses Docs API `documents.batchUpdate` `insertText`. Gate: **preview** (`update_document`).

### Share
```bash
garc drive share 1xxxxx --email colleague@co.com --role writer
```

Gate: **approval** (sharing = external visibility)

---

## Google Forms

### Read
```bash
garc forms get <form_id>
```

Gate: **none**

### Create an unpublished draft
```bash
garc forms create --title "SOP check" --description "Draft"
```

Gate: **preview**. This calls `forms.create` with `unpublished=true`. It does not publish the form and does not call `setPublishSettings`.

### Update title, description, or items
```bash
garc forms update <form_id> --title "SOP check" --description "Updated" --add-item "Owner"
garc forms update <form_id> --item-index 0 --item-title "Amount"
```

Gate: **preview**. Does not change publish state or responder access.

### Publish or change responder access — human GO only

```bash
garc forms publish <form_id>                 # REFUSES (exit 2). No API call.
garc forms publish <form_id> --go            # only after an explicit human GO
garc forms publish <form_id> --go --published true --accepting false
```

Gate: **approval**. Publishing, unpublishing, and changing whether the form accepts responses are **human-GO-only**. Do not pass `--go` yourself. `--confirm` is not a substitute. `forms.list` / `forms.responses` / `forms.watch` are unchanged and do not publish the form.

Required API: `forms.googleapis.com` (reported by `garc status` and `garc bootstrap` when a token is present).

---

## Google Sheets Operations

### Read data
```bash
garc sheets info                              # Show all tabs and dimensions
garc sheets read --range "memory!A:E"
garc sheets read --range "agents!A:H" --format json
garc sheets search --sheet memory --query "expense"
```

Gate: **none**

### Write data
```bash
garc sheets append --sheet memory --values '["main","2026-04-15T10:00:00Z","key decision: use GARC","manual",""]'
garc sheets write --range "agents!A2:F2" --values '[["crm-agent","claude-sonnet-4-6","...","CRM agent","writer","active"]]'
```

Gate: **preview**

---

## Memory Operations

```bash
garc memory pull             # Sync Sheets → local
garc memory push "important context: ..."
garc memory search "client A"
```

---

## Task Operations

```bash
garc task list
garc task list --completed --format json
garc task create "Write Q1 report" --due 2026-04-30 --notes "Include section on revenue"
garc task update <task_id> --due 2026-05-01
garc task done <task_id>
garc task delete <task_id>
garc task clear-completed
garc task tasklists          # List all task lists
```

Gate: **preview** for create/update/delete — confirm with user before modifying tasks.

---

## People & Contacts

```bash
garc people search "Alice"              # Search personal contacts
garc people directory "engineering"     # Search org directory (GWS)
garc people lookup "Bob Smith"          # Quick name → email lookup
garc people list --max 50              # List all contacts
garc people show <contact_id>
garc people create --name "Jane Doe" --email jane@co.com --company "Acme"
garc people update <contact_id> --title "Senior Manager"
```

Gate: **none** for search/read, **preview** for create/update, **approval** for delete.

---

## Agent Management

```bash
garc agent list              # Show registered agents
garc agent register          # Register from agents.yaml
garc agent show main         # Show specific agent details
```

---

## Scope & Gate Reference

| Operation | Gate | Scopes needed |
|-----------|------|--------------|
| Read email | none | gmail.readonly |
| Send email | preview | gmail.send |
| Delete email | approval | gmail.modify |
| Read calendar | none | calendar.readonly |
| Create event | preview | calendar |
| Delete event | approval | calendar |
| Read Drive | none | drive.readonly |
| Upload to Drive | preview | drive.file |
| Append / insert Doc text | preview | documents + drive.file |
| Read a Form | none | forms.body.readonly |
| Create / update a Form draft | preview | forms.body |
| Publish a Form or change responder access | approval (human `--go` only) | forms.body |
| Read Form responses | none | forms.responses.readonly |
| Delete/share Drive | approval | drive |
| Read Sheets | none | spreadsheets.readonly |
| Write Sheets | preview | spreadsheets |
| Read Tasks | none | tasks.readonly |
| Create/update Tasks | preview | tasks |
| Delete Tasks | approval | tasks |
| Read Contacts | none | contacts.readonly |
| Create/update Contacts | preview | contacts |
| Delete Contacts | approval | contacts |
| Search Directory | none | directory.readonly |
| Create expense | approval | spreadsheets + drive.file + gmail.send |

---

## Error patterns

| Error | Action |
|-------|--------|
| `credentials.json not found` | Guide user to Google Cloud Console |
| `Token refresh failed` | Run `garc auth login --profile backoffice_agent` |
| `403 insufficientPermissions` | Run `garc auth suggest "<task>"` to identify missing scopes, then re-login |
| `API not enabled` | Tell user to enable the specific API in Google Cloud Console |
| `Sheets tab missing` | Run `garc setup sheets` |
| Rate limit (429) | Wait and retry (garc has built-in retry with backoff) |
