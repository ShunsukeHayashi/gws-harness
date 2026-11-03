#!/usr/bin/env python3
"""
GARC Drive Helper — Full Google Drive operations
list / search / download / upload / create-doc / create-folder / share / move / delete / kg-build
"""

import argparse
import io
import json
import mimetypes
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garc_core import build_service, utc_now, with_retry


def get_svc():
    return build_service("drive", "v3")


MIME_FOLDER = "application/vnd.google-apps.folder"
MIME_DOC = "application/vnd.google-apps.document"
MIME_SHEET = "application/vnd.google-apps.spreadsheet"
MIME_SLIDE = "application/vnd.google-apps.presentation"


def _format_file(f: dict) -> str:
    kind = f.get("mimeType", "")
    if MIME_FOLDER in kind:
        icon = "📁"
    elif "document" in kind:
        icon = "📄"
    elif "spreadsheet" in kind:
        icon = "📊"
    elif "presentation" in kind:
        icon = "📺"
    elif "image" in kind:
        icon = "🖼️"
    else:
        icon = "📎"
    size = f.get("size", "")
    size_str = f" ({int(size):,}B)" if size else ""
    mod = f.get("modifiedTime", "")[:10]
    return f"{icon} [{f['id'][:12]}] {f['name']}{size_str}  {mod}"


@with_retry()
def list_files(folder_id: str = "root", max_results: int = 50,
               query: str = "", order_by: str = "modifiedTime desc"):
    """List files in a Drive folder."""
    svc = get_svc()

    q_parts = [f"'{folder_id}' in parents", "trashed = false"]
    if query:
        q_parts.append(f"name contains '{query}'")

    result = svc.files().list(
        q=" and ".join(q_parts),
        pageSize=max_results,
        orderBy=order_by,
        fields="files(id,name,mimeType,size,modifiedTime,webViewLink,parents)"
    ).execute()
    files = result.get("files", [])

    if not files:
        print(f"No files found in folder: {folder_id}")
        return []

    print(f"Files in {folder_id} ({len(files)}):")
    for f in files:
        print(f"  {_format_file(f)}")

    return files


@with_retry()
def search_files(query: str, max_results: int = 30, file_type: str = ""):
    """Search Drive files by name or content."""
    svc = get_svc()

    q_parts = ["trashed = false"]
    q_parts.append(f"(name contains '{query}' or fullText contains '{query}')")

    mime_map = {
        "doc": MIME_DOC,
        "sheet": MIME_SHEET,
        "slide": MIME_SLIDE,
        "folder": MIME_FOLDER,
        "pdf": "application/pdf",
    }
    if file_type and file_type in mime_map:
        q_parts.append(f"mimeType = '{mime_map[file_type]}'")

    result = svc.files().list(
        q=" and ".join(q_parts),
        pageSize=max_results,
        orderBy="modifiedTime desc",
        fields="files(id,name,mimeType,size,modifiedTime,webViewLink)"
    ).execute()
    files = result.get("files", [])

    if not files:
        print(f"No files found for: {query}")
        return []

    print(f"Search results for '{query}' ({len(files)}):")
    for f in files:
        print(f"  {_format_file(f)}")
        print(f"    🔗 {f.get('webViewLink', '')}")

    return files


@with_retry()
def get_file_info(file_id: str):
    """Get detailed file information."""
    svc = get_svc()
    f = svc.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,createdTime,modifiedTime,webViewLink,parents,owners,shared,sharingUser"
    ).execute()

    print(f"Name:      {f['name']}")
    print(f"ID:        {f['id']}")
    print(f"Type:      {f['mimeType']}")
    print(f"Size:      {f.get('size', 'N/A')}")
    print(f"Created:   {f.get('createdTime', '')[:19]}")
    print(f"Modified:  {f.get('modifiedTime', '')[:19]}")
    print(f"Shared:    {f.get('shared', False)}")
    print(f"Link:      {f.get('webViewLink', '')}")
    owners = f.get("owners", [])
    if owners:
        print(f"Owner:     {owners[0].get('emailAddress', '')}")
    return f


@with_retry()
def download_file(file_id: str = "", folder_id: str = "", filename: str = "",
                  output: str = ""):
    """Download a file from Google Drive."""
    svc = get_svc()

    # Find file by name in folder if file_id not given
    if not file_id and folder_id and filename:
        parts = filename.split("/")
        current_folder = folder_id
        for i, part in enumerate(parts):
            q = f"'{current_folder}' in parents and name='{part}' and trashed=false"
            results = svc.files().list(q=q, fields="files(id,mimeType)").execute()
            files = results.get("files", [])
            if not files:
                print(f"Not found: {filename}", file=sys.stderr)
                sys.exit(1)
            if i == len(parts) - 1:
                file_id = files[0]["id"]
                mime_type = files[0]["mimeType"]
            else:
                current_folder = files[0]["id"]

    if not file_id:
        print("Error: provide --file-id or --folder-id + --filename", file=sys.stderr)
        sys.exit(1)

    # Get file info
    f = svc.files().get(fileId=file_id, fields="name,mimeType").execute()
    mime_type = f.get("mimeType", "")
    out_path = Path(output) if output else Path(f["name"])

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if "google-apps.document" in mime_type:
        request = svc.files().export_media(fileId=file_id, mimeType="text/plain")
    elif "google-apps.spreadsheet" in mime_type:
        request = svc.files().export_media(fileId=file_id,
                                            mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if not str(out_path).endswith(".xlsx"):
            out_path = Path(str(out_path) + ".xlsx")
    elif "google-apps" in mime_type:
        request = svc.files().export_media(fileId=file_id, mimeType="application/pdf")
        if not str(out_path).endswith(".pdf"):
            out_path = Path(str(out_path) + ".pdf")
    else:
        request = svc.files().get_media(fileId=file_id)

    from googleapiclient.http import MediaIoBaseDownload
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    with open(out_path, "wb") as out:
        out.write(fh.getvalue())

    print(f"✅ Downloaded: {out_path} ({len(fh.getvalue()):,} bytes)")
    return str(out_path)


@with_retry()
def upload_file(local_path: str, folder_id: str = "root",
                name: str = "", convert: bool = False):
    """Upload a local file to Google Drive."""
    svc = get_svc()

    local = Path(local_path)
    if not local.exists():
        print(f"File not found: {local_path}", file=sys.stderr)
        sys.exit(1)

    file_name = name or local.name
    mime_type, _ = mimetypes.guess_type(str(local))
    mime_type = mime_type or "application/octet-stream"

    # Convert to Google format if requested
    convert_mime = None
    if convert:
        if local.suffix in (".docx", ".doc", ".txt", ".md"):
            convert_mime = MIME_DOC
        elif local.suffix in (".xlsx", ".xls", ".csv"):
            convert_mime = MIME_SHEET

    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(local), mimetype=mime_type, resumable=True)

    body = {"name": file_name, "parents": [folder_id]}
    if convert_mime:
        body["mimeType"] = convert_mime

    result = svc.files().create(
        body=body, media_body=media, fields="id,name,webViewLink"
    ).execute()

    print(f"✅ Uploaded: {result['name']}")
    print(f"   ID:   {result['id']}")
    print(f"   Link: {result.get('webViewLink', '')}")
    return result


@with_retry()
def create_folder(name: str, parent_id: str = "root"):
    """Create a folder in Google Drive."""
    svc = get_svc()
    result = svc.files().create(body={
        "name": name,
        "mimeType": MIME_FOLDER,
        "parents": [parent_id]
    }, fields="id,name,webViewLink").execute()

    print(f"✅ Folder created: {result['name']}")
    print(f"   ID:   {result['id']}")
    print(f"   Link: {result.get('webViewLink', '')}")
    return result


@with_retry()
def create_doc(name: str, folder_id: str = "root", content: str = ""):
    """Create a Google Doc (optionally with initial content)."""
    svc_drive = get_svc()
    svc_docs = build_service("docs", "v1")

    # Create empty Doc via Drive
    result = svc_drive.files().create(body={
        "name": name,
        "mimeType": MIME_DOC,
        "parents": [folder_id]
    }, fields="id,name,webViewLink").execute()

    doc_id = result["id"]

    # Add initial content if provided via batchUpdate
    if content:
        _doc_insert_text(svc_docs, doc_id, content, append=False)

    print(f"✅ Doc created: {name}")
    print(f"   ID:   {doc_id}")
    print(f"   Link: {result.get('webViewLink', '')}")
    return result


def _doc_insert_text(svc_docs, doc_id: str, text: str, append: bool = True):
    """Insert or append text to an existing Google Doc."""
    if append:
        # Get current end index
        doc = svc_docs.documents().get(documentId=doc_id).execute()
        body = doc.get("body", {})
        content_items = body.get("content", [])
        # End index of doc body is the last structural element's endIndex minus 1
        end_index = content_items[-1]["endIndex"] - 1 if content_items else 1
        insert_index = max(end_index, 1)
    else:
        insert_index = 1  # beginning of new doc

    svc_docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [
            {"insertText": {"location": {"index": insert_index}, "text": text}}
        ]}
    ).execute()


@with_retry()
def append_doc(doc_id: str, content: str, svc_docs=None):
    """Append raw text to an existing Google Doc (end of the body)."""
    svc_docs = svc_docs or build_service("docs", "v1")
    _doc_insert_text(svc_docs, doc_id, content, append=True)
    print(f"✅ Content appended to doc: {doc_id}")


def _paragraph_text(element: dict) -> str:
    paragraph = element.get("paragraph") or {}
    return "".join(
        el.get("textRun", {}).get("content", "")
        for el in paragraph.get("elements", [])
    )


def plan_doc_insert(doc: dict, text: str, after_heading: str = None,
                    at_end: bool = False, index: int = None) -> dict:
    """Plan a single insertText that lands as its own paragraph.

    Returns {"index": int, "text": str}. Does not call the API.
    """
    if text is None or text == "":
        raise ValueError("text is required")
    content = (doc.get("body") or {}).get("content") or []
    body_end = content[-1]["endIndex"] if content else 2

    if index is not None:
        if index < 1 or index >= body_end:
            raise ValueError(
                f"index {index} is outside the document body (1..{body_end - 1})"
            )
        inserted = text if text.endswith("\n") else text + "\n"
        return {"index": index, "text": inserted}

    if after_heading:
        match = None
        wanted = after_heading.strip()
        for element in content:
            if _paragraph_text(element).strip() == wanted:
                match = element
                break
        if match is None:
            raise LookupError(after_heading)
        insert_at = match["endIndex"]
        if insert_at >= body_end:
            # Heading is the last paragraph. Insert before its trailing newline
            # and open a new paragraph with a leading newline.
            body = text[1:] if text.startswith("\n") else text
            if body.endswith("\n"):
                body = body[:-1]
            return {"index": max(body_end - 1, 1), "text": "\n" + body}
        inserted = text if text.endswith("\n") else text + "\n"
        return {"index": insert_at, "text": inserted}

    if at_end:
        body = text[:-1] if text.endswith("\n") else text
        if not body.startswith("\n"):
            body = "\n" + body
        return {"index": max(body_end - 1, 1), "text": body}

    raise ValueError("specify after_heading, at_end, or index")


@with_retry()
def insert_doc(doc_id: str, content: str, after_heading: str = None,
               at_end: bool = False, index: int = None, svc_docs=None):
    """Insert a paragraph after a heading, at an index, or at the end."""
    svc_docs = svc_docs or build_service("docs", "v1")
    doc = svc_docs.documents().get(documentId=doc_id).execute()
    try:
        plan = plan_doc_insert(
            doc, content, after_heading=after_heading, at_end=at_end, index=index
        )
    except LookupError:
        print(f"Heading not found: {after_heading}", file=sys.stderr)
        raise SystemExit(1)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)

    svc_docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [
            {"insertText": {"location": {"index": plan["index"]}, "text": plan["text"]}}
        ]},
    ).execute()
    print(f"✅ Paragraph inserted into doc: {doc_id} at index {plan['index']}")
    return plan


@with_retry()
def share_file(file_id: str, email: str, role: str = "reader",
               send_notification: bool = True):
    """Share a file with a user."""
    svc = get_svc()

    valid_roles = ["reader", "writer", "commenter", "owner"]
    if role not in valid_roles:
        print(f"Invalid role. Choose: {', '.join(valid_roles)}", file=sys.stderr)
        sys.exit(1)

    result = svc.permissions().create(
        fileId=file_id,
        body={"type": "user", "role": role, "emailAddress": email},
        sendNotificationEmail=send_notification,
        fields="id,emailAddress,role"
    ).execute()

    print(f"✅ Shared with {email} as {role}")
    return result


@with_retry()
def move_file(file_id: str, new_folder_id: str):
    """Move a file to a different folder."""
    svc = get_svc()

    # Get current parents
    f = svc.files().get(fileId=file_id, fields="parents").execute()
    current_parents = ",".join(f.get("parents", []))

    result = svc.files().update(
        fileId=file_id,
        addParents=new_folder_id,
        removeParents=current_parents,
        fields="id,name,parents"
    ).execute()
    print(f"✅ Moved: {result.get('name', file_id)} → {new_folder_id}")
    return result


@with_retry()
def delete_file(file_id: str, permanent: bool = False):
    """Delete or trash a file."""
    svc = get_svc()

    if permanent:
        svc.files().delete(fileId=file_id).execute()
        print(f"✅ Permanently deleted: {file_id}")
    else:
        svc.files().update(fileId=file_id, body={"trashed": True}).execute()
        print(f"✅ Moved to trash: {file_id}")


@with_retry()
def kg_build(folder_id: str, output: str, depth: int = 3):
    """Build knowledge graph from Drive folder."""
    svc = get_svc()
    svc_docs = build_service("docs", "v1")

    print(f"Building knowledge graph from: {folder_id} (depth={depth})")
    nodes = []
    visited = set()

    import re

    def crawl(fid: str, level: int = 0):
        if level > depth or fid in visited:
            return
        visited.add(fid)

        try:
            q = f"'{fid}' in parents and trashed = false"
            files = []
            page_token = None
            while True:
                kwargs: dict = dict(
                    q=q, pageSize=100,
                    fields="nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)"
                )
                if page_token:
                    kwargs["pageToken"] = page_token
                results = svc.files().list(**kwargs).execute()
                files.extend(results.get("files", []))
                page_token = results.get("nextPageToken")
                if not page_token:
                    break
        except Exception:
            return

        for f in files:
            file_id = f["id"]
            if MIME_FOLDER in f["mimeType"]:
                crawl(file_id, level + 1)
                continue

            if MIME_DOC not in f["mimeType"]:
                continue

            content_preview = ""
            links = []
            try:
                req = svc.files().export_media(fileId=file_id, mimeType="text/plain")
                fh = io.BytesIO()
                from googleapiclient.http import MediaIoBaseDownload
                dl = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = dl.next_chunk()
                content = fh.getvalue().decode("utf-8", errors="replace")
                content_preview = content[:800]
                links = list(set(re.findall(
                    r'docs\.google\.com/document/d/([a-zA-Z0-9_-]{10,})', content
                )))
            except Exception:
                pass

            nodes.append({
                "doc_id": file_id,
                "title": f["name"],
                "mime_type": f["mimeType"],
                "modified_time": f.get("modifiedTime", ""),
                "web_link": f.get("webViewLink", ""),
                "content_preview": content_preview,
                "links": links,
                "depth": level,
            })
            indent = "  " * level
            print(f"  {indent}✅ {f['name']} ({len(links)} links)")

    crawl(folder_id)

    import datetime
    kg = {
        "built_at": utc_now(),
        "folder_id": folder_id,
        "node_count": len(nodes),
        "nodes": nodes,
    }

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fp:
        json.dump(kg, fp, ensure_ascii=False, indent=2)

    print(f"\n✅ Knowledge graph: {len(nodes)} docs indexed → {output}")
    return kg


def main():
    parser = argparse.ArgumentParser(description="GARC Drive Helper")
    sub = parser.add_subparsers(dest="command")

    # list
    lp = sub.add_parser("list", help="List files in folder")
    lp.add_argument("--folder-id", default="root")
    lp.add_argument("--max", type=int, default=50)
    lp.add_argument("--query", default="")

    # search
    sp = sub.add_parser("search", help="Search files")
    sp.add_argument("query")
    sp.add_argument("--max", type=int, default=30)
    sp.add_argument("--type", choices=["doc", "sheet", "slide", "folder", "pdf"], default="")

    # info
    ip = sub.add_parser("info", help="Get file info")
    ip.add_argument("file_id")

    # download
    dp = sub.add_parser("download", help="Download file")
    dp.add_argument("--file-id", default="")
    dp.add_argument("--folder-id", default="")
    dp.add_argument("--filename", default="")
    dp.add_argument("--output", default="")

    # upload
    up = sub.add_parser("upload", help="Upload file")
    up.add_argument("local_path")
    up.add_argument("--folder-id", default="root")
    up.add_argument("--name", default="")
    up.add_argument("--convert", action="store_true", help="Convert to Google format")

    # create-folder
    cf = sub.add_parser("create-folder", help="Create folder")
    cf.add_argument("name")
    cf.add_argument("--parent-id", default="root")

    # create-doc
    cd = sub.add_parser("create-doc", help="Create Google Doc")
    cd.add_argument("name")
    cd.add_argument("--folder-id", default="root")
    cd.add_argument("--content", default="")

    # append-doc
    adp = sub.add_parser("append-doc", help="Append text to an existing Google Doc")
    adp.add_argument("doc_id", help="Document ID")
    adp.add_argument("--content", required=True, help="Text to append")

    # insert-doc
    idp = sub.add_parser("insert-doc", help="Insert a paragraph into an existing Google Doc")
    idp.add_argument("doc_id", help="Document ID")
    idp.add_argument("--content", required=True, help="Paragraph text to insert")
    position = idp.add_mutually_exclusive_group(required=True)
    position.add_argument("--after-heading", default=None, help="Insert after the paragraph with this exact text")
    position.add_argument("--at", choices=["end"], default=None, help="Insert a new paragraph at the end")
    position.add_argument("--index", type=int, default=None, help="Docs API body index to insert at")

    # share
    sh = sub.add_parser("share", help="Share file")
    sh.add_argument("file_id")
    sh.add_argument("--email", required=True)
    sh.add_argument("--role", default="reader", choices=["reader", "writer", "commenter", "owner"])
    sh.add_argument("--no-notify", action="store_true")

    # move
    mv = sub.add_parser("move", help="Move file to folder")
    mv.add_argument("file_id")
    mv.add_argument("--to", required=True, dest="new_folder_id")

    # delete
    delp = sub.add_parser("delete", help="Delete/trash file")
    delp.add_argument("file_id")
    delp.add_argument("--permanent", action="store_true")

    # kg-build
    kb = sub.add_parser("kg-build", help="Build knowledge graph")
    kb.add_argument("--folder-id", required=True)
    kb.add_argument("--output", required=True)
    kb.add_argument("--depth", type=int, default=3)

    args = parser.parse_args()

    if args.command == "list":
        list_files(args.folder_id, args.max, args.query)
    elif args.command == "search":
        search_files(args.query, args.max, args.type)
    elif args.command == "info":
        get_file_info(args.file_id)
    elif args.command == "download":
        download_file(args.file_id, args.folder_id, args.filename, args.output)
    elif args.command == "upload":
        upload_file(args.local_path, args.folder_id, args.name, args.convert)
    elif args.command == "create-folder":
        create_folder(args.name, args.parent_id)
    elif args.command == "create-doc":
        create_doc(args.name, args.folder_id, args.content)
    elif args.command == "append-doc":
        append_doc(args.doc_id, args.content)
    elif args.command == "insert-doc":
        insert_doc(
            args.doc_id,
            args.content,
            after_heading=args.after_heading,
            at_end=(args.at == "end"),
            index=args.index,
        )
    elif args.command == "share":
        share_file(args.file_id, args.email, args.role, not args.no_notify)
    elif args.command == "move":
        move_file(args.file_id, args.new_folder_id)
    elif args.command == "delete":
        delete_file(args.file_id, args.permanent)
    elif args.command == "kg-build":
        kg_build(args.folder_id, args.output, args.depth)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
