#!/usr/bin/env python3
"""
GARC Setup — Interactive workspace provisioner
- Creates Google Drive folder structure
- Provisions Google Sheets with all required tabs and headers
- Uploads initial disclosure chain templates to Drive
- Validates all APIs are accessible
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add scripts dir to path for garc-core
sys.path.insert(0, str(Path(__file__).parent))
from garc_core import build_service, load_config, utc_now, GARC_CONFIG_DIR

# Sheet definitions: tab name → headers
SHEET_TABS = {
    "memory": ["agent_id", "timestamp", "entry", "source", "tags"],
    "agents": ["id", "model", "scopes", "description", "profile", "status", "drive_folder", "registered_at"],
    "queue": ["queue_id", "agent_id", "message", "status", "gate", "source", "created_at", "updated_at", "assigned_to"],
    "heartbeat": ["agent_id", "timestamp", "status", "notes", "platform", "context_file"],
    "approval": ["approval_id", "agent_id", "task", "status", "created_at", "resolved_at", "resolver", "notes"],
    "tasks_log": ["task_id", "agent_id", "title", "google_task_id", "status", "created_at", "completed_at"],
    "email_log": ["msg_id", "agent_id", "to", "subject", "sent_at", "thread_id"],
    "calendar_log": ["event_id", "agent_id", "title", "start", "end", "created_at"],
}

# Disclosure chain templates
DISCLOSURE_TEMPLATES = {
    "SOUL.md": """# SOUL — Agent Identity

agent_id: main
platform: Google Workspace
runtime: GARC v0.1.0
created: {timestamp}

## Core Principles

1. **Permission-first**: Always run `garc auth suggest` before a new task category.
2. **Minimum viable scopes**: Request only what is needed.
3. **Gate compliance**: Respect none / preview / approval execution gates.
4. **Transparency**: Explain actions before executing them.
5. **Reversibility preference**: Prefer reversible operations; flag irreversible ones.

## Identity

This agent operates within Google Workspace on behalf of the registered user.
It has access to Drive, Sheets, Gmail, Calendar, and Tasks as configured.

## Persona

Helpful, precise, audit-minded. Acts as a trusted digital colleague.
""",

    "USER.md": """# USER — User Profile

## Identity

name: (your name)
email: (your Gmail)
timezone: Asia/Tokyo
language: Japanese / English

## Work Context

role: (your role)
organization: (your organization)
primary_tools: [Gmail, Google Drive, Google Sheets, Google Calendar]

## Preferences

- Communication style: direct, structured
- Approval threshold: always confirm before sending external emails
- Memory: persist important decisions and context
- Calendar: treat work hours as 09:00-18:00 JST

## Created

{timestamp} — edit this file in Google Drive to customize.
""",

    "MEMORY.md": """# MEMORY — Long-term Memory Index

Last sync: {timestamp}
Backend: Google Sheets (configured in ~/.garc/config.env)

## How to use

- Pull latest: `garc memory pull`
- Add entry:   `garc memory push "key decision: ..."`
- Search:      `garc memory search "keyword"`
- View raw:    Google Sheets → memory tab

## Recent context

(populated by `garc memory pull`)
""",

    "RULES.md": """# RULES — Operating Rules

## Execution Rules

1. Always check execution gate before any write operation
   - `garc approve gate <task_type>`
2. For `preview` gate: show preview, ask for confirmation
3. For `approval` gate: create approval request, wait for human
4. Never send email without explicit confirmation unless gate is `none`
5. Never delete files or calendar events without `approval` gate clearance

## Memory Rules

1. After any significant decision, push to memory
   - `garc memory push "decided: ..."`
2. Pull memory at session start for context
   - `garc memory pull`
3. Heartbeat at session end
   - `garc heartbeat`

## Communication Rules

1. Default reply-to: use GARC_GMAIL_DEFAULT_TO for notifications
2. Subject prefix for agent emails: `[GARC]`
3. CC user on all outbound approvals

## Safety Rules

1. Max 50 emails/hour limit (self-imposed)
2. Max 100 Drive file operations/hour
3. Never modify shared Drives without explicit instruction
4. Always confirm before recurring calendar events
""",

    "HEARTBEAT.md": """# HEARTBEAT — System State

agent_id: main
last_bootstrap: {timestamp}
status: initialized
platform: Google Workspace

## Latest State

(updated by `garc heartbeat`)
""",
}


# A non-existent form id is enough to tell "API enabled" (404) from
# "API disabled" (accessNotConfigured). No form is created.
FORMS_PROBE_ID = "garc-api-probe"


def probe_forms_api(svc) -> str:
    """Return a status string for Forms API enablement. Never publishes a form."""
    try:
        svc.forms().get(formId=FORMS_PROBE_ID).execute()
        return "✅"
    except Exception as exc:
        msg = str(exc)
        low = msg.lower()
        disabled = (
            "accessnotconfigured" in low
            or "has not been used" in low
            or "it is disabled" in low
            or "service_disabled" in low
        )
        if disabled:
            return f"❌ {msg[:80]}"
        if "404" in low or "not found" in low or "400" in low:
            return "✅"
        return f"❌ {msg[:80]}"


def check_api_access(config: dict) -> dict:
    """Verify all required APIs are accessible."""
    results = {}

    print("\n🔍 Checking API access...")

    # Drive
    try:
        svc = build_service("drive", "v3")
        svc.about().get(fields="user").execute()
        results["Drive API"] = "✅"
    except Exception as e:
        results["Drive API"] = f"❌ {str(e)[:60]}"

    # Sheets
    try:
        svc = build_service("sheets", "v4")
        results["Sheets API"] = "✅"
    except Exception as e:
        results["Sheets API"] = f"❌ {str(e)[:60]}"

    # Gmail
    try:
        svc = build_service("gmail", "v1")
        svc.users().getProfile(userId="me").execute()
        results["Gmail API"] = "✅"
    except Exception as e:
        results["Gmail API"] = f"❌ {str(e)[:60]}"

    # Calendar
    try:
        svc = build_service("calendar", "v3")
        svc.calendarList().list(maxResults=1).execute()
        results["Calendar API"] = "✅"
    except Exception as e:
        results["Calendar API"] = f"❌ {str(e)[:60]}"

    # Tasks
    try:
        svc = build_service("tasks", "v1")
        svc.tasklists().list(maxResults=1).execute()
        results["Tasks API"] = "✅"
    except Exception as e:
        results["Tasks API"] = f"❌ {str(e)[:60]}"

    # Docs
    try:
        svc = build_service("docs", "v1")
        results["Docs API"] = "✅"
    except Exception as e:
        results["Docs API"] = f"❌ {str(e)[:60]}"

    # People
    try:
        svc = build_service("people", "v1", scopes=["https://www.googleapis.com/auth/contacts.readonly"])
        svc.people().connections().list(
            resourceName="people/me",
            personFields="names",
            pageSize=1,
        ).execute()
        results["People API"] = "✅"
    except Exception as e:
        results["People API"] = f"❌ {str(e)[:60]}"

    # Forms — enable forms.googleapis.com. 404 on the probe id means the API answered.
    print("  Forms API service: forms.googleapis.com")
    try:
        svc = build_service(
            "forms",
            "v1",
            scopes=["https://www.googleapis.com/auth/forms.body.readonly"],
        )
        results["Forms API"] = probe_forms_api(svc)
    except Exception as e:
        results["Forms API"] = f"❌ {str(e)[:60]}"

    for api, status in results.items():
        print(f"  {status} {api}")

    return results


def provision_sheets(config: dict) -> str:
    """Create or update Google Sheets with all required tabs."""
    sheets_id = config.get("GARC_SHEETS_ID", "")
    svc = build_service("sheets", "v4")

    if sheets_id:
        print(f"\n📊 Using existing Sheets: {sheets_id}")
        # Get existing sheet info
        try:
            meta = svc.spreadsheets().get(spreadsheetId=sheets_id).execute()
            existing_tabs = {s["properties"]["title"] for s in meta.get("sheets", [])}
            print(f"   Existing tabs: {', '.join(existing_tabs)}")
        except Exception as e:
            print(f"❌ Cannot access Sheets {sheets_id}: {e}")
            sheets_id = ""

    if not sheets_id:
        print("\n📊 Creating new Google Sheets for GARC...")
        result = svc.spreadsheets().create(body={
            "properties": {"title": "GARC Workspace Data"},
            "sheets": [{"properties": {"title": tab}} for tab in SHEET_TABS.keys()]
        }).execute()
        sheets_id = result["spreadsheetId"]
        existing_tabs = set(SHEET_TABS.keys())
        print(f"   ✅ Created: https://docs.google.com/spreadsheets/d/{sheets_id}")
    else:
        existing_tabs = existing_tabs  # from above

    # Add missing tabs
    meta = svc.spreadsheets().get(spreadsheetId=sheets_id).execute()
    existing_tab_names = {s["properties"]["title"] for s in meta.get("sheets", [])}

    add_requests = []
    for tab_name in SHEET_TABS:
        if tab_name not in existing_tab_names:
            add_requests.append({
                "addSheet": {"properties": {"title": tab_name}}
            })

    if add_requests:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sheets_id,
            body={"requests": add_requests}
        ).execute()
        print(f"   ✅ Added tabs: {[r['addSheet']['properties']['title'] for r in add_requests]}")

    # Write headers to each tab
    batch_data = []
    for tab_name, headers in SHEET_TABS.items():
        batch_data.append({
            "range": f"{tab_name}!A1:{chr(65 + len(headers) - 1)}1",
            "values": [headers]
        })

    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=sheets_id,
        body={
            "valueInputOption": "RAW",
            "data": batch_data
        }
    ).execute()
    print(f"   ✅ Headers written to all {len(SHEET_TABS)} tabs")

    # Bold the header row in each sheet (formatting)
    meta = svc.spreadsheets().get(spreadsheetId=sheets_id).execute()
    sheet_id_map = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta.get("sheets", [])}

    format_requests = []
    for tab_name in SHEET_TABS:
        sid = sheet_id_map.get(tab_name)
        if sid is not None:
            format_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
                    "fields": "userEnteredFormat(textFormat,backgroundColor)"
                }
            })
            # Freeze header row
            format_requests.append({
                "updateSheetProperties": {
                    "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount"
                }
            })

    if format_requests:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sheets_id,
            body={"requests": format_requests}
        ).execute()
        print("   ✅ Headers formatted (bold + freeze)")

    return sheets_id


def provision_drive(config: dict) -> str:
    """Create Drive folder structure for agent workspace."""
    folder_id = config.get("GARC_DRIVE_FOLDER_ID", "")
    svc = build_service("drive", "v3")

    if folder_id:
        print(f"\n📁 Using existing Drive folder: {folder_id}")
        try:
            meta = svc.files().get(fileId=folder_id, fields="id,name").execute()
            print(f"   Folder: {meta['name']}")
        except Exception:
            print(f"⚠️  Folder not accessible, creating new one...")
            folder_id = ""

    if not folder_id:
        print("\n📁 Creating GARC Drive folder...")
        result = svc.files().create(body={
            "name": "GARC Workspace",
            "mimeType": "application/vnd.google-apps.folder"
        }, fields="id,name").execute()
        folder_id = result["id"]
        print(f"   ✅ Created folder: {result['name']} ({folder_id})")

    # Create memory subfolder
    memory_query = f"'{folder_id}' in parents and name='memory' and mimeType='application/vnd.google-apps.folder'"
    existing = svc.files().list(q=memory_query, fields="files(id,name)").execute()
    if not existing.get("files"):
        svc.files().create(body={
            "name": "memory",
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [folder_id]
        }).execute()
        print("   ✅ Created memory/ subfolder")

    return folder_id


def upload_disclosure_chain(folder_id: str):
    """Upload disclosure chain template files to Google Drive."""
    svc = build_service("drive", "v3")
    ts = utc_now()

    print("\n📝 Uploading disclosure chain templates...")

    for filename, template in DISCLOSURE_TEMPLATES.items():
        content = template.replace("{timestamp}", ts).encode("utf-8")

        # Check if file exists
        query = f"'{folder_id}' in parents and name='{filename}' and trashed=false"
        existing = svc.files().list(q=query, fields="files(id,name)").execute()

        if existing.get("files"):
            # Skip if already exists (don't overwrite user's customized files)
            print(f"   ⏭️  {filename} (already exists, skipping)")
            continue

        from googleapiclient.http import MediaIoBaseUpload
        import io

        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="text/plain")
        svc.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id,name"
        ).execute()
        print(f"   ✅ {filename}")


def save_config(config_updates: dict):
    """Save updated config values to ~/.garc/config.env."""
    config_file = GARC_CONFIG_DIR / "config.env"
    GARC_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Read existing
    existing = {}
    if config_file.exists():
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()

    existing.update(config_updates)

    # Write back
    template_file = Path(__file__).parent.parent / "config" / "config.env.example"
    if template_file.exists():
        with open(template_file) as f:
            template_lines = f.readlines()

        out_lines = []
        written_keys = set()
        for line in template_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=")[0].strip()
                if key in existing:
                    out_lines.append(f"{key}={existing[key]}\n")
                    written_keys.add(key)
                    continue
            out_lines.append(line)

        # Add any extra keys not in template
        for key, val in existing.items():
            if key not in written_keys:
                out_lines.append(f"{key}={val}\n")

        with open(config_file, "w") as f:
            f.writelines(out_lines)
    else:
        with open(config_file, "w") as f:
            for key, val in existing.items():
                f.write(f"{key}={val}\n")

    config_file.chmod(0o600)
    print(f"\n✅ Config saved: {config_file}")


def main():
    parser = argparse.ArgumentParser(description="GARC Setup Wizard")
    subparsers = parser.add_subparsers(dest="command")

    # Full setup
    setup_p = subparsers.add_parser("all", help="Run full setup wizard")
    setup_p.add_argument("--skip-upload", action="store_true", help="Skip disclosure chain upload")

    # Check only
    subparsers.add_parser("check", help="Check API access only")
    subparsers.add_parser("check-forms", help="Check Forms API enablement only")

    # Provision sheets only
    subparsers.add_parser("sheets", help="Provision Sheets tabs only")

    # Provision drive only
    subparsers.add_parser("drive", help="Provision Drive folder only")

    args = parser.parse_args()

    config = load_config()

    if args.command == "check":
        check_api_access(config)
        return

    if args.command == "check-forms":
        print("Forms API enablement (forms.googleapis.com):")
        try:
            svc = build_service(
                "forms",
                "v1",
                scopes=["https://www.googleapis.com/auth/forms.body.readonly"],
            )
            status = probe_forms_api(svc)
        except Exception as exc:
            status = f"❌ {str(exc)[:80]}"
        print(f"  {status} Forms API")
        print("  Publish / responder access is human-GO-only: garc forms publish <id> --go")
        return

    if args.command == "sheets":
        sheets_id = provision_sheets(config)
        save_config({"GARC_SHEETS_ID": sheets_id})
        return

    if args.command == "drive":
        folder_id = provision_drive(config)
        save_config({"GARC_DRIVE_FOLDER_ID": folder_id})
        return

    # Full setup
    print("=" * 60)
    print("GARC Workspace Setup")
    print("=" * 60)

    # 1. Check APIs
    api_results = check_api_access(config)
    failed_apis = [k for k, v in api_results.items() if v.startswith("❌")]
    if failed_apis:
        print(f"\n⚠️  {len(failed_apis)} APIs not accessible: {', '.join(failed_apis)}")
        print("   See docs/google-cloud-setup.md for setup instructions")
        if len(failed_apis) > 3:
            print("   Too many failures. Please enable APIs first.")
            return

    # 2. Provision Drive
    folder_id = provision_drive(config)

    # 3. Provision Sheets
    sheets_id = provision_sheets(config)

    # 4. Upload disclosure chain
    if not getattr(args, "skip_upload", False):
        upload_disclosure_chain(folder_id)

    # 5. Save config
    save_config({
        "GARC_DRIVE_FOLDER_ID": folder_id,
        "GARC_SHEETS_ID": sheets_id,
    })

    # 6. Summary
    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)
    print(f"  Drive folder: https://drive.google.com/drive/folders/{folder_id}")
    print(f"  Sheets:       https://docs.google.com/spreadsheets/d/{sheets_id}")
    print()
    print("Next steps:")
    print("  garc bootstrap --agent main")
    print("  garc status")
    print("  garc memory pull")


if __name__ == "__main__":
    main()
