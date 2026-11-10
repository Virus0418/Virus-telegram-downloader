"""WebUI auth: web_login_secret gates every route except /login and /static."""

import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# download_stat imports pyrogram at import time. Tests still run the real client
# when the package is installed; otherwise stub only the symbol that import needs.
try:
    import pyrogram  # noqa: F401
except Exception:
    _pyro = types.ModuleType("pyrogram")

    class _Client:
        pass

    _pyro.Client = _Client
    sys.modules["pyrogram"] = _pyro

from module.download_stat import get_download_result
from module.web import configure_web_auth, get_flask_app


def _ensure_cache_hook():
    """delete_task imports this lazily. Stub it when the real extension cannot load."""
    try:
        import module.pyrogram_extension  # noqa: F401
    except Exception:
        ext = types.ModuleType("module.pyrogram_extension")
        ext.remove_download_cache = lambda *args, **kwargs: None
        sys.modules["module.pyrogram_extension"] = ext


class WebAuthTests(unittest.TestCase):
    def setUp(self):
        self.app = get_flask_app()
        _ensure_cache_hook()
        configure_web_auth("s3cret")
        self.client = self.app.test_client()

    def tearDown(self):
        configure_web_auth("")
        get_download_result().clear()

    def test_secret_key_is_not_hardcoded_and_is_stable_for_a_secret(self):
        configure_web_auth("abc")
        first = self.app.secret_key
        configure_web_auth("abc")
        self.assertEqual(self.app.secret_key, first)
        self.assertNotEqual(first, "tdl")
        self.assertNotIn("tdl", first)
        configure_web_auth("abd")
        self.assertNotEqual(self.app.secret_key, first)
        configure_web_auth("")
        disabled = self.app.secret_key
        configure_web_auth("")
        self.assertNotEqual(self.app.secret_key, disabled)
        self.assertTrue(self.app.config["LOGIN_DISABLED"])

    def test_blank_and_null_secret_disable_login(self):
        for value in ("", "   ", None, False):
            configure_web_auth(value)
            self.assertTrue(self.app.config["LOGIN_DISABLED"], value)
            client = self.app.test_client()
            page = client.get("/")
            self.assertEqual(page.status_code, 200, value)
            deleted = client.post("/delete_task?task_id=does-not-exist&delete_file=true")
            self.assertEqual(deleted.status_code, 200, value)
            self.assertEqual(deleted.get_json()["code"], "0")
            self.assertNotEqual(deleted.status_code, 401)

    def test_numeric_secret_matches_string_form(self):
        configure_web_auth(123)
        client = self.app.test_client()
        self.assertEqual(client.get("/").status_code, 302)
        ok = client.post("/login", data={"password": "123"})
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(client.get("/").status_code, 200)

    def test_get_root_redirects_to_login(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])
        page = self.client.get("/login")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'name="password"', page.data)
        self.assertIn("Telegram Downloader".encode(), page.data)

    def test_static_is_public(self):
        resp = self.client.get("/static/manifest.json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Telegram Downloader", resp.data)

    def test_every_route_except_login_and_static_is_gated(self):
        seen = set()
        for rule in self.app.url_map.iter_rules():
            seen.add(rule.endpoint)
            if rule.endpoint == "static":
                self.assertIn("<", rule.rule)
                continue
            self.assertNotIn("<", rule.rule, rule.rule)
            if rule.endpoint == "login":
                continue
            methods = (rule.methods or set()) - {"HEAD", "OPTIONS"}
            for method in methods:
                resp = self.client.open(rule.rule, method=method)
                self.assertIn(resp.status_code, (401, 302), (rule.rule, method, resp.status_code))
                if method == "POST":
                    self.assertEqual(resp.status_code, 401, rule.rule)
                    self.assertEqual(resp.get_json()["message"], "login required")
                elif resp.status_code == 302:
                    self.assertIn("/login", resp.headers["Location"])
        self.assertIn("login", seen)
        self.assertIn("static", seen)
        self.assertIn("web_delete_task", seen)
        self.assertIn("web_batch_delete", seen)

    def test_wrong_secret_rejected_and_right_secret_opens_pages_and_apis(self):
        _ensure_cache_hook()
        chat_id, msg_id = 4242, 7
        task_id = f"{chat_id}_{msg_id}"
        fd, path = tempfile.mkstemp(prefix="web-auth-")
        os.write(fd, b"do-not-delete")
        os.close(fd)
        get_download_result()[chat_id] = {
            msg_id: {
                "down_byte": 13,
                "total_size": 13,
                "file_name": path,
                "download_speed": 0,
                "task_id": task_id,
                "start_time": 1,
                "end_time": 2,
            }
        }
        try:
            listing = self.client.get("/get_download_list?already_down=true")
            self.assertEqual(listing.status_code, 401)
            self.assertNotIn(b"do-not-delete", listing.data)
            self.assertNotIn(os.path.basename(path).encode(), listing.data)

            denied = self.client.post(
                f"/delete_task?task_id={task_id}&delete_file=true"
            )
            self.assertEqual(denied.status_code, 401)
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(os.path.getsize(path), 13)
            self.assertIn(msg_id, get_download_result()[chat_id])

            batch = self.client.post(
                "/batch_delete",
                json={"task_ids": [task_id], "delete_file": True},
            )
            self.assertEqual(batch.status_code, 401)
            self.assertTrue(os.path.isfile(path))
            self.assertIn(msg_id, get_download_result()[chat_id])

            bad = self.client.post("/login", data={"password": "nope"})
            self.assertEqual(bad.status_code, 401)
            self.assertIn("登录密钥不正确".encode(), bad.data)
            self.assertEqual(self.client.get("/").status_code, 302)

            bad_json = self.client.post("/login", json={"password": "still-wrong"})
            self.assertEqual(bad_json.status_code, 401)
            self.assertEqual(bad_json.get_json()["code"], "0")

            open_redirect = self.client.post(
                "/login",
                data={"password": "s3cret", "next": "https://evil.example/phish"},
            )
            self.assertEqual(open_redirect.status_code, 302)
            self.assertNotIn("evil.example", open_redirect.headers["Location"])

            # The open-redirect attempt used the right secret, so the session exists.
            # Prove a fresh client still needs the password, then log in cleanly.
            fresh = self.app.test_client()
            self.assertEqual(fresh.get("/").status_code, 302)
            ok = fresh.post("/login", json={"password": "s3cret"})
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(ok.get_json()["code"], "1")

            page = fresh.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertIn(b"status === 401", page.data)
            self.assertIn(b"/login", page.data)

            visible = fresh.get("/get_download_list?already_down=true")
            self.assertEqual(visible.status_code, 200)
            self.assertIn(os.path.basename(path).encode(), visible.data)

            version = fresh.get("/get_app_version")
            self.assertEqual(version.status_code, 200)

            with patch("module.download_stat.save_downloads", lambda: None):
                removed = fresh.post(
                    f"/delete_task?task_id={task_id}&delete_file=true"
                )
            self.assertEqual(removed.status_code, 200)
            body = removed.get_json()
            self.assertEqual(body["code"], "1")
            self.assertTrue(body["file_deleted"])
            self.assertFalse(os.path.exists(path))
        finally:
            get_download_result().pop(chat_id, None)
            if os.path.exists(path):
                os.remove(path)

    def test_null_config_value_does_not_become_the_password_none(self):
        from module.app import Application

        # Skip building the PLY filter; assign_config does not need it, and
        # constructing it writes parser tables next to module/filter.py.
        with patch("module.app.Filter", lambda: None):
            app = Application("config.yaml", "data.yaml")
        base = {
            "api_id": 1,
            "api_hash": "hash",
            "media_types": ["photo"],
            "file_formats": {"photo": ["all"]},
        }
        app.assign_config(dict(base, web_login_secret=None))
        self.assertEqual(app.web_login_secret, "")
        app.assign_config(dict(base, web_login_secret=123))
        self.assertEqual(app.web_login_secret, "123")
        app.assign_config(dict(base, web_login_secret=""))
        self.assertEqual(app.web_login_secret, "")


if __name__ == "__main__":
    unittest.main()
