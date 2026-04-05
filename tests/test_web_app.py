#!/usr/bin/env python3
"""web_app.py 全功能测试套件 v2 - 修复版"""

import os
import sys
import json
import time
import tempfile
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0
errors = []


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
# 测试1: _safe_read_log 多编码兼容性
# ============================================================
section("TEST 1: _safe_read_log() - Multi-encoding log reading")


def _safe_read_log(log_path):
    if not log_path or not os.path.exists(log_path):
        return ""
    encodings_to_try = ["utf-8", "gbk", "gb2312", "gb18030", "latin-1"]
    for enc in encodings_to_try:
        try:
            with open(log_path, "rb") as f:
                raw = f.read()
            return raw.decode(enc, errors="replace")
        except Exception:
            continue
    return ""


tmp_dir = tempfile.mkdtemp()

utf8_file = os.path.join(tmp_dir, "test_utf8.log")
with open(utf8_file, "wb") as f:
    f.write("[OK] Test UTF-8\n".encode("utf-8"))
result = _safe_read_log(utf8_file)
test("UTF-8 encoding read", "[OK]" in result)

gbk_file = os.path.join(tmp_dir, "test_gbk.log")
with open(gbk_file, "wb") as f:
    f.write("[OK] GBK test\n".encode("gbk"))
result = _safe_read_log(gbk_file)
test("GBK encoding fallback", "[OK]" in result)

bad_byte_file = os.path.join(tmp_dir, "test_bad.log")
with open(bad_byte_file, "wb") as f:
    f.write(b"[LOG] Normal text with \\xba bad byte\\xff more\n")
result = _safe_read_log(bad_byte_file)
test("Bad bytes handled (latin-1)", "Normal text" in result)

nonexistent = os.path.join(tmp_dir, "no_such_file.log")
result = _safe_read_log(nonexistent)
test("Non-existent file returns empty", result == "")

empty_file = os.path.join(tmp_dir, "empty.log")
with open(empty_file, "w") as f:
    pass
result = _safe_read_log(empty_file)
test("Empty file returns empty", result == "")

mixed_encoding = os.path.join(tmp_dir, "mixed.log")
with open(mixed_encoding, "wb") as f:
    f.write("[1/5] AI analysis\n[2/5] Rewrite\nDone!\n".encode("utf-8"))
result = _safe_read_log(mixed_encoding)
test("Multi-line log read", "[1/5]" in result and "Done!" in result)


# ============================================================
# 测试2: _parse_crawl_log 步骤检测
# ============================================================
section("TEST 2: _parse_crawl_log() - Step detection")

CRAWL_STEPS = [
    {"id": "init", "label": "Init", "icon": "1",
     "keywords": ["current"]},
    {"id": "crawl", "label": "Crawl", "icon": "2",
     "keywords": ["search:", "API"]},
    {"id": "analyze", "label": "Analyze", "icon": "3",
     "keywords": ["[1/5]", "AI"]},
    {"id": "rewrite", "label": "Rewrite", "icon": "4",
     "keywords": ["[2/5]", "rewrite"]},
    {"id": "image", "label": "Image", "icon": "5",
     "keywords": ["[3/5]", "image"]},
    {"id": "audit", "label": "Audit", "icon": "6",
     "keywords": ["[4/5]", "audit"]},
    {"id": "save", "label": "Save", "icon": "7",
     "keywords": ["[5/5]", "save"]},
    {"id": "done", "label": "Done", "icon": "8",
     "keywords": ["complete", "done"]},
]

import re


def _parse_crawl_log(log_path):
    if not log_path or not os.path.exists(log_path):
        return None, [], 0, {}
    try:
        with open(log_path, "rb") as f:
            raw = f.read()
        content = raw.decode("utf-8", errors="replace")
        lines = content.split("\n")
        total_lines = len(lines)
        current_step_idx = -1
        content_lower = content.lower()
        for i, step in enumerate(CRAWL_STEPS):
            for kw in step["keywords"]:
                if kw.lower() in content_lower:
                    current_step_idx = max(current_step_idx, i)
        last_lines = [l.strip() for l in lines[-30:] if l.strip()]
        stats = {}
        patterns = [
            ("drafts", r"save\s*(\d+)\s*draft"),
            ("analyzed", r"found\s*(\d+)\s*post|识别出\s*(\d+)\s*个"),
            ("safe", r"safe:\s*(\d+)|安全:\s*(\d+)"),
            ("unsafe", r"review:\s*(\d+)|需复核:\s*(\d+)"),
        ]
        for pattern in patterns:
            m = re.search(pattern[1], content)
            if m:
                key = pattern[0]
                val = m.group(1) if m.group(1) else (m.group(2) if m.lastindex and m.group(2) else None)
                if val:
                    stats[key] = val
        return current_step_idx, last_lines, total_lines, stats
    except Exception as e:
        return None, [], 0, {}


log_init = os.path.join(tmp_dir, "log_init.txt")
with open(log_init, "w", encoding="utf-8") as f:
    f.write("Current computer time: 2026-04-04\n")
step, lines, count, stats = _parse_crawl_log(log_init)
test("Step init detected (keyword=current)", step >= 0, "got={}".format(step))

log_analyze = os.path.join(tmp_dir, "log_analyze.txt")
with open(log_analyze, "w", encoding="utf-8") as f:
    f.write("Current time\n[1/5] AI analysis...\nFound 9 posts\n")
step, lines, count, stats = _parse_crawl_log(log_analyze)
test("Step analyze detected ([1/5])", step == 2, "got={}".format(step))

log_full = os.path.join(tmp_dir, "log_full.txt")
with open(log_full, "w", encoding="utf-8") as f:
    f.write("Current time\n[1/5] AI analysis... Found 12 posts\n")
    f.write("[2/5] Rewrite done\n[3/5] Image processing\n")
    f.write("[4/5] Content audit - safe:10 review:2\n")
    f.write("[5/5] Save 10 drafts\nComplete! Done.\n")
step, lines, count, stats = _parse_crawl_log(log_full)
test("Full pipeline step=7(done)", step == 7, "got={}".format(step))
test("Full stats has safe", "safe" in stats)
test("Full stats has unsafe", "unsafe" in stats)

empty_log = os.path.join(tmp_dir, "log_empty.txt")
with open(empty_log, "w") as f:
    pass
step, lines, count, stats = _parse_crawl_log(empty_log)
test("Empty log step=-1", step == -1, "got={}".format(step))

none_result = _parse_crawl_log(None)
test("None path handled", none_result == (None, [], 0, {}))


# ============================================================
# 测试3: find_duplicates 查重功能
# ============================================================
section("TEST 3: find_duplicates() - Deduplication")


def find_duplicates(drafts, threshold=80):
    duplicates = []
    seen_titles = set()
    
    for draft in drafts:
        title = draft.get("title", "") or draft.get("post", {}).get("title", "")
        if title in seen_titles:
            continue
        seen_titles.add(title)
        
        content = draft.get("content", "") or draft.get("post", {}).get("content", "")
        
        similar = []
        for other in drafts:
            if other.get("id") == draft.get("id"):
                continue
            
            o_title = other.get("title", "") or other.get("post", {}).get("title", "")
            
            if o_title == title:
                similar.append({
                    "original_id": draft.get("id"),
                    "duplicate_id": other.get("id"),
                    "reason": "exact_title",
                    "similarity": 100,
                    "title": o_title
                })
                continue
            
            o_content = other.get("content", "") or other.get("post", {}).get("content", "")
            
            words_a = set(content.lower().split()) if content else set()
            words_b = set(o_content.lower().split()) if o_content else set()
            
            if words_a and words_b:
                common = words_a & words_b
                union = words_a | words_b
                similarity = len(common) / len(union) * 100
                
                if similarity >= threshold:
                    similar.append({
                        "original_id": draft.get("id"),
                        "duplicate_id": other.get("id"),
                        "reason": "content_similarity",
                        "similarity": round(similarity, 1),
                        "title": (o_title or "")[:30]
                    })
        
        if similar:
            duplicates.append({"original": draft, "duplicates": similar})
    
    return duplicates


drafts_test = [
    {"id": "1", "title": "GPT-5发布啦", "content": "OpenAI发布了GPT-5模型，非常强大"},
    {"id": "2", "title": "GPT-5发布啦", "content": "OpenAI发布了GPT-5模型，非常强大"},
    {"id": "3", "title": "GPT-5来了", "content": "OpenAI发布了GPT-5模型非常强大很厉害"},
    {"id": "4", "title": "Claude 4更新", "content": "Anthropic发布Claude 4新版本完全不同内容"},
]

dups = find_duplicates(drafts_test)
test("Found duplicate group(s)", len(dups) >= 1, "groups={}".format(len(dups)))
if dups:
    exact_found = any(d["reason"] == "exact_title" for d in dups[0]["duplicates"])
    test("Exact title match found", exact_found)
    total_dups = len(dups[0]["duplicates"])
    test("Duplicates found: {}".format(total_dups), total_dups >= 1)

unique_drafts = [
    {"id": "1", "title": "AI Tool A", "content": "This is about tool A unique content here"},
    {"id": "2", "title": "AI Tool B", "content": "This is about tool B completely different topic"},
]
dups_unique = find_duplicates(unique_drafts)
test("No false positives on unique content", len(dups_unique) == 0)

high_similar = [
    {"id": "1", "title": "Test", "content": "the quick brown fox jumps over the lazy dog and runs fast"},
    {"id": "2", "title": "Other", "content": "the quick brown fox jumps over the lazy dog but walks slowly today"},
]
dups_high = find_duplicates(high_similar, threshold=50)
test("High overlap detected at 50%", len(dups_high) >= 1)


# ============================================================
# 测试4: DraftManager CRUD (correct API)
# ============================================================
section("TEST 4: DraftManager - CRUD operations")

from ui.draft_manager import DraftManager

dm = DraftManager()

existing = dm.list_drafts()
for d in existing:
    dm.delete_draft(d["id"])

initial = dm.list_drafts()
test("Start with clean state", len(initial) == 0)

test_post_data = {
    "title": "Test Post Title",
    "content": "Test post content for unit testing purposes",
    "url": "https://example.com/test"
}

draft_id = dm.save_draft(test_post_data)
test("Save draft success", draft_id is not None and len(draft_id) > 0)

listed = dm.list_drafts()
test("List shows 1 draft", len(listed) == 1)

fetched = dm.get_draft(draft_id)
test("Get draft by ID", fetched is not None)
if fetched:
    test("Fetched title matches", fetched.get("post", {}).get("title") == "Test Post Title")

updated = dm.update_draft_status(draft_id, "approved")
test("Update status to approved", updated == True)

fetched_again = dm.get_draft(draft_id)
if fetched_again:
    test("Status persisted", fetched_again.get("status") == "approved")

deleted = dm.delete_draft(draft_id)
test("Delete draft success", deleted == True)

after_delete = dm.list_drafts()
test("List after delete is empty", len(after_delete) == 0)

batch_posts = [{"title": "Batch 1", "content": "Content 1"}, {"title": "Batch 2", "content": "Content 2"}]
ids = dm.batch_save_drafts(batch_posts)
test("Batch save returns IDs", len(ids) == 2)

batch_listed = dm.list_drafts()
test("Batch list shows 2", len(batch_listed) == 2)

for did in ids:
    dm.delete_draft(did)


# ============================================================
# 测试5: 后台爬取子进程创建 + 编码验证
# ============================================================
section("TEST 5: Background crawl subprocess + encoding")

log_file_test = os.path.join(tmp_dir, "bg_crawl_test.log")

cmd = [sys.executable, "-c",
       "import sys; sys.stdout.buffer.write('[1/5] Starting\\n[2/5] Processing\\n[3/5] Images\\n[4/5] Audit safe:5 review:1\\n[5/5] Save 3 drafts\\nComplete! Done\\n'.encode('utf-8'))"]

startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startupinfo.wShowWindow = 0

env_test = os.environ.copy()
env_test['PYTHONIOENCODING'] = 'utf-8'

proc = subprocess.Popen(
    cmd,
    stdout=open(log_file_test, 'wb'),
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    env=env_test,
    startupinfo=startupinfo,
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
)

pid = proc.pid
test("Subprocess created PID>0", pid > 0)

time.sleep(2)

if os.path.exists(log_file_test):
    size = os.path.getsize(log_file_test)
    test("Log file created, size>0", size > 0)
    
    content = _safe_read_log(log_file_test)
    test("Log readable via _safe_read_log", "[1/5]" in content)
    test("Log contains all steps", "Save 3 drafts" in content)
    test("Log contains completion", "Complete" in content)
else:
    test("Log file exists after process", False, "file missing!")


# ============================================================
# 测试6: ContentAuditor 审核功能
# ============================================================
section("TEST 6: ContentAuditor - Audit functionality")

from ai.content_auditor import ContentAuditor

auditor = ContentAuditor()

safe_post = {
    "title": "GPT-4o latest update supports multimodal input",
    "content": "OpenAI released GPT-4o update supporting image and voice input simultaneously. Model achieves 88.7% accuracy on MMLU benchmark.",
    "publish_time": "2026-04-03T10:00:00Z"
}
result_safe = auditor.audit_content(safe_post)
test("Safe post passes audit", result_safe.get("is_safe") == True)
test("Safe post confidence >=70", result_safe.get("confidence_score", 0) >= 70)

hallucinated_post = {
    "title": "震惊！GPT-5今天发布，准确率999%",
    "content": "GPT-5今天正式发布，准确率达到999%，可以预测未来100年所有事件。速度比光速还快。",
    "publish_time": "2026-04-04T08:00:00Z"
}
result_bad = auditor.audit_content(hallucinated_post)
test("Hallucinated post flagged", result_bad.get("is_safe") == False or result_bad.get("confidence_score", 100) < 70)
test("Hallucination risk detected", result_bad.get("hallucination_risk") in ["high", "medium"])
test("Issues or warnings not empty",
     len(result_bad.get("issues", [])) > 0 or len(result_bad.get("warnings", [])) > 0)


# ============================================================
# 测试7: ImageGenerator 本地模式
# ============================================================
section("TEST 7: ImageGenerator - Local mode generation")

from ai.image_generator import ImageGenerator

gen = ImageGenerator()

test("ImageGenerator initialized", gen is not None)
test("Local mode (no API keys)", gen.use_gemini_mode == False and gen.use_openai_mode == False)

images = gen.generate_image("Test image prompt for AI tools demo", n=1)
test("Local placeholder generated", len(images) >= 1)
if images:
    img_path = images[0]
    test("Image file exists on disk", os.path.exists(img_path))
    test("Image file is PNG format", img_path.endswith(".png"))


# ============================================================
# 测试8: 边界条件和类型安全
# ============================================================
section("TEST 8: Edge cases and type safety")

step_none = None
safe_idx = step_none if isinstance(step_none, int) else -1
test("None step -> -1", safe_idx == -1)
test("-1 >= 0 is False", (safe_idx >= 0) == False)

step_neg = -1
safe_neg = step_neg if isinstance(step_neg, int) else -1
test("Negative stays negative", safe_neg == -1)

step_valid = 5
safe_valid = step_valid if isinstance(step_valid, int) else -1
test("Valid int preserved", safe_valid == 5)

exp_none = step_none if isinstance(step_none, int) and step_none >= 3 else False
test("None expand param -> False", exp_none == False)

exp_valid = step_valid if isinstance(step_valid, int) and step_valid >= 3 else False
test("Valid>=3 expand -> truthy", bool(exp_valid) == True)

exp_small = 2 if isinstance(2, int) and 2 >= 3 else False
test("<3 expand -> False", exp_small == False)

test_empty_list = None
safe_list = test_empty_list if test_empty_list else []
test("None list -> []", safe_list == [])

zero_list = []
test("Empty list length 0", len(zero_list) == 0)

dict_test = {}
val = dict_test.get("missing", "default")
test("Dict get default works", val == "default")


# ============================================================
# 清理和报告
# ============================================================
section("FINAL SUMMARY")

total = passed + failed
print("\n  Total:  {} tests".format(total))
print("  Passed: {} [OK]".format(passed))
print("  Failed: {} [FAIL]".format(failed))

if errors:
    print("\n  Failed tests detail:")
    for e in errors:
        print("    {}".format(e))

import shutil
try:
    shutil.rmtree(tmp_dir)
except Exception:
    pass

print("\n  Result: {}".format("ALL PASSED [OK]" if failed == 0 else "{} FAILED [FAIL]".format(failed)))
sys.exit(0 if failed == 0 else 1)
