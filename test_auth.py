import time
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from app import create_app


class AuthTests(unittest.TestCase):
    def test_hosted_origin_and_secure_cookie(self):
        with patch.dict(os.environ, {"RENDER_EXTERNAL_URL": "https://example.onrender.com"}, clear=True):
            app = create_app({"DISCORD_CLIENT_ID": "test", "DISCORD_CLIENT_SECRET": "test"})
            response = app.test_client().get("/auth/login")
            params = parse_qs(urlparse(response.location).query)
            self.assertEqual(params["redirect_uri"], ["https://example.onrender.com/auth/callback"])
            self.assertIn("Secure", response.headers["Set-Cookie"])

    @patch("app.discord_api", return_value={"roles": ["1559163846541705226"]})
    def test_external_manual_file(self, api):
        with tempfile.TemporaryDirectory() as directory:
            content = Path(directory) / "manual.html"
            content.write_text("Protected deployment content", encoding="utf-8")
            self.app = create_app({"TESTING": True, "MANUAL_PATH": str(content)})
            self.client = self.app.test_client()
            self.authenticate()
            self.assertEqual(self.client.get("/manual/").get_data(as_text=True), "Protected deployment content")
            content.unlink()
            self.assertEqual(self.client.get("/manual/").status_code, 503)

    def setUp(self):
        self.app = create_app({"TESTING": True, "DISCORD_CLIENT_ID": "test",
                               "DISCORD_CLIENT_SECRET": "test", "BASE_URL": "http://localhost:8000"})
        self.client = self.app.test_client()

    def authenticate(self):
        with self.client.session_transaction() as session:
            session["sid"] = "test-session"
        self.app.extensions["auth_tokens"]["test-session"] = {"token": "secret-token", "expires": time.time() + 60}

    def test_unauthenticated_and_private_files(self):
        for path in ("/manual", "/manual/", "/manual/index.html"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 401)
            self.assertNotIn("黒髭", response.get_data(as_text=True))
        for path in ("/private/manual.html", "/.git/config", "/config.local.json", "/app.py"):
            self.assertEqual(self.client.get(path).status_code, 404)

    @patch("app.discord_api")
    def test_role_required_and_rechecked(self, api):
        self.authenticate()
        api.return_value = {"roles": ["1559163846541705226"]}
        response = self.client.get("/manual/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("黒髭</td><td>敵地上車両", response.get_data(as_text=True))
        self.assertIn("no-store", response.headers["Cache-Control"])
        api.return_value = {"roles": []}
        self.assertEqual(self.client.get("/manual/index.html").status_code, 403)
        api.side_effect = HTTPError("", 429, "limited", {}, None)
        self.assertEqual(self.client.get("/manual/").status_code, 503)

    @patch("app.discord_api")
    def test_oauth_state_and_token_stays_server_side(self, api):
        response = self.client.get("/auth/login")
        params = parse_qs(urlparse(response.location).query)
        self.assertEqual(params["scope"], ["guilds.members.read"])
        api.return_value = {"access_token": "secret-token", "expires_in": 3600}
        response = self.client.get("/auth/callback", query_string={"state": params["state"][0], "code": "code"})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn("secret-token", str(dict(session)))
        self.assertEqual(self.client.get("/auth/callback?state=forged&code=code").status_code, 400)
        self.assertEqual(api.call_count, 1)

    def test_expired_session_and_logout(self):
        self.authenticate()
        self.app.extensions["auth_tokens"]["test-session"]["expires"] = 0
        self.assertEqual(self.client.get("/manual/").status_code, 401)
        self.authenticate()
        self.client.get("/account")
        self.assertEqual(self.client.post("/auth/logout").status_code, 400)
        with self.client.session_transaction() as session:
            csrf = session["csrf"]
        self.assertEqual(self.client.post("/auth/logout", data={"csrf": csrf}).status_code, 302)
        self.assertEqual(self.client.get("/manual/").status_code, 401)


if __name__ == "__main__":
    unittest.main()
