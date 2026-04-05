#!/usr/bin/env python3
"""Basic regression tests for ContentAnalyzer output shape."""

from src.ai.content_analyzer import ContentAnalyzer


def test_local_analyzer_returns_current_shape():
    analyzer = ContentAnalyzer()
    analyzer.client = None
    analyzer.use_ai_mode = False
    analyzer.mode = "local"
    analyzer.mode_reason = "forced local for test"

    result = analyzer.analyze_content(
        {
            "title": "ChatGPT 最新功能介绍",
            "content": "OpenAI 发布了新的 AI 功能。",
        },
        user_keywords=["OpenAI"],
    )

    assert set(["is_ai_related", "content_type", "relevance_score", "keywords", "mode", "mode_reason"]).issubset(result)
    assert result["is_ai_related"] is True
    assert result["mode"] == "local"
    assert result["keyword_forced_ai"] is False
    assert result["matched_user_keywords"] == []
