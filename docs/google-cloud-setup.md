# Google Cloud Console セットアップガイド

## 有効化するAPI一覧

Google Cloud Console (https://console.cloud.google.com/) で以下を有効化してください。

### 必須 API（7種）

| API名 | サービス名 | 用途 |
|-------|-----------|------|
| **Google Drive API** | `drive.googleapis.com` | ファイル読み書き・開示チェーン |
| **Google Sheets API** | `sheets.googleapis.com` | メモリ・エージェント台帳・キュー |
| **Gmail API** | `gmail.googleapis.com` | メール送受信・承認通知 |
| **Google Calendar API** | `calendar-json.googleapis.com` | 予定管理・会議調整 |
| **Google Tasks API** | `tasks.googleapis.com` | タスク管理 |
| **Google Docs API** | `docs.googleapis.com` | ドキュメント作成・本文編集（`append-doc` / `insert-doc`） |
| **Google Forms API** | `forms.googleapis.com` | フォームの下書き作成・読取・更新。公開と回答受付の変更は人間の GO のみ |

### 推奨 API（2種）

| API名 | サービス名 | 用途 |
|-------|-----------|------|
| **Google People API** | `people.googleapis.com` | 連絡先・組織メンバー検索 |
| **Google Chat API** | `chat.googleapis.com` | Chatボット・スペースへの送信 |

---

## 有効化手順

1. https://console.cloud.google.com/ にアクセス
2. 上部のプロジェクト選択で **新しいプロジェクト** を作成（または既存を選択）
3. 左メニュー → **「APIとサービス」** → **「APIとサービスを有効化」**
4. 検索ボックスに上記のAPI名を入力 → **「有効にする」**

---

## OAuth2 認証情報の作成

1. **「APIとサービス」** → **「認証情報」**
2. **「認証情報を作成」** → **「OAuth 2.0 クライアント ID」**
3. アプリケーションの種類: **「デスクトップアプリ」**
4. 名前: `GARC CLI` など任意
5. 作成後 **「JSONをダウンロード」** → `~/.garc/credentials.json` に保存

---

## OAuth同意画面の設定

1. **「APIとサービス」** → **「OAuth 同意画面」**
2. ユーザーの種類: **「外部」**（個人Gmailの場合）または **「内部」**（Workspace組織の場合）
3. アプリ名: `GARC` など
4. **テストユーザー** に自分のGmailアドレスを追加
5. スコープは空でOK（CLIが実行時に要求します）

---

## サービスアカウント（ボット操作用・任意）

自動化・ヘッドレス実行には Service Account が推奨：

1. **「認証情報」** → **「認証情報を作成」** → **「サービスアカウント」**
2. 名前: `garc-bot` など
3. 作成後、サービスアカウントの **「キー」** タブ → **「鍵を追加」** → **「JSON」**
4. ダウンロードしたJSONを `~/.garc/service_account.json` に保存
5. 使用するDriveフォルダ・SheetsをサービスアカウントのメールアドレスにShare

---

## 確認用コマンド

APIを有効化してcredentials.jsonを配置したら：

```bash
garc auth login --profile backoffice_agent
# → ブラウザが開いてGoogleログイン画面
# → 全スコープを承認
# → ~/.garc/token.json が生成される

garc status
# → 全項目が ✅ になることを確認
# → トークンがある場合は Forms API (forms.googleapis.com) の有効化も確認する
```

## フォームの公開は人間の GO のみ

`garc forms create` は未公開の下書きだけを作ります。公開、または回答できる人・回答受付の変更は、人間が明示的に `--go` を付けたときだけ実行されます。

```bash
garc forms publish <form_id>          # 拒否（exit 2）。API は呼ばない
garc forms publish <form_id> --go     # 人間が GO したあとにだけ実行
```

`--confirm` は `--go` の代わりになりません。エージェントが `--go` を付けてはいけません。
