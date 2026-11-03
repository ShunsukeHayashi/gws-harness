#!/usr/bin/env python3
"""
GARC Forms Helper — Google Forms
list-forms / get / create (unpublished draft) / update /
publish (human --go only) / list-responses / watch
"""

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from garc_core import build_service, utc_now


# forms.body can create and edit form content. It can also publish, so garc
# refuses publish / responder-access changes unless a human passes --go.
FORMS_READ_SCOPES = ["https://www.googleapis.com/auth/forms.body.readonly"]
FORMS_WRITE_SCOPES = ["https://www.googleapis.com/auth/forms.body"]
FORMS_RESPONSES_SCOPES = ["https://www.googleapis.com/auth/forms.responses.readonly"]

HUMAN_GO_MESSAGE = """\
HUMAN GO REQUIRED
Publishing a Google Form, or changing responder access (who can open the form
and whether it accepts responses), is not automated.
garc will not call forms.setPublishSettings unless a human passes --go.
Re-run only after an explicit human GO:
  garc forms publish <form_id> --go
Do not pass --go on behalf of a user. --confirm is not a substitute.
"""


def get_svc(scopes=None):
    return build_service("forms", "v1", scopes=scopes)


def list_forms() -> list:
    """List Google Forms accessible to this user (via Drive)."""
    svc_drive = build_service("drive", "v3")
    results = svc_drive.files().list(
        q="mimeType='application/vnd.google-apps.form' and trashed=false",
        pageSize=50,
        fields="files(id,name,webViewLink,modifiedTime)"
    ).execute()
    forms = results.get("files", [])
    if not forms:
        print("No Forms found.")
        return []
    print(f"Forms ({len(forms)}):")
    for f in forms:
        modified = f.get("modifiedTime", "")[:10]
        print(f"  {f['id']:<44}  {f['name']:<40}  {modified}")
    return forms


def list_responses(form_id: str, max_results: int = 50,
                   since: str = "", output_format: str = "table") -> list:
    """List responses to a specific Form."""
    svc = get_svc(FORMS_RESPONSES_SCOPES)
    kwargs: dict = {"formId": form_id, "pageSize": max_results}
    if since:
        kwargs["filter"] = f"timestamp > {since}"

    result = svc.forms().responses().list(**kwargs).execute()
    responses = result.get("responses", [])

    if not responses:
        print(f"No responses for form: {form_id}")
        return []

    if output_format == "json":
        print(json.dumps(responses, ensure_ascii=False, indent=2))
    else:
        print(f"Responses ({len(responses)}):")
        for r in responses:
            resp_id = r.get("responseId", "?")[:16]
            create_time = r.get("createTime", "")[:19]
            answers = r.get("answers", {})
            answer_count = len(answers)
            print(f"  [{resp_id}]  {create_time}  ({answer_count} answers)")

    return responses


def watch_form(form_id: str, agent_id: str, interval: int = 60,
               max_msgs: int = 10, seen_file_path: str = ""):
    """Poll a Form for new responses and enqueue them via garc ingress."""
    import subprocess
    import os

    garc_dir = os.environ.get("GARC_DIR", "")
    garc_bin = Path(garc_dir) / "bin" / "garc"

    seen_path = Path(seen_file_path) if seen_file_path else \
        Path.home() / ".garc" / "cache" / "seen" / f"forms-{form_id[:16]}.txt"
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    seen_path.touch()

    try:
        seen = set(seen_path.read_text().splitlines())
    except Exception:
        seen = set()

    svc = get_svc(FORMS_RESPONSES_SCOPES)

    print(f"[forms-poller] Watching form {form_id} (agent={agent_id}, interval={interval}s)")

    while True:
        try:
            result = svc.forms().responses().list(
                formId=form_id, pageSize=max_msgs
            ).execute()
            responses = result.get("responses", [])
        except Exception as e:
            print(f"[forms-poller] fetch error: {e}", flush=True)
            time.sleep(interval)
            continue

        new_seen = []
        for resp in responses:
            resp_id = resp.get("responseId", "")
            if not resp_id or resp_id in seen:
                new_seen.append(resp_id)
                continue

            # Build a summary of the answers
            answers = resp.get("answers", {})
            answer_lines = []
            for q_id, ans in list(answers.items())[:5]:  # first 5 questions
                text_answers = ans.get("textAnswers", {}).get("answers", [])
                for ta in text_answers:
                    answer_lines.append(ta.get("value", ""))

            create_time = resp.get("createTime", "")[:10]
            summary = "; ".join(answer_lines[:3]) if answer_lines else "(no answers)"
            text = f"New Google Form response ({create_time}): {summary[:120]}"

            cmd = [str(garc_bin), "ingress", "enqueue",
                   "--text", text,
                   "--source", "google_forms",
                   "--sender", form_id,
                   "--agent", agent_id]

            env = dict(os.environ, GARC_DIR=garc_dir)
            r = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if r.returncode == 0:
                print(f"[forms-poller] Enqueued response: {resp_id[:16]}", flush=True)
            else:
                print(f"[forms-poller] Enqueue failed: {r.stderr.strip()}", flush=True)

            new_seen.append(resp_id)

        if new_seen:
            with open(seen_path, "a") as f:
                f.write("\n".join(new_seen) + "\n")

        if interval == 0:
            break  # single-shot mode
        time.sleep(interval)


def get_form(form_id: str, svc=None, output_format: str = "table") -> dict:
    """Read a form's title, description, items, and publish state."""
    svc = svc or get_svc(FORMS_READ_SCOPES)
    form = svc.forms().get(formId=form_id).execute()
    info = form.get("info", {})
    state = ((form.get("publishSettings") or {}).get("publishState") or {})
    if output_format == "json":
        print(json.dumps(form, ensure_ascii=False, indent=2))
    else:
        print(f"Title:       {info.get('title', '')}")
        print(f"Description: {info.get('description', '')}")
        print(f"Doc title:   {info.get('documentTitle', '')}")
        print(f"ID:          {form.get('formId', form_id)}")
        print(f"Items:       {len(form.get('items', []))}")
        if state:
            print(f"Published:   {state.get('isPublished')}")
            print(f"Accepting:   {state.get('isAcceptingResponses')}")
        else:
            print("Published:   legacy form (no publishSettings)")
        for i, item in enumerate(form.get("items", [])):
            print(f"  [{i}] {item.get('title', '(untitled)')}")
    return form


def create_form(title: str, description: str = "", document_title: str = "", svc=None) -> dict:
    """Create an unpublished draft. Never calls setPublishSettings."""
    svc = svc or get_svc(FORMS_WRITE_SCOPES)
    info = {"title": title, "documentTitle": document_title or title}
    if description:
        info["description"] = description
    body = {"info": info}
    try:
        result = svc.forms().create(body=body, unpublished=True).execute()
    except TypeError:
        print(
            "Note: Forms client has no unpublished=true parameter; "
            "relying on the API default (unpublished after 2026-06-30). "
            "Not calling setPublishSettings.",
            file=sys.stderr,
        )
        result = svc.forms().create(body=body).execute()
    form_id = result.get("formId", "")
    print("✅ Draft form created (unpublished; not accepting responses)")
    print(f"   Title: {title}")
    print(f"   ID:    {form_id}")
    if form_id:
        print(f"   Link:  https://docs.google.com/forms/d/{form_id}/edit")
    print("Publishing or responder-access changes are human-GO-only:")
    print(f"   garc forms publish {form_id} --go")
    return result


def _text_question_item(title: str) -> dict:
    return {
        "title": title,
        "questionItem": {
            "question": {
                "required": False,
                "textQuestion": {"paragraph": False},
            }
        },
    }


def update_form(form_id: str, title: str = None, description: str = None,
                document_title: str = None, add_items: list = None,
                item_index: int = None, item_title: str = None, svc=None) -> dict:
    """Update title, description, and items. Does not publish or change responders."""
    svc = svc or get_svc(FORMS_WRITE_SCOPES)
    requests = []
    info: dict = {}
    mask = []
    if title is not None:
        info["title"] = title
        mask.append("title")
    if description is not None:
        info["description"] = description
        mask.append("description")
    if document_title is not None:
        info["documentTitle"] = document_title
        mask.append("documentTitle")
    if mask:
        requests.append({"updateFormInfo": {"info": info, "updateMask": ",".join(mask)}})

    add_items = list(add_items or [])
    if add_items or item_index is not None:
        current = svc.forms().get(formId=form_id).execute()
        items = current.get("items", [])
        if item_index is not None:
            if item_title is None:
                print("Error: --item-title is required with --item-index", file=sys.stderr)
                raise SystemExit(2)
            if item_index < 0 or item_index >= len(items):
                print(f"Error: item index {item_index} is out of range (0..{len(items) - 1})", file=sys.stderr)
                raise SystemExit(2)
            updated = {"title": item_title}
            item_id = items[item_index].get("itemId")
            if item_id:
                updated["itemId"] = item_id
            requests.append({
                "updateItem": {
                    "item": updated,
                    "location": {"index": item_index},
                    "updateMask": "title",
                }
            })
        start = len(items)
        for offset, question in enumerate(add_items):
            requests.append({
                "createItem": {
                    "item": _text_question_item(question),
                    "location": {"index": start + offset},
                }
            })

    if not requests:
        print("Error: nothing to update. Pass --title, --description, --add-item, or --item-index.", file=sys.stderr)
        raise SystemExit(2)

    allowed = {"updateFormInfo", "updateItem", "createItem"}
    for req in requests:
        if set(req) - allowed:
            print("Refusing update request that is not title/description/items.", file=sys.stderr)
            raise SystemExit(2)

    result = svc.forms().batchUpdate(
        formId=form_id,
        body={"requests": requests, "includeFormInResponse": True},
    ).execute()
    print(f"✅ Form updated (draft fields only, publish state unchanged): {form_id}")
    return result


def set_publish_settings(form_id: str, go: bool = False, published: bool = True,
                         accepting: bool = True, svc=None) -> dict:
    """Change publish state or responder access. Human --go is mandatory."""
    if not go:
        print(HUMAN_GO_MESSAGE, file=sys.stderr)
        raise SystemExit(2)
    if (not published) and accepting:
        print("Refusing: a form cannot accept responses while unpublished.", file=sys.stderr)
        print(HUMAN_GO_MESSAGE, file=sys.stderr)
        raise SystemExit(2)

    svc = svc or get_svc(FORMS_WRITE_SCOPES)
    body = {
        "publishSettings": {
            "publishState": {
                "isPublished": bool(published),
                "isAcceptingResponses": bool(accepting),
            }
        },
        "updateMask": "publishState",
    }
    print("HUMAN GO: changing publish / responder access via forms.setPublishSettings", file=sys.stderr)
    result = svc.forms().setPublishSettings(formId=form_id, body=body).execute()
    print(f"✅ Publish settings updated for {form_id}")
    print(f"   isPublished={bool(published)} isAcceptingResponses={bool(accepting)}")
    return result


def _parse_bool(value: str) -> bool:
    if value.lower() not in ("true", "false"):
        print("Error: expected true or false", file=sys.stderr)
        raise SystemExit(2)
    return value.lower() == "true"


def main():
    parser = argparse.ArgumentParser(description="GARC Forms Helper")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list-forms", help="List accessible Google Forms")

    lrp = sub.add_parser("list-responses", help="List responses for a form")
    lrp.add_argument("form_id", help="Form ID")
    lrp.add_argument("--max", type=int, default=50)
    lrp.add_argument("--since", default="", help="ISO timestamp filter")
    lrp.add_argument("--format", default="table", choices=["table", "json"])

    wp = sub.add_parser("watch", help="Poll form for new responses and enqueue")
    wp.add_argument("form_id", help="Form ID to watch")
    wp.add_argument("--agent", required=True, help="GARC agent ID")
    wp.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    wp.add_argument("--max", type=int, default=10)
    wp.add_argument("--seen-file", default="", help="Path to seen-IDs file")

    gp = sub.add_parser("get", help="Read a form title, description, and items")
    gp.add_argument("form_id")
    gp.add_argument("--format", default="table", choices=["table", "json"])

    cp = sub.add_parser("create", help="Create an unpublished draft form")
    cp.add_argument("--title", required=True)
    cp.add_argument("--description", default="")
    cp.add_argument("--document-title", default="")

    up = sub.add_parser("update", help="Update title, description, or items (does not publish)")
    up.add_argument("form_id")
    up.add_argument("--title", default=None)
    up.add_argument("--description", default=None)
    up.add_argument("--document-title", default=None)
    up.add_argument("--add-item", action="append", default=[], dest="add_items",
                    help="Append a short-answer question. Repeatable.")
    up.add_argument("--item-index", type=int, default=None)
    up.add_argument("--item-title", default=None)

    pp = sub.add_parser(
        "publish",
        help="HUMAN GO ONLY. Publish or change responder access (requires --go)",
    )
    pp.add_argument("form_id")
    pp.add_argument("--go", action="store_true",
                    help="Required. Human explicitly authorizes this publish/responder-access change")
    pp.add_argument("--published", default="true", choices=["true", "false"])
    pp.add_argument("--accepting", default="true", choices=["true", "false"],
                    help="Whether the form accepts responses (responder access)")

    args = parser.parse_args()

    if args.command == "list-forms":
        list_forms()
    elif args.command == "list-responses":
        list_responses(args.form_id, args.max, args.since, args.format)
    elif args.command == "watch":
        watch_form(args.form_id, args.agent, args.interval, args.max, args.seen_file)
    elif args.command == "get":
        get_form(args.form_id, output_format=args.format)
    elif args.command == "create":
        create_form(args.title, args.description, args.document_title)
    elif args.command == "update":
        update_form(
            args.form_id,
            title=args.title,
            description=args.description,
            document_title=args.document_title,
            add_items=args.add_items,
            item_index=args.item_index,
            item_title=args.item_title,
        )
    elif args.command == "publish":
        set_publish_settings(
            args.form_id,
            go=args.go,
            published=_parse_bool(args.published),
            accepting=_parse_bool(args.accepting),
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
