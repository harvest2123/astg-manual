# Renderで公開する

リポジトリには設定だけを保存します。Client Secretと教本本文はRenderの管理画面へ直接登録します。

1. https://dashboard.render.com/ でGitHubを使ってログインする。
2. **New → Blueprint** から `harvest2123/astg-manual` の `main` を選ぶ。
3. `render.yaml` を使い、プランが **Free** であることを確認。
4. 入力を求められる `DISCORD_CLIENT_ID` と `DISCORD_CLIENT_SECRET` に、
   ローカルの `config.local.json` の対応する値を入力して作成する。
5. 作成されたサービスの **Environment → Secret Files → Add Secret File** で、
   ファイル名を `manual.html` とし、ローカルの `private/manual.html` の全文を貼り付ける。
   保存して再デプロイする。実行時には `/etc/secrets/manual.html` として読み込まれる。
6. Render画面の公開URLをコピーする（例: `https://astg-manual-xxxx.onrender.com`）。
   実際のURLはRenderで発行されたものを使う。`BASE_URL` は自動設定されるため入力不要。
7. Discord Developer Portal → OAuth2 → Redirects に
   `https://実際の公開ドメイン/auth/callback` を追加して保存。
   ローカル用のRedirectは残してよい。
8. 公開URLでポータルを開き、指定ロールありで閲覧、なしで拒否、ログアウトを確認する。
9. 確認後に公開URLを配布する。旧GitHub Pagesは停止するか、新URLへの案内に変更する。

教本の更新時はSecret Fileの内容を更新して再デプロイする。
許可ロールは `render.yaml` の `DISCORD_ROLE_ID` にカンマ区切りで指定する。
現在は開発陣 `1559163846541705226` または教官 `1527992363329519698` のどちらかで閲覧可能。
Blueprint同期・再デプロイ後に反映される。Render画面で直接変更する場合も同じ形式を使い、
次のBlueprint同期で戻らないよう `render.yaml` の値も一致させる。
独自ドメインを使う場合は `BASE_URL` をそのHTTPSオリジンに明示設定し、Redirectも変更する。

無料サービスは15分アクセスがないと休止し、次のアクセスで起動待ちが発生する。
セッションはメモリ内なので、再起動後は再ログインが必要。
このアプリは単一インスタンス・単一プロセスで運用する。

注意: 旧GitHubリポジトリの履歴には過去の本文が残る。ロール制限を実効的にするには、
リポジトリの非公開化など、既存の公開経路も閉じる必要がある。
この手順は既に取得された本文のコピーを削除するものではない。

公式資料:
- https://render.com/docs/deploy-flask
- https://render.com/docs/configure-environment-variables
- https://render.com/docs/free
