#!/usr/bin/env python3
"""Stable Streamlit app entrypoint for the Xiaohongshu agent."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime

import streamlit as st

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from _bootstrap import preferred_python_executable
from config.config import (
    DEFAULT_AI_RUNTIME_SETTINGS,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    VALID_AI_RUNTIME_MODES,
    XHS_AI_SETTINGS_FILE,
    XHS_COOKIE_FILE,
    XHS_CRAWL_SETTINGS_FILE,
    XHS_FAVORITE_FOLDER,
    XHS_PROFILE_DIR,
    XHS_STATE_DIR,
    has_valid_deepseek_api_key,
    has_valid_gemini_api_key,
    has_valid_openai_api_key,
)
from src.ai.text_llm_client import check_ollama_available
from src.publisher.login_state import LOGIN_STATUS_LABELS, resolve_login_state
from src.publisher.xiaohongshu_publisher import XiaohongshuPublisher
from src.ui.draft_manager import DraftManager


APP_TITLE = "小红书 Agent 控制台"
CRAWL_SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "crawl_latest_aigc.py")
UI_SETTINGS_FILE = os.path.join(XHS_STATE_DIR, "ui_runtime_state.json")


def load_json(path: str, default):
    if not path or not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def save_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def read_text(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""


def read_json(path: str):
    return load_json(path, {})


def load_crawl_settings():
    settings = load_json(XHS_CRAWL_SETTINGS_FILE, {})
    return {
        "keywords": settings.get("keywords", "Claude Code,ChatGPT,AIGC"),
        "max_posts": int(settings.get("max_posts", 5) or 5),
        "skip_video": bool(settings.get("skip_video", False)),
    }


def save_crawl_settings(keywords: str, max_posts: int, skip_video: bool) -> None:
    save_json(
        XHS_CRAWL_SETTINGS_FILE,
        {
            "keywords": keywords,
            "max_posts": int(max_posts),
            "skip_video": bool(skip_video),
            "updated_at": datetime.now().isoformat(),
        },
    )


def load_ai_settings():
    settings = load_json(XHS_AI_SETTINGS_FILE, {})
    merged = dict(DEFAULT_AI_RUNTIME_SETTINGS)
    for key in merged:
        value = str(settings.get(key, merged[key])).strip().lower()
        merged[key] = value if value in VALID_AI_RUNTIME_MODES else merged[key]
    return merged


def save_ai_settings(settings):
    payload = dict(settings)
    payload["updated_at"] = datetime.now().isoformat()
    save_json(XHS_AI_SETTINGS_FILE, payload)


def load_ui_state():
    return load_json(
        UI_SETTINGS_FILE,
        {
            "login_status_file": "",
            "login_log_file": "",
            "login_pid": 0,
            "crawl_status_file": "",
            "crawl_log_file": "",
            "crawl_pid": 0,
        },
    )


def save_ui_state(state):
    save_json(UI_SETTINGS_FILE, state)


def get_ui_state():
    if "ui_state" not in st.session_state:
        st.session_state.ui_state = load_ui_state()
    return st.session_state.ui_state


def persist_ui_state():
    save_ui_state(get_ui_state())


def pid_exists(pid: int) -> bool:
    if not pid:
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {int(pid)}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except Exception:
        return False
    return str(pid) in (result.stdout or "")


def collect_post_images(post: dict) -> list[str]:
    images = []
    for key in ("final_image_paths", "generated_image_paths", "original_image_paths", "video_frame_paths"):
        value = post.get(key, [])
        if isinstance(value, str):
            value = [value] if value else []
        for item in value if isinstance(value, list) else []:
            if item and os.path.exists(item) and item not in images:
                images.append(item)
    single = post.get("generated_image_path", "")
    if single and os.path.exists(single) and single not in images:
        images.insert(0, single)
    return images


def get_post_body(post: dict) -> str:
    return (
        post.get("publish_content")
        or post.get("optimized_content")
        or post.get("rewritten_content")
        or post.get("reading_notes")
        or post.get("content")
        or ""
    )


def get_source_url(post: dict) -> str:
    return post.get("source_url") or post.get("link") or ""


def format_mode_label(mode: str) -> str:
    return {
        "ollama": "Ollama 本地模型",
        "deepseek": "DeepSeek API",
        "auto": "自动选择",
        "openai": "OpenAI API",
        "local": "本地降级",
    }.get(str(mode or "").lower(), str(mode or "未设置"))


def format_status_label(status: str) -> str:
    return {
        "draft": "待发布",
        "published": "已发布",
        "discarded": "已丢弃",
    }.get(str(status or "").lower(), str(status or "未知"))


def format_media_label(media_type: str) -> str:
    return "视频" if str(media_type or "").lower() == "video" else "图文"


def start_login():
    publisher = XiaohongshuPublisher(headless=False)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    status_file = os.path.join(XHS_STATE_DIR, f"login_status_{timestamp}.json")
    log_file = os.path.join(XHS_STATE_DIR, f"login_log_{timestamp}.log")
    proc = publisher.spawn_background_login(status_file=status_file, log_file=log_file, timeout=180)
    state = get_ui_state()
    state["login_status_file"] = status_file
    state["login_log_file"] = log_file
    state["login_pid"] = getattr(proc, "pid", 0) if proc else 0
    persist_ui_state()


def get_login_state():
    publisher = XiaohongshuPublisher(headless=False)
    backend_status = publisher.login_status()
    state = get_ui_state()
    status_payload = read_json(state.get("login_status_file", ""))
    process_running = pid_exists(int(state.get("login_pid") or 0))
    resolved = resolve_login_state(
        backend_status=backend_status,
        status_payload=status_payload,
        process_running=process_running,
        current_status=(status_payload or {}).get("status", "idle"),
    )
    return resolved, status_payload


def start_crawl(keywords: str, max_posts: int, skip_video: bool):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    status_file = os.path.join(XHS_STATE_DIR, f"crawl_status_{timestamp}.json")
    log_file = os.path.join(XHS_STATE_DIR, f"crawl_log_{timestamp}.log")
    env = os.environ.copy()
    env["XHS_CRAWL_STATUS_FILE"] = status_file
    env["XHS_PYTHON_EXE"] = preferred_python_executable()
    cmd = [
        preferred_python_executable(),
        "-u",
        CRAWL_SCRIPT,
        "--keywords",
        keywords,
        "--max-posts",
        str(max_posts),
    ]
    if skip_video:
        cmd.append("--skip-video")
    log_handle = open(log_file, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    state = get_ui_state()
    state["crawl_status_file"] = status_file
    state["crawl_log_file"] = log_file
    state["crawl_pid"] = proc.pid
    persist_ui_state()


def render_images(images: list[str], key_prefix: str):
    if not images:
        st.caption("暂无图片")
        return
    cols = st.columns(min(3, len(images)))
    for idx, image_path in enumerate(images[:9]):
        with cols[idx % len(cols)]:
            st.image(image_path, caption=os.path.basename(image_path), width="stretch")


def render_source(post: dict):
    st.markdown("**原贴出处**")
    st.write("作者: {}".format(post.get("author") or "未知"))
    st.write("发布时间: {}".format(post.get("publish_time") or "未知"))
    st.write("点赞/热度: {}".format(post.get("likes") or "未知"))
    st.write("来源标识: {}".format(post.get("source") or "未知来源"))
    source_url = get_source_url(post)
    if source_url:
        st.markdown("[查看原贴]({})".format(source_url))
    favorite_status = (
        "已收藏到 {}".format(post.get("source_favorite_folder") or XHS_FAVORITE_FOLDER)
        if post.get("source_favorited")
        else (post.get("source_favorite_status") or "未收藏")
    )
    st.caption("收藏状态: {}".format(favorite_status))


def render_audit(post: dict):
    audit = post.get("audit", {})
    if not audit:
        st.caption("暂无审核结果")
        return
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("可信度", int(round(audit.get("confidence_score", 0))))
    col2.metric("来源分", int(round(audit.get("source_score", 0))))
    col3.metric("引用分", int(round(audit.get("citation_score", 0))))
    col4.metric("详实度", int(round(audit.get("detail_score", 0))))
    st.caption("是否通过审核: {}".format("是" if audit.get("publish_ready") else "否"))
    issues = audit.get("issues", []) + audit.get("warnings", [])
    if issues:
        st.markdown("**问题与提醒**")
        for item in issues[:8]:
            st.write("- {}".format(item.get("message", "")))


def render_media_assets(post: dict, key_prefix: str):
    st.write("媒体类型: {}".format(format_media_label(post.get("media_type", "image"))))
    images = collect_post_images(post)
    if images:
        st.markdown("**图片预览**")
        render_images(images, "{}_images".format(key_prefix))
    else:
        st.caption("当前没有可预览的图片文件。")

    if str(post.get("media_type") or "").lower() == "video":
        video_path = post.get("original_video_path") or post.get("video_path")
        video_url = post.get("original_video_url") or ""
        if video_path and os.path.exists(video_path):
            st.video(video_path)
        elif video_url:
            st.markdown("[查看原视频]({})".format(video_url))
        transcript = post.get("video_transcript") or ""
        if transcript:
            st.text_area(
                "视频转写",
                value=transcript[:4000],
                height=220,
                key="{}_transcript".format(key_prefix),
            )
        summary = post.get("video_summary") or ""
        if summary:
            st.text_area(
                "视频摘要",
                value=summary,
                height=160,
                key="{}_video_summary".format(key_prefix),
            )


def render_post_tabs(post: dict, key_prefix: str):
    body = get_post_body(post)
    tabs = st.tabs(["待发布文案", "阅读笔记", "原贴详情", "媒体资产", "审核结果"])
    with tabs[0]:
        if body:
            st.text_area(
                "最终待发布文案",
                value=body[:4000],
                height=300,
                key="{}_body".format(key_prefix),
            )
        else:
            st.caption("当前草稿还没有可发布文案。")
    with tabs[1]:
        reading_notes = post.get("reading_notes") or ""
        if reading_notes:
            st.text_area(
                "阅读笔记",
                value=reading_notes,
                height=260,
                key="{}_notes".format(key_prefix),
            )
        else:
            st.caption("当前草稿还没有阅读笔记。")
        image_ocr = post.get("image_ocr_text") or ""
        if image_ocr:
            st.text_area(
                "图片文字转写",
                value=image_ocr[:4000],
                height=180,
                key="{}_ocr".format(key_prefix),
            )
        image_summary = post.get("image_semantic_summary") or post.get("image_summary") or ""
        if image_summary:
            st.text_area(
                "图片语义摘要",
                value=image_summary[:3000],
                height=160,
                key="{}_image_summary".format(key_prefix),
            )
    with tabs[2]:
        render_source(post)
        original_title = post.get("original_title") or post.get("source_title") or post.get("title")
        original_body = post.get("original_content") or post.get("source_content") or post.get("content")
        if original_title:
            st.write("原贴标题: {}".format(original_title))
        if original_body:
            st.text_area(
                "原贴正文",
                value=original_body[:4000],
                height=240,
                key="{}_source_body".format(key_prefix),
            )
        matched_keywords = post.get("matched_user_keywords") or []
        if matched_keywords:
            st.write("命中的用户关键词: {}".format("、".join(matched_keywords)))
        if post.get("keyword_forced_ai"):
            st.caption("该帖子因命中用户关键词，已跳过“是否 AI 相关”的拦截。")
    with tabs[3]:
        render_media_assets(post, key_prefix)
    with tabs[4]:
        render_audit(post)


def publish_draft(dm: DraftManager, draft: dict):
    publisher = XiaohongshuPublisher(headless=False)
    result = publisher.publish_post(draft, dry_run=False)
    if isinstance(result, dict) and result.get("success"):
        dm.update_draft_status(draft["id"], "published")
    return result


def favorite_source(dm: DraftManager, draft: dict):
    publisher = XiaohongshuPublisher(headless=False)
    result = publisher.favorite_source_post(draft.get("post", {}), folder_name=XHS_FAVORITE_FOLDER)
    if isinstance(result, dict) and result.get("success"):
        latest = dm.get_draft(draft["id"]) or draft
        post = dict(latest.get("post", {}))
        post["source_favorited"] = True
        post["source_favorite_folder"] = XHS_FAVORITE_FOLDER
        post["source_favorite_status"] = result.get("message", "已收藏")
        dm.update_draft_post(draft["id"], post)
        dm.set_favorite(draft["id"], True, favorite_source="source_post")
    return result


def show_dashboard(dm: DraftManager):
    drafts = dm.list_drafts()
    image_posts = sum(1 for d in drafts if d.get("post", {}).get("media_type") != "video")
    video_posts = sum(1 for d in drafts if d.get("post", {}).get("media_type") == "video")
    favorites = sum(1 for d in drafts if d.get("favorite"))
    pending = sum(1 for d in drafts if d.get("status") == "draft")
    approved = sum(1 for d in drafts if d.get("post", {}).get("audit", {}).get("publish_ready"))

    st.header("仪表盘")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("草稿总数", len(drafts))
    col2.metric("待发布", pending)
    col3.metric("图文帖", image_posts)
    col4.metric("视频帖", video_posts)
    col5.metric("审核通过", approved)
    st.caption("已收藏草稿: {}".format(favorites))
    st.markdown("---")

    if not drafts:
        st.info("暂无草稿，请先执行抓取流程。")
        st.code("python scripts/crawl_latest_aigc.py")
        return

    st.subheader("最新草稿")
    for idx, draft in enumerate(drafts[:8]):
        post = draft.get("post", {})
        title = post.get("title") or "无标题"
        images = collect_post_images(post)
        status_label = format_status_label(draft.get("status", "未知"))
        media_label = format_media_label(post.get("media_type", "image"))
        with st.expander("{} | {} | {} | {}张图片".format(title, status_label, media_label, len(images)), expanded=False):
            info_cols = st.columns(3)
            info_cols[0].caption("收藏状态: {}".format("已收藏" if draft.get("favorite") else "未收藏"))
            info_cols[1].caption("来源: {}".format(post.get("source") or "未知"))
            info_cols[2].caption("作者: {}".format(post.get("author") or "未知"))
            render_post_tabs(post, "dashboard_post_{}".format(idx))


def show_login_page():
    st.header("登录授权")
    status, file_state = get_login_state()
    state_label = LOGIN_STATUS_LABELS.get(status.get("state"), format_status_label(status.get("state")))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("登录状态", state_label)
    col2.metric("后端", "MCP")
    col3.metric("Profile 目录", "已存在" if os.path.isdir(XHS_PROFILE_DIR) else "未创建")
    col4.metric("Cookie 回退", "未生成（正常）" if not os.path.exists(XHS_COOKIE_FILE) else "已存在")

    if st.button("启动浏览器登录", type="primary", key="start_login_btn"):
        start_login()
        st.success("已启动登录流程，请在浏览器中完成登录。")

    if status.get("reason"):
        st.caption("状态说明: {}".format(status.get("reason")))

    ui_state = get_ui_state()
    status_file = ui_state.get("login_status_file", "")
    log_file = ui_state.get("login_log_file", "")
    if status_file:
        st.caption("状态文件: {}".format(status_file))
    if log_file:
        st.caption("日志文件: {}".format(log_file))
        st.text_area("最近日志", value=read_text(log_file)[-4000:], height=220, key="login_log_view")

    st.caption("MCP Profile 目录: {}".format(XHS_PROFILE_DIR))
    st.caption("Cookie 回退文件: {}".format(XHS_COOKIE_FILE))

    profile_url = status.get("data", {}).get("profileUrl") or status.get("profileUrl")
    if profile_url:
        st.markdown("[账号主页]({})".format(profile_url))
    if file_state:
        st.json(file_state)


def show_drafts(dm: DraftManager):
    drafts = dm.list_drafts()
    st.header("草稿管理")
    if not drafts:
        st.info("暂无草稿。")
        return

    status_filter = st.selectbox(
        "状态筛选",
        ["全部", "draft", "published", "discarded"],
        format_func=lambda value: "全部" if value == "全部" else format_status_label(value),
        key="draft_status_filter",
    )
    media_filter = st.selectbox(
        "媒体类型",
        ["全部", "image", "video"],
        format_func=lambda value: {"全部": "全部", "image": "图文", "video": "视频"}.get(value, value),
        key="draft_media_filter",
    )
    favorite_filter = st.selectbox("收藏筛选", ["全部", "仅收藏", "未收藏"], key="draft_favorite_filter")
    keyword = st.text_input("搜索标题或文案", "", key="draft_keyword")

    filtered = []
    for draft in drafts:
        post = draft.get("post", {})
        if status_filter != "全部" and draft.get("status") != status_filter:
            continue
        if media_filter != "全部" and post.get("media_type", "image") != media_filter:
            continue
        if favorite_filter == "仅收藏" and not draft.get("favorite"):
            continue
        if favorite_filter == "未收藏" and draft.get("favorite"):
            continue
        title = post.get("title", "")
        body = get_post_body(post)
        if keyword and keyword.lower() not in (title + "\n" + body).lower():
            continue
        filtered.append(draft)

    st.info("筛选结果: {} / {} 个草稿".format(len(filtered), len(drafts)))

    for idx, draft in enumerate(filtered):
        post = draft.get("post", {})
        title = post.get("title") or "无标题"
        images = collect_post_images(post)
        status_label = format_status_label(draft.get("status", "未知"))
        media_label = format_media_label(post.get("media_type", "image"))
        with st.expander("{} | {} | {} | {}张图片".format(title, status_label, media_label, len(images)), expanded=False):
            badge_cols = st.columns(4)
            badge_cols[0].caption("收藏: {}".format("是" if draft.get("favorite") else "否"))
            badge_cols[1].caption("来源: {}".format(post.get("source") or "未知"))
            badge_cols[2].caption("作者: {}".format(post.get("author") or "未知"))
            badge_cols[3].caption("审核通过: {}".format("是" if post.get("audit", {}).get("publish_ready") else "否"))
            render_post_tabs(post, "draft_post_{}".format(idx))

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("发布到小红书", key="publish_{}".format(draft["id"])):
                    result = publish_draft(dm, draft)
                    if isinstance(result, dict) and result.get("success"):
                        st.success(result.get("message", "发布成功"))
                    else:
                        st.error((result or {}).get("message", "发布失败") if isinstance(result, dict) else "发布失败")
                    st.rerun()
            with col2:
                if st.button("收藏原贴", key="favorite_{}".format(draft["id"])):
                    result = favorite_source(dm, draft)
                    if isinstance(result, dict) and result.get("success"):
                        st.success(result.get("message", "已收藏"))
                    else:
                        st.warning((result or {}).get("message", "收藏失败") if isinstance(result, dict) else "收藏失败")
                    st.rerun()
            with col3:
                if st.button("删除草稿", key="delete_{}".format(draft["id"])):
                    dm.delete_draft(draft["id"])
                    st.success("草稿已删除")
                    st.rerun()


def show_crawl_management(dm: DraftManager):
    st.header("爬取管理")
    settings = load_crawl_settings()

    keywords = st.text_input("搜索关键词", settings["keywords"], key="crawl_keywords")
    max_posts = st.number_input("最大帖子数", min_value=1, max_value=50, value=settings["max_posts"], step=1, key="crawl_max_posts")
    skip_video = st.checkbox("跳过视频帖", value=settings["skip_video"], key="crawl_skip_video")

    st.caption("当前模式: 关键词 [{}] | 最大帖子数 {} | {}".format(keywords, int(max_posts), "跳过视频" if skip_video else "保留视频"))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("保存爬取设置", key="save_crawl_settings_btn"):
            save_crawl_settings(keywords, int(max_posts), skip_video)
            st.success("爬取设置已保存")
    with col2:
        if st.button("开始实时爬取", type="primary", key="start_crawl_btn"):
            save_crawl_settings(keywords, int(max_posts), skip_video)
            start_crawl(keywords, int(max_posts), skip_video)
            st.success("已启动后台爬取任务。")

    ui_state = get_ui_state()
    status_file = ui_state.get("crawl_status_file", "")
    log_file = ui_state.get("crawl_log_file", "")
    payload = read_json(status_file)

    if payload:
        stage = payload.get("stage_label") or payload.get("stage_id") or "初始化"
        current = int(payload.get("current") or 0)
        total = max(1, int(payload.get("total") or 1))
        st.progress(min(current / total, 1.0), text="当前阶段: {} ({}/{})".format(stage, current, total))

        cols = st.columns(6)
        cols[0].metric("候选数", int(payload.get("searched") or 0))
        cols[1].metric("补抓详情", int(payload.get("hydrated") or 0))
        cols[2].metric("AI 相关", int(payload.get("ai_related") or 0))
        cols[3].metric("媒体处理", int(payload.get("media_processed") or 0))
        cols[4].metric("通过审核", int(payload.get("approved") or 0))
        cols[5].metric("打回数", int(payload.get("rejected") or 0))

        if payload.get("last_message"):
            st.caption(payload.get("last_message"))
        if payload.get("last_error"):
            st.error("最近错误: {}".format(payload.get("last_error")))

        summary = payload.get("result_summary") or {}
        if summary:
            st.subheader("结果汇总")
            sum_cols = st.columns(4)
            sum_cols[0].metric("搜索候选", int(summary.get("searched") or payload.get("searched") or 0))
            sum_cols[1].metric("详情成功", int(summary.get("hydrated_success") or payload.get("hydrated") or 0))
            sum_cols[2].metric("媒体成功", int(summary.get("media_processed") or payload.get("media_processed") or 0))
            sum_cols[3].metric("最终草稿", int(summary.get("approved_posts") or payload.get("approved") or 0))
            if summary.get("notes"):
                for note in summary.get("notes", []):
                    st.write("- {}".format(note))
            if summary.get("keyword_hits"):
                st.write("关键词命中:")
                for item in summary.get("keyword_hits", []):
                    st.write("- {}: {}".format(item.get("keyword", ""), item.get("hits", 0)))
            if summary.get("top_rejection_reasons"):
                st.write("主要打回原因:")
                for item in summary.get("top_rejection_reasons", []):
                    st.write("- {}: {}".format(item.get("reason", "未说明"), item.get("count", 0)))
    else:
        st.info("当前还没有进行中的爬取任务。保存设置后即可启动实时爬取。")

    if log_file:
        st.subheader("实时日志")
        st.text_area("后台输出", value=read_text(log_file)[-6000:], height=280, key="crawl_log_view")

    latest_drafts = dm.list_drafts()[:5]
    if latest_drafts:
        st.subheader("最近生成的草稿")
        for index, draft in enumerate(latest_drafts):
            post = draft.get("post", {})
            st.write("- {} | {} | {}".format(post.get("title") or "无标题", format_status_label(draft.get("status")), format_media_label(post.get("media_type"))))


def show_settings():
    st.header("设置")
    settings = load_ai_settings()
    ollama_available, ollama_message, detected_model = check_ollama_available()

    st.subheader("模型路由")
    mode_options = ["ollama", "deepseek", "auto", "openai", "local"]
    labels = {
        "content_analyzer_mode": "内容分析",
        "content_rewriter_mode": "内容润色",
        "content_auditor_mode": "内容审核",
        "image_processing_mode": "图片理解",
        "video_transcription_mode": "视频转写",
    }

    updated = {}
    for key, label in labels.items():
        current = settings.get(key, DEFAULT_AI_RUNTIME_SETTINGS.get(key, "deepseek"))
        index = mode_options.index(current) if current in mode_options else 0
        updated[key] = st.selectbox(
            label,
            mode_options,
            index=index,
            format_func=format_mode_label,
            key="setting_{}".format(key),
        )

    if st.button("保存模型设置", type="primary", key="save_ai_settings_btn"):
        save_ai_settings(updated)
        st.success("模型设置已保存")
        settings = load_ai_settings()

    st.markdown("---")
    st.subheader("服务状态")
    col1, col2, col3 = st.columns(3)
    col1.metric("Ollama 状态", "可用" if ollama_available else "不可用")
    col2.metric("默认地址", OLLAMA_BASE_URL)
    col3.metric("默认模型", detected_model or OLLAMA_MODEL)
    st.caption(ollama_message)

    key_cols = st.columns(3)
    key_cols[0].metric("DeepSeek Key", "已配置" if has_valid_deepseek_api_key() else "未配置")
    key_cols[1].metric("OpenAI Key", "已配置" if has_valid_openai_api_key() else "未配置")
    key_cols[2].metric("Gemini Key", "已配置" if has_valid_gemini_api_key() else "未配置")

    st.subheader("当前生效策略")
    for key, label in labels.items():
        st.write("- {}: {}".format(label, format_mode_label(settings.get(key))))

    st.markdown("---")
    st.subheader("说明")
    st.write("- ChatGPT Plus 会员不能直接替代 API Key；脚本调用 DeepSeek、OpenAI、Gemini 仍需要各自的 API Key。")
    st.write("- 如果选择“自动选择”，系统会优先尝试 Ollama，其次 DeepSeek，再其次 OpenAI，最后回退到本地模式。")
    st.write("- 当前模型设置文件: {}".format(XHS_AI_SETTINGS_FILE))
    st.write("- 当前爬取设置文件: {}".format(XHS_CRAWL_SETTINGS_FILE))


def show_about():
    st.header("关于")
    st.write("这是当前项目的稳定版控制台入口，负责串联登录、抓取、草稿查看与基础设置。")
    st.write("当前页面优先保证中文可读、结构稳定、核心功能可用，后续可以继续在这份干净版本上补回更复杂的高级交互。")


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    dm = DraftManager()
    with st.sidebar:
        page = st.radio("页面", ["仪表盘", "登录授权", "草稿管理", "爬取管理", "设置", "关于"], key="sidebar_page")
        if st.button("刷新页面", key="sidebar_refresh"):
            st.rerun()

    if page == "仪表盘":
        show_dashboard(dm)
    elif page == "登录授权":
        show_login_page()
    elif page == "草稿管理":
        show_drafts(dm)
    elif page == "爬取管理":
        show_crawl_management(dm)
    elif page == "设置":
        show_settings()
    else:
        show_about()


if __name__ == "__main__":
    main()
