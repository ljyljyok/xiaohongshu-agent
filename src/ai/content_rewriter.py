#!/usr/bin/env python3
"""Rewrite crawled Xiaohongshu posts into reading-note drafts."""

import os
import random
import re
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from config.config import get_ai_runtime_mode
from src.ai.text_llm_client import initialize_text_llm


class ContentRewriter:
    def __init__(self):
        self.client = None
        self.use_ai_mode = False
        self.mode = "local"
        self.mode_reason = ""
        requested_mode = get_ai_runtime_mode("content_rewriter_mode")
        try:
            self.client, self.mode, self.mode_reason = initialize_text_llm(requested_mode, "内容润色")
            if self.client:
                self.use_ai_mode = True
                print("[OK] {}".format(self.mode_reason))
            else:
                print("[INFO] {}".format(self.mode_reason))
        except Exception as exc:
            self.mode_reason = "内容润色初始化失败，已退回本地模式：{}".format(str(exc)[:80])
            print("[WARNING] {}".format(self.mode_reason))

        self.opening_templates = [
            "这次不说空话，先把原帖里真正有价值的信息拆开讲清楚。",
            "我把原帖、配图和补充素材重新整理了一遍，下面直接给阅读笔记版结论。",
            "这条内容的信息密度不错，我把关键观点、适用场景和细节整理成了可直接参考的笔记。",
            "先把原帖的核心事实抽出来，再补上图片或视频里提供的上下文。",
        ]
        self.cta_templates = [
            "如果你准备按这个方向继续研究，建议先收藏，再结合自己的场景补充实测和对比。",
            "真正好用的内容，一定要把场景、过程和结果一起写清楚，这样可信度会更高。",
            "如果你也在做同类内容，可以直接按这份阅读笔记继续展开。",
        ]

    def _active_model(self):
        return getattr(self.client, "default_model", None)

    def summarize_content(self, content, max_length=220):
        if not content:
            return ""
        if self.use_ai_mode and self.client:
            summary = self._summarize_with_ai(content, max_length)
            if summary:
                return summary
        return self._summarize_locally(content, max_length)

    def process_post(self, post):
        processed = dict(post or {})
        title = processed.get("title", "")
        content = processed.get("content", "")
        full_content = "{} {}".format(title, content).strip()

        reading_notes = self.build_reading_notes(processed)
        rewritten_content = self.rewrite_content(
            content=reading_notes or full_content,
            original_content=full_content,
            reading_notes=reading_notes,
            media_summary=self._get_media_summary(processed),
            media_insights=self._get_media_insights(processed),
            analysis=processed.get("analysis", {}),
            media_type=processed.get("media_type", "image"),
        )
        optimized_content = self.optimize_content(rewritten_content)
        publish_content = self.compose_publish_content(
            title=title,
            polished_content=optimized_content,
            reading_notes=reading_notes,
            media_summary=self._get_media_summary(processed),
            media_insights=self._get_media_insights(processed),
            media_type=processed.get("media_type", "image"),
        )
        summary = self.summarize_content(reading_notes or rewritten_content or full_content)

        processed["reading_notes"] = reading_notes
        processed["summary"] = summary
        processed["rewritten_content"] = rewritten_content
        processed["optimized_content_raw"] = optimized_content
        processed["optimized_content"] = publish_content or optimized_content
        processed["publish_content"] = publish_content or optimized_content
        processed["rewrite_mode"] = "ai" if self.use_ai_mode else "local"
        processed["rewrite_mode_reason"] = self.mode_reason
        return processed

    def batch_process(self, posts):
        processed = []
        for index, post in enumerate(posts):
            try:
                if post.get("analysis", {}).get("is_ai_related", False):
                    processed_post = self.process_post(post)
                    print(
                        "[{}] Rewrite complete: {} | mode={}".format(
                            index + 1,
                            processed_post.get("title", "Untitled")[:30],
                            processed_post.get("rewrite_mode", "unknown"),
                        )
                    )
                    processed.append(processed_post)
                else:
                    processed.append(post)
            except Exception as exc:
                print("[ERROR] Rewrite failed for post {}: {}".format(index + 1, str(exc)[:80]))
                failed = dict(post)
                failed["error"] = str(exc)
                processed.append(failed)
        return processed

    def enrich_post_with_media_context(self, post):
        processed = dict(post or {})
        content = (
            processed.get("publish_content")
            or processed.get("optimized_content")
            or processed.get("rewritten_content")
            or processed.get("content", "")
        )
        if not content:
            return processed

        enriched = self.rewrite_content(
            content=content,
            original_content=processed.get("original_content") or processed.get("content", content),
            reading_notes=processed.get("reading_notes", ""),
            media_summary=self._get_media_summary(processed),
            media_insights=self._get_media_insights(processed),
            analysis=processed.get("analysis", {}),
            media_type=processed.get("media_type", "image"),
        )
        processed["optimized_content_raw"] = self.optimize_content(enriched)
        processed["publish_content"] = self.compose_publish_content(
            title=processed.get("title", ""),
            polished_content=processed.get("optimized_content_raw", ""),
            reading_notes=processed.get("reading_notes", ""),
            media_summary=self._get_media_summary(processed),
            media_insights=self._get_media_insights(processed),
            media_type=processed.get("media_type", "image"),
        )
        processed["optimized_content"] = processed.get("publish_content") or processed.get("optimized_content_raw", "")
        processed["media_enriched"] = True
        return processed

    def build_reading_notes(self, post):
        media_type = post.get("media_type", "image")
        if self.use_ai_mode and self.client:
            notes = self._build_reading_notes_with_ai(post, media_type)
            if notes:
                return notes
        return self._build_reading_notes_locally(post, media_type)

    def rewrite_content(
        self,
        content,
        original_content=None,
        reading_notes="",
        media_summary="",
        media_insights=None,
        analysis=None,
        media_type="image",
    ):
        if not content:
            return ""
        if self.use_ai_mode and self.client:
            rewritten = self._rewrite_with_ai(
                content=content,
                original_content=original_content,
                reading_notes=reading_notes,
                media_summary=media_summary,
                media_insights=media_insights or [],
                analysis=analysis or {},
                media_type=media_type,
            )
            if rewritten:
                return rewritten
        return self._rewrite_locally(
            content=content,
            reading_notes=reading_notes,
            media_summary=media_summary,
            media_insights=media_insights or [],
            analysis=analysis or {},
            media_type=media_type,
        )

    def optimize_content(self, content, platform="小红书"):
        if not content:
            return ""
        if self.use_ai_mode and self.client and platform != "小红书":
            try:
                response = self.client.chat.completions.create(
                    model=self._active_model(),
                    messages=[
                        {"role": "system", "content": "请根据平台风格优化内容。"},
                        {"role": "user", "content": "请把下面内容优化成更适合{}平台的版本：\n\n{}".format(platform, content[:2500])},
                    ],
                    temperature=0.4,
                    max_tokens=1200,
                )
                return response.choices[0].message.content.strip()
            except Exception:
                pass
        return content

    def compose_publish_content(
        self,
        title,
        polished_content,
        reading_notes="",
        media_summary="",
        media_insights=None,
        media_type="image",
    ):
        base_content = (polished_content or "").strip()
        notes = (reading_notes or "").strip()
        media_insights = media_insights or []
        if self.use_ai_mode and self.client and (base_content or notes):
            merged = self._compose_publish_content_with_ai(
                title=title,
                polished_content=base_content,
                reading_notes=notes,
                media_summary=media_summary,
                media_insights=media_insights,
                media_type=media_type,
            )
            if merged:
                return merged
        return self._compose_publish_content_locally(
            title=title,
            polished_content=base_content,
            reading_notes=notes,
            media_summary=media_summary,
            media_insights=media_insights,
            media_type=media_type,
        )

    def _build_reading_notes_with_ai(self, post, media_type):
        try:
            prompt = [
                "请把下面的小红书原帖整理成中文阅读笔记。",
                "要求：",
                "1. 只保留原帖和媒体素材里能确认的事实，不要编造；",
                "2. 笔记结构要清晰，覆盖主题、核心结论、关键信息、适用场景、来源信息；",
                "3. 图文帖要优先吸收图片 OCR 文本和图片语义摘要，不要只写分辨率、亮度这类属性；",
                "4. 视频帖要吸收视频转写和关键帧信息；",
                "5. 输出直接可读的中文笔记，不要返回 JSON。",
                "",
                "媒体类型：{}".format("视频帖" if media_type == "video" else "图文帖"),
                "原帖标题：{}".format(post.get("original_title") or post.get("title", "")),
                "原帖正文：{}".format((post.get("original_content") or post.get("content") or "")[:2800]),
                "作者：{}".format(post.get("author", "")),
                "发布时间：{}".format(post.get("publish_time", "")),
                "媒体摘要：{}".format(self._get_media_summary(post) or "无"),
                "媒体细节：{}".format("；".join(self._get_media_insights(post)[:8]) or "无"),
            ]
            if post.get("image_ocr_text"):
                prompt.append("图片 OCR 文本：{}".format((post.get("image_ocr_text") or "")[:3500]))
            if post.get("image_semantic_summary"):
                prompt.append("图片语义摘要：{}".format((post.get("image_semantic_summary") or "")[:1600]))
            if media_type == "video":
                prompt.append("视频转写：{}".format((post.get("video_transcript") or "")[:3500]))
            response = self.client.chat.completions.create(
                model=self._active_model(),
                messages=[
                    {"role": "system", "content": "你是一名负责整理技术内容阅读笔记的编辑。"},
                    {"role": "user", "content": "\n".join(prompt)},
                ],
                temperature=0.3,
                max_tokens=1200,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            print("[WARNING] AI reading-notes build failed: {}".format(str(exc)[:80]))
            return ""

    def _build_reading_notes_locally(self, post, media_type):
        original_title = (post.get("original_title") or post.get("title") or "").strip()
        original_content = (post.get("original_content") or post.get("content") or "").strip()
        media_summary = self._get_media_summary(post)
        media_insights = self._get_media_insights(post)
        image_ocr_text = (post.get("image_ocr_text") or "").strip()
        image_semantic_summary = (post.get("image_semantic_summary") or "").strip()
        key_points = self._extract_key_points(original_content)
        audience = self._detect_audience(post.get("analysis", {}), original_content)

        lines = []
        if original_title:
            lines.append("主题：{}".format(original_title))
        if audience:
            lines.append("适合人群：{}".format(audience))
        if key_points:
            lines.append("原帖重点：")
            for idx, point in enumerate(key_points[:5], start=1):
                lines.append("{}. {}".format(idx, point))
        if image_ocr_text:
            lines.append("图片文字转写：")
            for idx, point in enumerate(self._extract_key_points(image_ocr_text)[:6], start=1):
                lines.append("{}. {}".format(idx, point))
        if image_semantic_summary:
            lines.append("图片语义补充：{}".format(image_semantic_summary))
        if media_summary:
            lines.append("{}补充：{}".format("视频" if media_type == "video" else "图片", media_summary))
        if media_insights:
            lines.append("媒体细节：")
            for idx, item in enumerate(media_insights[:5], start=1):
                lines.append("- {}. {}".format(idx, item))
        if media_type == "video" and post.get("video_transcript"):
            transcript_points = self._extract_key_points(post.get("video_transcript", ""))
            if transcript_points:
                lines.append("视频转写重点：")
                for idx, point in enumerate(transcript_points[:4], start=1):
                    lines.append("{}. {}".format(idx, point))
        lines.append(
            "来源：{} | 作者：{} | 发布时间：{}".format(
                post.get("source_url") or post.get("link") or "未记录",
                post.get("author") or "未知",
                post.get("publish_time") or "未知",
            )
        )
        return "\n".join(line for line in lines if line)

    def _compose_publish_content_with_ai(
        self,
        title,
        polished_content,
        reading_notes="",
        media_summary="",
        media_insights=None,
        media_type="image",
    ):
        try:
            media_insights = media_insights or []
            prompt = [
                "请把已经润色好的草稿与阅读笔记合并成最终待发布文案。",
                "要求：",
                "1. 以润色稿为主体，把阅读笔记里更具体、更可靠的细节自然补充进去；",
                "2. 不要简单重复同一句话，不要堆空话；",
                "3. 保留信息密度和可读性，适合直接发布到小红书；",
                "4. 如果是图文帖，优先吸收图片里的关键信息；如果是视频帖，优先吸收转写和关键帧重点；",
                "5. 直接返回最终中文文案，不要返回 JSON。",
                "",
                "标题：{}".format(title or "无标题"),
                "媒体类型：{}".format("视频帖" if media_type == "video" else "图文帖"),
                "当前润色稿：{}".format((polished_content or "")[:2600]),
                "阅读笔记：{}".format((reading_notes or "")[:3200]),
                "媒体摘要：{}".format((media_summary or "无")[:1200]),
                "媒体细节：{}".format("；".join(media_insights[:6]) or "无"),
            ]
            response = self.client.chat.completions.create(
                model=self._active_model(),
                messages=[
                    {"role": "system", "content": "你是一名擅长整理高信息密度小红书文案的中文编辑。"},
                    {"role": "user", "content": "\n".join(prompt)},
                ],
                temperature=0.4,
                max_tokens=1400,
            )
            merged = (response.choices[0].message.content or "").strip()
            return merged or None
        except Exception as exc:
            print("[WARNING] AI publish-content merge failed: {}".format(str(exc)[:80]))
            return None

    def _compose_publish_content_locally(
        self,
        title,
        polished_content,
        reading_notes="",
        media_summary="",
        media_insights=None,
        media_type="image",
    ):
        base_content = (polished_content or "").strip()
        if not base_content:
            base_content = (reading_notes or "").strip()
        supplement_points = self._build_note_supplement_points(
            reading_notes=reading_notes,
            base_content=base_content,
            media_summary=media_summary,
            media_insights=media_insights or [],
        )
        if not supplement_points:
            return base_content

        label = "阅读笔记补充"
        if media_type == "video":
            label = "视频阅读笔记补充"
        elif media_type == "image":
            label = "图文阅读笔记补充"

        lines = []
        if base_content:
            lines.append(base_content)
        if title and title not in (base_content or "") and len(base_content) < 40:
            lines.insert(0, title.strip())
        lines.append("{}：".format(label))
        for point in supplement_points[:4]:
            lines.append("- {}".format(point))
        return "\n\n".join(part for part in lines if part)

    def _build_note_supplement_points(self, reading_notes, base_content, media_summary="", media_insights=None):
        media_insights = media_insights or []
        candidate_points = []
        candidate_points.extend(self._extract_key_points(reading_notes or ""))
        candidate_points.extend(self._extract_key_points(media_summary or ""))
        for item in media_insights[:6]:
            text = item.get("summary", "") if isinstance(item, dict) else str(item)
            candidate_points.extend(self._extract_key_points(text))

        existing = (base_content or "").replace(" ", "")
        picked = []
        for point in candidate_points:
            normalized = point.replace(" ", "")
            if len(normalized) < 10:
                continue
            if normalized[:12] and normalized[:12] in existing:
                continue
            if point in picked:
                continue
            picked.append(point)
            if len(picked) >= 4:
                break
        return picked

    def _rewrite_with_ai(self, content, original_content=None, reading_notes="", media_summary="", media_insights=None, analysis=None, media_type="image"):
        try:
            media_insights = media_insights or []
            analysis = analysis or {}
            prompt = [
                "请把下面的小红书原帖阅读笔记改写成信息密度更高、避免空话、结构清晰的中文图文帖。",
                "要求：",
                "1. 保留原帖核心观点，但补足背景、细节、适用场景和具体结论；",
                "2. 不要写空泛的“很强”“太香了”之类口号，优先给具体描述；",
                "3. 自然吸收媒体信息；",
                "4. 适合小红书发布，不要返回 JSON。",
                "",
                "内容类型：{}".format(analysis.get("content_type", "未分类")),
                "媒体类型：{}".format("视频帖" if media_type == "video" else "图文帖"),
                "原始内容：{}".format((original_content or content)[:2500]),
                "阅读笔记：{}".format((reading_notes or content)[:3000]),
                "媒体摘要：{}".format(media_summary or "无"),
                "媒体细节：{}".format("；".join(media_insights[:6]) or "无"),
            ]
            response = self.client.chat.completions.create(
                model=self._active_model(),
                messages=[
                    {"role": "system", "content": "你是一名擅长写信息密度高的小红书内容编辑。"},
                    {"role": "user", "content": "\n".join(prompt)},
                ],
                temperature=0.5,
                max_tokens=1200,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            print("[WARNING] AI rewrite failed: {}".format(str(exc)[:80]))
            return None

    def _rewrite_locally(self, content, reading_notes="", media_summary="", media_insights=None, analysis=None, media_type="image"):
        analysis = analysis or {}
        media_insights = media_insights or []
        points = self._extract_key_points(reading_notes or content)
        audience = self._detect_audience(analysis, content)
        lines = [random.choice(self.opening_templates)]
        if audience:
            lines.append("适合人群：{}".format(audience))
        if points:
            lines.append("我整理出的重点：")
            for idx, point in enumerate(points[:4], start=1):
                lines.append("{}. {}".format(idx, point))
        if media_summary:
            label = "视频补充信息" if media_type == "video" else "图片补充信息"
            lines.append("{}：{}".format(label, media_summary))
        elif media_insights:
            label = "关键帧补充信息" if media_type == "video" else "图片补充信息"
            lines.append("{}：{}".format(label, "；".join(media_insights[:4])))

        lines.append("如果你准备把这类内容写成自己的帖子，建议补上真实体验、操作过程和结果截图，这样可信度会高很多。")
        lines.append(random.choice(self.cta_templates))
        return "\n\n".join(line for line in lines if line)

    def _summarize_with_ai(self, content, max_length):
        try:
            response = self.client.chat.completions.create(
                model=self._active_model(),
                messages=[
                    {"role": "system", "content": "请把内容总结成简洁但信息密度高的中文摘要。"},
                    {"role": "user", "content": "请把以下内容总结到{}字以内：\n\n{}".format(max_length, content[:2000])},
                ],
                temperature=0.2,
                max_tokens=max_length,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            print("[WARNING] AI summary failed: {}".format(str(exc)[:80]))
            return None

    def _summarize_locally(self, content, max_length):
        sentences = [part.strip() for part in re.split(r"[。！？?!]", content) if part.strip()]
        if not sentences:
            return content[:max_length]
        picked = []
        total = 0
        for sentence in sentences[:4]:
            if total + len(sentence) > max_length:
                break
            picked.append(sentence)
            total += len(sentence)
        return "。".join(picked) + ("。" if picked else "")

    def _get_media_summary(self, post):
        if post.get("media_type") == "video":
            return (post.get("video_summary") or "").strip()
        return (
            (post.get("image_semantic_summary") or "").strip()
            or (post.get("image_summary") or "").strip()
        )

    def _get_media_insights(self, post):
        if post.get("media_type") == "video":
            raw_items = post.get("video_frame_insights", []) or []
        else:
            raw_items = post.get("image_insights", []) or []
        cleaned = []
        for item in raw_items:
            if isinstance(item, dict):
                value = item.get("summary", "") or item.get("semantic_summary", "") or item.get("ocr_text", "")
            else:
                value = str(item)
            value = value.strip()
            if value:
                cleaned.append(value)
        if post.get("media_type") != "video":
            ocr_text = (post.get("image_ocr_text") or "").strip()
            if ocr_text:
                cleaned.extend("图中文字：{}".format(point) for point in self._extract_key_points(ocr_text)[:4])
        return cleaned

    def _extract_key_points(self, content):
        sentences = [part.strip() for part in re.split(r"[。！？?!\n]", content) if len(part.strip()) >= 8]
        points = []
        for sentence in sentences[:10]:
            cleaned = re.sub(r"\s+", " ", sentence).strip(" -")
            if cleaned and cleaned not in points:
                points.append(cleaned)
        return points

    def _detect_audience(self, analysis, content):
        content_type = str((analysis or {}).get("content_type") or "")
        combined = "{} {}".format(content_type, content or "").lower()
        if any(keyword in combined for keyword in ["教程", "guide", "tutorial", "如何"]):
            return "想快速上手的入门用户"
        if any(keyword in combined for keyword in ["编程", "code", "cursor", "claude code", "copilot"]):
            return "开发者和 AI 工具重度使用者"
        if any(keyword in combined for keyword in ["资讯", "发布", "update", "release"]):
            return "关注 AI 趋势和产品更新的人"
        return "想把信息快速看懂的人"
