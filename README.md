# ASTG 入隊教本 — Discordロール認証

Botの追加は不要。Discord OAuth2の `guilds.members.read` で本人の所属・ロールを確認します。
サーバー `1520413994425385030`、許可ロールは開発陣 `1559163846541705226` と教官 `1527992363329519698` です。
`DISCORD_ROLE_ID` にカンマ区切りで複数IDを指定でき、どれか1つを持っていれば閲覧できます。
ローカルは `config.local.json`、本番は `render.yaml` の同名設定で管理します。

## ローカルで試す（Windows / Python 3.12）

1. [Discord Developer Portal](https://discord.com/developers/applications) で New Application を作成。
2. OAuth2 の Redirects に `http://localhost:8000/auth/callback` を登録して保存。
3. `config.example.json` を `config.local.json` にコピー（この作業環境では作成済み）。
4. Client ID と Client Secret を `config.local.json` の対応する欄へ入力。秘密情報はチャットやGitへ貼らない。
5. 以下を実行して `http://localhost:8000` を開く。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

設定未入力でも起動できますが、Discordログインは準備中と表示します。
設定を変更したらサーバーを再起動してください。
Live Serverでは認証は動きません。必ずPythonサーバーから開いてください。

## 本文と本番公開

Renderでの公開手順は [DEPLOY.md](DEPLOY.md) を参照。`render.yaml` に無料プランの設定を用意しています。

本文は `private/manual.html` に保存し、Git管理から除外しています。別途バックアップしてください。
新しい環境へのcloneだけでは本文は入りません。非公開の経路でサーバーに配置してください。
公開される `manual/index.html` は移行案内のみです。

本番にはPythonを実行できるHTTPSの配信先が必要です。GitHub Pagesでは動きません。
配信先で `BASE_URL` をHTTPSの公開オリジン（末尾パスなし）に変更し、DiscordのRedirectsにも
`https://公開ドメイン/auth/callback` を登録します。設定は同名の環境変数でも指定できます。
起動は `python app.py`。必要なら環境変数 `HOST=0.0.0.0`、`PORT` を指定してください。
HTTPSは配信サービスまたはリバースプロキシで終端してください。
この構成は単一プロセス用です。セッションはメモリに保持し、再起動・最大1時間で再ログインが必要です。
複数プロセス・複数台へ増やす場合は共有セッションストアへの変更が必要です。

**既存のGitHub Pagesと公開リポジトリの履歴には、以前の本文が残っています。**
この実装だけでは既に公開した内容を非公開にできません。本番移行時には旧Pagesを停止し、
リポジトリの公開範囲を見直してください。既に保存されたコピーを取り消すことはできません。
Git履歴の削除や公開設定の変更は、この変更では行っていません。

教本への各リクエストでロールを再確認します。ロールなし・サーバー未参加・Discord障害時は本文を返しません。
閲覧済みのページや保存したコピーはロール削除後も回収できません。
Discordトークンはサーバーのメモリのみ、ブラウザにはランダムなセッション識別子を保存します。

## 検証

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

自動テストはDiscord APIの代替応答で検証します。実際のログインはClient ID/Secret設定後に、
指定ロールあり・なしのアカウント、ログアウト、ロール削除後の再読み込みを確認してください。

公式仕様: https://docs.discord.com/developers/topics/oauth2
