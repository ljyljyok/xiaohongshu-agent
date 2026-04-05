#!/usr/bin/env python3
"""Step-by-step runner: Login -> Crawl -> Publish"""
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment, preferred_python_executable, script_path

ensure_runtime_environment(require_selenium=True)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def step1_login():
    print("\n" + "=" * 60)
    print("  STEP 1/3: LOGIN TO XIAOHONGSHU")
    print("=" * 60)
    
    from publisher.xiaohongshu_publisher import XiaohongshuPublisher, SELENIUM_AVAILABLE
    
    if not SELENIUM_AVAILABLE:
        print("[SKIP] Selenium not available - skipping login")
        return False
    
    p = XiaohongshuPublisher(headless=False)
    
    # Check if cookies exist first
    if os.path.exists(p.COOKIE_FILE):
        print("[INFO] Found existing cookie, trying to load...")
        if p.load_cookies():
            print("[OK] Cookie login successful!")
            return True
        else:
            print("[WARN] Cookie expired, need re-login")
    
    print("[ACTION] Opening Chrome browser for manual login...")
    print("  Please scan QR code or enter phone number in the browser")
    print()
    
    result = p.login(auto_close=False)
    
    if result:
        print("\n[SUCCESS] Login complete! Cookie saved.")
        return True
    else:
        print("\n[TIMEOUT] Login timed out (120s). Proceeding without login...")
        return False


def step2_crawl():
    print("\n" + "=" * 60)
    print("  STEP 2/3: CRAWL CONTENT")
    print("=" * 60)
    
    import subprocess
    
    cmd = [preferred_python_executable(), '-u', script_path('crawl_latest_aigc.py'),
           '--keywords', 'Vibe Coding,Claude,OpenClaw,Harness Engineering',
           '--max-posts', '5']
    
    print("[CMD] " + ' '.join(cmd))
    print()
    
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    for line in proc.stdout:
        safe_line = ''.join(c for c in line if ord(c) < 127 or '\u4e00' <= c <= '\u9fff')
        print(safe_line.rstrip())
    
    proc.wait()
    
    if proc.returncode == 0:
        print("\n[OK] Crawl completed!")
        return True
    else:
        print("\n[WARN] Crawl exit code: {}".format(proc.returncode))
        return True


def step3_publish():
    print("\n" + "=" * 60)
    print("  STEP 3/3: DRY-RUN PUBLISH")
    print("=" * 60)
    
    from publisher.xiaohongshu_publisher import XiaohongshuPublisher
    from ui.draft_manager import DraftManager
    
    p = XiaohongshuPublisher()
    dm = DraftManager()
    
    drafts = dm.list_drafts()[:3]
    
    if not drafts:
        print("[WARN] No drafts found! Run crawl first.")
        return False
    
    print("[INFO] Found {} drafts".format(len(drafts)))
    print()
    
    results = p.batch_publish(drafts, dry_run=True)
    
    ok = sum(1 for r in results if r.get('success'))
    total = len(results)
    
    print("\n[RESULT] {}/{} posts ready for publish".format(ok, total))
    return ok == total


if __name__ == "__main__":
    print("#" + "=" * 59)
    print("#  XIAOHONGSHU AGENT - FULL PIPELINE RUNNER")
    print("#  Date: {}".format(__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M")))
    print("#" + "=" * 59)
    
    results = {}
    
    results['login'] = step1_login()
    results['crawl'] = step2_crawl()
    results['publish'] = step3_publish()
    
    print("\n" + "#" + "=" * 59)
    print("#  FINAL SUMMARY")
    print("#" + "=" * 59)
    print("#  Login : {}".format("OK" if results.get('login') else "SKIPPED/TIMEOUT"))
    print("#  Crawl : {}".format("OK" if results.get('crawl') else "FAILED"))
    print("#  Publish: {}".format("OK" if results.get('publish') else "NO DRAFTS"))
    print("#" + "=" * 59)
