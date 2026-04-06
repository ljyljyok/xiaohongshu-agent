#!/usr/bin/env python3
"""Regression tests for Ollama image semantic summarization."""

import os
import tempfile
from types import SimpleNamespace

from PIL import Image, ImageDraw

from src.ai.image_generator import ImageGenerator


def _make_test_image():
    handle, path = tempfile.mkstemp(suffix=".png")
    os.close(handle)
    image = Image.new("RGB", (640, 360), (245, 247, 250))
    draw = ImageDraw.Draw(image)
    draw.text((30, 40), "AI Tools Overview", fill=(20, 20, 20))
    draw.text((30, 100), "ChatGPT workflow", fill=(20, 20, 20))
    draw.text((30, 140), "Claude Code review", fill=(20, 20, 20))
    image.save(path)
    return path


def test_semantic_summary_uses_ollama_default_model():
    image_path = _make_test_image()
    try:
        generator = ImageGenerator()
        captured = {}

        def fake_create(**kwargs):
            captured["model"] = kwargs.get("model")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="这是一张关于 AI 工具工作流对比的概览图。"))]
            )

        generator.semantic_client = SimpleNamespace(
            default_model="gemma4:e4b",
            chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)),
        )
        generator.semantic_provider = "ollama"

        result = generator._summarize_image_semantically(
            image_path,
            "AI Tools Overview\nChatGPT workflow\nClaude Code review",
            "横图",
        )
        assert captured["model"] == "gemma4:e4b"
        assert "AI 工具" in result
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)
