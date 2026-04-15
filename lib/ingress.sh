#!/usr/bin/env bash
# GARC ingress.sh — Queue/ingress system (Claude Code execution bridge)
#
# Flow:
#   enqueue → list → run-once → [execute-stub → Claude reads prompt] → done/fail
#
# Claude Code is the execution engine. run-once outputs a structured prompt
# that Claude Code reads and acts on — no external agent process needed.

GARC_QUEUE_DIR="${GARC_CACHE_DIR:-${HOME}/.garc/cache}/queue"
INGRESS_HELPER="${GARC_DIR}/scripts/garc-ingress-helper.py"

garc_ingress() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    enqueue)       _ingress_enqueue "$@" ;;
    list)          _ingress_list "$@" ;;
    next)          _ingress_next "$@" ;;
    run-once)      _ingress_run_once "$@" ;;
    execute-stub)  _ingress_execute_stub "$@" ;;
    context)       _ingress_context "$@" ;;
    approve)       _ingress_approve "$@" ;;
    resume)        _ingress_resume "$@" ;;
    delegate)      _ingress_delegate "$@" ;;
    handoff)       _ingress_handoff "$@" ;;
    done)          _ingress_done "$@" ;;
    fail)          _ingress_fail "$@" ;;
    verify)        _ingress_verify "$@" ;;
    stats)         _ingress_stats "$@" ;;
    *)
      cat <<EOF
Usage: garc ingress <subcommand> [options]

Subcommands:
  enqueue       --text "<msg>" [--source gmail|manual] [--sender <email>] [--agent <id>]
  list          [--agent <id>] [--status pending|done|failed|all]
  next          [--agent <id>]
  run-once      [--agent <id>] [--dry-run]   Run next pending item (outputs Claude prompt)
  execute-stub  --queue-id <id>              Show execution plan for a queue item
  context       --queue-id <id>              Output full Claude-readable context bundle
  approve       --queue-id <id>              Unblock an approval-gated item
  resume        --queue-id <id>              Resume a blocked item
  delegate      --queue-id <id> --to <agent>  Reassign to another agent
  handoff       --queue-id <id>             Handoff with full context (for multi-agent)
  done          --queue-id <id> [--note <text>]
  fail          --queue-id <id> [--note <text>]
  verify        --queue-id <id>             Verify expected output was produced
  stats                                      Queue statistics

Examples:
  garc ingress enqueue --text "Send weekly report to manager"
  garc ingress enqueue --text "Schedule team meeting next week" --source manual
  garc ingress list
  garc ingress run-once
  garc ingress execute-stub --queue-id abc12345
  garc ingress done --queue-id abc12345 --note "Report sent to manager@co.com"
EOF
      return 1
      ;;
  esac
}

# ─────────────────────────────────────────────────────────────────
# enqueue
# ─────────────────────────────────────────────────────────────────

_ingress_enqueue() {
  local text="" source="manual" sender="" agent="${GARC_DEFAULT_AGENT:-main}"
  local dry_run=false

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --text|-t)   text="$2"; shift 2 ;;
      --source)    source="$2"; shift 2 ;;
      --sender)    sender="$2"; shift 2 ;;
      --agent|-a)  agent="$2"; shift 2 ;;
      --dry-run)   dry_run=true; shift ;;
      *)           [[ -z "${text}" ]] && text="$1"; shift ;;
    esac
  done

  if [[ -z "${text}" ]]; then
    echo "Usage: garc ingress enqueue --text \"<message>\" [--source gmail|manual] [--sender <email>]"
    return 1
  fi

  mkdir -p "${GARC_QUEUE_DIR}"

  # Delegate entirely to Python — avoids shell quoting / multiline issues
  python3 - \
    "${text}" "${source}" "${sender}" "${agent}" \
    "${GARC_QUEUE_DIR}" "${INGRESS_HELPER}" "${dry_run}" <<'PY'
import json, sys, subprocess, os, hashlib, time
from datetime import datetime, timezone

text      = sys.argv[1]
source    = sys.argv[2]
sender    = sys.argv[3]
agent_id  = sys.argv[4]
queue_dir = sys.argv[5]
helper    = sys.argv[6]
dry_run   = sys.argv[7] == "true"

# Build payload via helper
result = subprocess.run(
    ["python3", helper, "build-payload",
     "--text", text, "--source", source,
     "--sender", sender, "--agent", agent_id],
    capture_output=True, text=True
)

# Parse helper stdout for display fields
queue_id = ""
gate = "preview"
task_types_str = ""
for line in result.stdout.splitlines():
    if "Queued:" in line:
        queue_id = line.split()[-1].strip()
    elif "gate:" in line and "gate_policy" not in line:
        gate = line.split("gate:")[-1].strip()
    elif "tasks:" in line:
        task_types_str = line.split("tasks:")[-1].strip()

# Fallback queue_id
if not queue_id:
    digest = hashlib.sha256(f"{text}{time.time()}".encode()).hexdigest()
    queue_id = digest[:8]

# Parse task_types
task_types = []
if task_types_str and task_types_str not in ("(none matched)", "(inferred offline)"):
    task_types = [t.strip() for t in task_types_str.split(",") if t.strip()]

payload = {
    "queue_id":    queue_id,
    "message_text": text,
    "source":      source,
    "sender":      sender,
    "agent_id":    agent_id,
    "task_types":  task_types,
    "gate":        gate,
    "status":      "pending",
    "created_at":  datetime.now(timezone.utc).isoformat(),
    "updated_at":  None,
    "approval_id": None,
    "note":        "",
}

if dry_run:
    print("[dry-run] Would enqueue:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    sys.exit(0)

queue_file = os.path.join(queue_dir, f"{queue_id}.jsonl")
with open(queue_file, "w") as f:
    f.write(json.dumps(payload, ensure_ascii=False))

print()
print(f"✅ Enqueued: {queue_id}")
print(f"   Gate:   {gate}")
print(f"   Tasks:  {', '.join(task_types) if task_types else 'unknown'}")
print(f"   Source: {source}")
if sender:
    print(f"   Sender: {sender}")
print()
print("Next: garc ingress run-once")
PY
}

# ─────────────────────────────────────────────────────────────────
# list
# ─────────────────────────────────────────────────────────────────

_ingress_list() {
  local agent="" status_filter="all"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent|-a)  agent="$2"; shift 2 ;;
      --status|-s) status_filter="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  mkdir -p "${GARC_QUEUE_DIR}"

  python3 - <<PY
import json, glob, os

queue_dir    = "${GARC_QUEUE_DIR}"
agent_filter = "${agent}"
status_filter = "${status_filter}"

STATUS_ICON = {
    "pending":     "⏳",
    "in_progress": "🔄",
    "blocked":     "🔒",
    "done":        "✅",
    "failed":      "❌",
}
GATE_ICON = {
    "none":     "🟢",
    "preview":  "🟡",
    "approval": "🔴",
}

files = sorted(glob.glob(os.path.join(queue_dir, "*.jsonl")))
items = []
for f in files:
    try:
        q = json.loads(open(f).readline().strip())
        if agent_filter and q.get("agent_id", q.get("agent", "main")) != agent_filter:
            continue
        if status_filter != "all" and q.get("status") != status_filter:
            continue
        items.append(q)
    except Exception:
        continue

if not items:
    print("(queue is empty)")
else:
    print(f"{'ID':10} {'STATUS':12} {'GATE':8} {'TASKS':30} MESSAGE")
    print("─" * 80)
    for q in items:
        qid     = q.get("queue_id", "?")[:10]
        status  = q.get("status", "?")
        gate    = q.get("gate", "?")
        tasks   = ", ".join(q.get("task_types", []))[:28] or "-"
        msg     = (q.get("message_text") or q.get("message", ""))[:40]
        s_icon  = STATUS_ICON.get(status, "❓")
        g_icon  = GATE_ICON.get(gate, "❓")
        print(f"{qid:<10} {s_icon}{status:<11} {g_icon}{gate:<7} {tasks:<30} {msg}")
PY
}

# ─────────────────────────────────────────────────────────────────
# next — return the next actionable queue item
# ─────────────────────────────────────────────────────────────────

_ingress_next() {
  local agent="${GARC_DEFAULT_AGENT:-main}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent|-a) agent="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  mkdir -p "${GARC_QUEUE_DIR}"

  python3 - <<PY
import json, glob, os, sys

queue_dir = "${GARC_QUEUE_DIR}"
agent_id  = "${agent}"

files = sorted(glob.glob(os.path.join(queue_dir, "*.jsonl")))
for f in files:
    try:
        q = json.loads(open(f).readline().strip())
        q_agent = q.get("agent_id", q.get("agent", "main"))
        if q.get("status") == "pending" and (not agent_id or q_agent == agent_id or agent_id == "any"):
            print(json.dumps(q, ensure_ascii=False))
            sys.exit(0)
    except Exception:
        continue

print("(no pending items)")
PY
}

# ─────────────────────────────────────────────────────────────────
# run-once — the core Claude Code execution bridge
# ─────────────────────────────────────────────────────────────────

_ingress_run_once() {
  local agent="${GARC_DEFAULT_AGENT:-main}" dry_run=false

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent|-a) agent="$2"; shift 2 ;;
      --dry-run)  dry_run=true; shift ;;
      *) shift ;;
    esac
  done

  local next_raw
  next_raw=$(_ingress_next --agent "${agent}")

  if [[ "${next_raw}" == "(no pending items)" ]]; then
    echo "✅ Queue is empty — nothing to run."
    return 0
  fi

  local queue_id gate message
  queue_id=$(echo "${next_raw}" | python3 -c "import json,sys; q=json.loads(sys.stdin.read()); print(q.get('queue_id',''))")
  gate=$(echo "${next_raw}" | python3 -c "import json,sys; q=json.loads(sys.stdin.read()); print(q.get('gate','preview'))")
  message=$(echo "${next_raw}" | python3 -c "import json,sys; q=json.loads(sys.stdin.read()); print(q.get('message_text') or q.get('message',''))")

  echo "▶ Next queue item: ${queue_id}"
  echo "  Gate:    ${gate}"
  echo "  Message: ${message}"
  echo ""

  # ── Gate routing ──────────────────────────────────────────────

  if [[ "${gate}" == "approval" ]]; then
    echo "🔒 Approval gate — creating approval request before execution."
    if [[ "${dry_run}" != "true" ]]; then
      _ingress_update_status "${queue_id}" "blocked"
      source "${GARC_LIB}/approve.sh"
      garc_approve_create "${message}"
    fi
    echo ""
    echo "Status set to: blocked"
    echo "Run after approval: garc ingress resume --queue-id ${queue_id}"
    return 0
  fi

  if [[ "${gate}" == "preview" && "${dry_run}" != "true" ]]; then
    # Claude Code context: output the plan and let Claude confirm with the user
    # rather than blocking on stdin. Use --confirm flag to skip this prompt.
    if [[ "${GARC_AUTO_CONFIRM:-false}" != "true" ]] && [[ -t 0 ]]; then
      echo "⚠️  Preview gate — confirm before execution? [y/N]"
      read -r confirm
      [[ "${confirm}" != "y" ]] && echo "Cancelled." && return 0
    fi
  fi

  if [[ "${dry_run}" == "true" ]]; then
    echo "[dry-run] Would execute queue item ${queue_id}"
    echo ""
    _ingress_execute_stub --queue-id "${queue_id}"
    return 0
  fi

  # ── Mark in_progress ──────────────────────────────────────────
  _ingress_update_status "${queue_id}" "in_progress"

  # ── Output Claude Code prompt bundle ─────────────────────────
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "GARC → Claude Code: execute the following task"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  _ingress_context --queue-id "${queue_id}"
}

# ─────────────────────────────────────────────────────────────────
# execute-stub — show the execution plan for a queue item
# ─────────────────────────────────────────────────────────────────

_ingress_execute_stub() {
  local queue_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queue-id) queue_id="$2"; shift 2 ;;
      *) [[ -z "${queue_id}" ]] && queue_id="$1"; shift ;;
    esac
  done

  [[ -z "${queue_id}" ]] && { echo "Usage: garc ingress execute-stub --queue-id <id>"; return 1; }

  local queue_file
  queue_file=$(_find_queue_file "${queue_id}")
  [[ -z "${queue_file}" ]] && { echo "Queue item not found: ${queue_id}" >&2; return 1; }

  python3 "${INGRESS_HELPER}" execute-stub --queue-file "${queue_file}"
}

# ─────────────────────────────────────────────────────────────────
# context — Claude Code–readable prompt bundle
# ─────────────────────────────────────────────────────────────────

_ingress_context() {
  local queue_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queue-id) queue_id="$2"; shift 2 ;;
      *) [[ -z "${queue_id}" ]] && queue_id="$1"; shift ;;
    esac
  done

  [[ -z "${queue_id}" ]] && { echo "Usage: garc ingress context --queue-id <id>"; return 1; }

  local queue_file
  queue_file=$(_find_queue_file "${queue_id}")
  [[ -z "${queue_file}" ]] && { echo "Queue item not found: ${queue_id}" >&2; return 1; }

  local agent_id="${GARC_DEFAULT_AGENT:-main}"
  local context_path="${GARC_CACHE_DIR:-${HOME}/.garc/cache}/workspace/${agent_id}/AGENT_CONTEXT.md"

  if [[ ! -f "${context_path}" ]]; then
    echo "⚠️  Agent context not found: ${context_path}" >&2
    echo "   Run 'garc bootstrap --agent ${agent_id}' first." >&2
    echo "   Continuing without agent context." >&2
  fi

  python3 "${INGRESS_HELPER}" build-prompt \
    --queue-file "${queue_file}" \
    --agent-context "${context_path}"
}

# ─────────────────────────────────────────────────────────────────
# approve / resume — unblock an approval-gated item
# ─────────────────────────────────────────────────────────────────

_ingress_approve() {
  local queue_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queue-id) queue_id="$2"; shift 2 ;;
      *) [[ -z "${queue_id}" ]] && queue_id="$1"; shift ;;
    esac
  done

  [[ -z "${queue_id}" ]] && { echo "Usage: garc ingress approve --queue-id <id>"; return 1; }

  _ingress_update_status "${queue_id}" "pending"
  echo "✅ Queue item ${queue_id} approved — status reset to pending."
  echo "   Run: garc ingress run-once"
}

_ingress_resume() {
  _ingress_approve "$@"
}

# ─────────────────────────────────────────────────────────────────
# delegate — reassign a queue item to another agent
# ─────────────────────────────────────────────────────────────────

_ingress_delegate() {
  local queue_id="" to_agent=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queue-id) queue_id="$2"; shift 2 ;;
      --to)       to_agent="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${queue_id}" ]] || [[ -z "${to_agent}" ]] && {
    echo "Usage: garc ingress delegate --queue-id <id> --to <agent_id>"
    return 1
  }

  local queue_file
  queue_file=$(_find_queue_file "${queue_id}")
  [[ -z "${queue_file}" ]] && { echo "Queue item not found: ${queue_id}" >&2; return 1; }

  python3 - <<PY
import json
f = "${queue_file}"
q = json.loads(open(f).readline())
old_agent = q.get("agent_id", q.get("agent", "main"))
q["agent_id"] = "${to_agent}"
q["status"] = "pending"
q["note"] = f"Delegated from {old_agent} to ${to_agent}"
q["updated_at"] = "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
with open(f, "w") as fh:
    fh.write(json.dumps(q, ensure_ascii=False))
print(f"✅ Delegated {q['queue_id'][:8]} → ${to_agent}")
PY
}

# ─────────────────────────────────────────────────────────────────
# handoff — pass queue item with full context to another agent
# ─────────────────────────────────────────────────────────────────

_ingress_handoff() {
  local queue_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queue-id) queue_id="$2"; shift 2 ;;
      *) [[ -z "${queue_id}" ]] && queue_id="$1"; shift ;;
    esac
  done

  [[ -z "${queue_id}" ]] && { echo "Usage: garc ingress handoff --queue-id <id>"; return 1; }

  echo "## GARC Handoff Bundle"
  echo ""
  echo "Queue item \`${queue_id}\` is being handed off."
  echo "Full context for the receiving agent:"
  echo ""
  _ingress_context --queue-id "${queue_id}"
  echo ""
  echo "---"
  echo "To pick up this item:"
  echo "  garc ingress resume --queue-id ${queue_id}"
  echo "  garc ingress run-once --agent <receiving_agent>"
}

# ─────────────────────────────────────────────────────────────────
# done / fail
# ─────────────────────────────────────────────────────────────────

_ingress_done() {
  local queue_id="" note=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queue-id) queue_id="$2"; shift 2 ;;
      --note|-n)  note="$2"; shift 2 ;;
      *) [[ -z "${queue_id}" ]] && queue_id="$1"; shift ;;
    esac
  done

  [[ -z "${queue_id}" ]] && { echo "Usage: garc ingress done --queue-id <id> [--note <text>]"; return 1; }

  _ingress_update_status "${queue_id}" "done" "${note}"
  echo "✅ Queue item ${queue_id} — done."
  [[ -n "${note}" ]] && echo "   Note: ${note}"

  # Optionally log to Sheets heartbeat
  if [[ -n "${GARC_SHEETS_ID:-}" ]]; then
    python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" heartbeat \
      --sheets-id "${GARC_SHEETS_ID}" \
      --agent-id "${GARC_DEFAULT_AGENT:-main}" \
      --status "ok" \
      --notes "ingress done: ${queue_id}${note:+ — }${note}" 2>/dev/null || true
  fi
}

_ingress_fail() {
  local queue_id="" note=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queue-id) queue_id="$2"; shift 2 ;;
      --note|-n)  note="$2"; shift 2 ;;
      *) [[ -z "${queue_id}" ]] && queue_id="$1"; shift ;;
    esac
  done

  [[ -z "${queue_id}" ]] && { echo "Usage: garc ingress fail --queue-id <id> [--note <text>]"; return 1; }

  _ingress_update_status "${queue_id}" "failed" "${note}"
  echo "❌ Queue item ${queue_id} — failed."
  [[ -n "${note}" ]] && echo "   Reason: ${note}"
}

# ─────────────────────────────────────────────────────────────────
# verify — check that expected output was produced
# ─────────────────────────────────────────────────────────────────

_ingress_verify() {
  local queue_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queue-id) queue_id="$2"; shift 2 ;;
      *) [[ -z "${queue_id}" ]] && queue_id="$1"; shift ;;
    esac
  done

  [[ -z "${queue_id}" ]] && { echo "Usage: garc ingress verify --queue-id <id>"; return 1; }

  local queue_file
  queue_file=$(_find_queue_file "${queue_id}")
  [[ -z "${queue_file}" ]] && { echo "Queue item not found: ${queue_id}" >&2; return 1; }

  python3 - <<PY
import json
q = json.loads(open("${queue_file}").readline())
status   = q.get("status", "?")
note     = q.get("note", "")
task_types = q.get("task_types", [])
updated  = q.get("updated_at") or q.get("created_at", "?")

print(f"Queue ID:  {q.get('queue_id','?')}")
print(f"Status:    {status}")
print(f"Updated:   {updated}")
if note:
    print(f"Note:      {note}")
print()

if status == "done":
    print("✅ Task completed.")
elif status == "failed":
    print("❌ Task failed.")
elif status in ("pending", "in_progress"):
    print(f"⏳ Task still {status}.")
elif status == "blocked":
    print("🔒 Task is waiting for approval.")
    if q.get("approval_id"):
        print(f"   Approval ID: {q['approval_id']}")
PY
}

# ─────────────────────────────────────────────────────────────────
# stats
# ─────────────────────────────────────────────────────────────────

_ingress_stats() {
  python3 "${INGRESS_HELPER}" stats --queue-dir "${GARC_QUEUE_DIR}"
}

# ─────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────

_find_queue_file() {
  local queue_id="$1"
  local exact="${GARC_QUEUE_DIR}/${queue_id}.jsonl"
  if [[ -f "${exact}" ]]; then
    echo "${exact}"
    return 0
  fi
  # Partial match
  local match
  match=$(ls "${GARC_QUEUE_DIR}"/ 2>/dev/null | grep "^${queue_id}" | head -1)
  if [[ -n "${match}" ]]; then
    echo "${GARC_QUEUE_DIR}/${match}"
    return 0
  fi
  return 1
}

_ingress_update_status() {
  local queue_id="$1"
  local new_status="$2"
  local note="${3:-}"

  local queue_file
  queue_file=$(_find_queue_file "${queue_id}")
  [[ -z "${queue_file}" ]] && return 1

  # Pass note via argv to avoid shell→Python string injection
  python3 - "${queue_file}" "${new_status}" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "${note}" <<'PY'
import json, sys
f, new_status, updated_at, note = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
q = json.loads(open(f).readline())
q["status"]     = new_status
q["updated_at"] = updated_at
if note:
    q["note"] = note
with open(f, "w") as fh:
    fh.write(json.dumps(q, ensure_ascii=False))
PY
}
