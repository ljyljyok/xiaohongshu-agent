#!/usr/bin/env python3
"""Dry-run publish test"""
import sys, os
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from publisher.xiaohongshu_publisher import XiaohongshuPublisher
from ui.draft_manager import DraftManager

print("=" * 60)
print("  STEP 3/3: DRY-RUN PUBLISH")
print("=" * 60)

p = XiaohongshuPublisher()
dm = DraftManager()
drafts = dm.list_drafts()[:5]

if not drafts:
    print("[INFO] No saved drafts found; using synthetic smoke-test draft")
    drafts = [
        {
            "id": "smoke-test-draft",
            "status": "draft",
            "post": {
                "title": "Smoke test post for dry-run publish",
                "content": "This is a synthetic draft used to validate the publisher dry-run path.",
                "rewritten_content": "This is a synthetic draft used to validate the publisher dry-run path.",
                "optimized_content": "This is a synthetic draft used to validate the publisher dry-run path.",
                "final_image_paths": [],
            },
        }
    ]

print("[INFO] Testing publish for {} drafts (dry-run)".format(len(drafts)))
print()

results = p.batch_publish(drafts, dry_run=True)

ok = sum(1 for r in results if r.get('success'))
total = len(results)

print()
print("=" * 60)
print("  RESULT: {}/{} posts ready".format(ok, total))
if ok == total:
    print("  STATUS: ALL PASSED!")
print("=" * 60)
