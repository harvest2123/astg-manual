"""Discord role-gated manual. Run one server process (sessions stay in memory)."""
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from flask import Flask, redirect, request, session, render_template_string

ROOT = Path(__file__).resolve().parent


def discord_api(path, token=None, form=None):
    headers = {"User-Agent": "ASTG-Manual/1.0"}
    data = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if form is not None:
        data = urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    with urlopen(Request("https://discord.com/api/v10/" + path,
                         data=data, headers=headers), timeout=10) as response:
        return json.load(response)


def create_app(overrides=None):
    config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    local = ROOT / "config.local.json"
    if local.exists():
        config.update(json.loads(local.read_text(encoding="utf-8-sig")))
    for key in config:
        config[key] = os.environ.get(key, config[key])
    # Render supplies its HTTPS origin after assigning the service URL.
    if os.environ.get("RENDER_EXTERNAL_URL") and not os.environ.get("BASE_URL"):
        config["BASE_URL"] = os.environ["RENDER_EXTERNAL_URL"]
    config["MANUAL_PATH"] = os.environ.get("MANUAL_PATH", str(ROOT / "private" / "manual.html"))
    config.update(overrides or {})
    allowed_roles = {role.strip() for role in config["DISCORD_ROLE_ID"].split(",") if role.strip()}
    if not allowed_roles or any(not role.isascii() or not role.isdigit() for role in allowed_roles):
        raise ValueError("DISCORD_ROLE_ID must contain comma-separated numeric role IDs")
    base = config["BASE_URL"].rstrip("/")
    parsed = urlparse(base)
    if (parsed.scheme != "https" and not
            (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1"))):
        raise ValueError("BASE_URL must use HTTPS except on localhost")
    if parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("BASE_URL must be an origin without a path")
    app = Flask(__name__, static_folder=None)
    app.config.update(config)
    app.config.update(SECRET_KEY=secrets.token_hex(32), SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=parsed.scheme == "https")
    tokens = {}
    lock = threading.Lock()
    app.extensions["auth_tokens"] = tokens

    def page(message, status=200):
        return render_template_string('''<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ASTG 入隊教本</title>
<style>body{background:#101720;color:#e9f0f7;font:16px/1.8 system-ui;margin:10vh auto;padding:24px;max-width:560px}a,button{color:#8fd3ff}button{background:#182332;padding:12px;border:1px solid #53677d;border-radius:8px}</style>
<h1>ASTG 入隊教本</h1><p>{{message}}</p><p><a href="/auth/login">Discordでログイン</a></p>
<form method="post" action="/auth/logout"><input type="hidden" name="csrf" value="{{csrf}}"><button>ログアウト</button></form>
<p><a href="/">ポータルへ戻る</a></p></html>''', message=message,
            csrf=session.setdefault("csrf", secrets.token_urlsafe(32))), status

    @app.after_request
    def headers(response):
        response.headers.update({"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff",
                                 "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
                                 "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    @app.get("/")
    @app.get("/index.html")
    def home():
        return (ROOT / "index.html").read_text(encoding="utf-8")

    @app.get("/<section>/", strict_slashes=False)
    @app.get("/<section>/index.html")
    def section(section):
        if section == "manual":
            return manual()
        if section in ("training", "regulations", "exam"):
            return (ROOT / section / "index.html").read_text(encoding="utf-8")
        return page("ページが見つかりません。", 404)

    @app.get("/manual")
    def manual():
        sid = session.get("sid")
        with lock:
            now = time.time()
            for key in list(tokens):
                if tokens[key]["expires"] <= now:
                    del tokens[key]
            auth = tokens.get(sid)
        if not auth:
            return page("Discordでログインしてください。ASTGの指定ロールを持つ方が閲覧できます。", 401)
        try:
            member = discord_api("users/@me/guilds/" + config["DISCORD_GUILD_ID"] + "/member", auth["token"])
        except HTTPError as error:
            if error.code in (401, 403, 404):
                with lock:
                    tokens.pop(sid, None)
                session.clear()
                return page("認証が切れたか、ASTGサーバーへの参加を確認できませんでした。", 403)
            return page("Discordに接続できません。少し待って再度お試しください。", 503)
        except (URLError, TimeoutError, ValueError):
            return page("Discordに接続できません。少し待って再度お試しください。", 503)
        if not allowed_roles.intersection(member.get("roles", [])):
            return page("閲覧に必要なロールがありません。ASTGの管理者に確認してください。", 403)
        content = Path(config["MANUAL_PATH"])
        if not content.exists():
            return page("教本を準備中です。管理者に確認してください。", 503)
        return content.read_text(encoding="utf-8")

    @app.get("/account")
    def account():
        return page("別のアカウントでログインする場合は、ログアウトしてください。")

    @app.get("/auth/login")
    def login():
        if not config["DISCORD_CLIENT_ID"] or not config["DISCORD_CLIENT_SECRET"]:
            return page("Discordログインは準備中です。", 503)
        state = secrets.token_urlsafe(32)
        session["oauth_state"] = state
        session["oauth_started"] = time.time()
        return redirect("https://discord.com/oauth2/authorize?" + urlencode({
            "client_id": config["DISCORD_CLIENT_ID"], "redirect_uri": base + "/auth/callback",
            "response_type": "code", "scope": "guilds.members.read", "state": state}))

    @app.get("/auth/callback")
    def callback():
        expected = session.pop("oauth_state", None)
        started = session.pop("oauth_started", 0)
        if (not expected or not secrets.compare_digest(expected, request.args.get("state", ""))
                or time.time() - started > 600):
            return page("ログイン確認の期限が切れました。もう一度ログインしてください。", 400)
        if request.args.get("iss", "https://discord.com") != "https://discord.com":
            return page("ログイン元を確認できませんでした。", 400)
        if request.args.get("error") or not request.args.get("code"):
            return page("ログインがキャンセルされました。", 400)
        try:
            result = discord_api("oauth2/token", form={
                "client_id": config["DISCORD_CLIENT_ID"], "client_secret": config["DISCORD_CLIENT_SECRET"],
                "grant_type": "authorization_code", "code": request.args["code"],
                "redirect_uri": base + "/auth/callback"})
            access = result["access_token"]
            expires = min(3600, int(result["expires_in"]))
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError):
            return page("ログインを完了できませんでした。もう一度お試しください。", 503)
        with lock:
            tokens.pop(session.get("sid"), None)
            sid = secrets.token_urlsafe(32)
            tokens[sid] = {"token": access, "expires": time.time() + expires}
        session.clear()
        session["sid"] = sid
        return redirect("/manual/")

    @app.post("/auth/logout")
    def logout():
        expected = session.get("csrf")
        if not expected or not secrets.compare_digest(expected, request.form.get("csrf", "")):
            return page("操作を確認できませんでした。", 400)
        with lock:
            tokens.pop(session.get("sid"), None)
        session.clear()
        return redirect("/manual/")

    return app


if __name__ == "__main__":
    from waitress import serve
    serve(create_app(), host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
