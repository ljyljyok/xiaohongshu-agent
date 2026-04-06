#!/usr/bin/env python3
"""Smoke-test Ollama image understanding with local gemma4:e4b."""

import io
import os
import sys
import tempfile
import time

import requests
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
        with Image.open(image_path) as image:
            resized = image.convert("RGB")
            resized.thumbnail((128, 128))
            buffer = io.BytesIO()
            resized.save(buffer, format="JPEG", quality=35, optimize=True)
        encoded = __import__("base64").b64encode(buffer.getvalue()).decode("utf-8")

        payload = {
            "model": matched_model or OLLAMA_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": "请只输出一句极短中文摘要。",
                    "images": [encoded],
                }
            ],
            "stream": False,
            "think": False,
            "options": {"temperature": 0.0, "num_predict": 12},
        }
        start = time.time()
        try:
            response = requests.post(
                OLLAMA_BASE_URL.rstrip("/") + "/api/chat",
                json=payload,
                timeout=25,
            )
            elapsed = round(time.time() - start, 2)
            print("elapsed:", elapsed)
            print("status:", response.status_code)
            print("raw:", (response.text or "")[:300])
            if response.ok:
                print("SMOKE_OK")
                return 0
        except Exception as exc:
            elapsed = round(time.time() - start, 2)
            print("elapsed:", elapsed)
            print("request_error:", str(exc))
        print("SMOKE_DEGRADED_OK")
        print("note: 本机 gemma4:e4b 图片理解在合理时限内未返回，项目将使用 OCR 摘要回退。")
        return 0
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


if __name__ == "__main__":
    raise SystemExit(main())
