#!/usr/bin/env python3
"""Image handling with original-image download, OCR, and semantic summaries."""

import base64
import io
import os
import sys
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image as PILImage, ImageDraw, ImageFont, ImageStat

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from config.config import (
    DATA_DIR,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    get_ai_runtime_mode,
    has_valid_gemini_api_key,
    has_valid_openai_api_key,
)
from src.ai.text_llm_client import initialize_text_llm


class ImageGenerator:
    """Download original images, run OCR, and build reading-note friendly insights."""

    def __init__(self):
        self.openai_client = None
        self.semantic_client = None
        self.semantic_provider = "local"
        self.gemini_client = None
        self.gemini_sdk = ""
        self.gemini_types = None
        self.use_openai_mode = False
        self.use_gemini_mode = False
        self.mode_reason = ""
        self.ocr_engine = None
        self.image_dir = os.path.join(DATA_DIR, "images")
        os.makedirs(self.image_dir, exist_ok=True)

        self._initialize_gemini_client()

        requested_mode = get_ai_runtime_mode("image_processing_mode")
        try:
            self.semantic_client, self.semantic_provider, self.mode_reason = initialize_text_llm(requested_mode, "图片理解")
            if self.semantic_provider == "deepseek":
                self.semantic_client = None
                self.semantic_provider = "local"
                self.mode_reason = "已选择 DeepSeek 图片理解，但当前图片语义补全仅支持 Ollama 视觉或 OpenAI，已退回本地 OCR 模式。"
                print("[INFO] {}".format(self.mode_reason))
            elif self.semantic_client:
                print("[OK] {}".format(self.mode_reason))
            else:
                print("[INFO] {}".format(self.mode_reason))

            if requested_mode == "ollama":
                self.use_openai_mode = False
            elif requested_mode == "deepseek":
                self.use_openai_mode = False
            elif requested_mode != "local" and has_valid_openai_api_key(OPENAI_API_KEY):
                from openai import OpenAI

                self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
                self.use_openai_mode = True
                print("[OK] ImageGenerator using OpenAI image mode")
            elif requested_mode == "openai":
                print("[INFO] 已选择 OpenAI 图像生成，但未配置有效 API Key，图片生成将退回占位图模式。")
        except Exception as exc:
            print("[INFO] Image semantic mode unavailable: {}".format(str(exc)[:80]))

        try:
            from rapidocr_onnxruntime import RapidOCR

            self.ocr_engine = RapidOCR()
            print("[OK] ImageGenerator using RapidOCR")
        except Exception as exc:
            print("[INFO] RapidOCR unavailable: {}".format(str(exc)[:80]))

        self.color_schemes = [
            {"bg": (66, 133, 244), "text": (255, 255, 255)},
            {"bg": (52, 168, 83), "text": (255, 255, 255)},
            {"bg": (251, 188, 5), "text": (0, 0, 0)},
            {"bg": (234, 67, 53), "text": (255, 255, 255)},
            {"bg": (154, 51, 235), "text": (255, 255, 255)},
        ]

    def generate_image(self, prompt, size="1024x1024", quality="standard", n=1):
        if not prompt:
            return []
        if self.use_gemini_mode and self.gemini_client:
            paths = self._generate_with_gemini(prompt, size, n)
            if paths:
                return paths
        if self.use_openai_mode and self.openai_client:
            paths = self._generate_with_openai(prompt, size, quality, n)
            if paths:
                return paths
        return self._generate_placeholder_images(prompt, size, n)

    def _initialize_gemini_client(self):
        if not has_valid_gemini_api_key(GEMINI_API_KEY):
            return

        try:
            from google import genai
            from google.genai import types

            self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            self.gemini_types = types
            self.gemini_sdk = "google-genai"
            self.use_gemini_mode = True
            print("[OK] ImageGenerator using Gemini image mode (google-genai)")
            return
        except Exception as exc:
            print("[INFO] Gemini image mode unavailable with google-genai: {}".format(str(exc)[:120]))

        try:
            import google.generativeai as legacy_genai

            legacy_genai.configure(api_key=GEMINI_API_KEY)
            self.gemini_client = legacy_genai
            self.gemini_sdk = "google-generativeai"
            self.use_gemini_mode = True
            print("[OK] ImageGenerator using Gemini image mode (legacy google-generativeai)")
        except Exception as exc:
            print(
                "[INFO] Gemini image mode unavailable. "
                "Please install google-genai in the active environment. Detail: {}".format(str(exc)[:120])
            )

    def generate_image_from_content(self, content, size="1024x1024", quality="standard"):
        prompt = "根据以下内容生成一张适合小红书图文帖封面的配图：\n\n{}".format((content or "")[:500])
        paths = self.generate_image(prompt, size=size, quality=quality, n=1)
        return paths[0] if paths else ""

    def process_post(self, post, allow_fallback=True):
        processed = dict(post or {})
        content = processed.get("optimized_content", "") or processed.get("rewritten_content", "") or processed.get("content", "")
        original_urls = processed.get("original_image_urls") or processed.get("images", []) or []
        original_paths = self._download_original_images(original_urls)
        generated_paths = []
        image_mode = "original"

        if not original_paths:
            if allow_fallback and content:
                fallback_path = self.generate_image_from_content(content)
                if fallback_path:
                    generated_paths = [fallback_path]
                    if self.use_gemini_mode and os.path.basename(fallback_path).startswith("gemini_"):
                        image_mode = "gemini"
                    elif self.use_openai_mode and os.path.basename(fallback_path).startswith("ai_"):
                        image_mode = "openai"
                    else:
                        image_mode = "local"
                else:
                    image_mode = "failed"
            else:
                image_mode = "missing_original"

        insight_source = original_paths if original_paths else generated_paths
        image_insights, image_summary = self._analyze_image_set(insight_source)
        final_image_paths = self._select_final_images(original_paths, generated_paths)

        processed["media_type"] = processed.get("media_type") or "image"
        processed["original_image_urls"] = self._clean_urls(original_urls)
        processed["original_image_paths"] = original_paths
        processed["generated_image_paths"] = generated_paths
        processed["generated_image_path"] = generated_paths[0] if generated_paths else (final_image_paths[0] if final_image_paths else "")
        processed["final_image_paths"] = final_image_paths
        processed["final_image_count"] = len(final_image_paths)
        processed["image_insights"] = image_insights
        processed["image_summary"] = image_summary
        processed["image_mode"] = image_mode if final_image_paths else image_mode
        processed["image_ocr_items"] = [item.get("ocr_items", []) for item in image_insights if item.get("ocr_items")]
        processed["image_ocr_text"] = "\n\n".join(
            item.get("ocr_text", "").strip() for item in image_insights if item.get("ocr_text", "").strip()
        ).strip()
        processed["image_text_coverage"] = round(
            sum(float(item.get("text_coverage", 0.0) or 0.0) for item in image_insights) / max(len(image_insights), 1),
            4,
        ) if image_insights else 0.0
        processed["image_semantic_summary"] = "\n".join(
            item.get("semantic_summary", "").strip()
            for item in image_insights
            if item.get("semantic_summary", "").strip()
        ).strip()
        return processed

    def batch_process(self, posts, allow_fallback=True):
        processed = []
        for index, post in enumerate(posts):
            try:
                if post.get("analysis", {}).get("is_ai_related", False):
                    processed_post = self.process_post(post, allow_fallback=allow_fallback)
                    print(
                        "[{}] Image processing complete: {} | images={} | mode={}".format(
                            index + 1,
                            processed_post.get("title", "Untitled")[:30],
                            processed_post.get("final_image_count", 0),
                            processed_post.get("image_mode", "unknown"),
                        )
                    )
                    processed.append(processed_post)
                else:
                    processed.append(post)
            except Exception as exc:
                print("[ERROR] Failed to process images for post {}: {}".format(index + 1, str(exc)[:80]))
                failed = dict(post)
                failed["image_mode"] = "failed"
                failed["image_error"] = str(exc)
                processed.append(failed)
        return processed

    def analyze_image_paths(self, image_paths):
        return self._analyze_image_set(image_paths or [])

    def _download_original_images(self, image_urls):
        if not image_urls:
            return []

        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        }

        urls = self._clean_urls(image_urls)
        workers = min(max(len(urls), 1), 4)
        results = {}

        def _download(index, url):
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            if "png" in content_type:
                ext = ".png"
            elif "gif" in content_type:
                ext = ".gif"
            elif "webp" in content_type:
                ext = ".webp"
            else:
                ext = ".jpg"
            filename = "original_{}_{}{}".format(uuid.uuid4().hex[:8], index, ext)
            path = os.path.join(self.image_dir, filename)
            with open(path, "wb") as fh:
                fh.write(response.content)
            return index, path

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="xhs-image-download") as executor:
            future_map = {executor.submit(_download, index, url): index for index, url in enumerate(urls)}
            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    item_index, path = future.result()
                    results[item_index] = path
                except Exception as exc:
                    print("[WARNING] Failed to download original image {}: {}".format(index + 1, str(exc)[:80]))

        return [results[index] for index in sorted(results.keys()) if results.get(index)]

    def _generate_with_gemini(self, prompt, size, n):
        try:
            saved_paths = []
            aspect_ratio = "1:1" if "1024" in size else "16:9"
            if self.gemini_sdk == "google-genai" and self.gemini_client and self.gemini_types:
                response = self.gemini_client.models.generate_images(
                    model="imagen-4.0-generate-001",
                    prompt=prompt[:800],
                    config=self.gemini_types.GenerateImagesConfig(
                        number_of_images=max(1, min(int(n or 1), 4)),
                        aspect_ratio=aspect_ratio,
                    ),
                )
                for index, generated_image in enumerate(getattr(response, "generated_images", []) or []):
                    image_data = getattr(getattr(generated_image, "image", None), "image_bytes", None)
                    if not image_data:
                        continue
                    filename = "gemini_{}_{}.png".format(uuid.uuid4().hex[:8], index)
                    path = os.path.join(self.image_dir, filename)
                    with open(path, "wb") as fh:
                        fh.write(image_data)
                    saved_paths.append(path)
                return saved_paths

            if self.gemini_sdk == "google-generativeai":
                print("[INFO] Legacy google-generativeai SDK does not support the current image generation flow; falling back.")
                return []

            return saved_paths
        except Exception as exc:
            print("[WARNING] Gemini image generation failed: {}".format(str(exc)[:100]))
            return []

    def _generate_with_openai(self, prompt, size, quality, n):
        try:
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                n=n,
            )
            saved_paths = []
            import requests

            for index, item in enumerate(response.data):
                try:
                    resp = requests.get(item.url, timeout=30)
                    resp.raise_for_status()
                    filename = "ai_{}_{}.png".format(uuid.uuid4().hex[:8], index)
                    path = os.path.join(self.image_dir, filename)
                    with open(path, "wb") as fh:
                        fh.write(resp.content)
                    saved_paths.append(path)
                except Exception as exc:
                    print("[WARNING] Failed to download generated image: {}".format(str(exc)[:80]))
            return saved_paths
        except Exception as exc:
            print("[WARNING] OpenAI image generation failed: {}".format(str(exc)[:100]))
            return []

    def _generate_placeholder_images(self, prompt, size, n):
        paths = []
        width, height = map(int, size.split("x"))
        for index in range(n):
            try:
                image = self._create_text_image(
                    text=prompt[:100],
                    title=self._extract_title_from_prompt(prompt),
                    size=(width, height),
                    index=index,
                )
                filename = "local_{}_{}.png".format(uuid.uuid4().hex[:8], index)
                path = os.path.join(self.image_dir, filename)
                image.save(path, "PNG", quality=95)
                paths.append(path)
            except Exception as exc:
                print("[ERROR] Failed to create placeholder image: {}".format(str(exc)[:80]))
        return paths

    def _create_text_image(self, text, title="", size=(1024, 1024), index=0):
        width, height = size
        scheme = self.color_schemes[index % len(self.color_schemes)]
        image = PILImage.new("RGB", size, scheme["bg"])
        draw = ImageDraw.Draw(image)
        try:
            font_large = ImageFont.truetype("arial.ttf", 48)
            font_small = ImageFont.truetype("arial.ttf", 32)
            font_tiny = ImageFont.truetype("arial.ttf", 24)
        except Exception:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_tiny = ImageFont.load_default()

        if title:
            draw.text((width // 2, height // 3), title, fill=scheme["text"], font=font_large, anchor="mm")

        lines = []
        line = ""
        for char in text:
            line += char
            if len(line) >= 20 or char in ["。", "，", ".", ","]:
                lines.append(line)
                line = ""
        if line:
            lines.append(line)

        y = height // 2
        for current_line in lines[:6]:
            draw.text((width // 2, y), current_line, fill=scheme["text"], font=font_small, anchor="mm")
            y += 45

        draw.text((width // 2, height - 60), "Generated by Local Mode", fill=scheme["text"], font=font_tiny, anchor="mm")
        return image

    def _extract_title_from_prompt(self, prompt):
        if not prompt:
            return "AI Content"
        for sep in ["。", ".", "\n"]:
            if sep in prompt:
                first = prompt[: prompt.find(sep)]
                if 10 < len(first) < 50:
                    return first.strip()
        return prompt[:30] + ("..." if len(prompt) > 30 else "")

    def _analyze_image_set(self, image_paths):
        paths = [path for path in (image_paths or []) if path and os.path.exists(path)]
        if not paths:
            return [], ""

        insights = [None] * len(paths)
        workers = min(max(len(paths), 1), 4)
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="xhs-image-analyze") as executor:
            future_map = {
                executor.submit(self._describe_image, path, index): index
                for index, path in enumerate(paths)
            }
            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    insights[index] = future.result()
                except Exception as exc:
                    insights[index] = {
                        "index": index,
                        "path": paths[index],
                        "summary": "第{}张配图解析失败：{}".format(index + 1, str(exc)[:60]),
                        "ocr_items": [],
                        "ocr_text": "",
                        "text_coverage": 0.0,
                        "semantic_summary": "",
                    }

        cleaned = [item for item in insights if item]
        summary = "；".join(item.get("summary", "").strip() for item in cleaned if item.get("summary", "").strip())
        return cleaned, summary

    def _describe_image(self, image_path, index):
        image, metadata = self._load_image_normalized(image_path)
        if image is None:
            return {
                "index": index,
                "path": image_path,
                "summary": "第{}张配图已保存，但解析失败".format(index + 1),
                "ocr_items": [],
                "ocr_text": "",
                "text_coverage": 0.0,
                "semantic_summary": "",
            }

        width, height = image.size
        stat = ImageStat.Stat(image.convert("RGB"))
        brightness = sum(stat.mean) / max(len(stat.mean), 1)
        orientation = "竖图" if height > width else "横图" if width > height else "方图"
        ocr_items, ocr_text, text_coverage = self._extract_image_text(image_path)
        semantic_summary = ""

        if self._needs_semantic_fallback(ocr_text, text_coverage, width, height):
            semantic_summary = self._summarize_image_semantically(image_path, ocr_text, orientation)

        summary = self._build_image_summary(index, orientation, width, height, brightness, ocr_text, semantic_summary)
        image.close()

        return {
            "index": index,
            "path": image_path,
            "width": width,
            "height": height,
            "orientation": orientation,
            "brightness": round(brightness, 1),
            "summary": summary,
            "ocr_items": ocr_items,
            "ocr_text": ocr_text,
            "text_coverage": text_coverage,
            "semantic_summary": semantic_summary,
            "converted_mode": metadata.get("converted_mode", ""),
        }

    def _build_image_summary(self, index, orientation, width, height, brightness, ocr_text, semantic_summary):
        tone = "偏亮" if brightness >= 170 else "明暗均衡" if brightness >= 90 else "偏暗"
        parts = ["第{}张为{}，分辨率{}x{}，整体{}".format(index + 1, orientation, width, height, tone)]
        cleaned_text = self._truncate_text(ocr_text, 140)
        if cleaned_text:
            parts.append("图中文字：{}".format(cleaned_text))
        if semantic_summary:
            parts.append("语义摘要：{}".format(self._truncate_text(semantic_summary, 160)))
        return "；".join(parts)

    def _extract_image_text(self, image_path):
        if not self.ocr_engine:
            return [], "", 0.0

        try:
            ocr_result, _ = self.ocr_engine(image_path)
        except Exception as exc:
            print("[WARNING] OCR failed for {}: {}".format(os.path.basename(image_path), str(exc)[:80]))
            return [], "", 0.0

        if not ocr_result:
            return [], "", 0.0

        items = []
        texts = []
        total_chars = 0
        for row in ocr_result:
            if not row or len(row) < 2:
                continue
            text = str(row[1] or "").strip()
            if not text:
                continue
            score = None
            if len(row) >= 3:
                try:
                    score = float(row[2])
                except Exception:
                    score = None
            items.append({"text": text, "score": score})
            texts.append(text)
            total_chars += len(text)

        image, _ = self._load_image_normalized(image_path)
        area = 0
        if image is not None:
            area = max(image.size[0] * image.size[1], 1)
            image.close()
        coverage = min(1.0, round((total_chars * 22) / max(area, 1), 4))
        merged_text = "\n".join(texts).strip()
        return items, merged_text, coverage

    def _needs_semantic_fallback(self, ocr_text, text_coverage, width, height):
        text_len = len((ocr_text or "").strip())
        if text_len >= 60:
            return False
        if text_coverage >= 0.02:
            return False
        if abs(width - height) <= 80:
            return True
        return text_len < 24

    def _summarize_image_semantically(self, image_path, ocr_text, orientation):
        if not self.semantic_client:
            if ocr_text:
                return "该图更像截图或海报，核心信息主要来自图中文字。"
            return "该图缺少足够文字，建议结合原帖正文理解其用途与结论。"

        try:
            with PILImage.open(image_path) as image:
                buffer = io.BytesIO()
                normalized = image.convert("RGB")
                normalized.thumbnail((256, 256))
                normalized.save(buffer, format="JPEG", quality=55, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
            response = self.semantic_client.chat.completions.create(
                model=getattr(self.semantic_client, "default_model", None),
                messages=[
                    {
                        "role": "system",
                        "content": "请只输出一句非常简短的图片摘要，优先概括图片里的关键信息，不要解释，不要描述分辨率和颜色。",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "这是一张{}。已识别的文字如下：{}\n请只输出一句不超过 20 个字或 10 个英文单词的图片摘要。".format(
                                    orientation, self._truncate_text(ocr_text, 160) or "无明显文字"
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/jpeg;base64,{}".format(encoded)},
                            },
                        ],
                    },
                ],
                temperature=0.2,
                max_tokens=32,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            print("[WARNING] Semantic image summary failed: {}".format(str(exc)[:80]))
            if ocr_text:
                return "图片主要承载文字信息，可结合 OCR 文本整理阅读笔记。"
            return ""

    def _load_image_normalized(self, image_path):
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Palette images with Transparency expressed in bytes should be converted to RGBA images",
                    category=UserWarning,
                )
                image = PILImage.open(image_path)
                converted_mode = ""
                if image.mode == "P":
                    transparency = image.info.get("transparency")
                    if transparency is not None:
                        image = image.convert("RGBA")
                        converted_mode = "RGBA"
                    else:
                        image = image.convert("RGB")
                        converted_mode = "RGB"
                elif image.mode not in ("RGB", "RGBA", "L"):
                    image = image.convert("RGB")
                    converted_mode = "RGB"
                return image, {"converted_mode": converted_mode}
        except Exception:
            return None, {}

    def _select_final_images(self, original_paths, generated_paths):
        final_paths = []
        for path in list(original_paths or []) + list(generated_paths or []):
            if path and os.path.exists(path) and path not in final_paths:
                final_paths.append(path)
        return final_paths

    def _clean_urls(self, image_urls):
        cleaned_urls = []
        seen = set()
        for url in image_urls or []:
            if isinstance(url, dict):
                url = url.get("url_default") or url.get("url") or url.get("src") or ""
            url = str(url or "").strip()
            if not url:
                continue
            if url.startswith("//"):
                url = "https:" + url
            if url not in seen:
                cleaned_urls.append(url)
                seen.add(url)
        return cleaned_urls

    def _truncate_text(self, text, max_len):
        cleaned = " ".join(str(text or "").split()).strip()
        if len(cleaned) <= max_len:
            return cleaned
        return cleaned[: max_len - 1] + "…"
