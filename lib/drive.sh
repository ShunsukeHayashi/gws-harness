#!/usr/bin/env bash
# GARC drive.sh — Full Google Drive operations
# list / search / info / download / upload / create-folder / create-doc / share / move / delete

DRIVE_HELPER="${GARC_DIR}/scripts/garc-drive-helper.py"

garc_drive() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    list)          garc_drive_list "$@" ;;
    search)        garc_drive_search "$@" ;;
    info)          garc_drive_info "$@" ;;
    download)      garc_drive_download "$@" ;;
    upload)        garc_drive_upload "$@" ;;
    create-folder) garc_drive_create_folder "$@" ;;
    create-doc)    garc_drive_create_doc "$@" ;;
    append-doc)    garc_drive_append_doc "$@" ;;
    insert-doc)    garc_drive_insert_doc "$@" ;;
    share)         garc_drive_share "$@" ;;
    move)          garc_drive_move "$@" ;;
    delete)        garc_drive_delete "$@" ;;
    *)
      cat <<EOF
Usage: garc drive <subcommand> [options]

Subcommands:
  list          [--folder-id <id>] [--max N] [--query <name>]
  search        <query> [--max N] [--type doc|sheet|slide|folder|pdf]
  info          <file_id>
  download      --file-id <id> | --folder-id <id> --filename <name>  [--output <path>]
  upload        <local_path> [--folder-id <id>] [--name <name>] [--convert]
  create-folder <name> [--parent-id <id>]
  create-doc    <name> [--folder-id <id>] [--content <text>]
  append-doc    <doc_id> --content <text>
  insert-doc    <doc_id> --content <text> (--after-heading <text> | --at end | --index <n>)
  share         <file_id> --email <email> [--role reader|writer|commenter]
  move          <file_id> --to <folder_id>
  delete        <file_id> [--permanent]

Examples:
  garc drive list --folder-id 1xxxxxxxxx
  garc drive search "Q1 report" --type doc
  garc drive upload ./report.pdf --folder-id 1xxxxxxxxx --convert
  garc drive create-doc "Meeting Notes 2026-04-15" --folder-id 1xxxxxxxxx
  garc drive append-doc 1xxxxxxxxx --content "追記"
  garc drive insert-doc 1xxxxxxxxx --content "正本: https://docs.google.com/document/d/abc" --after-heading "手順"
  garc drive insert-doc 1xxxxxxxxx --content "末尾の段落" --at end
  garc drive share 1xxxxxxxxx --email colleague@co.com --role writer
EOF
      return 1
      ;;
  esac
}

garc_drive_list() {
  local folder_id="${GARC_DRIVE_FOLDER_ID:-root}" max=50 query=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --folder-id|-f) folder_id="$2"; shift 2 ;;
      --max|-n) max="$2"; shift 2 ;;
      --query|-q) query="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  python3 "${DRIVE_HELPER}" list \
    --folder-id "${folder_id}" \
    --max "${max}" \
    ${query:+--query "${query}"}
}

garc_drive_search() {
  local query="" max=30 type=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max|-n) max="$2"; shift 2 ;;
      --type|-t) type="$2"; shift 2 ;;
      *) query="${query:+${query} }$1"; shift ;;
    esac
  done

  [[ -z "${query}" ]] && { echo "Usage: garc drive search <query> [--type doc|sheet|slide|folder|pdf]"; return 1; }

  python3 "${DRIVE_HELPER}" search "${query}" --max "${max}" ${type:+--type "${type}"}
}

garc_drive_info() {
  # No arg → show workspace folder info
  if [[ -z "${1:-}" ]]; then
    local folder_id="${GARC_DRIVE_FOLDER_ID:-}"
    if [[ -z "${folder_id}" ]]; then
      echo "No GARC_DRIVE_FOLDER_ID set. Run 'garc setup all' first."
      echo "Usage: garc drive info <file_id>"
      return 1
    fi
    python3 "${DRIVE_HELPER}" info "${folder_id}"
    return $?
  fi
  python3 "${DRIVE_HELPER}" info "$1"
}

garc_drive_download() {
  local file_id="" folder_id="" filename="" output=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --file-id) file_id="$2"; shift 2 ;;
      --folder-id) folder_id="$2"; shift 2 ;;
      --filename) filename="$2"; shift 2 ;;
      --output|-o) output="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  python3 "${DRIVE_HELPER}" download \
    ${file_id:+--file-id "${file_id}"} \
    ${folder_id:+--folder-id "${folder_id}"} \
    ${filename:+--filename "${filename}"} \
    ${output:+--output "${output}"}
}

garc_drive_upload() {
  local local_path="${1:-}"
  shift || true
  local folder_id="${GARC_DRIVE_FOLDER_ID:-root}" name="" convert=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --folder-id|-f) folder_id="$2"; shift 2 ;;
      --name|-n) name="$2"; shift 2 ;;
      --convert) convert="--convert"; shift ;;
      *) shift ;;
    esac
  done

  [[ -z "${local_path}" ]] && { echo "Usage: garc drive upload <local_path> [--folder-id <id>] [--convert]"; return 1; }

  python3 "${DRIVE_HELPER}" upload "${local_path}" \
    --folder-id "${folder_id}" \
    ${name:+--name "${name}"} \
    ${convert}
}

garc_drive_create_folder() {
  local name="${1:-}" parent_id="${GARC_DRIVE_FOLDER_ID:-root}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --parent-id|-p) parent_id="$2"; shift 2 ;;
      *) name="${name:-$1}"; shift ;;
    esac
  done

  [[ -z "${name}" ]] && { echo "Usage: garc drive create-folder <name> [--parent-id <id>]"; return 1; }

  python3 "${DRIVE_HELPER}" create-folder "${name}" --parent-id "${parent_id}"
}

garc_drive_create_doc() {
  local name="${1:-}" folder_id="${GARC_DRIVE_FOLDER_ID:-root}" content=""
  shift || true

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --folder-id|-f) folder_id="$2"; shift 2 ;;
      --content|-c) content="$2"; shift 2 ;;
      *) name="${name:-$1}"; shift ;;
    esac
  done

  [[ -z "${name}" ]] && { echo "Usage: garc drive create-doc <name> [--folder-id <id>] [--content <text>]"; return 1; }

  python3 "${DRIVE_HELPER}" create-doc "${name}" \
    --folder-id "${folder_id}" \
    ${content:+--content "${content}"}
}

garc_drive_append_doc() {
  local doc_id="${1:-}"
  shift || true
  local content=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --content|-c) content="$2"; shift 2 ;;
      *) doc_id="${doc_id:-$1}"; shift ;;
    esac
  done

  [[ -z "${doc_id}" ]] && { echo "Usage: garc drive append-doc <doc_id> --content <text>"; return 1; }
  [[ -z "${content}" ]] && { echo "Usage: garc drive append-doc <doc_id> --content <text>"; return 1; }

  python3 "${DRIVE_HELPER}" append-doc "${doc_id}" --content "${content}"
}

garc_drive_insert_doc() {
  local doc_id="${1:-}"
  shift || true
  local content="" after="" at="" index=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --content|-c) content="$2"; shift 2 ;;
      --after-heading) after="$2"; shift 2 ;;
      --at) at="$2"; shift 2 ;;
      --index) index="$2"; shift 2 ;;
      *) doc_id="${doc_id:-$1}"; shift ;;
    esac
  done

  [[ -z "${doc_id}" || -z "${content}" ]] && {
    echo "Usage: garc drive insert-doc <doc_id> --content <text> (--after-heading <text> | --at end | --index <n>)"
    return 1
  }
  if [[ -n "${after}" && -n "${at}" ]] || [[ -n "${after}" && -n "${index}" ]] || [[ -n "${at}" && -n "${index}" ]]; then
    echo "Pass only one of --after-heading, --at end, or --index" >&2
    return 1
  fi
  if [[ -z "${after}" && -z "${at}" && -z "${index}" ]]; then
    echo "Pass --after-heading <text>, --at end, or --index <n>" >&2
    return 1
  fi

  python3 "${DRIVE_HELPER}" insert-doc "${doc_id}" --content "${content}" \
    ${after:+--after-heading "${after}"} \
    ${at:+--at "${at}"} \
    ${index:+--index "${index}"}
}

garc_drive_share() {
  local file_id="${1:-}"
  shift || true
  local email="" role="reader" no_notify=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --email|-e) email="$2"; shift 2 ;;
      --role|-r) role="$2"; shift 2 ;;
      --no-notify) no_notify="--no-notify"; shift ;;
      *) shift ;;
    esac
  done

  [[ -z "${file_id}" ]] || [[ -z "${email}" ]] && {
    echo "Usage: garc drive share <file_id> --email <email> [--role reader|writer|commenter]"
    return 1
  }

  python3 "${DRIVE_HELPER}" share "${file_id}" \
    --email "${email}" \
    --role "${role}" \
    ${no_notify}
}

garc_drive_move() {
  local file_id="${1:-}" new_folder_id=""
  shift || true

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --to) new_folder_id="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${file_id}" ]] || [[ -z "${new_folder_id}" ]] && {
    echo "Usage: garc drive move <file_id> --to <folder_id>"
    return 1
  }

  python3 "${DRIVE_HELPER}" move "${file_id}" --to "${new_folder_id}"
}

garc_drive_delete() {
  local file_id="${1:-}" permanent=""
  shift || true

  [[ "${1:-}" == "--permanent" ]] && permanent="--permanent"

  [[ -z "${file_id}" ]] && { echo "Usage: garc drive delete <file_id> [--permanent]"; return 1; }

  if [[ -z "${permanent}" ]]; then
    echo "Move to trash: ${file_id}? [y/N]"
  else
    echo "⚠️  Permanently delete: ${file_id}? This cannot be undone. [y/N]"
  fi
  read -r confirm
  [[ "${confirm}" != "y" ]] && echo "Cancelled." && return 0

  python3 "${DRIVE_HELPER}" delete "${file_id}" ${permanent}
}
