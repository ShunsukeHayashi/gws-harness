# GWS API Command Alignment

This document maps LARC's lark-cli commands to GARC's equivalent Google API calls.

## Drive / File Storage

| Operation | LARC (lark-cli) | GARC (garc-drive-helper.py) |
|-----------|----------------|------------------------------|
| List folder | `drive files list --params '{"folder_token":"..."}'` | `files().list(q="'{id}' in parents")` |
| Download file | `drive +download --file-token` | `files().get_media(fileId=...)` |
| Create folder | `drive files create_folder --data '...'` | `files().create(body={mimeType:'application/vnd.google-apps.folder'})` |
| Upload file | `drive files upload` | `files().create(media_body=MediaFileUpload(...))` |
| Export Doc | (n/a, native format) | `files().export_media(fileId=..., mimeType='text/plain')` |
| Append text to a Doc | (n/a) | `documents().batchUpdate` `insertText` at end index − 1 (`garc drive append-doc`) |
| Insert a paragraph | (n/a) | `documents().batchUpdate` `insertText` after a heading, at an index, or at the end (`garc drive insert-doc`) |

## Structured Data

| Operation | LARC (Lark Base) | GARC (Google Sheets) |
|-----------|-----------------|----------------------|
| List records | `base +record-list --base-token` | `values().get(spreadsheetId=..., range='Sheet!A:Z')` |
| Create record | `base +record-upsert --base-token` | `values().append(spreadsheetId=..., range=..., body=...)` |
| Update record | `base +record-upsert --base-token` | `values().update(spreadsheetId=..., range=..., body=...)` |
| Search records | (filter in Base) | Python-side filter after `values().get()` |

## Messaging

| Operation | LARC (Lark IM) | GARC (Gmail) |
|-----------|---------------|--------------|
| Send message | `lark-cli im send --chat-id` | `messages().send(userId='me', body={raw:...})` |
| Read messages | `lark-cli im list` | `messages().list(userId='me', q='...')` |
| Send to space | (IM chat) | Google Chat API: `spaces.messages().create(parent=..., body=...)` |

## Calendar

| Operation | LARC (Lark Calendar) | GARC (Google Calendar) |
|-----------|---------------------|------------------------|
| List events | `lark-cli calendar +list` | `events().list(calendarId='primary', timeMin=..., timeMax=...)` |
| Create event | `lark-cli calendar +create` | `events().insert(calendarId='primary', body=...)` |
| Update event | `lark-cli calendar +update` | `events().update(calendarId='primary', eventId=..., body=...)` |

## Tasks

| Operation | LARC (Lark Project) | GARC (Google Tasks) |
|-----------|---------------------|---------------------|
| List tasks | `task +get-my-tasks` | `tasks().list(tasklist='@default')` |
| Create task | `task +create` | `tasks().insert(tasklist='@default', body=...)` |
| Complete task | `task +complete` | `tasks().patch(tasklist=..., task=..., body={status:'completed'})` |

## Forms

| Operation | GARC | Google API |
|-----------|------|------------|
| Read title / description / items | `garc forms get <id>` | `forms().get(formId=...)` |
| Create unpublished draft | `garc forms create --title ...` | `forms().create(body=..., unpublished=true)` — does **not** call `setPublishSettings` |
| Update title, description, items | `garc forms update <id> ...` | `forms().batchUpdate` `updateFormInfo` / `updateItem` / `createItem` |
| Publish or change responder access | `garc forms publish <id> --go` | `forms().setPublishSettings` `publishState` (`isPublished`, `isAcceptingResponses`) |

**Human GO only.** `garc forms publish` without `--go` exits 2 and does not call the API. `--confirm` is not a substitute. Do not pass `--go` unless a human explicitly approved publishing or a responder-access change. Creating or updating a form never publishes it.

## OAuth Scope Reference

### Minimal Scopes by Operation Type

| Operations | Scope |
|-----------|-------|
| Read any Drive file | `drive.readonly` |
| Read/write owned Drive files | `drive.file` |
| Full Drive access | `drive` |
| Read Google Docs | `drive.readonly` + `documents.readonly` |
| Edit Google Docs | `drive.file` + `documents` |
| Read Sheets | `spreadsheets.readonly` |
| Write Sheets | `spreadsheets` |
| Send Gmail | `gmail.send` |
| Read Gmail | `gmail.readonly` |
| Full Gmail | `gmail.modify` |
| Read Calendar | `calendar.readonly` |
| Write Calendar | `calendar` |
| Read Tasks | `tasks.readonly` |
| Write Tasks | `tasks` |
| Read Contacts | `contacts.readonly` |
| Write Contacts | `contacts` |
| Google Chat (bot) | `chat.messages` |
| Read a Form | `forms.body.readonly` |
| Create or edit a Form (draft) | `forms.body` |
| Publish a Form / responder access (human `--go` only) | `forms.body` |
| Read Form responses | `forms.responses.readonly` |

All Google OAuth scopes are prefixed with `https://www.googleapis.com/auth/`.

## API Quotas and Rate Limits

| API | Default Quota | Notes |
|-----|---------------|-------|
| Google Drive | 1,000 req/100s/user | File operations |
| Google Sheets | 300 req/min/project | Read: use batch |
| Gmail | 250 quota units/user/second | Send = 100 units |
| Google Calendar | 1,000,000 req/day | |
| Google Tasks | 50,000 req/day | |
| Google Forms | project quota in Cloud Console | Create stays unpublished unless a human passes `--go` |

GARC implements basic retry with exponential backoff via `google-api-python-client`'s built-in retry mechanism.
