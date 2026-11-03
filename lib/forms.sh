#!/usr/bin/env bash
# GARC forms.sh — Google Forms
# Draft CRUD (get/create/update) plus response pipeline (list/responses/watch).
# Publish and responder-access changes require a human --go.

FORMS_HELPER="${GARC_DIR}/scripts/garc-forms-helper.py"

garc_forms() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    list)           garc_forms_list "$@" ;;
    get|show)       garc_forms_get "$@" ;;
    create)         garc_forms_create "$@" ;;
    update)         garc_forms_update "$@" ;;
    publish)        garc_forms_publish "$@" ;;
    responses)      garc_forms_responses "$@" ;;
    watch)          garc_forms_watch "$@" ;;
    *)
      cat <<EOF
Usage: garc forms <subcommand>

Subcommands:
  list                           List accessible Google Forms
  get <form_id>                  Read title, description, and items
  create --title <text>          Create an UNPUBLISHED draft
    [--description <text>]       Does not publish or accept responses
  update <form_id>               Update title, description, or items
    [--title <text>] [--description <text>]
    [--add-item <question>]      Repeatable. Short-answer item.
    [--item-index N --item-title <text>]
  publish <form_id> --go         HUMAN GO ONLY. Publish or change
    [--published true|false]     responder access. Refuses without --go.
    [--accepting true|false]     --confirm is not a substitute for --go.
  responses <form_id> [--max N]  List responses for a form
  watch <form_id> --agent <id>   Poll form and auto-enqueue new responses
    [--interval <sec>]           Poll interval (default: 60)
    [--max <N>]                  Max responses per cycle (default: 10)

Publishing a form or changing who can respond is a human-GO-only operation.
Agents must not pass --go. A human re-runs the command after an explicit GO.

Examples:
  garc forms list
  garc forms get 1xxxxxxxxxxxxxxxx
  garc forms create --title "SOP check" --description "Draft"
  garc forms update 1xxxxxxxxxxxxxxxx --title "SOP check" --add-item "Owner"
  garc forms publish 1xxxxxxxxxxxxxxxx --go
  garc forms responses 1xxxxxxxxxxxxxxxx
  garc forms watch 1xxxxxxxxxxxxxxxx --agent main --interval 30
EOF
      return 1
      ;;
  esac
}

garc_forms_list() {
  python3 "${FORMS_HELPER}" list-forms
}

garc_forms_get() {
  local form_id="${1:-}" fmt="table"
  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --format) fmt="$2"; shift 2 ;;
      *) form_id="${form_id:-$1}"; shift ;;
    esac
  done
  [[ -z "${form_id}" ]] && { echo "Usage: garc forms get <form_id>"; return 1; }
  python3 "${FORMS_HELPER}" get "${form_id}" --format "${fmt}"
}

garc_forms_create() {
  local title="" description="" document_title=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title) title="$2"; shift 2 ;;
      --description) description="$2"; shift 2 ;;
      --document-title) document_title="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  [[ -z "${title}" ]] && { echo "Usage: garc forms create --title <text> [--description <text>]"; return 1; }
  python3 "${FORMS_HELPER}" create --title "${title}" \
    ${description:+--description "${description}"} \
    ${document_title:+--document-title "${document_title}"}
}

garc_forms_update() {
  local form_id="${1:-}"
  shift || true
  local title="" description="" document_title="" item_index="" item_title=""
  local add_items=()
  local saw_description=0 saw_title=0 saw_doc_title=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title) title="$2"; saw_title=1; shift 2 ;;
      --description) description="$2"; saw_description=1; shift 2 ;;
      --document-title) document_title="$2"; saw_doc_title=1; shift 2 ;;
      --add-item) add_items+=("$2"); shift 2 ;;
      --item-index) item_index="$2"; shift 2 ;;
      --item-title) item_title="$2"; shift 2 ;;
      *) form_id="${form_id:-$1}"; shift ;;
    esac
  done

  [[ -z "${form_id}" ]] && { echo "Usage: garc forms update <form_id> [--title ...] [--add-item ...]"; return 1; }

  local args=(update "${form_id}")
  [[ "${saw_title}" -eq 1 ]] && args+=(--title "${title}")
  [[ "${saw_description}" -eq 1 ]] && args+=(--description "${description}")
  [[ "${saw_doc_title}" -eq 1 ]] && args+=(--document-title "${document_title}")
  local item
  for item in "${add_items[@]}"; do
    args+=(--add-item "${item}")
  done
  [[ -n "${item_index}" ]] && args+=(--item-index "${item_index}")
  [[ -n "${item_title}" ]] && args+=(--item-title "${item_title}")

  python3 "${FORMS_HELPER}" "${args[@]}"
}

garc_forms_publish() {
  local form_id="${1:-}"
  shift || true
  local go=0 published="true" accepting="true"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --go) go=1; shift ;;
      --published) published="$2"; shift 2 ;;
      --accepting) accepting="$2"; shift 2 ;;
      *) form_id="${form_id:-$1}"; shift ;;
    esac
  done

  [[ -z "${form_id}" ]] && {
    echo "Usage: garc forms publish <form_id> --go [--published true|false] [--accepting true|false]"
    echo "HUMAN GO REQUIRED. Publishing or changing responder access is not automated."
    return 2
  }

  if [[ "${go}" -ne 1 ]]; then
    cat <<EOF >&2
HUMAN GO REQUIRED
Publishing a Google Form, or changing responder access (who can open the form
and whether it accepts responses), is not automated.
Re-run only after an explicit human GO:
  garc forms publish ${form_id} --go
Do not pass --go on behalf of a user. --confirm is not a substitute.
EOF
    return 2
  fi

  echo "HUMAN GO: this will change publish / responder access for ${form_id}" >&2
  python3 "${FORMS_HELPER}" publish "${form_id}" --go \
    --published "${published}" \
    --accepting "${accepting}"
}

garc_forms_responses() {
  local form_id="${1:-}"
  shift || true
  local max=50 since="" fmt="table"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max|-n) max="$2"; shift 2 ;;
      --since) since="$2"; shift 2 ;;
      --format) fmt="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${form_id}" ]] && { echo "Usage: garc forms responses <form_id> [--max N]"; return 1; }

  python3 "${FORMS_HELPER}" list-responses "${form_id}" \
    --max "${max}" \
    ${since:+--since "${since}"} \
    --format "${fmt}"
}

garc_forms_watch() {
  local form_id="${1:-}"
  shift || true
  local agent="${GARC_DEFAULT_AGENT:-main}" interval=60 max=10

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent|-a) agent="$2"; shift 2 ;;
      --interval|-i) interval="$2"; shift 2 ;;
      --max|-n) max="$2"; shift 2 ;;
      *) form_id="${form_id:-$1}"; shift ;;
    esac
  done

  [[ -z "${form_id}" ]] && {
    echo "Usage: garc forms watch <form_id> --agent <id> [--interval <sec>]"
    return 1
  }

  echo "👁  Watching form: ${form_id}"
  echo "   Agent: ${agent}  Interval: ${interval}s"
  echo "   Press Ctrl+C to stop."
  echo ""

  python3 "${FORMS_HELPER}" watch "${form_id}" \
    --agent "${agent}" \
    --interval "${interval}" \
    --max "${max}"
}
