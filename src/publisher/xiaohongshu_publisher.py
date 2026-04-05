#!/usr/bin/env python3
"""Xiaohongshu publisher with MCP-first backend and legacy Selenium fallback."""

import json
import os
import pickle
import random
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from webdriver_manager.chrome import ChromeDriverManager

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    webdriver = None
    TimeoutException = Exception
    Options = None
    Service = None
    ActionChains = None
    By = None
    EC = None
    WebDriverWait = None
    ChromeDriverManager = None

from config.config import (
    CRAWLER_HEADERS,
    XHS_BACKEND,
    XHS_COOKIE_FILE,
    XHS_COOKIE_FILE_LEGACY,
    XHS_FAVORITE_FOLDER,
    XHS_MCP_ARGS,
    XHS_MCP_CMD,
    XHS_PROFILE_DIR,
)
from publisher.login_state import normalize_login_result


def _root_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))


def _ensure_parent(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _load_cookie_list(json_path, legacy_path):
    data = _load_json(json_path)
    if isinstance(data, list):
        return data, json_path
    if os.path.exists(legacy_path):
        try:
            with open(legacy_path, "rb") as f:
                data = pickle.load(f)
            if isinstance(data, list):
                return data, legacy_path
        except Exception:
            pass
    return [], None


def _resolve_post_image_paths(post):
    image_paths = []
    for key in ["final_image_paths", "generated_image_paths", "original_image_paths"]:
        value = post.get(key, [])
        if isinstance(value, str):
            value = [value] if value else []
        for path in value if isinstance(value, list) else []:
            if path and os.path.exists(path) and path not in image_paths:
                image_paths.append(os.path.abspath(path))
    single_path = post.get("generated_image_path", "")
    if single_path and os.path.exists(single_path) and os.path.abspath(single_path) not in image_paths:
        image_paths.insert(0, os.path.abspath(single_path))
    return image_paths[:9]


def _resolve_post_content(post):
    return (
        post.get("publish_content", "")
        or post.get("optimized_content", "")
        or post.get("rewritten_content", "")
        or post.get("content", "")
    )


class BasePublisherBackend:
    def __init__(self, publisher):
        self.publisher = publisher

    def login(self, auto_close=False):
        raise NotImplementedError

    def login_status(self):
        raise NotImplementedError

    def validate_credentials(self):
        raise NotImplementedError

    def publish_post(self, draft):
        raise NotImplementedError

    def favorite_source_post(self, post, folder_name=XHS_FAVORITE_FOLDER):
        raise NotImplementedError

    def save_cookies(self):
        return False

    def load_cookies(self, validate_only=False, auto_close=True):
        return False

    def cleanup(self):
        pass


class MCPPublisherBackend(BasePublisherBackend):
    def __init__(self, publisher):
        super().__init__(publisher)
        self.log_file = None

    def _split_tokens(self, raw):
        if not raw:
            return []
        try:
            return shlex.split(raw, posix=False)
        except ValueError:
            return [raw]

    def _base_command(self):
        cmd = self._split_tokens(XHS_MCP_CMD) + self._split_tokens(XHS_MCP_ARGS)
        cmd = [item for item in cmd if item]
        if not cmd:
            return []
        program = cmd[0]
        if not (os.path.isabs(program) or os.path.sep in program):
            resolved = shutil.which(program)
            if resolved:
                cmd[0] = resolved
        return cmd

    def is_available(self):
        base = self._base_command()
        if not base:
            return False
        program = base[0]
        if os.path.isabs(program) or os.path.sep in program:
            return os.path.exists(program)
        return shutil.which(program) is not None

    def _command_env(self):
        env = os.environ.copy()
        env["XHS_PROFILE_DIR"] = self.publisher.profile_dir
        env["XHS_COOKIE_FILE"] = self.publisher.COOKIE_FILE
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return env

    def _build_command(self, subcommand, extra_args=None):
        cmd = self._base_command()
        if subcommand:
            cmd.append(subcommand)
        if extra_args:
            cmd.extend(extra_args)
        return cmd

    def _extract_json(self, text):
        if not text:
            return None
        raw = text.strip()
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except Exception:
                    pass
        for line in reversed([line.strip() for line in text.splitlines() if line.strip()]):
            try:
                return json.loads(line)
            except Exception:
                continue
        return None

    def _normalize_status(self, completed, stdout="", stderr="", returncode=0, payload=None):
        payload = payload or {}
        merged = " ".join(
            str(item).lower()
            for item in [
                payload.get("status"),
                payload.get("message"),
                payload.get("authenticated"),
                payload.get("logged_in"),
                payload.get("loggedIn"),
                stdout,
                stderr,
            ]
            if item is not None
        )
        if payload.get("authenticated") is True or payload.get("logged_in") is True or payload.get("loggedIn") is True:
            return "logged_in"
        if "logged_in" in merged or "authenticated" in merged or "already logged in" in merged:
            return "logged_in"
        if not completed:
            return "running"
        if any(key in merged for key in ["expired", "invalid", "unauthorized", "not logged"]):
            return "expired"
        if returncode == 0 and any(key in merged for key in ["success", "ok"]):
            return "logged_in"
        return "idle"

    def _run_capture(self, subcommand, extra_args=None, timeout=60):
        if not self.is_available():
            return {
                "success": False,
                "message": "MCP command not available",
                "status": "unavailable",
                "data": {},
                "log_file": self.log_file,
                "returncode": None,
                "stdout": "",
                "stderr": "",
            }
        try:
            proc = subprocess.run(
                self._build_command(subcommand, extra_args),
                cwd=_root_dir(),
                env=self._command_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            payload = self._extract_json(proc.stdout)
            status = self._normalize_status(
                completed=True,
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                payload=payload,
            )
            message = ""
            if isinstance(payload, dict):
                message = str(payload.get("message", "")).strip()
            if not message:
                message = (proc.stdout or proc.stderr or "").strip()[:200]
            return {
                "success": proc.returncode == 0 and status in {"logged_in", "idle"},
                "message": message or "Command completed",
                "status": status,
                "data": payload or {},
                "log_file": self.log_file,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except FileNotFoundError:
            return {
                "success": False,
                "message": "MCP command not found",
                "status": "unavailable",
                "data": {},
                "log_file": self.log_file,
                "returncode": None,
                "stdout": "",
                "stderr": "",
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "success": False,
                "message": "MCP command timed out",
                "status": "timeout",
                "data": {},
                "log_file": self.log_file,
                "returncode": None,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
            }

    def spawn_login(self, status_file, log_file, timeout=180):
        _ensure_parent(status_file)
        _ensure_parent(log_file)
        self.log_file = log_file
        if not self.is_available():
            payload = {
                "status": "error",
                "success": False,
                "backend": "mcp",
                "message": "MCP command not available",
                "log_file": log_file,
                "updated_at": datetime.now().isoformat(),
            }
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return None, payload

        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

        with open(log_file, "w", encoding="utf-8", errors="replace") as log_handle:
            process = subprocess.Popen(
                self._build_command("login", ["--timeout", str(timeout)]),
                cwd=_root_dir(),
                env=self._command_env(),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )

        payload = {
            "pid": process.pid,
            "status": "running",
            "success": False,
            "backend": "mcp",
            "message": "Waiting for browser login to complete",
            "log_file": log_file,
            "updated_at": datetime.now().isoformat(),
        }
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return process.pid, payload

    def login_status(self):
        result = self._run_capture("status", timeout=30)
        fallback = None
        if result["status"] == "unavailable" and (
            os.path.exists(self.publisher.COOKIE_FILE) or os.path.exists(self.publisher.COOKIE_FILE_LEGACY)
        ):
            fallback = self.publisher.legacy_backend.login_status()
        return normalize_login_result(result, fallback_result=fallback)

    def validate_credentials(self):
        result = self.login_status()
        if result.get("status") == "logged_in":
            return result
        if self.publisher.legacy_backend.load_cookies(validate_only=False, auto_close=True):
            return normalize_login_result(
                result,
                fallback_result={
                    "success": True,
                    "message": "Validated legacy cookie fallback",
                    "status": "logged_in",
                    "source": "cookie_fallback",
                    "reason": "Validated legacy cookie fallback",
                    "data": {"backend": "legacy", "auth_source": "cookie_fallback"},
                    "log_file": result.get("log_file"),
                },
            )
        return result

    def login(self, auto_close=False):
        status = self.validate_credentials()
        if status.get("status") == "logged_in":
            return True
        result = self._run_capture("login", ["--timeout", "180"], timeout=240)
        return result.get("status") == "logged_in" or result.get("success", False)

    def publish_post(self, draft):
        if not self.is_available():
            return {
                "success": False,
                "message": "MCP command not available",
                "url": "",
                "status": "unavailable",
                "data": {},
                "log_file": self.log_file,
            }
        post = draft.get("post", {}) if isinstance(draft, dict) else {}
        title = post.get("title", "")[:20]
        content = _resolve_post_content(post)
        valid_images = _resolve_post_image_paths(post)
        cmd = self._build_command("publish", ["--title", title, "--content", content[:1000]])
        for image in valid_images[:9]:
            cmd.extend(["--image", image])
        proc = subprocess.run(
            cmd,
            cwd=_root_dir(),
            env=self._command_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        payload = self._extract_json(proc.stdout) or {}
        message = str(payload.get("message", "") or (proc.stdout or proc.stderr or "").strip()[:200])
        return {
            "success": proc.returncode == 0,
            "message": message or ("Published successfully" if proc.returncode == 0 else "Publish failed"),
            "url": str(payload.get("url", "") or ""),
            "status": "published" if proc.returncode == 0 else "error",
            "data": payload,
            "log_file": self.log_file,
        }

    def favorite_source_post(self, post, folder_name=XHS_FAVORITE_FOLDER):
        status = self.validate_credentials()
        if status.get("status") != "logged_in":
            return {
                "success": False,
                "status": "login_required",
                "message": status.get("message", "MCP login required"),
                "folder_name": folder_name,
                "source_url": str((post or {}).get("source_url") or (post or {}).get("link") or ""),
            }
        return self.publisher.legacy_backend.favorite_source_post(post, folder_name=folder_name)


class LegacySeleniumPublisherBackend(BasePublisherBackend):
    LOGIN_URL = "https://www.xiaohongshu.com"
    PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"
    HOME_URL = "https://www.xiaohongshu.com/explore"

    def __init__(self, publisher):
        super().__init__(publisher)
        self.driver = None

    def _init_driver(self):
        if self.driver or not SELENIUM_AVAILABLE:
            return self.driver
        options = Options()
        options.add_argument(
            "--user-agent={}".format(
                CRAWLER_HEADERS.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            )
        )
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-blink-features=AutomationControlled")
        if self.publisher.headless:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(30)
        self.driver.set_script_timeout(30)
        try:
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
            )
        except Exception:
            pass
        return self.driver

    def cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def save_cookies(self):
        if not self.driver:
            return False
        cookies = self.driver.get_cookies()
        _ensure_parent(self.publisher.COOKIE_FILE)
        with open(self.publisher.COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        with open(self.publisher.COOKIE_FILE_LEGACY, "wb") as f:
            pickle.dump(cookies, f)
        print("[OK] Cookies saved to {}".format(self.publisher.COOKIE_FILE))
        return True

    def load_cookies(self, validate_only=False, auto_close=True):
        cookies, source_path = _load_cookie_list(self.publisher.COOKIE_FILE, self.publisher.COOKIE_FILE_LEGACY)
        if not cookies:
            print("[INFO] No saved cookies found")
            return False
        created_here = False
        try:
            if not self.driver:
                created_here = True
            self._init_driver()
            self.driver.get(self.LOGIN_URL)
            time.sleep(2)
            for cookie in cookies:
                try:
                    cleaned = {
                        key: value
                        for key, value in cookie.items()
                        if key in {"name", "value", "domain", "path", "expiry", "secure", "httpOnly", "sameSite"}
                    }
                    self.driver.add_cookie(cleaned)
                except Exception:
                    continue
            self.driver.get(self.HOME_URL)
            time.sleep(3)
            current_url = self.driver.current_url.lower()
            success = "login" not in current_url and "passport" not in current_url
            if success:
                print("[OK] Cookie login successful! Source: {}".format(source_path))
            else:
                print("[WARN] Cookie expired or invalid")
            return success
        except Exception as exc:
            print("[ERROR] Load cookies failed: {}".format(str(exc)[:120]))
            return False
        finally:
            if validate_only or (auto_close and created_here):
                self.cleanup()

    def login_status(self):
        if os.path.exists(self.publisher.COOKIE_FILE) or os.path.exists(self.publisher.COOKIE_FILE_LEGACY):
            if self.load_cookies(validate_only=False, auto_close=True):
                return {
                    "success": True,
                    "message": "Legacy cookies are valid",
                    "status": "logged_in",
                    "source": "cookie_fallback",
                    "reason": "Validated legacy cookie session",
                    "data": {"backend": "legacy", "auth_source": "cookie_fallback"},
                    "log_file": None,
                }
            return {
                "success": False,
                "message": "Legacy cookies expired",
                "status": "expired",
                "source": "cookie_fallback",
                "reason": "Legacy cookie session expired",
                "data": {"backend": "legacy", "auth_source": "cookie_fallback"},
                "log_file": None,
            }
        return {
            "success": False,
            "message": "No legacy cookies found",
            "status": "idle",
            "source": "cookie_fallback",
            "reason": "No legacy cookies found",
            "data": {"backend": "legacy", "auth_source": "cookie_fallback"},
            "log_file": None,
        }

    def validate_credentials(self):
        return self.login_status()

    def login(self, auto_close=False):
        if not SELENIUM_AVAILABLE:
            print("[ERROR] Selenium not installed. Run: pip install selenium webdriver-manager")
            return False
        if self.load_cookies(validate_only=False, auto_close=auto_close):
            return True
        try:
            self._init_driver()
            self.driver.get(self.LOGIN_URL)
            time.sleep(3)
            print("=" * 60)
            print("  BROWSER OPENED - Please login manually!")
            print("=" * 60)
            print("  1. Login via phone number / WeChat scan / email")
            print("  2. After successful login, keep the browser open")
            print("  3. The script will detect login automatically")
            print("  4. Waiting up to 120 seconds...")
            print("=" * 60)
            waited = 0
            while waited < 120:
                try:
                    current_url = self.driver.current_url.lower()
                    has_user_element = bool(
                        self.driver.find_elements(
                            By.CSS_SELECTOR,
                            ".user-avatar, .header-user-info, [class*='user'], .side-bar-avatar",
                        )
                    )
                    if "login" not in current_url and "passport" not in current_url and has_user_element:
                        self.save_cookies()
                        if auto_close:
                            self.cleanup()
                        return True
                except Exception:
                    pass
                time.sleep(2)
                waited += 2
            current_url = ""
            try:
                current_url = self.driver.current_url.lower()
            except Exception:
                pass
            if "login" not in current_url and "passport" not in current_url:
                self.save_cookies()
                if auto_close:
                    self.cleanup()
                return True
            return False
        except Exception as exc:
            print("[ERROR] Login error: {}".format(str(exc)[:120]))
            return False

    def _safe_wait(self, seconds):
        try:
            time.sleep(seconds)
        except Exception:
            pass

    def _find_first(self, selectors, by=None, timeout=3):
        if not SELENIUM_AVAILABLE or not By or not WebDriverWait or not EC:
            return None
        by = by or By.CSS_SELECTOR
        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
                self._safe_wait(0.5)
                if element.is_displayed():
                    return element
            except Exception:
                continue
        return None

    def _find_by_text(self, texts, tag="*", timeout=2):
        if not SELENIUM_AVAILABLE or not By or not WebDriverWait or not EC:
            return None
        for text in texts:
            xpath = '//{}[contains(normalize-space(.), "{}")]'.format(tag, text)
            try:
                return WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
            except Exception:
                continue
        return None

    def _open_collect_panel(self):
        button = self._find_first(
            [
                '[aria-label*="收藏"]',
                '[class*="collect"]',
                '[class*="favorite"]',
                'button[class*="collect"]',
                'button[class*="favorite"]',
            ],
            timeout=2,
        )
        if button:
            return button
        return self._find_by_text(["收藏", "加入收藏"], tag="button", timeout=2) or self._find_by_text(
            ["收藏", "加入收藏"], tag="*", timeout=2
        )

    def _ensure_folder_exists(self, folder_name):
        folder = self._find_by_text([folder_name], tag="*", timeout=2)
        if folder:
            return folder
        create_button = self._find_by_text(["新建收藏夹", "新建"], tag="button", timeout=2) or self._find_by_text(
            ["新建收藏夹", "新建"], tag="*", timeout=2
        )
        if not create_button:
            return None
        try:
            create_button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", create_button)
        input_box = None
        for selector in ['input[placeholder*="收藏夹"]', 'input[placeholder*="名称"]', 'input[type="text"]']:
            try:
                input_box = WebDriverWait(self.driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                if input_box:
                    break
            except Exception:
                continue
        if not input_box:
            return None
        try:
            input_box.clear()
        except Exception:
            pass
        input_box.send_keys(folder_name)
        confirm = self._find_by_text(["确定", "创建", "完成"], tag="button", timeout=2) or self._find_by_text(
            ["确定", "创建", "完成"], tag="*", timeout=2
        )
        if confirm:
            try:
                confirm.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", confirm)
            self._safe_wait(1)
        return self._find_by_text([folder_name], tag="*", timeout=2)

    def favorite_source_post(self, post, folder_name=XHS_FAVORITE_FOLDER):
        result = {
            "success": False,
            "status": "error",
            "message": "",
            "folder_name": folder_name,
            "source_url": str((post or {}).get("source_url") or (post or {}).get("link") or ""),
        }
        source_url = result["source_url"]
        if not source_url:
            result["status"] = "missing_source_url"
            result["message"] = "Missing source_url"
            return result
        try:
            if not self.driver:
                if not self.load_cookies(validate_only=False, auto_close=False):
                    result["status"] = "login_required"
                    result["message"] = "Login required before favoriting"
                    return result

            try:
                self.driver.get(source_url)
            except TimeoutException:
                try:
                    self.driver.execute_script("window.stop();")
                except Exception:
                    pass
            self._safe_wait(3)
            current_url = (self.driver.current_url or "").lower()
            if "login" in current_url or "passport" in current_url:
                result["status"] = "login_required"
                result["message"] = "Login expired while opening note"
                return result

            collect_entry = self._open_collect_panel()
            if not collect_entry:
                result["status"] = "collect_button_not_found"
                result["message"] = "Collect button not found"
                return result
            try:
                collect_entry.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", collect_entry)
            self._safe_wait(1.5)

            folder = self._ensure_folder_exists(folder_name)
            if folder:
                try:
                    folder.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", folder)
                self._safe_wait(0.8)

                confirm = self._find_by_text(["完成", "确定", "保存"], tag="button", timeout=2) or self._find_by_text(
                    ["完成", "确定", "保存"], tag="*", timeout=2
                )
                if confirm:
                    try:
                        confirm.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", confirm)
                    self._safe_wait(1)

                result["success"] = True
                result["status"] = "favorited"
                result["message"] = 'Source note favorited to folder "{}"'.format(folder_name)
                return result

            page_source = (self.driver.page_source or "").lower()
            if "已收藏" in (self.driver.page_source or "") or "取消收藏" in (self.driver.page_source or ""):
                result["success"] = True
                result["status"] = "already_favorited"
                result["message"] = 'Source note already favorited; folder "{}" was not confirmed'.format(folder_name)
                return result
            result["status"] = "folder_not_found"
            result["message"] = 'Collection folder "{}" not found or could not be created'.format(folder_name)
            return result
        except Exception as exc:
            result["status"] = "error"
            result["message"] = "Favorite failed: {}".format(str(exc)[:160])
            return result

    def publish_post(self, draft):
        result = {"success": False, "message": "", "url": ""}
        try:
            if not self.driver:
                if not self.load_cookies(validate_only=False, auto_close=False):
                    if not self.login(auto_close=False):
                        result["message"] = "Login required"
                        return result
            self.driver.get(self.PUBLISH_URL)
            time.sleep(5)
            post = draft.get("post", {}) if isinstance(draft, dict) else {}
            title = post.get("title", "")
            content = _resolve_post_content(post)
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
            for image_path in _resolve_post_image_paths(post):
                if not file_inputs:
                    break
                try:
                    file_inputs[0].send_keys(os.path.abspath(image_path))
                    time.sleep(2)
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
                except Exception:
                    continue
            title_input = None
            for selector in [
                'input[placeholder*="标题"]',
                'input[placeholder*="title"]',
                ".title-input input",
                '[class*="title"] input',
                "#title-textarea",
            ]:
                try:
                    candidate = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if candidate.is_displayed():
                        title_input = candidate
                        break
                except Exception:
                    continue
            if title_input:
                title_input.clear()
                title_input.send_keys(title[:20])
            content_input = None
            for selector in [
                'textarea[placeholder*="分享"]',
                'textarea[placeholder*="内容"]',
                'div[contenteditable="true"]',
                ".ql-editor",
                '[class*="editor"]',
                "#post-textarea",
                ".publish-content textarea",
            ]:
                try:
                    for candidate in self.driver.find_elements(By.CSS_SELECTOR, selector):
                        if candidate.is_displayed():
                            content_input = candidate
                            break
                    if content_input:
                        break
                except Exception:
                    continue
            if content_input:
                if content_input.tag_name.lower() == "textarea":
                    content_input.clear()
                    content_input.send_keys(content[:1000])
                else:
                    self.driver.execute_script("arguments[0].innerText = arguments[1];", content_input, content[:1000])
                    ActionChains(self.driver).click(content_input).perform()
            publish_button = None
            for selector in [
                'button[class*="publish"]',
                ".publish-btn button",
                'button[type="submit"]',
                '[class*="submit"] button',
            ]:
                try:
                    candidate = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if candidate.is_displayed() and candidate.is_enabled():
                        publish_button = candidate
                        break
                except Exception:
                    continue
            if not publish_button:
                for xpath in ['//button[contains(text(),"发布")]', '//button[contains(text(),"Publish")]']:
                    try:
                        candidate = self.driver.find_element(By.XPATH, xpath)
                        if candidate.is_displayed() and candidate.is_enabled():
                            publish_button = candidate
                            break
                    except Exception:
                        continue
            if not publish_button:
                result["message"] = "Publish button not found"
                return result
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior:'smooth', block:'center'});",
                publish_button,
            )
            time.sleep(1)
            publish_button.click()
            time.sleep(8)
            result["success"] = True
            result["message"] = "Publish button clicked, please verify manually"
            result["url"] = self.driver.current_url
            time.sleep(random.uniform(5, 10))
            return result
        except Exception as exc:
            result["message"] = "Error: {}".format(str(exc)[:120])
            return result


class XiaohongshuPublisher:
    COOKIE_FILE = XHS_COOKIE_FILE
    COOKIE_FILE_LEGACY = XHS_COOKIE_FILE_LEGACY

    def __init__(self, username=None, password=None, headless=False, backend=None):
        self.username = username
        self.password = password
        self.headless = headless
        self.backend_name = (backend or XHS_BACKEND or "mcp").lower()
        self.profile_dir = XHS_PROFILE_DIR
        self.driver = None
        self.mcp_backend = MCPPublisherBackend(self)
        self.legacy_backend = LegacySeleniumPublisherBackend(self)

    @property
    def active_backend(self):
        if self.backend_name == "legacy":
            return self.legacy_backend
        return self.mcp_backend

    @property
    def backend(self):
        """Backwards-compatible alias used by older scripts/tests."""
        return self.active_backend

    @backend.setter
    def backend(self, value):
        if isinstance(value, BasePublisherBackend):
            self.backend_name = "legacy" if value is self.legacy_backend else "mcp"
            return
        if isinstance(value, str) and value.strip():
            self.backend_name = value.strip().lower()

    def _sync_driver(self):
        self.driver = self.legacy_backend.driver

    def save_cookies(self):
        result = self.legacy_backend.save_cookies()
        self._sync_driver()
        return result

    def load_cookies(self, validate_only=False, auto_close=True):
        result = self.legacy_backend.load_cookies(validate_only=validate_only, auto_close=auto_close)
        self._sync_driver()
        return result

    def login_status(self):
        return self.active_backend.login_status()

    def validate_credentials(self):
        return self.active_backend.validate_credentials()

    def login(self, auto_close=False):
        result = self.active_backend.login(auto_close=auto_close)
        self._sync_driver()
        return result

    def spawn_background_login(self, status_file, log_file, timeout=180):
        return self.mcp_backend.spawn_login(status_file=status_file, log_file=log_file, timeout=timeout)

    def publish_post(self, draft, dry_run=False):
        if dry_run:
            post = draft.get("post", {}) if isinstance(draft, dict) else {}
            title = post.get("title", "") or post.get("rewritten_content", "")[:30]
            content = _resolve_post_content(post)
            image_paths = _resolve_post_image_paths(post)
            safe_title = "".join(ch for ch in str(title)[:100] if ord(ch) < 127 or "\u4e00" <= ch <= "\u9fff") or "(contains special chars)"
            safe_content = "".join(ch for ch in str(content)[:100] if ord(ch) < 127 or "\u4e00" <= ch <= "\u9fff") or "(contains special chars)"
            print("\n" + "=" * 60)
            print("  DRY RUN - Simulated Publish")
            print("=" * 60)
            print("  Title:   {}".format(safe_title))
            print("  Content: {}...".format(safe_content))
            print("  Images:  {} {}".format(len(image_paths), image_paths[:3] if image_paths else "(none)"))
            print("  Status:  Would be published successfully")
            print("=" * 60)
            return {"success": True, "message": "Dry run OK", "url": ""}
        result = self.active_backend.publish_post(draft)
        self._sync_driver()
        return result

    def favorite_source_post(self, post, folder_name=XHS_FAVORITE_FOLDER):
        result = self.active_backend.favorite_source_post(post, folder_name=folder_name)
        self._sync_driver()
        return result

    def batch_publish(self, drafts, dry_run=True, interval_range=(10, 25)):
        results = []
        total = len(drafts)
        print("\n" + "=" * 60)
        print("  BATCH PUBLISH - Total: {} posts | Mode: {}".format(total, "DRY RUN" if dry_run else "LIVE"))
        print("=" * 60)
        if not dry_run:
            status = self.validate_credentials()
            if status.get("status") != "logged_in" and not self.login(auto_close=False):
                return [{"success": False, "message": "Login failed"}] * total
        for index, draft in enumerate(drafts):
            print("\n--- [{}/{}] ---".format(index + 1, total))
            print("Post: {}".format(draft.get("post", {}).get("title", "Untitled")[:30]))
            results.append(self.publish_post(draft, dry_run=dry_run))
            if index < total - 1:
                delay = random.randint(*interval_range)
                print("Waiting {}s before next post...".format(delay))
                time.sleep(delay)
        success_count = sum(1 for item in results if item.get("success"))
        print("\n" + "=" * 60)
        print("  RESULT: {}/{} published successfully".format(success_count, total))
        print("=" * 60)
        if not dry_run:
            self.cleanup()
        return results

    def cleanup(self):
        self.legacy_backend.cleanup()
        self._sync_driver()


def _write_cli_status(status_file, payload):
    if not status_file:
        return
    _ensure_parent(status_file)
    payload = dict(payload)
    payload["updated_at"] = datetime.now().isoformat()
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Xiaohongshu Publisher")
    parser.add_argument("--action", "-a", choices=["login", "publish", "batch", "status"], default="login")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without actually publishing")
    parser.add_argument("--count", "-n", type=int, default=3, help="Number of posts to publish")
    parser.add_argument("--backend", choices=["mcp", "legacy"], default=None)
    parser.add_argument("--status-file", default="", help="Optional status output JSON path")
    args = parser.parse_args()

    publisher = XiaohongshuPublisher(headless=False, backend=args.backend)

    if args.action == "login":
        success = publisher.login(auto_close=False)
        print("\nLogin complete!" if success else "\nLogin failed. Please try again.")
        _write_cli_status(
            args.status_file,
            {"success": success, "status": "logged_in" if success else "idle", "backend": publisher.backend_name},
        )
        return

    if args.action == "status":
        status = publisher.login_status()
        print(json.dumps(status, ensure_ascii=False))
        _write_cli_status(args.status_file, status)
        return

    if args.action == "batch":
        from ui.draft_manager import DraftManager

        drafts = DraftManager().list_drafts()[: args.count]
        if not drafts:
            print("No drafts found! Run crawl_latest_aigc.py first.")
            _write_cli_status(args.status_file, {"success": False, "status": "idle", "message": "No drafts found"})
            return
        results = publisher.batch_publish(drafts, dry_run=args.dry_run)
        for index, (draft, result) in enumerate(zip(drafts, results)):
            label = "[OK]" if result.get("success") else "[FAIL]"
            title = draft.get("post", {}).get("title", "?")[:30]
            print("{} {}: {}".format(label, index + 1, title))
        _write_cli_status(
            args.status_file,
            {"success": all(item.get("success") for item in results), "status": "done", "count": len(results)},
        )
        return

    if args.action == "publish":
        from ui.draft_manager import DraftManager

        drafts = DraftManager().list_drafts()[:1]
        if not drafts:
            print("No drafts found! Run crawl_latest_aigc.py first.")
            return
        result = publisher.publish_post(drafts[0], dry_run=args.dry_run)
        print("Result: {}".format(result))
        _write_cli_status(args.status_file, result)


if __name__ == "__main__":
    main()
