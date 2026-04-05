#!/usr/bin/env python3

import os
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)

from publisher.login_state import normalize_login_result, resolve_login_ui_status
from publisher.xiaohongshu_publisher import XiaohongshuPublisher


class LoginStateHelpersTest(unittest.TestCase):
    def test_logged_in_primary_result_wins(self):
        result = normalize_login_result(
            {"status": "logged_in", "success": True, "message": "ok", "data": {"backend": "mcp"}}
        )
        self.assertEqual(result["status"], "logged_in")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["auth_source"], "mcp")

    def test_unavailable_primary_uses_valid_legacy_fallback(self):
        result = normalize_login_result(
            {"status": "unavailable", "success": False, "message": "", "data": {"backend": "mcp"}},
            fallback_result={"status": "logged_in", "success": True, "message": "legacy ok", "data": {"backend": "legacy"}},
        )
        self.assertEqual(result["status"], "logged_in")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["auth_source"], "legacy_cookie_fallback")
        self.assertEqual(result["data"]["fallback"]["status"], "logged_in")

    def test_unavailable_primary_uses_expired_fallback_state(self):
        result = normalize_login_result(
            {"status": "unavailable", "success": False, "message": "", "data": {"backend": "mcp"}},
            fallback_result={"status": "expired", "success": False, "message": "expired", "data": {"backend": "legacy"}},
        )
        self.assertEqual(result["status"], "expired")
        self.assertFalse(result["success"])
        self.assertIn("legacy", result["message"].lower())

    def test_ui_resolution_prefers_logged_in_over_running(self):
        current = resolve_login_ui_status(
            backend_status={"status": "logged_in"},
            status_payload={"status": "running"},
            process_running=True,
            current_status="running",
        )
        self.assertEqual(current, "logged_in")

    def test_ui_resolution_prefers_running_over_idle_backend(self):
        current = resolve_login_ui_status(
            backend_status={"status": "idle"},
            status_payload={"status": "starting"},
            process_running=True,
            current_status="idle",
        )
        self.assertEqual(current, "running")

    def test_ui_resolution_uses_terminal_status_payload(self):
        current = resolve_login_ui_status(
            backend_status={"status": "idle"},
            status_payload={"status": "timeout"},
            process_running=False,
            current_status="running",
        )
        self.assertEqual(current, "timeout")


class MCPPublisherFallbackTest(unittest.TestCase):
    def test_mcp_login_status_promotes_valid_legacy_fallback(self):
        publisher = XiaohongshuPublisher(headless=False, backend="mcp")
        with tempfile.TemporaryDirectory() as tmp_dir:
            cookie_path = os.path.join(tmp_dir, "cookies.json")
            with open(cookie_path, "w", encoding="utf-8") as fh:
                fh.write("[]")
            publisher.COOKIE_FILE = cookie_path
            publisher.COOKIE_FILE_LEGACY = os.path.join(tmp_dir, "cookies.pkl")

            with mock.patch.object(
                publisher.mcp_backend,
                "_run_capture",
                return_value={"status": "unavailable", "success": False, "message": "", "data": {"backend": "mcp"}},
            ), mock.patch.object(
                publisher.legacy_backend,
                "login_status",
                return_value={"status": "logged_in", "success": True, "message": "legacy ok", "data": {"backend": "legacy"}},
            ):
                result = publisher.mcp_backend.login_status()

        self.assertEqual(result["status"], "logged_in")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["auth_source"], "legacy_cookie_fallback")


if __name__ == "__main__":
    unittest.main()
