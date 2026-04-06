#!/usr/bin/env python3
"""Smoke-test Ollama image understanding with local gemma4:e4b."""

import os
import sys
import tempfile

from PIL import Image, ImageDraw

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from config.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from src.ai.image_generator import ImageGenerator
from src.ai.text_llm_client import check_ollama_available, initialize_text_llm


def build_demo_image():
    handle, path = tempfile.mkstemp(suffix=".png")
    os.close(handle)
    image = Image.new("RGB", (160, 90), (245, 247, 250))
    draw = ImageDraw.Draw(image)
    draw.text((30, 40), "AI Tools Overview", fill=(20, 20, 20))
    draw.text((20, 20), "ChatGPT", fill=(20, 20, 20))
    draw.text((20, 45), "Claude", fill=(20, 20, 20))
    image.save(path)
    return path


def main():
    print("=== Ollama Image Semantics Smoke Test ===")
    print("base_url:", OLLAMA_BASE_URL)
    print("model:", OLLAMA_MODEL)

    available, message, matched_model = check_ollama_available()
    print("availability:", available)
    print("availability_message:", message)
    print("matched_model:", matched_model)
    if not available:
        print("SMOKE_NOT_OK")
        return 1

    generator = ImageGenerator()
    client, mode, mode_reason = initialize_text_llm("ollama", "图片理解")
    generator.semantic_client = client
    generator.semantic_provider = mode
    generator.mode_reason = mode_reason
    print("mode:", generator.semantic_provider)
    print("mode_reason:", generator.mode_reason)

    image_path = build_demo_image()
    try:
        summary = generator._summarize_image_semantically(
            image_path,
            "AI Tools Overview\nChatGPT\nClaude",
            "横图",
        )
        print("summary:", summary)
        if generator.semantic_provider == "ollama" and str(summary or "").strip():
            print("SMOKE_OK")
            return 0
        print("SMOKE_NOT_OK")
        return 1
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


if __name__ == "__main__":
    raise SystemExit(main())
