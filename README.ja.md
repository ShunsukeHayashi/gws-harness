# GARC — Google Workspace エージェントランタイム CLI

Google Workspace ネイティブなオフィスワークエージェントのためのパーミッションファーストランタイム。

GARC は [LARC](../larc-openclaw-coding-agent/) の Google Workspace 版です。同じガバナンスアーキテクチャ（開示チェーン・実行ゲート・エージェントレジストリ・スコープ推定）を、Google Drive・Sheets・Gmail・Calendar・Tasks を使う組織向けに実装します。

## GARCとは

```
上位エージェント（Claude Code / OpenClaw）
  -> GARC CLI/ランタイム
  -> Google Workspace APIs（Drive, Sheets, Gmail, Calendar, Tasks, Chat）
```

GARCが追加するもの:

1. **パーミッションインテリジェンス** — `garc auth suggest "<タスク>"` で自然言語タスクに必要な最小OAuthスコープを推定
2. **実行ゲート** — エージェントアクション実行前に `none / preview / approval` の3段階ゲート
3. **エージェントレジストリ** — エージェント定義をGoogle Sheetsに保存（id, model, scopes, folder）
4. **開示チェーン** — `SOUL.md / USER.md / MEMORY.md / HEARTBEAT.md` をGoogle Driveにバックアップ
5. **メモリ同期** — Google Sheetsとの日次メモリ双方向同期
6. **キュー/イングレス** — Gmail起動のタスクライフサイクル管理
7. **ナレッジグラフ** — Google Docsをリンクされた概念ノードとして活用

## GWS ↔ LARC バックエンド対応表

| 機能 | LARC（Lark） | GARC（Google Workspace） |
|------|-------------|------------------------|
| ファイルストレージ | Lark Drive | Google Drive |
| 構造化データ | Lark Base | Google Sheets |
| メッセージング | Lark IM | Gmail / Google Chat |
| ナレッジ | Lark Wiki | Google Docs |
| 承認フロー | Lark Approval | Sheets連携承認フロー |
| カレンダー | Lark Calendar | Google Calendar |
| タスク | Lark Project | Google Tasks |
| 認証CLI | `lark-cli` | `gcloud` + googleapis |
| MCPツール | `openclaw-lark` | Gmail/Drive/Calendar MCP |

## クイックスタート

```bash
# インストール
git clone <this-repo>
cd garc-gws-agent-runtime
./scripts/setup-workspace.sh

# 設定
cp config/config.env.example ~/.garc/config.env
# ~/.garc/config.env をGWS認証情報で編集

# 初期化
garc init
garc bootstrap --agent main

# 日常使用
garc memory pull
garc auth suggest "経費サマリーをマネージャーに送信"
garc task list
```

## 設定（`~/.garc/config.env`）

```bash
GARC_DRIVE_FOLDER_ID=1xxxxx          # エージェントワークスペース用Driveフォルダ
GARC_SHEETS_ID=1xxxxx                # メモリ/レジストリ/キュー用Sheets
GARC_GMAIL_DEFAULT_TO=you@gmail.com  # デフォルト通知先メール
GARC_CALENDAR_ID=primary             # Google Calendar ID
GARC_CREDENTIALS_FILE=~/.garc/credentials.json
GARC_TOKEN_FILE=~/.garc/token.json
```

## コマンド一覧

```bash
garc init                          # ワークスペース初期化
garc bootstrap [--agent <id>]      # Driveから開示チェーン読み込み
garc memory pull/push/search       # Sheetsとメモリ同期
garc send "<msg>" [--to <email>]   # Gmail/Google Chat経由で送信
garc task list/create/done         # Google Tasks操作
garc approve gate <task_type>      # 実行ゲートポリシー確認
garc approve list/create           # 承認管理
garc agent list/register           # エージェントレジストリ操作
garc auth suggest "<タスク>"       # OAuthスコープ推定
garc auth check [--profile <p>]    # 現在のトークンスコープ確認
garc auth login [--profile <p>]    # OAuthフロー起動
garc heartbeat                     # システム状態をSheetsに記録
garc status                        # 設定とヘルスチェック表示（Forms API の有効化も表示）
garc kg build/query/show           # ナレッジグラフ操作
garc ingress enqueue/list/next     # キュー管理

# Docs 本文（既存ドキュメント）
garc drive append-doc <doc_id> --content "追記"
garc drive insert-doc <doc_id> --content "正本: <Docs URL>" --after-heading "手順"
garc drive insert-doc <doc_id> --content "末尾の段落" --at end

# Forms（下書きの作成・読取・更新。公開は人間の GO のみ）
garc forms get <form_id>
garc forms create --title "SOP確認" --description "下書き"
garc forms update <form_id> --title "SOP確認" --add-item "担当"
garc forms publish <form_id>            # 拒否される（exit 2）。API は呼ばない
garc forms publish <form_id> --go       # 人間が明示的に GO したときだけ
```

## フォーム公開は人間の GO のみ

`garc forms create` / `update` は未公開の下書きだけを扱います。公開、または回答できる相手・回答受付（`isPublished` / `isAcceptingResponses`）の変更は、人間が `--go` を付けたときだけ実行されます。`--confirm` は代わりになりません。エージェントが `--go` を付けてはいけません。

必要なスコープ:

| 操作 | スコープ |
|------|----------|
| フォームを読む | `forms.body.readonly` |
| 下書きの作成・更新、および人間 GO 後の公開 | `forms.body` |
| 回答の読取 | `forms.responses.readonly` |
| 既存 Docs への段落挿入 | `documents` + `drive.file` |

Google Cloud で `forms.googleapis.com` を有効にしてください。`garc status` と `garc bootstrap` はトークンがあるとき Forms API の有効化を確認します。

## LARCとの関係

GARCとLARCは同じランタイムガバナンスモデルを共有します。バックエンドに応じて選択してください：

- Feishu / Lark → **LARC**
- Google Workspace → **GARC**
- 両方のプラットフォーム → 両方デプロイ（エージェントYAML形式は互換性あり）

## ライセンス

MIT
