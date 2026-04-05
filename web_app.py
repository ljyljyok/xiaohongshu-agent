#!/usr/bin/env python3
"""Stable Streamlit app entrypoint for the Xiaohongshu agent."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime

import streamlit as st
from PIL import Image

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
PAGE_OPTIONS = {
    "🏠 仪表盘": "仪表盘",
    "🔐 登录授权": "登录授权",
    "📝 草稿管理": "草稿管理",
    "🚀 爬取管理": "爬取管理",
    "🛠️ 设置": "设置",
    "ℹ️ 关于": "关于",
}

APP_CSS = """
<style>
    :root {
        --bg-0: #f8fafc;
        --bg-1: #eef2ff;
        --bg-2: #fff7ed;
        --ink-0: #0f172a;
        --ink-1: #334155;
        --line-0: rgba(148, 163, 184, 0.18);
        --shadow-0: 0 16px 36px rgba(15, 23, 42, 0.08);
        --shadow-1: 0 10px 22px rgba(15, 23, 42, 0.05);
        --accent: #2563eb;
        --accent-2: #ea580c;
    }
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(37, 99, 235, 0.13), transparent 28%),
            radial-gradient(circle at top right, rgba(234, 88, 12, 0.1), transparent 24%),
            linear-gradient(180deg, var(--bg-0) 0%, #f3f6fb 100%);
        color: var(--ink-0);
        font-family: "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
    }
    .stApp p, .stApp li, .stApp label, .stApp span, .stApp div {
        color: inherit;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
        color: var(--ink-0) !important;
    }
    .stCaptionContainer, [data-testid="stCaptionContainer"] {
        color: #475569 !important;
    }
    .stApp > header {
        background: transparent;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #101827 0%, #0f172a 100%);
        color: #e5e7eb;
    }
    section[data-testid="stSidebar"] .stRadio label,
    section[data-testid="stSidebar"] .stButton button,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {
        color: #e5e7eb !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        border-radius: 14px;
        margin: 0.18rem 0;
        padding: 0.32rem 0.45rem;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid transparent;
        transition: all 0.18s ease;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background: rgba(255, 255, 255, 0.06);
        border-color: rgba(255, 255, 255, 0.08);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.24), rgba(249, 115, 22, 0.16));
        border-color: rgba(147, 197, 253, 0.22);
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.05), 0 10px 20px rgba(15, 23, 42, 0.18);
        transform: translateX(2px);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
        color: #ffffff !important;
        font-weight: 700;
    }
    div[data-testid="stMetric"] {
        border-radius: 20px;
        padding: 1rem 1rem 0.8rem 1rem;
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid var(--line-0);
        box-shadow: var(--shadow-1);
        animation: softRise 0.45s ease both;
        min-height: 116px;
    }
    div[data-testid="stMetric"] label[data-testid="stMetricLabel"] p {
        font-size: 0.84rem !important;
        color: #475569 !important;
        font-weight: 700 !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 1.42rem !important;
        color: #0f172a !important;
        font-weight: 800 !important;
    }
    div[data-testid="stExpander"] {
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid var(--line-0);
        box-shadow: var(--shadow-1);
        margin-bottom: 0.85rem;
        animation: softRise 0.45s ease both;
    }
    div[data-testid="stTabs"] {
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.92);
        padding: 0.25rem 0.5rem 0.5rem 0.5rem;
        border: 1px solid var(--line-0);
        box-shadow: var(--shadow-1);
    }
    div[data-testid="stButton"] > button {
        border-radius: 14px;
        border: 1px solid rgba(37, 99, 235, 0.18);
        box-shadow: 0 8px 18px rgba(37, 99, 235, 0.08);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 12px 24px rgba(37, 99, 235, 0.14);
    }
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {
        border-radius: 14px !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        background: rgba(255, 255, 255, 0.96) !important;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .hero-banner {
        border-radius: 24px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        color: var(--ink-0);
        background:
            linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(236, 72, 153, 0.08)),
            rgba(255, 255, 255, 0.82);
        border: 1px solid var(--line-0);
        box-shadow: var(--shadow-0);
        animation: heroFade 0.55s ease both;
    }
    .hero-banner h1 {
        margin: 0 0 0.25rem 0;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        display: flex;
        align-items: center;
        gap: 0.55rem;
    }
    .hero-banner p {
        margin: 0;
        color: #334155;
        font-size: 0.98rem;
    }
    .small-note {
        color: #64748b;
        font-size: 0.92rem;
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.7rem;
        margin-right: 0.35rem;
        border-radius: 999px;
        font-size: 0.78rem;
        line-height: 1.4;
        background: rgba(37, 99, 235, 0.08);
        color: var(--accent);
        border: 1px solid rgba(37, 99, 235, 0.12);
    }
    .status-badge.green {
        background: rgba(22, 163, 74, 0.08);
        color: #15803d;
        border-color: rgba(22, 163, 74, 0.12);
    }
    .status-badge.orange {
        background: rgba(234, 88, 12, 0.08);
        color: #c2410c;
        border-color: rgba(234, 88, 12, 0.12);
    }
    .status-badge.slate {
        background: rgba(100, 116, 139, 0.1);
        color: #475569;
        border-color: rgba(100, 116, 139, 0.12);
    }
    .section-shell {
        border-radius: 22px;
        padding: 1rem 1.1rem;
        margin-bottom: 0.9rem;
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid var(--line-0);
        box-shadow: var(--shadow-1);
        animation: softRise 0.4s ease both;
    }
    .section-shell h2 {
        margin: 0 0 0.2rem 0;
        font-size: 1.1rem;
    }
    .cover-card {
        border-radius: 20px;
        overflow: hidden;
        background: rgba(255, 255, 255, 0.95);
        border: 1px solid var(--line-0);
        box-shadow: var(--shadow-1);
        margin-bottom: 0.8rem;
    }
    .cover-card-head {
        padding: 0.9rem 1rem 0.6rem 1rem;
    }
    .cover-frame {
        border-radius: 18px;
        overflow: hidden;
        border: 1px solid rgba(148, 163, 184, 0.14);
        background: linear-gradient(135deg, rgba(59,130,246,0.06), rgba(249,115,22,0.06));
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.4);
        margin: 0.2rem 0 0.85rem 0;
    }
    .cover-stack {
        position: relative;
        margin: 0.2rem 0 0.85rem 0;
    }
    .cover-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.5rem;
        padding: 0.55rem 0.75rem;
        background: linear-gradient(180deg, rgba(15,23,42,0.88), rgba(30,41,59,0.82));
        color: #f8fafc;
        font-size: 0.82rem;
    }
    .cover-meta strong {
        color: #ffffff;
        font-weight: 700;
    }
    .cover-hover-note {
        position: absolute;
        left: 0.85rem;
        right: 0.85rem;
        bottom: 0.85rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.8rem;
        padding: 0.6rem 0.8rem;
        border-radius: 14px;
        background: linear-gradient(180deg, rgba(15,23,42,0.08), rgba(15,23,42,0.82));
        color: #f8fafc;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 24px rgba(15,23,42,0.18);
    }
    .cover-hover-note strong,
    .cover-hover-note span {
        color: #f8fafc !important;
        font-size: 0.82rem;
    }
    .cover-card-title {
        margin: 0 0 0.2rem 0;
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--ink-0);
        line-height: 1.45;
    }
    .cover-card-sub {
        margin: 0;
        color: var(--ink-1);
        font-size: 0.9rem;
    }
    .summary-card {
        border-radius: 18px;
        padding: 0.95rem 1rem;
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid var(--line-0);
        box-shadow: var(--shadow-1);
        min-height: 116px;
        height: 100%;
    }
    .summary-card-value {
        display: block;
        font-size: 1.12rem;
        font-weight: 800;
        color: var(--ink-0);
        margin-bottom: 0.18rem;
        line-height: 1.35;
        word-break: break-word;
    }
    .summary-card-label {
        color: var(--ink-1);
        font-size: 0.86rem;
        line-height: 1.4;
        word-break: break-word;
    }
    .state-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.8rem;
        margin: 0.35rem 0 1rem 0;
    }
    .state-card {
        border-radius: 18px;
        padding: 0.95rem 1rem;
        background: rgba(255,255,255,0.92);
        border: 1px solid var(--line-0);
        box-shadow: var(--shadow-1);
        min-height: 112px;
    }
    .state-card-head {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        margin-bottom: 0.35rem;
        color: var(--ink-0);
        font-weight: 700;
    }
    .state-card-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2rem;
        height: 2rem;
        border-radius: 999px;
        background: rgba(37,99,235,0.1);
        font-size: 1rem;
    }
    .state-card-value {
        font-size: 1rem;
        font-weight: 700;
        color: var(--ink-0);
        line-height: 1.45;
    }
    .state-card-note {
        margin-top: 0.22rem;
        color: var(--ink-1);
        font-size: 0.84rem;
        line-height: 1.45;
    }
    .state-panel {
        border-radius: 18px;
        padding: 0.95rem 1rem;
        background: rgba(255,255,255,0.92);
        border: 1px solid var(--line-0);
        box-shadow: var(--shadow-1);
        min-height: 122px;
        margin-bottom: 0.6rem;
    }
    .state-panel-head {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        margin-bottom: 0.35rem;
        font-weight: 700;
        color: var(--ink-0);
    }
    .state-panel-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2rem;
        height: 2rem;
        border-radius: 999px;
        background: rgba(37,99,235,0.1);
        font-size: 1rem;
    }
    .state-panel-value {
        font-size: 1rem;
        line-height: 1.45;
        font-weight: 700;
        color: var(--ink-0);
        word-break: break-word;
    }
    .state-panel-note {
        margin-top: 0.22rem;
        color: var(--ink-1);
        font-size: 0.84rem;
        line-height: 1.45;
    }
    .dashboard-shell {
        display: grid;
        grid-template-columns: minmax(0, 1.7fr) minmax(300px, 0.9fr);
        gap: 1rem;
        align-items: start;
    }
    .quick-panel {
        border-radius: 20px;
        padding: 1rem 1.05rem;
        background: rgba(255,255,255,0.92);
        border: 1px solid var(--line-0);
        box-shadow: var(--shadow-1);
        margin-bottom: 0.9rem;
    }
    .quick-panel h3 {
        margin: 0 0 0.45rem 0;
        font-size: 1rem;
        color: var(--ink-0);
    }
    .quick-panel p {
        margin: 0.15rem 0;
        color: var(--ink-1);
        font-size: 0.9rem;
    }
    .empty-shell {
        border-radius: 20px;
        padding: 1.1rem 1.15rem;
        background: linear-gradient(135deg, rgba(59,130,246,0.08), rgba(249,115,22,0.08));
        border: 1px dashed rgba(148,163,184,0.35);
        color: var(--ink-1);
        margin: 0.4rem 0 0.9rem 0;
    }
    .action-strip {
        display: flex;
        gap: 0.55rem;
        flex-wrap: wrap;
        margin: 0.2rem 0 0.3rem 0;
    }
    .action-chip {
        display: inline-block;
        padding: 0.32rem 0.75rem;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.04);
        color: var(--ink-1);
        font-size: 0.82rem;
        border: 1px solid rgba(148, 163, 184, 0.14);
    }
    .toolbar-shell {
        position: sticky;
        top: 0.5rem;
        z-index: 5;
        display: flex;
        gap: 0.55rem;
        flex-wrap: wrap;
        margin: 0 0 0.8rem 0;
        padding: 0.75rem 0.8rem;
        border-radius: 16px;
        background: rgba(248, 250, 252, 0.92);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.18);
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
    }
    .toolbar-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.32rem 0.7rem;
        border-radius: 999px;
        background: rgba(37, 99, 235, 0.08);
        color: var(--accent);
        font-size: 0.82rem;
        border: 1px solid rgba(37, 99, 235, 0.12);
    }
    .sidebar-brand {
        border-radius: 18px;
        padding: 0.95rem 0.95rem 0.85rem 0.95rem;
        margin-bottom: 0.9rem;
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.18), rgba(249, 115, 22, 0.14));
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 12px 28px rgba(2, 6, 23, 0.22);
    }
    .sidebar-brand h3 {
        margin: 0;
        color: #f8fafc;
        font-size: 1.02rem;
        font-weight: 800;
        letter-spacing: 0.02em;
    }
    .sidebar-brand p {
        margin: 0.32rem 0 0 0;
        color: rgba(226, 232, 240, 0.84);
        font-size: 0.84rem;
        line-height: 1.45;
    }
    @keyframes heroFade {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes softRise {
        from { opacity: 0; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>
"""


def apply_theme():
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_hero(title: str, subtitle: str, icon: str = ""):
    icon_html = f"<span>{icon}</span>" if icon else ""
    st.markdown(
        """
        <div class="hero-banner">
            <h1>{}{}</h1>
            <p>{}</p>
        </div>
        """.format(icon_html, title, subtitle),
        unsafe_allow_html=True,
    )


def render_section(title: str, subtitle: str = "", icon: str = ""):
    extra = f"<div class='small-note'>{subtitle}</div>" if subtitle else ""
    icon_html = f"{icon} " if icon else ""
    st.markdown(
        f"""
        <div class="section-shell">
            <h2>{icon_html}{title}</h2>
            {extra}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_badges(items: list[tuple[str, str]]):
    html = "".join(
        f"<span class='status-badge {cls}'>{text}</span>"
        for text, cls in items
        if text
    )
    if html:
        st.markdown(html, unsafe_allow_html=True)


def render_cover_card(title: str, subtitle: str, badges: list[tuple[str, str]]):
    st.markdown(
        """
        <div class="cover-card">
            <div class="cover-card-head">
                <div class="cover-card-title">{}</div>
                <div class="cover-card-sub">{}</div>
            </div>
        </div>
        """.format(title, subtitle),
        unsafe_allow_html=True,
    )
    render_badges(badges)


def render_action_strip(items: list[str]):
    html = "".join(f"<span class='action-chip'>{item}</span>" for item in items if item)
    if html:
        st.markdown(f"<div class='action-strip'>{html}</div>", unsafe_allow_html=True)


def render_toolbar(items: list[str]):
    html = "".join(f"<span class='toolbar-chip'>{item}</span>" for item in items if item)
    if html:
        st.markdown(f"<div class='toolbar-shell'>{html}</div>", unsafe_allow_html=True)


def render_summary_ribbon(items: list[tuple[str, str]]):
    if not items:
        return
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(
                """
                <div class="summary-card">
                    <span class="summary-card-value">{}</span>
                    <span class="summary-card-label">{}</span>
                </div>
                """.format(value, label),
                unsafe_allow_html=True,
            )


def render_state_grid(items: list[tuple[str, str, str, str]]):
    if not items:
        return
    cols = st.columns(len(items))
    for col, (icon, title, value, note) in zip(cols, items):
        with col:
            card = st.container(border=True)
            card.markdown("### {} {}".format(icon, title))
            card.write(value)
            card.caption(note)


def render_empty_shell(title: str, description: str):
    st.markdown(
        """
        <div class="empty-shell">
            <strong>{}</strong><br/>
            {}
        </div>
        """.format(title, description),
        unsafe_allow_html=True,
    )


def render_sidebar_brand():
    st.markdown(
        """
        <div class="sidebar-brand">
            <h3>小红书 Agent</h3>
            <p>抓取、审核、润色、发布，一站式工作台。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def go_to_sidebar_page(label: str):
    st.session_state["sidebar_page"] = label
    st.rerun()


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


def status_icon(status: str) -> str:
    return {
        "draft": "🕒",
        "published": "✅",
        "discarded": "🗑️",
    }.get(str(status or "").lower(), "📄")


def media_icon(media_type: str) -> str:
    return "🎬" if str(media_type or "").lower() == "video" else "🖼️"


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


def render_cover_preview(images: list[str], key_prefix: str):
    if not images:
        st.markdown(
            """
            <div class="cover-card cover-frame" style="padding:0; min-height:220px; display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg, rgba(59,130,246,0.08), rgba(249,115,22,0.08));">
                <div class="small-note">暂无封面图片</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    image_path = images[0]
    try:
        with Image.open(image_path) as img:
            prepared = img.convert("RGB")
            target_ratio = 16 / 9
            width, height = prepared.size
            current_ratio = width / max(height, 1)
            if current_ratio > target_ratio:
                new_width = int(height * target_ratio)
                left = max((width - new_width) // 2, 0)
                prepared = prepared.crop((left, 0, left + new_width, height))
            elif current_ratio < target_ratio:
                new_height = int(width / target_ratio)
                top = max((height - new_height) // 2, 0)
                prepared = prepared.crop((0, top, width, top + new_height))
            st.markdown(
                """
                <div class="cover-frame">
                    <div class="cover-meta">
                        <strong>封面预览</strong>
                        <span>16:9 统一裁切</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.image(prepared, width="stretch")
            st.markdown(
                """
                <div class="cover-hover-note">
                    <strong>内容封面</strong>
                    <span>统一裁切，便于快速浏览</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption("封面区采用统一裁切和说明浮层，便于在仪表盘里快速判断内容质量。")
    except Exception:
        st.image(image_path, caption="封面预览", width="stretch")


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
    else:
        st.caption("当前内容没有明显风险提示，适合继续检查排版和最终文案。")


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
    else:
        st.caption("图文帖会重点展示图片理解和阅读笔记，便于直接判断是否适合发布。")


def render_post_tabs(post: dict, key_prefix: str):
    body = get_post_body(post)
    render_toolbar([
        "媒体 {}".format(format_media_label(post.get("media_type", "image"))),
        "来源 {}".format(post.get("source") or "未知"),
        "原贴 {}".format("可访问" if get_source_url(post) else "缺失"),
        "审核 {}".format("通过" if post.get("audit", {}).get("publish_ready") else "待确认"),
    ])
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

    render_hero("仪表盘", "总览草稿、审核、收藏和发布进度，快速找到下一步要处理的内容。", icon="🏠")
    render_section("仪表盘", "总览草稿、审核、收藏和发布进度。", icon="📊")
    st.header("仪表盘")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("草稿总数", len(drafts))
    col2.metric("待发布", pending)
    col3.metric("图文帖", image_posts)
    col4.metric("视频帖", video_posts)
    col5.metric("审核通过", approved)
    render_summary_ribbon([
        ("今日焦点", "优先处理待发布草稿"),
        ("审核通过", str(approved)),
        ("已收藏", str(favorites)),
        ("内容类型", "{} 图文 / {} 视频".format(image_posts, video_posts)),
    ])
    st.caption("已收藏草稿: {}".format(favorites))
    st.markdown("---")

    if not drafts:
        st.info("暂无草稿，请先执行抓取流程。")
        st.code("python scripts/crawl_latest_aigc.py")
        return

    main_col, side_col = st.columns([1.8, 1], gap="large")
    with main_col:
        st.subheader("✨ 最新草稿")
        for idx, draft in enumerate(drafts[:8]):
            post = draft.get("post", {})
            title = post.get("title") or "无标题"
            images = collect_post_images(post)
            status_label = format_status_label(draft.get("status", "未知"))
            media_label = format_media_label(post.get("media_type", "image"))
            title_line = "{} {} | {} {} | {}".format(
                media_icon(post.get("media_type", "image")),
                title,
                status_icon(draft.get("status", "unknown")),
                status_label,
                media_label,
            )
            with st.expander("{} | {}张图片".format(title_line, len(images)), expanded=False):
                render_cover_card(
                    "{} {}  {} {}".format(
                        media_icon(post.get("media_type", "image")),
                        title,
                        status_icon(draft.get("status", "unknown")),
                        status_label,
                    ),
                    "{} | {} | 作者 {}".format(status_label, media_label, post.get("author") or "未知"),
                    [
                        ("{}".format(status_label), "green" if draft.get("status") == "published" else "slate"),
                        ("{}".format(media_label), "orange" if post.get("media_type") == "video" else "slate"),
                        ("已收藏" if draft.get("favorite") else "未收藏", "green" if draft.get("favorite") else "slate"),
                    ],
                )
                render_action_strip([
                    "来源 {}".format(post.get("source") or "未知"),
                    "图片 {} 张".format(len(images)),
                    "审核 {}".format("通过" if post.get("audit", {}).get("publish_ready") else "待确认"),
                ])
                render_cover_preview(images, "dashboard_cover_{}".format(idx))
                render_post_tabs(post, "dashboard_post_{}".format(idx))
    with side_col:
        st.markdown(
            """
            <div class="quick-panel">
                <h3>快捷总览</h3>
                <p>待发布草稿: {}</p>
                <p>已收藏草稿: {}</p>
                <p>审核通过: {}</p>
                <p>视频草稿: {}</p>
            </div>
            """.format(pending, favorites, approved, video_posts),
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="quick-panel">
                <h3>建议下一步</h3>
                <p>1. 先检查待发布草稿的阅读笔记与封面。</p>
                <p>2. 再确认原贴来源与审核状态。</p>
                <p>3. 最后统一执行发布或收藏动作。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def show_login_page():
    render_hero("登录授权", "通过 MCP 维持登录态，并同步查看账号状态与登录日志。", icon="🔐")
    render_section("登录状态", "检查当前登录态、MCP Profile 与 Cookie 回退信息。", icon="🪪")
    st.header("登录授权")
    status, file_state = get_login_state()
    state_label = LOGIN_STATUS_LABELS.get(status.get("state"), format_status_label(status.get("state")))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("登录状态", state_label)
    col2.metric("后端", "MCP")
    col3.metric("Profile 目录", "已存在" if os.path.isdir(XHS_PROFILE_DIR) else "未创建")
    col4.metric("Cookie 回退", "未生成（正常）" if not os.path.exists(XHS_COOKIE_FILE) else "已存在")
    render_state_grid([
        ("🔐", "登录状态", state_label, "当前账号是否可用于发布和抓取"),
        ("🧩", "后端", "MCP", "默认通过 MCP 维持登录态"),
        ("📁", "Profile 目录", "已存在" if os.path.isdir(XHS_PROFILE_DIR) else "未创建", XHS_PROFILE_DIR),
        ("🍪", "Cookie 回退", "未生成（正常）" if not os.path.exists(XHS_COOKIE_FILE) else "已存在", XHS_COOKIE_FILE),
    ])
    render_summary_ribbon([
        ("登录状态", state_label),
        ("后端", "MCP"),
        ("Profile", "已存在" if os.path.isdir(XHS_PROFILE_DIR) else "未创建"),
        ("Cookie 回退", "正常未生成" if not os.path.exists(XHS_COOKIE_FILE) else "已存在"),
    ])

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
    else:
        render_empty_shell("还没有登录状态文件", "点击“启动浏览器登录”后，这里会显示最新状态和日志。")


def show_drafts(dm: DraftManager):
    drafts = dm.list_drafts()
    render_hero("草稿管理", "查看、筛选、发布或收藏已生成的草稿，并直接打开原贴来源。", icon="📝")
    render_section("草稿列表", "快速筛选内容类型、收藏状态和审核状态。", icon="📚")
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
        title_line = "{} {} | {} {} | {}".format(
            media_icon(post.get("media_type", "image")),
            title,
            status_icon(draft.get("status", "unknown")),
            status_label,
            media_label,
        )
        with st.expander("{} | {}张图片".format(title_line, len(images)), expanded=False):
            render_cover_card(
                "{} {}  {} {}".format(
                    media_icon(post.get("media_type", "image")),
                    title,
                    status_icon(draft.get("status", "unknown")),
                    status_label,
                ),
                "{} | {} | {}".format(status_label, media_label, post.get("source") or "未知来源"),
                [
                    ("收藏" if draft.get("favorite") else "未收藏", "green" if draft.get("favorite") else "slate"),
                    ("通过审核" if post.get("audit", {}).get("publish_ready") else "待审核", "green" if post.get("audit", {}).get("publish_ready") else "orange"),
                    ("{}".format(media_label), "orange" if post.get("media_type") == "video" else "slate"),
                ],
            )
            render_action_strip([
                "作者 {}".format(post.get("author") or "未知"),
                "图片 {} 张".format(len(images)),
                "原贴 {}".format("已收藏" if post.get("source_favorited") else "未收藏"),
            ])
            render_cover_preview(images, "draft_cover_{}".format(idx))
            render_post_tabs(post, "draft_post_{}".format(idx))

            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("🚀 发布", key="publish_{}".format(draft["id"])):
                    result = publish_draft(dm, draft)
                    if isinstance(result, dict) and result.get("success"):
                        st.success(result.get("message", "发布成功"))
                    else:
                        st.error((result or {}).get("message", "发布失败") if isinstance(result, dict) else "发布失败")
                    st.rerun()
            with col2:
                if st.button("⭐ 收藏", key="favorite_{}".format(draft["id"])):
                    result = favorite_source(dm, draft)
                    if isinstance(result, dict) and result.get("success"):
                        st.success(result.get("message", "已收藏"))
                    else:
                        st.warning((result or {}).get("message", "收藏失败") if isinstance(result, dict) else "收藏失败")
                    st.rerun()
            with col3:
                if st.button("🗑 删除", key="delete_{}".format(draft["id"])):
                    dm.delete_draft(draft["id"])
                    st.success("草稿已删除")
                    st.rerun()


def show_crawl_management(dm: DraftManager):
    render_hero("爬取管理", "配置关键词、抓取规模与视频策略，并实时查看任务进度和结果汇总。", icon="🚀")
    render_section("任务配置", "先保存参数，再启动实时爬取。", icon="🧭")
    st.header("爬取管理")
    settings = load_crawl_settings()

    keywords = st.text_input("搜索关键词", settings["keywords"], key="crawl_keywords")
    max_posts = st.number_input("最大帖子数", min_value=1, max_value=50, value=settings["max_posts"], step=1, key="crawl_max_posts")
    skip_video = st.checkbox("跳过视频帖", value=settings["skip_video"], key="crawl_skip_video")

    ui_state = get_ui_state()
    status_file = ui_state.get("crawl_status_file", "")
    log_file = ui_state.get("crawl_log_file", "")
    payload = read_json(status_file)
    task_status = "运行中" if payload and payload.get("status") == "running" else "待启动"

    st.caption("当前模式: 关键词 [{}] | 最大帖子数 {} | {}".format(keywords, int(max_posts), "跳过视频" if skip_video else "保留视频"))
    render_summary_ribbon([
        ("关键词", keywords or "未设置"),
        ("最大帖子数", str(int(max_posts))),
        ("视频策略", "跳过视频" if skip_video else "保留视频"),
        ("任务状态", task_status),
    ])
    render_state_grid([
        ("🔎", "搜索关键词", keywords or "未设置", "决定本轮抓取的主题范围"),
        ("📚", "最大帖子数", str(int(max_posts)), "限制本轮抓取和处理的规模"),
        ("🎞️", "视频策略", "跳过视频" if skip_video else "保留视频", "决定视频帖是否进入后续链路"),
        ("📡", "任务状态", task_status, "根据状态文件实时更新"),
    ])

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

    if payload:
        render_section("实时进度", "阶段、统计和日志都在这里刷新。", icon="📡")
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
        render_empty_shell("暂无进行中的爬取任务", "先配置关键词和最大帖子数，再点击“开始实时爬取”。")

    if log_file:
        st.subheader("实时日志")
        st.text_area("后台输出", value=read_text(log_file)[-6000:], height=280, key="crawl_log_view")

    latest_drafts = dm.list_drafts()[:5]
    if latest_drafts:
        render_section("最近草稿", "这里会直接显示最新生成的内容，方便快速检查结果。", icon="🆕")
        st.subheader("🆕 最近生成的草稿")
        for index, draft in enumerate(latest_drafts):
            post = draft.get("post", {})
            st.write("- {} | {} | {}".format(post.get("title") or "无标题", format_status_label(draft.get("status")), format_media_label(post.get("media_type"))))


def show_settings():
    render_hero("设置", "统一管理模型路由、本地 Ollama、API Key 和降级策略。", icon="🛠️")
    render_section("模型路由", "为内容分析、润色、审核和媒体理解分别指定模型策略。", icon="⚙️")
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
    render_section("服务状态", "检查本地模型、默认地址、默认模型和当前策略。", icon="🧪")
    st.subheader("服务状态")
    col1, col2, col3 = st.columns(3)
    col1.metric("Ollama 状态", "可用" if ollama_available else "不可用")
    col2.metric("默认地址", OLLAMA_BASE_URL)
    col3.metric("默认模型", detected_model or OLLAMA_MODEL)
    st.caption(ollama_message)
    render_state_grid([
        ("🤖", "Ollama 状态", "可用" if ollama_available else "不可用", "本地模型链路是否可直接调用"),
        ("🌐", "默认地址", OLLAMA_BASE_URL, "本地 Ollama 服务地址"),
        ("🧠", "默认模型", detected_model or OLLAMA_MODEL, "当前检测到的默认模型"),
        ("🪄", "默认策略", format_mode_label(settings.get("content_analyzer_mode")), "内容分析当前优先使用的模式"),
    ])
    render_summary_ribbon([
        ("Ollama", "可用" if ollama_available else "不可用"),
        ("默认地址", OLLAMA_BASE_URL),
        ("默认模型", detected_model or OLLAMA_MODEL),
        ("默认策略", format_mode_label(settings.get("content_analyzer_mode"))),
    ])

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
    render_hero("关于", "这是一份稳定、可维护的控制台入口，优先保证可读性与核心功能的完整性。", icon="ℹ️")
    render_section("说明", "用更清晰的视觉层次，把抓取、草稿和登录流程串起来。", icon="🧾")
    st.header("关于")
    st.write("这是当前项目的稳定版控制台入口，负责串联登录、抓取、草稿查看与基础设置。")
    st.write("当前页面优先保证中文可读、结构稳定、核心功能可用，后续可以继续在这份干净版本上补回更复杂的高级交互。")


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    apply_theme()
    st.title(APP_TITLE)

    dm = DraftManager()
    page_options = {
        "🏠 仪表盘": "仪表盘",
        "🔐 登录授权": "登录授权",
        "📝 草稿管理": "草稿管理",
        "🚀 爬取管理": "爬取管理",
        "🛠️ 设置": "设置",
        "ℹ️ 关于": "关于",
    }
    with st.sidebar:
        render_sidebar_brand()
        page_label = st.radio("页面", list(page_options.keys()), key="sidebar_page")
        if st.button("刷新页面", key="sidebar_refresh"):
            st.rerun()
    page = page_options[page_label]

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
