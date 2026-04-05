#!/usr/bin/env python3
"""Smoke-test ContentAnalyzer against local Ollama."""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from config.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from src.ai.content_analyzer import ContentAnalyzer
from src.ai.text_llm_client import check_ollama_available, initialize_text_llm


def main():
    print("=== Ollama Analyzer Smoke Test ===")
    print("base_url:", OLLAMA_BASE_URL)
    print("model:", OLLAMA_MODEL)

    available, message, matched_model = check_ollama_available()
    print("availability:", available)
    print("availability_message:", message)
    print("matched_model:", matched_model)

    analyzer = ContentAnalyzer()
    client, mode, mode_reason = initialize_text_llm("ollama", "内容分析")
    analyzer.client = client
    analyzer.mode = mode
    analyzer.mode_reason = mode_reason
    analyzer.use_ai_mode = client is not None
    print("mode:", analyzer.mode)
    print("mode_reason:", analyzer.mode_reason)

    post = {
        "title": "ChatGPT 与 Claude Code 的最新协作工作流",
        "content": "这是一条关于 AI 工具、工作流和内容生产效率的分析帖。",
    }
    result = analyzer.analyze_content(post, user_keywords=["ChatGPT", "Claude Code"])
    print("result:", result)

    if analyzer.mode == "ollama" and result.get("mode") == "ollama":
        print("SMOKE_OK")
        return 0

    print("SMOKE_NOT_OK")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
