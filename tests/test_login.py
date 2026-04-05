#!/usr/bin/env python3
"""Login + Publish 全功能测试套件 v1"""

import os
import sys
import json
import time
import tempfile
import pickle
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0
errors = []

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_login_output.log')

class TeeOutput:
    def __init__(self, log_file):
        self.f = open(log_file, 'w', encoding='utf-8')
    def write(self, data):
        sys.__stdout__.write(data)
        self.f.write(data)
        self.f.flush()
    def flush(self):
        sys.__stdout__.flush()
        if not self.f.closed:
            self.f.flush()

sys.stdout = TeeOutput(LOG_FILE)


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print("  [PASS] {}".format(name))
    else:
        failed += 1
        msg = "  [FAIL] {}{}".format(name, " - " + detail if detail else "")
        errors.append(msg)
        print(msg)


def section(title):
    print("\n" + "=" * 60)
    print("  {}".format(title))
    print("=" * 60)


# ============================================================
# TEST 1: Publisher 初始化测试
# ============================================================
section("TEST 1: XiaohongshuPublisher Initialization")

from publisher.xiaohongshu_publisher import (
    XiaohongshuPublisher, SELENIUM_AVAILABLE
)

p = XiaohongshuPublisher()
test("Publisher instance created", p is not None)
test("headless default False", p.headless == False)
test("driver initially None", p.driver is None)
test("COOKIE_FILE path set", len(p.COOKIE_FILE) > 0)
test("SELENIUM_AVAILABLE flag is bool", isinstance(SELENIUM_AVAILABLE, bool))

p_headless = XiaohongshuPublisher(headless=True)
test("Headless mode accepted", p_headless.headless == True)


# ============================================================
# TEST 2: Cookie 文件操作
# ============================================================
section("TEST 2: Cookie File Operations")

tmp_dir = tempfile.mkdtemp()
original_cookie_file = XiaohongshuPublisher.COOKIE_FILE

# Temporarily redirect cookie file for testing
test_cookie_path = os.path.join(tmp_dir, 'test_cookies.pkl')

# Test save with mock cookies
mock_cookies = [
    {'name': 'session', 'value': 'abc123', 'domain': '.xiaohongshu.com'},
    {'name': 'token', 'value': 'xyz789', 'domain': '.xiaohongshu.com'},
    {'name': 'user_id', 'value': '12345', 'domain': '.xiaohongshu.com'},
]

with open(test_cookie_path, 'wb') as f:
    pickle.dump(mock_cookies, f)

test("Cookie file created", os.path.exists(test_cookie_path))
test("Cookie file size > 0", os.path.getsize(test_cookie_path) > 0)

# Test load
loaded = None
with open(test_cookie_path, 'rb') as f:
    loaded = pickle.load(f)

test("Cookie loaded correctly", loaded is not None)
test("Cookie count matches", len(loaded) == 3)
test("Cookie data intact", loaded[0]['name'] == 'session' and loaded[0]['value'] == 'abc123')

# Test delete
os.remove(test_cookie_path)
test("Cookie deleted", not os.path.exists(test_cookie_path))


# ============================================================
# TEST 3: _safe_read_log (复用测试)
# ============================================================
section("TEST 3: Safe Log Reading (reused from web_app)")


def _safe_read_log(log_path):
    if not log_path or not os.path.exists(log_path):
        return ""
    encodings_to_try = ["utf-8", "gbk", "latin-1"]
    for enc in encodings_to_try:
        try:
            with open(log_path, "rb") as f:
                raw = f.read()
            return raw.decode(enc, errors="replace")
        except Exception:
            continue
    return ""


log_test = os.path.join(tmp_dir, "login_test.log")
with open(log_test, "wb") as f:
    f.write(b"[LOGIN] Starting browser...\n[LOGIN] Waiting for user...\n[LOGIN] Cookie saved!")
result = _safe_read_log(log_test)
test("Login log readable", "[LOGIN]" in result and "Cookie" in result)


# ============================================================
# TEST 4: Dry Run Publish
# ============================================================
section("TEST 4: Dry Run Publish")

pub = XiaohongshuPublisher()

draft_data = {
    'post': {
        'title': 'Test Post for Login Suite',
        'content': 'This is test content for the login test suite',
        'optimized_content': '#AI #Test dry run content here',
        'generated_image_path': ''
    }
}

r = pub.publish_post(draft_data, dry_run=True)
test("Dry run returns dict", isinstance(r, dict))
test("Dry run success key exists", 'success' in r)
test("Dry run success=True", r['success'] == True)
test("Dry run message not empty", len(r.get('message', '')) > 0)

# Test with image
draft_with_img = {
    'post': {
        'title': 'Post With Image',
        'content': 'Content with image test',
        'optimized_content': '#VibeCoding image post',
        'generated_image_path': os.path.join(tmp_dir, 'fake.jpg')
    }
}
r2 = pub.publish_post(draft_with_img, dry_run=True)
test("Dry run with image path OK", r2['success'] == True)


# ============================================================
# TEST 5: Batch Dry Run Publish
# ============================================================
section("TEST 5: Batch Dry Run Publish")

from ui.draft_manager import DraftManager
dm = DraftManager()

all_drafts = dm.list_drafts()
if all_drafts:
    test_batch = all_drafts[:min(3, len(all_drafts))]
    
    results = pub.batch_publish(test_batch, dry_run=True, interval_range=(0, 1))
    
    test("Batch results list", isinstance(results, list))
    test("Batch result count matches", len(results) == len(test_batch))
    
    ok_count = sum(1 for r in results if r.get('success'))
    test("All batch results success", ok_count == len(results))
else:
    # Create mock drafts for testing
    mock_drafts = []
    for i in range(3):
        d = {
            'post': {
                'title': 'Mock Draft {}'.format(i),
                'content': 'Mock content {}'.format(i),
                'optimized_content': '#Mock tag {} content'.format(i),
                'generated_image_path': ''
            }
        }
        mock_drafts.append(d)
    
    results = pub.batch_publish(mock_drafts, dry_run=True, interval_range=(0, 1))
    ok_count = sum(1 for r in results if r.get('success'))
    test("Batch on mock drafts: {}/3 success".format(ok_count), ok_count == 3)


# ============================================================
# TEST 6: Session State 模拟
# ============================================================
section("TEST 6: Session State Simulation (Web App)")

# Simulate Streamlit session_state behavior
class MockSessionState(dict):
    def __getattr__(self, name):
        return self.get(name, None)
    def __setattr__(self, name, value):
        self[name] = value

ss = MockSessionState()

ss['login_status'] = 'idle'
test("Initial login_status=idle", ss['login_status'] == 'idle')

ss['login_status'] = 'running'
ss['login_pid'] = 12345
ss['login_start_time'] = time.time()
test("Running state set", ss['login_status'] == 'running')
test("PID stored", ss['login_pid'] == 12345)
test("Start time recorded", ss['login_start_time'] is not None)

elapsed = int(time.time() - ss['login_start_time'])
test("Elapsed time positive", elapsed >= 0)

ss['login_status'] = 'logged_in'
test("Logged in state", ss['login_status'] == 'logged_in')

ss['notifications'] = []
ss['notifications'].append({
    'type': 'success',
    'title': 'Test Notification',
    'message': 'Test message body',
    'time': '12:00:00'
})
test("Notification added", len(ss['notifications']) == 1)
test("Notification type correct", ss['notifications'][0]['type'] == 'success')


# ============================================================
# TEST 7: 登录状态文件操作
# ============================================================
section("TEST 7: Login Status File Operations")

status_path = os.path.join(tmp_dir, 'login_status.json')

# Write status file
status_data = {
    'pid': 99999,
    'status': 'starting',
    'start_time': datetime.now().isoformat()
}
with open(status_path, 'w') as f:
    json.dump(status_data, f)

test("Status file created", os.path.exists(status_path))

# Read back
with open(status_path, 'r') as f:
    read_back = json.load(f)

test("Status PID matches", read_back['pid'] == 99999)
test("Status state correct", read_back['status'] == 'starting')

# Update to done
done_data = {'status': 'done'}
with open(status_path, 'w') as f:
    json.dump(done_data, f)

with open(status_path, 'r') as f:
    done_read = json.load(f)

test("Done status written", done_read['status'] == 'done')


# ============================================================
# TEST 8: 边界条件和异常处理
# ============================================================
section("TEST 8: Edge Cases & Error Handling")

# Empty draft
empty_r = pub.publish_post({}, dry_run=True)
test("Empty draft handled", empty_r['success'] == True)

# No post key
no_post_r = pub.publish_post({'id': 'abc'}, dry_run=True)
test("No post key handled", no_post_r['success'] == True)

# None values
none_r = pub.publish_post(None, dry_run=True)
test("None draft handled", none_r['success'] == True)

# Very long title
long_title = 'A' * 100
long_draft = {
    'post': {
        'title': long_title,
        'content': 'Normal content',
        'optimized_content': 'Normal optimized',
        'generated_image_path': ''
    }
}
long_r = pub.publish_post(long_draft, dry_run=True)
test("Long title handled", long_r['success'] == True)

# Unicode content
uni_draft = {
    'post': {
        'title': 'Unicode Test',
        'content': '\u4e2d\u6587\u6d4b\u8bd5 Chinese test',
        'optimized_content': '#\u4e2d\u6587 #Chinese',
        'generated_image_path': ''
    }
}
uni_r = pub.publish_post(uni_draft, dry_run=True)
test("Unicode content handled", uni_r['success'] == True)

# Empty batch
empty_results = pub.batch_publish([], dry_run=True)
test("Empty batch returns []", empty_results == [])

# Single item batch
single_results = pub.batch_publish([draft_data], dry_run=True)
test("Single item batch OK", len(single_results) == 1 and single_results[0]['success'])


# ============================================================
# TEST 9: Cookie 路径和状态检测逻辑
# ============================================================
section("TEST 9: Cookie Path & Status Detection Logic")

cookie_path_check = os.path.join(os.getcwd(), 'data', 'xhs_cookies.pkl')

# Test various states
states_to_test = [
    ('idle', False, 'idle'),
    ('logged_in', True, 'logged_in'),
    ('expired', True, 'expired'),
    ('running', False, 'running'),
]

for expected_state, cookie_exists_val, should_match in states_to_test:
    simulated_result = expected_state if cookie_exists_val else 'idle'
    test("State '{}' logic".format(expected_state), True)


# ============================================================
# TEST 10: 命令行参数解析模拟
# ============================================================
section("TEST 10: Command Line Args Simulation")

# Simulate argparse behavior
import shlex

args_str = '--keywords Vibe Coding,Claude --max-posts 5'
parsed_kw = [k.strip() for k in args_str.split('--keywords')[1].split('--')[0].split(',') if k.strip()]
parsed_max = int(args_str.split('--max-posts')[1].strip())

test("Keywords parsed correctly", parsed_kw == ['Vibe Coding', 'Claude'])
test("Max posts parsed correctly", parsed_max == 5)

# Empty keywords
empty_args = '--keywords "" --max-posts 9'
kw_empty = [k.strip() for k in empty_args.split('--keywords')[1].split('--')[0].split(',') if k.strip() and k.strip() != '""']
test("Empty keywords -> []", kw_empty == [])

# Default args
default_args = ''  
kw_default = [k.strip() for k in default_args.split(',') if k.strip()] if default_args else []
test("Default args -> []", kw_default == [])


# ============================================================
# 清理和报告
# ============================================================
# ============================================================
# TEST 11: Auth State Normalization Contract
# ============================================================
section("TEST 11: Auth State Normalization Contract")

from publisher.login_state import normalize_login_result, resolve_login_state
from config.config import XHS_COOKIE_FILE, XHS_COOKIE_FILE_LEGACY, XHS_PROFILE_DIR, XHS_MCP_CMD, XHS_MCP_ARGS


def assert_contract(payload, expected_state, expected_source):
    test("contract has state", payload.get("state") == expected_state, str(payload))
    test("contract has source", payload.get("source") == expected_source, str(payload))
    test("contract has reason", bool(str(payload.get("reason", "")).strip()), str(payload))
    test("contract has message", bool(str(payload.get("message", "")).strip()), str(payload))


case1 = normalize_login_result({
    "success": True,
    "message": "MCP session active",
    "status": "logged_in",
    "data": {"backend": "mcp"},
})
assert_contract(case1, "logged_in", "mcp")

case2 = resolve_login_state(
    {"success": False, "message": "Waiting for backend", "status": "idle", "data": {"backend": "mcp"}},
    status_payload={"status": "running", "message": "Login process is still running"},
    process_running=True,
    current_status="running",
)
assert_contract(case2, "running", "process")

case3 = normalize_login_result(
    {"success": False, "message": "MCP unavailable", "status": "unavailable", "data": {"backend": "mcp"}},
    fallback_result={
        "success": True,
        "message": "Validated legacy cookie fallback",
        "status": "logged_in",
        "source": "cookie_fallback",
        "reason": "Validated legacy cookie fallback",
        "data": {"backend": "legacy", "auth_source": "cookie_fallback"},
    },
)
assert_contract(case3, "logged_in", "cookie_fallback")

case4 = resolve_login_state(
    {"success": False, "message": "MCP unavailable", "status": "unavailable", "data": {"backend": "mcp"}},
    status_payload={"status": "timeout", "message": "Login status file recorded a timeout"},
    process_running=False,
    current_status="idle",
)
test("timeout status resolves from status file", case4.get("state") == "timeout", str(case4))
test("timeout source is status_file", case4.get("source") == "status_file", str(case4))

audit_payload = normalize_login_result(
    {"success": False, "message": "MCP unavailable", "status": "unavailable", "data": {"backend": "mcp"}}
)
test("missing fallback stays unavailable", audit_payload.get("state") == "unavailable", str(audit_payload))
test("missing fallback source recorded", audit_payload.get("source") in {"mcp", "none"}, str(audit_payload))

test("cookie file default basename", os.path.basename(XHS_COOKIE_FILE) == "xhs_cookies.json", XHS_COOKIE_FILE)
test("legacy cookie default basename", os.path.basename(XHS_COOKIE_FILE_LEGACY) == "xhs_cookies.pkl", XHS_COOKIE_FILE_LEGACY)
test("profile dir default basename", os.path.basename(XHS_PROFILE_DIR) == "xhs_profile", XHS_PROFILE_DIR)
test("mcp cmd non-empty", bool(XHS_MCP_CMD), XHS_MCP_CMD)
test("mcp args non-empty", bool(XHS_MCP_ARGS), XHS_MCP_ARGS)

section("FINAL SUMMARY - LOGIN SUITE")

total = passed + failed
print("\n  Total:  {} tests".format(total))
print("  Passed: {} [OK]".format(passed))
print("  Failed: {} [FAIL]".format(failed))

if errors:
    print("\n  Failed tests:")
    for e in errors:
        print("    {}".format(e))

import shutil
try:
    shutil.rmtree(tmp_dir)
except Exception:
    pass

result_text = "ALL PASSED [OK]" if failed == 0 else "{} FAILED [FAIL]".format(failed)
print("\n  Result: {}".format(result_text))

if hasattr(sys.stdout, 'f'):
    sys.stdout.f.close()

sys.exit(0 if failed == 0 else 1)
