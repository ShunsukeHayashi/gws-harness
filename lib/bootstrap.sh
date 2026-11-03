#!/usr/bin/env bash
# GARC bootstrap.sh — Disclosure chain loading from Google Drive
# Mirrors LARC's bootstrap.sh but uses Google Drive instead of Lark Drive

GARC_DISCLOSURE_FILES=("SOUL.md" "USER.md" "MEMORY.md" "RULES.md" "HEARTBEAT.md")

garc_init() {
  echo "GARC v0.1.0 — Initializing workspace..."

  local config_dir="${HOME}/.garc"
  mkdir -p "${config_dir}/cache/workspace"

  # Check for config file
  if [[ ! -f "${config_dir}/config.env" ]]; then
    echo "Config not found. Creating from example..."
    cp "${GARC_DIR}/config/config.env.example" "${config_dir}/config.env"
    echo "✅ Created ${config_dir}/config.env"
    echo ""
    echo "Next steps:"
    echo "  1. Edit ~/.garc/config.env with your Google Drive folder ID and Sheets ID"
    echo "  2. Download OAuth2 credentials.json from Google Cloud Console"
    echo "  3. Save to ~/.garc/credentials.json"
    echo "  4. Run: garc auth login --profile backoffice_agent"
    echo "  5. Run: garc bootstrap --agent main"
    return 0
  fi

  # Validate required config
  source "${config_dir}/config.env"

  local missing=()
  [[ -z "${GARC_DRIVE_FOLDER_ID:-}" ]] && missing+=("GARC_DRIVE_FOLDER_ID")
  [[ -z "${GARC_SHEETS_ID:-}" ]] && missing+=("GARC_SHEETS_ID")

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "⚠️  Missing required config values in ~/.garc/config.env:"
    for key in "${missing[@]}"; do
      echo "   - ${key}"
    done
    return 1
  fi

  echo "✅ Config OK"
  echo "   Drive folder: ${GARC_DRIVE_FOLDER_ID}"
  echo "   Sheets ID: ${GARC_SHEETS_ID}"

  # Verify auth token
  if [[ -f "${GARC_TOKEN_FILE:-${config_dir}/token.json}" ]]; then
    echo "✅ Auth token present"
  else
    echo "⚠️  No auth token. Run: garc auth login --profile backoffice_agent"
  fi

  echo ""
  echo "Workspace initialized. Run 'garc bootstrap --agent main' to load context."
}

garc_bootstrap() {
  local agent_id="${GARC_DEFAULT_AGENT:-main}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent) agent_id="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  echo "Bootstrapping agent '${agent_id}' from Google Drive..."

  local workspace_dir="${GARC_CACHE_DIR}/workspace/${agent_id}"
  mkdir -p "${workspace_dir}/memory"

  local drive_folder="${GARC_DRIVE_FOLDER_ID:-}"
  if [[ -z "${drive_folder}" ]]; then
    echo "Error: GARC_DRIVE_FOLDER_ID not set in ~/.garc/config.env" >&2
    return 1
  fi

  # Download disclosure chain files from Google Drive
  echo "Downloading disclosure chain from Drive folder: ${drive_folder}"

  for filename in "${GARC_DISCLOSURE_FILES[@]}"; do
    local local_path="${workspace_dir}/${filename}"
    echo -n "  ${filename}... "

    if python3 "${GARC_DIR}/scripts/garc-drive-helper.py" download \
        --folder-id "${drive_folder}" \
        --filename "${filename}" \
        --output "${local_path}" 2>/dev/null; then
      echo "✅"
    else
      echo "⚠️  (not found, creating placeholder)"
      _garc_create_placeholder "${local_path}" "${filename}" "${agent_id}"
    fi
  done

  # Download today's daily memory if present
  local today
  today=$(date +%Y-%m-%d)
  local daily_memory="${workspace_dir}/memory/${today}.md"
  echo -n "  memory/${today}.md... "
  if python3 "${GARC_DIR}/scripts/garc-drive-helper.py" download \
      --folder-id "${drive_folder}" \
      --filename "memory/${today}.md" \
      --output "${daily_memory}" 2>/dev/null; then
    echo "✅"
  else
    echo "(none)"
  fi

  # Build consolidated AGENT_CONTEXT.md
  _garc_build_context "${workspace_dir}" "${agent_id}"

  echo ""
  echo "Forms API enablement (forms.googleapis.com):"
  local token_file="${GARC_TOKEN_FILE:-${HOME}/.garc/token.json}"
  if [[ -f "${token_file}" ]]; then
    python3 "${GARC_DIR}/scripts/garc-setup.py" check-forms || true
  else
    echo "  skipped (no auth token). Enable forms.googleapis.com before 'garc forms create'."
    echo "  Publish / responder access is human-GO-only: garc forms publish <id> --go"
  fi

  echo ""
  echo "✅ Bootstrap complete."
  echo "   Context: ${workspace_dir}/AGENT_CONTEXT.md"
  echo ""
  cat "${workspace_dir}/AGENT_CONTEXT.md" | head -20
  echo "   [... $(wc -l < "${workspace_dir}/AGENT_CONTEXT.md") lines total]"
}

_garc_create_placeholder() {
  local filepath="$1"
  local filename="$2"
  local agent_id="$3"

  case "${filename}" in
    SOUL.md)
      cat > "${filepath}" <<EOF
# SOUL — Agent Identity

agent_id: ${agent_id}
platform: Google Workspace
runtime: GARC v0.1.0

## Core Principles
- Permission-first: always check scopes before acting
- Transparency: explain actions before executing
- Gate compliance: respect none/preview/approval tiers

## Created
$(date -u +"%Y-%m-%dT%H:%M:%SZ") (placeholder — upload your SOUL.md to Google Drive)
EOF
      ;;
    USER.md)
      cat > "${filepath}" <<EOF
# USER — User Profile

## Identity
name: (set in Google Drive)
email: ${GARC_GMAIL_DEFAULT_TO:-not set}

## Preferences
language: Japanese / English
timezone: Asia/Tokyo

## Created
$(date -u +"%Y-%m-%dT%H:%M:%SZ") (placeholder — upload your USER.md to Google Drive)
EOF
      ;;
    MEMORY.md)
      cat > "${filepath}" <<EOF
# MEMORY — Long-term Memory Index

Last sync: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Backend: Google Sheets (${GARC_SHEETS_ID:-not configured})

## Recent entries
(pull from Sheets with: garc memory pull)
EOF
      ;;
    RULES.md)
      cat > "${filepath}" <<EOF
# RULES — Operating Rules

1. Always run 'garc auth suggest' before new task categories
2. Respect execution gate policies (none/preview/approval)
3. Confirm with user before preview-gated operations
4. Wait for approval before approval-gated operations
5. Log all actions to heartbeat table
EOF
      ;;
    HEARTBEAT.md)
      cat > "${filepath}" <<EOF
# HEARTBEAT — System State

agent_id: ${agent_id}
last_bootstrap: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
status: initialized
platform: Google Workspace
sheets_id: ${GARC_SHEETS_ID:-not configured}
EOF
      ;;
  esac
}

_garc_build_context() {
  local workspace_dir="$1"
  local agent_id="$2"
  local context_file="${workspace_dir}/AGENT_CONTEXT.md"

  cat > "${context_file}" <<EOF
# AGENT_CONTEXT — ${agent_id}
# Built: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Source: Google Drive folder ${GARC_DRIVE_FOLDER_ID:-unknown}
# ════════════════════════════════════════════════════════

EOF

  for filename in "${GARC_DISCLOSURE_FILES[@]}"; do
    local filepath="${workspace_dir}/${filename}"
    if [[ -f "${filepath}" ]]; then
      echo "## ${filename}" >> "${context_file}"
      echo "" >> "${context_file}"
      cat "${filepath}" >> "${context_file}"
      echo "" >> "${context_file}"
      echo "---" >> "${context_file}"
      echo "" >> "${context_file}"
    fi
  done

  # Append daily memory if present
  local today
  today=$(date +%Y-%m-%d)
  local daily_memory="${workspace_dir}/memory/${today}.md"
  if [[ -f "${daily_memory}" ]]; then
    echo "## Daily Memory (${today})" >> "${context_file}"
    echo "" >> "${context_file}"
    cat "${daily_memory}" >> "${context_file}"
    echo "" >> "${context_file}"
  fi
}

garc_status() {
  echo "GARC Status"
  echo "==========="

  local config_file="${HOME}/.garc/config.env"
  if [[ -f "${config_file}" ]]; then
    source "${config_file}"
    echo "Config: ✅ ${config_file}"
    echo "  Drive folder: ${GARC_DRIVE_FOLDER_ID:-❌ not set}"
    echo "  Sheets ID:    ${GARC_SHEETS_ID:-❌ not set}"
    echo "  Gmail to:     ${GARC_GMAIL_DEFAULT_TO:-❌ not set}"
    echo "  Calendar:     ${GARC_CALENDAR_ID:-primary}"
  else
    echo "Config: ❌ not found (run: garc init)"
    return 1
  fi

  local token_file="${GARC_TOKEN_FILE:-${HOME}/.garc/token.json}"
  if [[ -f "${token_file}" ]]; then
    echo "Auth token: ✅ ${token_file}"
  else
    echo "Auth token: ❌ not found (run: garc auth login)"
  fi

  local creds_file="${GARC_CREDENTIALS_FILE:-${HOME}/.garc/credentials.json}"
  if [[ -f "${creds_file}" ]]; then
    echo "Credentials: ✅ ${creds_file}"
  else
    echo "Credentials: ❌ not found (download from Google Cloud Console)"
  fi

  local agent_id="${GARC_DEFAULT_AGENT:-main}"
  local workspace_dir="${GARC_CACHE_DIR:-${HOME}/.garc/cache}/workspace/${agent_id}"
  if [[ -f "${workspace_dir}/AGENT_CONTEXT.md" ]]; then
    echo "Context: ✅ ${workspace_dir}/AGENT_CONTEXT.md"
  else
    echo "Context: ❌ not bootstrapped (run: garc bootstrap --agent ${agent_id})"
  fi

  echo ""
  echo "API enablement:"
  echo "  Required: Drive, Sheets, Gmail, Calendar, Tasks, Docs, People, Forms (forms.googleapis.com)"
  if [[ -f "${token_file}" ]]; then
    python3 "${GARC_DIR}/scripts/garc-setup.py" check || true
  else
    echo "  API probe: skipped (no auth token). Run 'garc setup check' after login."
  fi
  echo "  Forms publish / responder access is human-GO-only: garc forms publish <id> --go"
}
