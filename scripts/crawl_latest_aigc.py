#!/usr/bin/env python3
"""Crawl real Xiaohongshu AI posts and turn them into audited reading-note drafts."""

import argparse
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import quote

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "src"))


def _preferred_python_candidates():
    explicit = str(os.environ.get("XHS_PYTHON_EXE", "") or "").strip()
    candidates = []
    if explicit:
        candidates.append(explicit)

    current = os.path.abspath(sys.executable)
    current_dir = os.path.dirname(current)
    candidates.append(os.path.join(current_dir, "envs", "LJY", "python.exe"))
    candidates.append(os.path.join(os.path.dirname(current_dir), "envs", "LJY", "python.exe"))
    candidates.append(r"C:\Users\ljy\miniconda3\envs\LJY\python.exe")
    return candidates


def _ensure_runtime_dependencies():
    if importlib.util.find_spec("selenium") is not None:
        return

    if os.environ.get("XHS_REEXECUTED_FOR_DEPS") == "1":
        return

    current = os.path.abspath(sys.executable)
    for candidate in _preferred_python_candidates():
        if not candidate:
            continue
        candidate = os.path.abspath(candidate)
        if candidate == current or not os.path.exists(candidate):
            continue
        env = os.environ.copy()
        env["XHS_REEXECUTED_FOR_DEPS"] = "1"
        env["XHS_PYTHON_EXE"] = candidate
        print(
            "[INFO] 当前 Python 缺少 selenium，已自动切换到 LJY 环境继续执行：{}".format(candidate),
            file=sys.stderr,
        )
        completed = subprocess.run([candidate] + sys.argv, env=env)
        raise SystemExit(completed.returncode)


_ensure_runtime_dependencies()

from ai.content_analyzer import ContentAnalyzer
from ai.content_auditor import ContentAuditor
from ai.content_rewriter import ContentRewriter
from ai.image_generator import ImageGenerator
from ai.video_processor import VideoProcessor
from config.config import XHS_CRAWL_SETTINGS_FILE, XHS_CRAWL_THREADS, XHS_FAVORITE_FOLDER, XHS_MCP_ARGS, XHS_MCP_CMD
from crawler.xiaohongshu_crawler import XiaohongshuCrawler
from publisher.xiaohongshu_publisher import XiaohongshuPublisher
from ui.draft_manager import DraftManager


DEFAULT_KEYWORDS = []


def load_saved_crawl_settings():
    if not os.path.exists(XHS_CRAWL_SETTINGS_FILE):
        return {}
    try:
        with open(XHS_CRAWL_SETTINGS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def parse_args():
    parser = argparse.ArgumentParser(description="Xiaohongshu AI crawler with image/video reading-note drafts")
    parser.add_argument("--keywords", "-k", type=str, default="", help="Comma-separated search keywords")
    parser.add_argument("--max-posts", "-n", type=int, default=None, help="Maximum number of approved drafts to save")
    parser.add_argument("--skip-video", action="store_true", help="Skip video posts and only keep image posts")
    return parser.parse_args()


def resolve_runtime_options(args):
    settings = load_saved_crawl_settings()

    if args.keywords:
        keywords = [item.strip() for item in args.keywords.split(",") if item.strip()]
    else:
        saved_keywords = settings.get("keywords", "")
        if isinstance(saved_keywords, list):
            keywords = [str(item).strip() for item in saved_keywords if str(item).strip()]
        else:
            keywords = [item.strip() for item in str(saved_keywords or "").split(",") if item.strip()]
    if not keywords:
        keywords = DEFAULT_KEYWORDS

    max_posts = args.max_posts if args.max_posts is not None else int(settings.get("max_posts") or 10)
    max_posts = max(1, int(max_posts))

    skip_video = bool(args.skip_video or settings.get("skip_video", False))
    return keywords, max_posts, skip_video


ARGS = parse_args()
SEARCH_KEYWORDS, MAX_POSTS, SKIP_VIDEO = resolve_runtime_options(ARGS)
STATUS_FILE = os.environ.get("XHS_CRAWL_STATUS_FILE", "").strip()


class CrawlProgress:
    STAGES = {
        "init": "初始化",
        "search": "搜索候选",
        "hydrate": "详情补抓",
        "filter": "AI 相关筛选",
        "media": "媒体处理",
        "notes": "阅读笔记",
        "audit": "内容审核",
        "save": "保存草稿",
        "done": "完成",
    }

    def __init__(self, status_file, keywords, max_posts, skip_video):
        self.status_file = status_file
        self.payload = {
            "status": "running",
            "stage_id": "init",
            "stage_label": self.STAGES["init"],
            "current": 0,
            "total": max_posts,
            "searched": 0,
            "hydrated": 0,
            "ai_related": 0,
            "skipped_non_ai": 0,
            "skipped_video": 0,
            "media_processed": 0,
            "approved": 0,
            "rejected": 0,
            "keywords": list(keywords or []),
            "max_posts": int(max_posts),
            "skip_video": bool(skip_video),
            "last_message": "",
            "last_error": "",
            "result_summary": {},
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.flush()

    def update(self, stage_id=None, current=None, total=None, message=None, error=None, **fields):
        if stage_id:
            self.payload["stage_id"] = stage_id
            self.payload["stage_label"] = self.STAGES.get(stage_id, stage_id)
        if current is not None:
            self.payload["current"] = int(current)
        if total is not None:
            self.payload["total"] = int(total)
        if message is not None:
            self.payload["last_message"] = str(message)
        if error is not None:
            self.payload["last_error"] = str(error)
        for key, value in fields.items():
            self.payload[key] = value
        self.payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.flush()

    def complete(self, result_summary=None, message="抓取任务完成"):
        self.payload["status"] = "completed"
        self.payload["stage_id"] = "done"
        self.payload["stage_label"] = self.STAGES["done"]
        self.payload["current"] = self.payload.get("total", 0)
        self.payload["last_message"] = message
        if result_summary is not None:
            self.payload["result_summary"] = result_summary
        self.payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.flush()

    def fail(self, message):
        self.payload["status"] = "failed"
        self.payload["last_error"] = str(message)
        self.payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.flush()

    def flush(self):
        if not self.status_file:
            return
        try:
            directory = os.path.dirname(self.status_file)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.status_file, "w", encoding="utf-8") as fh:
                json.dump(self.payload, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass


def print_banner():
    now = datetime.now()
    print("=" * 72)
    print("  小红书 AI 内容抓取与阅读笔记草稿生成")
    print("  时间: {}".format(now.strftime("%Y-%m-%d %H:%M:%S")))
    print("  关键词: {}".format("、".join(SEARCH_KEYWORDS) if SEARCH_KEYWORDS else "未配置"))
    print("  目标草稿数: {}".format(MAX_POSTS))
    print("  跳过视频: {}".format("是" if SKIP_VIDEO else "否"))
    print("=" * 72)


def normalize_post_record(post, source_label="real_crawl"):
    normalized = dict(post or {})
    image_urls = normalized.get("original_image_urls") or normalized.get("images") or []
    if isinstance(image_urls, str):
        image_urls = [image_urls]

    cleaned_images = []
    seen_images = set()
    for image in image_urls:
        if isinstance(image, dict):
            image = image.get("url_default") or image.get("url") or image.get("src") or ""
        image = str(image or "").strip()
        if not image:
            continue
        if image.startswith("//"):
            image = "https:" + image
        if image not in seen_images:
            cleaned_images.append(image)
            seen_images.add(image)

    video_urls = normalized.get("video_urls") or []
    if isinstance(video_urls, str):
        video_urls = [video_urls]
    cleaned_videos = []
    seen_videos = set()
    for video in video_urls:
        video = str(video or "").strip()
        if not video:
            continue
        if video.startswith("//"):
            video = "https:" + video
        if video not in seen_videos:
            cleaned_videos.append(video)
            seen_videos.add(video)

    source_url = str(normalized.get("source_url") or normalized.get("link") or normalized.get("url") or "").strip()
    if source_url.startswith("/"):
        source_url = "https://www.xiaohongshu.com" + source_url

    media_type = str(normalized.get("media_type") or "").strip().lower()
    if media_type not in ("image", "video"):
        media_type = "video" if cleaned_videos else "image"

    normalized["images"] = cleaned_images
    normalized["original_image_urls"] = cleaned_images
    normalized["video_urls"] = cleaned_videos
    normalized["original_video_url"] = normalized.get("original_video_url") or (cleaned_videos[0] if cleaned_videos else "")
    normalized["source_url"] = source_url
    normalized["link"] = source_url
    normalized["original_title"] = normalized.get("original_title") or normalized.get("title", "")
    normalized["original_content"] = normalized.get("original_content") or normalized.get("content", "")
    normalized["source"] = normalized.get("source") or source_label
    normalized["media_type"] = media_type
    normalized["skip_video"] = bool(normalized.get("skip_video", False))
    normalized.setdefault("reading_notes", "")
    normalized.setdefault("image_insights", [])
    normalized.setdefault("video_frame_insights", [])
    return normalized


def merge_unique_posts(existing_posts, new_posts):
    merged = []
    seen_keys = set()
    for post in list(existing_posts or []) + list(new_posts or []):
        normalized = normalize_post_record(post, source_label=post.get("source", "real_crawl") if isinstance(post, dict) else "real_crawl")
        key = (normalized.get("source_url") or normalized.get("title") or "").strip()
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(normalized)
    return merged


def _split_tokens(raw):
    if not raw:
        return []
    try:
        return shlex.split(raw, posix=False)
    except ValueError:
        return [raw]


def _mcp_base_command():
    cmd = _split_tokens(XHS_MCP_CMD) + _split_tokens(XHS_MCP_ARGS)
    cmd = [item for item in cmd if item]
    if not cmd:
        return []
    program = cmd[0]
    if not (os.path.isabs(program) or os.path.sep in program):
        resolved = shutil.which(program)
        if resolved:
            cmd[0] = resolved
    return cmd


def _extract_json_payload(text):
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
    return None


def _extract_search_image_urls(note_card):
    images = []
    seen = set()
    for image in note_card.get("imageList", []) or []:
        url = ""
        for info in image.get("infoList", []) or []:
            if info.get("imageScene") == "WB_DFT" and info.get("url"):
                url = info.get("url")
                break
        if not url:
            info_list = image.get("infoList", []) or []
            if info_list:
                url = info_list[0].get("url", "")
        if url and url not in seen:
            images.append(url)
            seen.add(url)
    cover = (note_card.get("cover") or {}).get("urlDefault", "")
    if cover and cover not in seen:
        images.insert(0, cover)
    return images


def _resolve_worker_count(task_count, limit=None):
    if task_count <= 1:
        return 1
    workers = max(1, XHS_CRAWL_THREADS)
    if limit is not None:
        workers = min(workers, limit)
    return min(workers, task_count)


def _fetch_mcp_posts_for_keyword(base_cmd, keyword, max_count):
    try:
        proc = subprocess.run(
            base_cmd + ["search", "-k", keyword, "--compact"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
    except Exception as exc:
        print("  - MCP 搜索失败 [{}]: {}".format(keyword, str(exc)[:90]))
        return []

    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip()[:160]
        print("  - MCP 搜索失败 [{}]: {}".format(keyword, message or "未知错误"))
        return []

    payload = _extract_json_payload(proc.stdout)
    feeds = (payload or {}).get("feeds", []) or []
    print("  - MCP 关键词 [{}] 返回 {} 条".format(keyword, len(feeds)))

    posts = []
    for feed in feeds:
        if feed.get("modelType") != "note":
            continue

        note = feed.get("noteCard") or {}
        user = note.get("user") or {}
        note_type = str(note.get("type") or "").strip().lower()
        xsec_token = str(feed.get("xsecToken") or "").strip()
        source_url = "https://www.xiaohongshu.com/explore/{}".format(feed.get("id", ""))
        if xsec_token:
            source_url += "?xsec_token={}&xsec_source=pc_search".format(quote(xsec_token, safe=""))

        post = normalize_post_record(
            {
                "title": note.get("displayTitle", "") or note.get("display_title", "") or "",
                "content": note.get("desc", "") or "",
                "author": user.get("nickname", "未知"),
                "likes": str(
                    ((note.get("interactInfo") or note.get("interact_info") or {})).get("likedCount")
                    or ((note.get("interactInfo") or note.get("interact_info") or {})).get("liked_count", "")
                ),
                "images": _extract_search_image_urls(note),
                "link": source_url,
                "publish_time": ((note.get("cornerTagInfo") or [{}])[0] or {}).get("text", ""),
                "source": "mcp_search",
                "media_type": "video" if note_type == "video" else "image",
            },
            source_label="mcp_search",
        )
        if post.get("title"):
            posts.append(post)
        if len(posts) >= max_count:
            break
    return posts


def _summarize_keyword_hits(search_keywords, posts):
    stats = []
    for keyword in search_keywords or []:
        normalized_keyword = str(keyword or "").strip().lower()
        hits = 0
        for post in posts or []:
            haystack = "{} {}".format(post.get("title", ""), post.get("original_content", "") or post.get("content", ""))
            if normalized_keyword and normalized_keyword in haystack.lower():
                hits += 1
        stats.append({"keyword": keyword, "hits": hits})
    return stats


def _fetch_browser_posts_for_keyword(keyword, max_posts):
    crawler = XiaohongshuCrawler()
    try:
        return crawler.search_posts(keyword, max_posts=max_posts, hydrate_details=False)
    except Exception as exc:
        print("  - 浏览器补抓失败 [{}]: {}".format(keyword, str(exc)[:90]))
        return []


def _hydrate_post_chunk(chunk_index, chunk_posts):
    crawler = XiaohongshuCrawler()
    return chunk_index, crawler.hydrate_posts(chunk_posts, close_driver=True)


def fetch_mcp_real_posts(search_keywords, max_count, skip_video=False):
    print("\n" + "=" * 72)
    print("[阶段1] 通过 MCP 搜索真实原帖")
    print("=" * 72)

    base_cmd = _mcp_base_command()
    if not base_cmd:
        print("MCP 命令未配置，自动跳过 MCP 搜索。")
        return []

    workers = _resolve_worker_count(len(search_keywords), limit=4)
    print("MCP 并发搜索线程数: {}".format(workers))
    per_keyword_limit = max_count if not skip_video else max(max_count * 3, 12)

    keyword_results = [[] for _ in search_keywords]
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="xhs-mcp-search") as executor:
        future_to_index = {
            executor.submit(_fetch_mcp_posts_for_keyword, base_cmd, keyword, per_keyword_limit): index
            for index, keyword in enumerate(search_keywords)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                keyword_results[index] = future.result() or []
            except Exception as exc:
                print("  - MCP 搜索线程失败 [{}]: {}".format(search_keywords[index], str(exc)[:90]))
                keyword_results[index] = []

    posts = []
    for items in keyword_results:
        posts.extend(items)
    posts = merge_unique_posts([], posts)
    if skip_video:
        image_posts = [post for post in posts if post.get("media_type") != "video"]
        video_posts = [post for post in posts if post.get("media_type") == "video"]
        posts = image_posts + video_posts
    print("MCP 真实帖子累计: {}".format(len(posts)))
    return posts[:max_count]


def fetch_browser_real_posts(search_keywords, max_count, existing_posts=None, skip_video=False):
    existing_posts = existing_posts or []
    if max_count <= 0:
        return []

    print("\n" + "=" * 72)
    print("[阶段2] 使用浏览器补抓原帖详情")
    print("=" * 72)

    browser_posts = []
    workers = _resolve_worker_count(len(search_keywords), limit=2)
    per_keyword = max(1, min(max_count, 4))
    if skip_video:
        per_keyword = max(per_keyword, min(max_count * 3, 12))
    print("浏览器并发搜索线程数: {}".format(workers))

    keyword_results = [[] for _ in search_keywords]
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="xhs-browser-search") as executor:
        future_to_index = {
            executor.submit(_fetch_browser_posts_for_keyword, keyword, per_keyword): index
            for index, keyword in enumerate(search_keywords)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                keyword_results[index] = future.result() or []
            except Exception as exc:
                print("  - 浏览器补抓线程失败 [{}]: {}".format(search_keywords[index], str(exc)[:90]))
                keyword_results[index] = []

    for index, keyword in enumerate(search_keywords):
        fetched = keyword_results[index]
        merged = merge_unique_posts(existing_posts + browser_posts, fetched)
        browser_posts = [post for post in merged if post not in existing_posts][:max_count]
        print("  - 浏览器关键词 [{}] 补抓后累计 {} 条".format(keyword, len(browser_posts)))
        if len(browser_posts) >= max_count:
            break

    if skip_video:
        image_posts = [post for post in browser_posts if post.get("media_type") != "video"]
        video_posts = [post for post in browser_posts if post.get("media_type") == "video"]
        browser_posts = image_posts + video_posts

    return browser_posts[:max_count]


def hydrate_posts_with_browser_details(posts, max_count=None, progress=None):
    if not posts:
        return []

    limited_posts = list(posts[: max_count or len(posts)])
    print("\n" + "=" * 72)
    print("[阶段1.5] 使用浏览器补齐原帖详情、正文与媒体信息")
    print("=" * 72)

    if progress:
        progress.update(
            stage_id="hydrate",
            current=0,
            total=len(limited_posts),
            message="开始详情补抓",
        )

    workers = _resolve_worker_count(len(limited_posts), limit=3)
    print("详情补抓线程数: {}".format(workers))

    if workers <= 1:
        crawler = XiaohongshuCrawler()
        hydrated_posts = crawler.hydrate_posts(limited_posts, close_driver=True)
    else:
        chunk_size = max(1, (len(limited_posts) + workers - 1) // workers)
        chunks = [(start, limited_posts[start : start + chunk_size]) for start in range(0, len(limited_posts), chunk_size)]
        chunk_results = {}
        completed = 0
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="xhs-detail-hydrate") as executor:
            future_to_start = {
                executor.submit(_hydrate_post_chunk, start, chunk_posts): start
                for start, chunk_posts in chunks
            }
            for future in as_completed(future_to_start):
                start = future_to_start[future]
                try:
                    _, chunk_posts = future.result()
                except Exception as exc:
                    print("  - 详情补抓线程失败 [start={}]: {}".format(start, str(exc)[:90]))
                    chunk_posts = limited_posts[start : start + chunk_size]
                completed += len(chunk_posts)
                if progress:
                    progress.update(
                        stage_id="hydrate",
                        current=min(completed, len(limited_posts)),
                        total=len(limited_posts),
                        message="详情补抓进行中",
                    )
                chunk_results[start] = chunk_posts
        hydrated_posts = []
        for start, _ in chunks:
            hydrated_posts.extend(chunk_results.get(start, []))

    normalized_posts = []
    blocked_count = 0
    enriched_count = 0
    timeout_count = 0

    for original, hydrated in zip(limited_posts, hydrated_posts):
        merged = normalize_post_record(hydrated, source_label=hydrated.get("source", original.get("source", "mcp_search")))
        if merged.get("crawl_warning"):
            blocked_count += 1
        if merged.get("hydrate_timeout"):
            timeout_count += 1
        if len((merged.get("original_content") or "").strip()) > len((original.get("original_content") or "").strip()):
            enriched_count += 1
        normalized_posts.append(merged)

    if progress:
        progress.update(
            stage_id="hydrate",
            current=len(normalized_posts),
            total=len(limited_posts),
            hydrated=len(normalized_posts) - timeout_count,
            last_error="hydrate_timeout={}".format(timeout_count) if timeout_count else "",
            message="详情补抓完成",
        )

    print(
        "详情补齐完成: {} 条，正文增强 {} 条，仍被拦截 {} 条，超时 {} 条".format(
            len(normalized_posts), enriched_count, blocked_count, timeout_count
        )
    )
    return normalized_posts


def process_candidates(
    posts,
    analyzer,
    rewriter,
    image_generator,
    video_processor,
    auditor,
    skip_video=False,
    user_keywords=None,
    progress=None,
):
    if not posts:
        return [], []

    total = len(posts)
    print("\n[处理] 候选帖子 {} 条".format(total))
    processed_posts = []
    skipped_posts = []
    ai_posts = []

    if progress:
        progress.update(stage_id="filter", current=0, total=total, message="开始 AI 相关筛选")

    for index, post in enumerate(posts, start=1):
        result = analyzer.analyze_content(post, user_keywords=user_keywords or [])
        post["analysis"] = result
        if result.get("is_ai_related", False):
            ai_posts.append(post)
        else:
            skipped = dict(post)
            skipped["skip_reason"] = "非AI相关"
            skipped_posts.append(skipped)
        if progress:
            progress.update(
                stage_id="filter",
                current=index,
                total=total,
                ai_related=len(ai_posts),
                skipped_non_ai=len([item for item in skipped_posts if item.get("skip_reason") == "非AI相关"]),
                message="AI 相关筛选中",
            )

    print("      -> AI 相关帖子 {} 条".format(len(ai_posts)))
    if not ai_posts:
        return [], skipped_posts

    if progress:
        progress.update(stage_id="media", current=0, total=len(ai_posts), message="开始媒体处理")

    media_ready_posts = []
    for index, post in enumerate(ai_posts, start=1):
        media_type = post.get("media_type", "image")
        if media_type == "video" and skip_video:
            skipped = dict(post)
            skipped["skip_video"] = True
            skipped["skip_reason"] = "配置为跳过视频"
            skipped_posts.append(skipped)
        else:
            current = video_processor.process_post(post) if media_type == "video" else image_generator.process_post(post, allow_fallback=False)
            current["skip_video"] = bool(skip_video)
            media_ready_posts.append(current)
        if progress:
            progress.update(
                stage_id="media",
                current=index,
                total=len(ai_posts),
                media_processed=len(media_ready_posts),
                skipped_video=len([item for item in skipped_posts if item.get("skip_video")]),
                message="媒体处理中",
            )

    if progress:
        progress.update(stage_id="notes", current=0, total=len(media_ready_posts), message="开始生成阅读笔记")

    notes_ready_posts = []
    for index, post in enumerate(media_ready_posts, start=1):
        current = rewriter.process_post(post)
        current = rewriter.enrich_post_with_media_context(current)
        notes_ready_posts.append(current)
        if progress:
            progress.update(
                stage_id="notes",
                current=index,
                total=len(media_ready_posts),
                message="阅读笔记生成中",
            )

    if progress:
        progress.update(stage_id="audit", current=0, total=len(notes_ready_posts), message="开始内容审核")

    for index, post in enumerate(notes_ready_posts, start=1):
        auditor.audit_content(post)
        processed_posts.append(post)
        approved = len([item for item in processed_posts if is_publish_ready(item)])
        rejected = len(processed_posts) - approved
        if progress:
            progress.update(
                stage_id="audit",
                current=index,
                total=len(notes_ready_posts),
                approved=approved,
                rejected=rejected,
                message="内容审核中",
            )

    return processed_posts, skipped_posts


def is_publish_ready(post):
    audit = post.get("audit", {}) or {}
    media_type = post.get("media_type", "image")
    if media_type == "video":
        has_media = bool(post.get("original_video_path")) and bool(post.get("video_transcript")) and bool(post.get("final_image_paths"))
    else:
        has_media = bool(post.get("original_image_paths")) and bool(post.get("final_image_paths"))
    return bool(audit.get("publish_ready")) and bool(audit.get("is_safe")) and has_media


def get_rejection_reason(post):
    audit = post.get("audit", {}) or {}
    if audit.get("rejection_reason"):
        return audit.get("rejection_reason")
    if post.get("video_error"):
        return "视频处理失败: {}".format(post.get("video_error"))
    if post.get("image_mode") == "missing_original":
        return "原贴图片缺失，已按规则丢弃"
    issue_messages = []
    for issue in audit.get("issues", [])[:3]:
        if isinstance(issue, dict):
            issue_messages.append(issue.get("message", ""))
        else:
            issue_messages.append(str(issue))
    return "；".join(message for message in issue_messages if message) or "综合评分不足"


def save_approved_drafts(approved_posts, draft_manager):
    print("\n" + "=" * 72)
    print("[阶段3] 保存通过审核的高质量草稿")
    print("=" * 72)
    publisher = XiaohongshuPublisher(headless=False, backend="mcp")
    draft_ids = []
    favorite_success = 0
    favorite_failed = 0
    for post in approved_posts:
        current = dict(post or {})
        favorite_result = publisher.favorite_source_post(current, folder_name=XHS_FAVORITE_FOLDER)
        current["source_favorite_status"] = favorite_result.get("status", "")
        current["source_favorite_message"] = favorite_result.get("message", "")
        current["source_favorite_folder"] = favorite_result.get("folder_name", XHS_FAVORITE_FOLDER)
        current["source_favorited"] = bool(favorite_result.get("success", False))
        if current["source_favorited"]:
            favorite_success += 1
        else:
            favorite_failed += 1
            print("[WARN] 原贴收藏失败: {}".format(current.get("source_favorite_message", "")[:160]))
        draft_id = draft_manager.save_draft(
            current,
            favorite=current["source_favorited"],
            favorite_source="xhs_folder:{}".format(XHS_FAVORITE_FOLDER) if current["source_favorited"] else "",
        )
        draft_ids.append(draft_id)
    publisher.cleanup()
    print("已保存 {} 条草稿；原贴收藏成功 {} 条，失败 {} 条".format(len(draft_ids), favorite_success, favorite_failed))
    return draft_ids


def build_result_summary(
    approved_posts,
    rejected_posts,
    skipped_posts,
    searched_count=0,
    hydrated_count=0,
    media_processed_count=0,
    notes=None,
    keyword_hits=None,
):
    rejection_counter = Counter()
    for post in rejected_posts:
        rejection_counter[get_rejection_reason(post)] += 1
    return {
        "searched": int(searched_count),
        "hydrated": int(hydrated_count),
        "approved": len(approved_posts),
        "rejected": len(rejected_posts),
        "skipped_non_ai": len([item for item in skipped_posts if item.get("skip_reason") == "非AI相关"]),
        "skipped_video": len([item for item in skipped_posts if item.get("skip_video")]),
        "media_processed": int(media_processed_count),
        "favorited": len([post for post in approved_posts if post.get("source_favorited")]),
        "image_count": len([post for post in approved_posts if post.get("media_type") == "image"]),
        "video_count": len([post for post in approved_posts if post.get("media_type") == "video"]),
        "video_transcribed": len([post for post in approved_posts if post.get("video_transcript")]),
        "top_rejection_reasons": rejection_counter.most_common(5),
        "notes": list(notes or []),
        "keyword_hits": list(keyword_hits or []),
    }


def print_result_summary(
    approved_posts,
    rejected_posts,
    skipped_posts,
    draft_ids,
    searched_count=0,
    hydrated_count=0,
    media_processed_count=0,
    notes=None,
    keyword_hits=None,
):
    print("\n" + "=" * 72)
    print("结果汇总")
    print("=" * 72)

    image_count = len([post for post in approved_posts if post.get("media_type") == "image"])
    video_count = len([post for post in approved_posts if post.get("media_type") == "video"])
    transcribed_count = len([post for post in approved_posts if post.get("video_transcript")])
    non_ai_skipped = len([item for item in skipped_posts if item.get("skip_reason") == "非AI相关"])
    skipped_video = len([item for item in skipped_posts if item.get("skip_video")])

    print("搜索候选数: {}".format(searched_count))
    print("详情补抓完成数: {}".format(hydrated_count))
    print("媒体处理完成数: {}".format(media_processed_count))
    print("用户设置目标草稿数: {}".format(MAX_POSTS))
    print("通过审核并保存的草稿: {}（图文 {}，视频来源 {}）".format(len(approved_posts), image_count, video_count))
    print("视频转写成功数: {}".format(transcribed_count))
    print("跳过的非 AI 帖子数: {}".format(non_ai_skipped))
    print("跳过的视频数: {}".format(skipped_video))
    if keyword_hits:
        print("关键词命中概览:")
        for item in keyword_hits:
            print("  - {} => {} 条".format(item.get("keyword", ""), item.get("hits", 0)))
    if notes:
        print("诊断说明:")
        for item in notes:
            print("  - {}".format(item))
    if len(approved_posts) < MAX_POSTS:
        print("未凑满目标值，原因：已按严格上限限制详情补抓和媒体处理，剩余候选未通过审核或被跳过。")

    if approved_posts:
        for index, post in enumerate(approved_posts, start=1):
            audit = post.get("audit", {}) or {}
            media_label = "视频" if post.get("media_type") == "video" else "图文"
            print(
                "  [{}] {} | {} | 总分 {} | 来源 {} | 引用 {} | 预览图 {} 张".format(
                    index,
                    post.get("title", "")[:40],
                    media_label,
                    audit.get("confidence_score", 0),
                    audit.get("source_score", 0),
                    audit.get("citation_score", 0),
                    len(post.get("final_image_paths", []) or []),
                )
            )

    if rejected_posts:
        print("\n被淘汰并已重抓补位的帖子: {}".format(len(rejected_posts)))
        for index, post in enumerate(rejected_posts[:10], start=1):
            audit = post.get("audit", {}) or {}
            print(
                "  [{}] {} | 类型 {} | 原因: {} | 来源 {} | 引用 {}".format(
                    index,
                    post.get("title", "")[:40],
                    post.get("media_type", "image"),
                    get_rejection_reason(post),
                    audit.get("source_score", 0),
                    audit.get("citation_score", 0),
                )
            )
        rejection_counter = Counter(get_rejection_reason(post) for post in rejected_posts)
        if rejection_counter:
            print("\nTop rejection reasons:")
            for reason, count in rejection_counter.most_common(5):
                print("  - {} x{}".format(reason, count))

    if skipped_posts:
        print("\n跳过候选总数: {}".format(len(skipped_posts)))
        for index, post in enumerate(skipped_posts[:8], start=1):
            print("  [{}] {} | {}".format(index, post.get("title", "")[:40], post.get("skip_reason", "跳过视频")))

    print("\n草稿目录: data/drafts/")
    print("图片目录: data/images/")
    print("视频目录: data/media/videos/")
    if draft_ids:
        print("下一步: 运行 streamlit run web_app.py 查看并发布。")


def main():
    if not SEARCH_KEYWORDS:
        print("未配置搜索关键词。请先在网页“爬取管理”里填写搜索关键词，再启动爬取。")
        return

    print_banner()
    progress = CrawlProgress(STATUS_FILE, SEARCH_KEYWORDS, MAX_POSTS, SKIP_VIDEO)

    try:
        analyzer = ContentAnalyzer()
        rewriter = ContentRewriter()
        image_generator = ImageGenerator()
        video_processor = VideoProcessor()
        auditor = ContentAuditor()
        draft_manager = DraftManager()

        approved_posts = []
        rejected_posts = []
        skipped_posts = []
        seen_posts = []
        result_notes = []
        keyword_hits = []

        if getattr(analyzer, "mode_reason", ""):
            result_notes.append(str(analyzer.mode_reason))

        candidate_search_count = max(MAX_POSTS, min(MAX_POSTS + max(len(SEARCH_KEYWORDS), 1), MAX_POSTS * 2))
        if SKIP_VIDEO:
            candidate_search_count = max(candidate_search_count, MAX_POSTS * 3)
        progress.update(stage_id="search", current=0, total=candidate_search_count, message="开始搜索候选")
        mcp_posts = fetch_mcp_real_posts(SEARCH_KEYWORDS, candidate_search_count, skip_video=SKIP_VIDEO)
        seen_posts = merge_unique_posts(seen_posts, mcp_posts)
        keyword_hits = _summarize_keyword_hits(SEARCH_KEYWORDS, seen_posts)
        progress.update(
            stage_id="search",
            current=len(mcp_posts),
            total=candidate_search_count,
            searched=len(seen_posts),
            message="MCP 搜索完成，共 {} 条".format(len(mcp_posts)),
            keyword_hits=keyword_hits,
        )

        if len(seen_posts) < MAX_POSTS:
            if not seen_posts:
                result_notes.append("MCP 搜索未找到可用候选，开始尝试浏览器补抓。")
            browser_posts = fetch_browser_real_posts(
                SEARCH_KEYWORDS,
                MAX_POSTS - len(seen_posts),
                existing_posts=seen_posts,
                skip_video=SKIP_VIDEO,
            )
            seen_posts = merge_unique_posts(seen_posts, browser_posts)
            keyword_hits = _summarize_keyword_hits(SEARCH_KEYWORDS, seen_posts)
            progress.update(
                stage_id="search",
                current=min(len(seen_posts), candidate_search_count),
                total=candidate_search_count,
                searched=len(seen_posts),
                message="浏览器搜索补充完成，共 {} 条".format(len(seen_posts)),
                keyword_hits=keyword_hits,
            )

        if SKIP_VIDEO:
            image_candidates = [post for post in seen_posts if post.get("media_type") != "video"]
            video_candidates = [post for post in seen_posts if post.get("media_type") == "video"]
            candidate_posts = image_candidates[:MAX_POSTS]
            if len(candidate_posts) < MAX_POSTS:
                result_notes.append(
                    "已开启“跳过视频帖”。本轮搜索到的图文帖不足 {} 条，已有 {} 条视频帖被排除在候选池外。".format(
                        MAX_POSTS,
                        len(video_candidates),
                    )
                )
        else:
            candidate_posts = seen_posts[:MAX_POSTS]
        if not candidate_posts:
            result_notes.append("搜索阶段没有拿到任何候选帖子。请优先检查关键词是否过冷、登录态是否有效，或直接换成更贴近小红书语境的关键词。")
            result_summary = build_result_summary(
                approved_posts,
                rejected_posts,
                skipped_posts,
                searched_count=0,
                hydrated_count=0,
                media_processed_count=0,
                notes=result_notes,
                keyword_hits=keyword_hits,
            )
            progress.complete(result_summary=result_summary, message="未找到候选帖子，任务已提前结束")
            print_result_summary(
                approved_posts,
                rejected_posts,
                skipped_posts,
                [],
                searched_count=0,
                hydrated_count=0,
                media_processed_count=0,
                notes=result_notes,
                keyword_hits=keyword_hits,
            )
            return
        progress.update(
            stage_id="search",
            current=len(candidate_posts),
            total=MAX_POSTS,
            searched=len(seen_posts),
            message="候选池已锁定，严格按用户上限处理{}".format("（已优先筛掉视频帖）" if SKIP_VIDEO else ""),
            keyword_hits=keyword_hits,
        )

        hydrated_posts = hydrate_posts_with_browser_details(candidate_posts, max_count=MAX_POSTS, progress=progress)
        progress.update(
            stage_id="hydrate",
            current=len(hydrated_posts),
            total=len(candidate_posts),
            hydrated=len([post for post in hydrated_posts if not post.get("hydrate_timeout")]),
            message="详情补抓完成",
        )

        processed_posts, skipped_batch = process_candidates(
            hydrated_posts,
            analyzer,
            rewriter,
            image_generator,
            video_processor,
            auditor,
            skip_video=SKIP_VIDEO,
            user_keywords=SEARCH_KEYWORDS,
            progress=progress,
        )
        skipped_posts.extend(skipped_batch)

        for post in processed_posts:
            if is_publish_ready(post):
                approved_posts.append(post)
            else:
                rejected_posts.append(post)

        approved_posts = merge_unique_posts([], approved_posts)[:MAX_POSTS]
        media_processed_count = len(
            [
                post
                for post in processed_posts
                if (
                    post.get("media_type") == "video"
                    and post.get("original_video_path")
                )
                or (
                    post.get("media_type") != "video"
                    and post.get("original_image_paths")
                )
            ]
        )

        progress.update(
            stage_id="save",
            current=0,
            total=max(len(approved_posts), 1),
            approved=len(approved_posts),
            rejected=len(rejected_posts),
            media_processed=media_processed_count,
            message="准备保存草稿",
        )
        draft_ids = save_approved_drafts(approved_posts, draft_manager) if approved_posts else []
        result_summary = build_result_summary(
            approved_posts,
            rejected_posts,
            skipped_posts,
            searched_count=len(seen_posts),
            hydrated_count=len([post for post in hydrated_posts if not post.get("hydrate_timeout")]),
            media_processed_count=media_processed_count,
            notes=result_notes,
            keyword_hits=keyword_hits,
        )
        result_summary["draft_ids"] = draft_ids
        completion_message = (
            "抓取完成，已生成 {} 条草稿，可在网页中查看草稿和结果汇总".format(len(draft_ids))
            if draft_ids
            else "抓取完成，但本轮没有生成草稿，请查看结果汇总中的跳过/打回原因"
        )
        progress.complete(result_summary=result_summary, message=completion_message)
        print_result_summary(
            approved_posts,
            rejected_posts,
            skipped_posts,
            draft_ids,
            searched_count=len(seen_posts),
            hydrated_count=len([post for post in hydrated_posts if not post.get("hydrate_timeout")]),
            media_processed_count=media_processed_count,
            notes=result_notes,
            keyword_hits=keyword_hits,
        )
    except Exception as exc:
        progress.fail(str(exc))
        raise


if __name__ == "__main__":
    main()
