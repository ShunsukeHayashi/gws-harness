# GARC Quickstart — 15分で動かす

## このドキュメントについて

このガイドは GARC v0.1.0 の初期リリース向けです。
**以下の前提条件を全て満たしてから**進めてください。途中でスキップすると認証エラーになります。

---

## 前提条件チェックリスト

すべてに ✅ が付いてから先に進んでください。

- [ ] Python 3.10 以上がインストールされている (`python3 --version`)
- [ ] Google アカウントを持っている（Gmail / Drive が使える状態）
- [ ] Google Cloud Console でプロジェクトを作成済み
- [ ] 下記7つのAPIを有効化済み（[詳細手順](google-cloud-setup.md)）
- [ ] OAuth 2.0 クライアント ID を作成し `~/.garc/credentials.json` に保存済み

### 必須 API（7種）

| API | サービス名 |
|-----|---------|
| Google Drive API | `drive.googleapis.com` |
| Google Sheets API | `sheets.googleapis.com` |
| Gmail API | `gmail.googleapis.com` |
| Google Calendar API | `calendar-json.googleapis.com` |
| Google Tasks API | `tasks.googleapis.com` |
| Google Docs API | `docs.googleapis.com` |
| Google People API | `people.googleapis.com` |

> **APIを有効化しないと** `googleapiclient.errors.HttpError: 403 API not enabled` が出ます。
> 有効化の詳細手順: [google-cloud-setup.md](google-cloud-setup.md)

### credentials.json の配置

```bash
mkdir -p ~/.garc
# Google Cloud Console からダウンロードした JSON を配置
mv ~/Downloads/client_secret_*.json ~/.garc/credentials.json
ls ~/.garc/credentials.json   # ← このファイルがないと全コマンドが失敗します
```

---

## Step 1 — インストール

```bash
git clone <this-repo> ~/study/garc-gws-agent-runtime
cd ~/study/garc-gws-agent-runtime

# Python依存パッケージ
pip3 install -r requirements.txt

# CLIをPATHに追加
echo 'export PATH="$HOME/study/garc-gws-agent-runtime/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 確認
garc --version
# → garc 0.1.0
```

---

## Step 2 — 認証

```bash
garc auth login --profile backoffice_agent
# → ブラウザが開く → Googleログイン → 全スコープを承認
# → ~/.garc/token.json が生成される（以降は自動更新）

garc auth status
# → 付与されたスコープ一覧が表示される
```

> **よくあるエラー**
> - `credentials.json not found` → Step 0 の前提条件に戻ってください
> - `Access blocked: This app's request is invalid` → OAuth同意画面でテストユーザーに自分のGmailを追加してください

---

## Step 3 — ワークスペースを自動プロビジョニング

```bash
garc setup all
```

このコマンドが実行すること:

| 処理 | 結果 |
|------|------|
| Google Drive に `GARC Workspace` フォルダ作成 | `~/.garc/config.env` に `GARC_DRIVE_FOLDER_ID` が書き込まれる |
| Google Sheets に全タブ作成 | memory / agents / queue / heartbeat / approval タブが作成される |
| 開示チェーンテンプレートをアップロード | SOUL.md / USER.md / MEMORY.md / RULES.md / HEARTBEAT.md が Drive に配置される |

> **所要時間**: 初回は Google API のプロビジョニングで 1〜2 分かかります。

---

## Step 4 — 動作確認

```bash
garc status
# → 全項目が ✅ になることを確認

garc bootstrap --agent main
# → DriveからSOUL.md/USER.md/MEMORY.md等を読み込み
# → ~/.garc/cache/workspace/main/AGENT_CONTEXT.md に統合コンテキストを出力

garc auth suggest "send weekly report to manager"
# → gate: preview   scopes: gmail.send
```

---

## 主な操作例

```bash
# メール
garc gmail inbox --unread
garc gmail send --to boss@co.com --subject "週次レポート" --body "先週の進捗..."
garc gmail search "from:alice@co.com" --max 10

# カレンダー
garc calendar today
garc calendar week
garc calendar create --summary "MTG" --start "2026-04-16T14:00:00" --end "2026-04-16T15:00:00" --attendees alice@co.com
garc calendar freebusy --start 2026-04-16 --end 2026-04-17 --emails alice@co.com bob@co.com

# Drive
garc drive list
garc drive search "議事録" --type doc
garc drive upload ./report.pdf --convert
garc drive create-doc "Meeting Notes 2026-04-15"

# Sheets
garc sheets info
garc sheets read --range "memory!A:E" --format json
garc sheets search --sheet memory --query "経費"

# メモリ
garc memory pull
garc memory push "顧客Aとの商談: 来週デモを実施することになった"
garc memory search "顧客A"

# タスク
garc task list
garc task create "Q1レポートを作成" --due 2026-04-30
garc task done <task_id>

# 権限確認
garc auth suggest "経費精算を申請してマネージャーに送る"
garc approve gate create_expense

# エージェント登録
garc agent register
garc agent list
```

---

## 設定ファイル

`~/.garc/config.env`（`garc setup all` で自動生成）:

```bash
GARC_DRIVE_FOLDER_ID=1xxxxxxxxxxxxxxxxxxxxxxxxx
GARC_SHEETS_ID=1xxxxxxxxxxxxxxxxxxxxxxxxx
GARC_GMAIL_DEFAULT_TO=your@gmail.com
GARC_CALENDAR_ID=primary
GARC_DEFAULT_AGENT=main
```

---

## トラブルシューティング

| エラー | 原因 | 対処 |
|--------|------|------|
| `credentials.json not found` | 認証情報ファイルが未配置 | Google Cloud ConsoleでOAuth認証情報をダウンロードし `~/.garc/credentials.json` に保存 |
| `Token refresh failed` | トークン期限切れ | `garc auth login` で再認証 |
| `403 API not enabled` | APIが有効化されていない | Google Cloud ConsoleでAPIを有効化（[手順](google-cloud-setup.md)） |
| `403 insufficientPermissions` | スコープが不足 | `garc auth login --profile backoffice_agent` で再認証（全スコープを付与） |
| `Sheets tab missing` | Sheetsが未作成 | `garc setup sheets` でタブを再作成 |
| `Access blocked` | テストユーザー未登録 | OAuth同意画面でテストユーザーにGmailを追加 |

---

## v0.1.0 の既知制限

このリリースで未実装の機能です。詳細は [README の Known Limitations](../README.md#known-limitations) を参照してください。

- Google Chat 通知 → Gmail で代替
- Service Account（ヘッドレス・ボット用途）→ v0.2 で対応予定
- 監査ログ → v0.2 で対応予定
- `garc auth revoke` → 手動で `~/.garc/token.json` を削除してください
