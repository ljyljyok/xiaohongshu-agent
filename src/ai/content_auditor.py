#!/usr/bin/env python3
"""Audit generated posts for source quality, evidence, and publish readiness."""

import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from config.config import get_ai_runtime_mode
from src.ai.text_llm_client import initialize_text_llm


class ContentAuditor:
    """Rule-first auditor with optional AI assistance."""

    SOURCE_DOMAINS = (
        "xiaohongshu.com",
        "xhslink.com",
        "xhscdn.com",
    )

    GENERATED_SOURCE_PREFIXES = (
        "generated",
        "generated_fallback",
        "keyword_",
        "trending_",
    )

    STOPWORDS = {
        "我们", "你们", "他们", "这个", "那个", "内容", "帖子", "原贴", "小红书",
        "图片", "配图", "视频", "发布", "使用", "一个", "一些", "可以", "如果",
        "因为", "所以", "就是", "然后", "已经", "今天", "最近", "现在", "真的",
        "非常", "比较", "还是", "相关", "进行", "内容里", "原文里", "以及", "需要", "通过",
    }

    def __init__(self):
        self.client = None
        self.use_ai_mode = False
        self.mode = "local"
        self.mode_reason = ""
        requested_mode = get_ai_runtime_mode("content_auditor_mode")
        try:
            self.client, self.mode, self.mode_reason = initialize_text_llm(requested_mode, "内容审核")
            if self.client:
                self.use_ai_mode = True
                print("[OK] {}".format(self.mode_reason))
            else:
                print("[INFO] {}".format(self.mode_reason))
        except Exception as exc:
            self.mode_reason = "内容审核初始化失败，已退回本地模式：{}".format(str(exc)[:80])
            print("[WARNING] {}".format(self.mode_reason))

        self.known_entities = {
            "GPT-4": "real",
            "GPT-4o": "real",
            "GPT-4o mini": "real",
            "ChatGPT": "real",
            "Claude 3": "real",
            "Claude 3.5 Sonnet": "real",
            "Llama 3": "real",
            "DeepSeek-R1": "real",
            "Midjourney V6": "real",
            "Sora": "real",
            "Gemini Pro": "real",
            "Cursor": "real",
            "GPT-5": "unverified",
            "Claude 4": "unverified",
            "Llama 4": "unverified",
            "DeepSeek-R2": "unverified",
            "Veo 4": "unverified",
        }

        self.empty_talk_phrases = [
            "太强了",
            "太香了",
            "直接封神",
            "彻底改变",
            "颠覆一切",
            "闭眼冲",
            "无脑冲",
            "真的绝",
            "神级",
            "王炸",
        ]

        self.hallucination_patterns = [
            (r"提升\s*(\d{3,})%", "性能提升幅度过大，建议核实具体测试条件。"),
            (r"准确率(?:达到|高达|飙升到)?\s*(\d{3,})%", "准确率数值明显异常，建议核实。"),
            (r"100%准确", "出现绝对化表述，可信度不足。"),
            (r"刚刚发布.*?(GPT-5|Claude 4|Llama 4|DeepSeek-R2)", "提到了仍需核实的新产品发布表述。"),
            (r"(?:今天|今日|刚刚|正式).{0,12}发布.*?(GPT-5|Claude 4|Llama 4|DeepSeek-R2)", "提到了未证实产品的即时发布表述。"),
            (r"免费.*?(企业|商用)", "涉及商用授权时应补充明确依据。"),
            (r"\b\d{3,}%", "出现过高的百分比描述，建议补充来源。"),
            (r"(predict|future).{0,12}\d{2,3}", "对未来能力的预测较武断，建议删除或弱化。"),
            (r"预测未来\s*\d+\s*年", "内容包含明显夸张的预测能力描述。"),
            (r"比光速还快", "内容包含明显不可信的性能描述。"),
        ]

    def _active_model(self):
        return getattr(self.client, "default_model", None)

    def audit_content(self, post):
        audit_result = {
            "is_safe": True,
            "confidence_score": 100,
            "detail_score": 100,
            "reliability_score": 100,
            "readability_score": 100,
            "image_coverage_score": 100,
            "empty_talk_score": 100,
            "substance_score": 100,
            "source_score": 100,
            "citation_score": 100,
            "source_valid": True,
            "citation_valid": True,
            "publish_ready": True,
            "rejection_reason": "",
            "source_summary": "",
            "issues": [],
            "warnings": [],
            "suggestions": [],
            "hallucination_risk": "low",
            "summary": "",
        }

        title = post.get("title", "") or ""
        content = post.get("content", "") or ""
        publish_content = post.get("publish_content", "") or ""
        rewritten = post.get("rewritten_content", "") or ""
        optimized = post.get("optimized_content", "") or ""
        reading_notes = post.get("reading_notes", "") or ""
        media_type = post.get("media_type", "image")

        text = " ".join(part for part in [title, content, reading_notes, rewritten, optimized, publish_content] if part)
        source_parts = [
            post.get("original_title", "") or "",
            post.get("original_content", "") or "",
            post.get("image_summary", "") or "",
            post.get("image_semantic_summary", "") or "",
            (post.get("image_ocr_text", "") or "")[:2000],
            post.get("video_summary", "") or "",
            (post.get("video_transcript", "") or "")[:2000],
        ]
        source_text = " ".join(part for part in source_parts if part)

        self._check_source_quality(post, source_text, audit_result)
        self._check_citation_alignment(post, text, source_text, audit_result)
        self._check_unverified_entities(text, audit_result)
        self._check_hallucination_patterns(text, audit_result)
        self._check_empty_talk(text, audit_result)
        self._check_detail_and_evidence(post, text, audit_result)
        self._check_temporal_consistency(post, audit_result)
        self._check_image_coverage(post, audit_result)

        if self.use_ai_mode and self.client:
            ai_result = self._ai_audit(post, text, source_text)
            if ai_result:
                audit_result["issues"].extend(ai_result.get("issues", []))
                audit_result["warnings"].extend(ai_result.get("warnings", []))
                if ai_result.get("suggestions"):
                    audit_result["suggestions"].extend(ai_result.get("suggestions", []))

        self._finalize_scores(audit_result, media_type)
        audit_result["mode"] = self.mode
        audit_result["mode_reason"] = self.mode_reason
        post["audit"] = audit_result
        return audit_result

    def batch_audit(self, posts):
        audited = []
        for index, post in enumerate(posts):
            try:
                audit = self.audit_content(post)
                print(
                    "[{}] Audit complete: {} | score={}/100 | source={} | publish_ready={}".format(
                        index + 1,
                        post.get("title", "Untitled")[:35],
                        audit.get("confidence_score", 0),
                        audit.get("source_score", 0),
                        audit.get("publish_ready", False),
                    )
                )
                audited.append(post)
            except Exception as exc:
                print("[ERROR] Audit failed for post {}: {}".format(index + 1, str(exc)[:80]))
                failed = dict(post)
                failed["audit"] = {
                    "is_safe": False,
                    "confidence_score": 0,
                    "detail_score": 0,
                    "reliability_score": 0,
                    "readability_score": 0,
                    "image_coverage_score": 0,
                    "empty_talk_score": 0,
                    "substance_score": 0,
                    "source_score": 0,
                    "citation_score": 0,
                    "source_valid": False,
                    "citation_valid": False,
                    "publish_ready": False,
                    "rejection_reason": "审核执行失败",
                    "source_summary": "审核执行失败",
                    "issues": [{"message": str(exc), "severity": "high"}],
                    "warnings": [],
                    "suggestions": ["审核失败，请丢弃并重新抓取。"],
                    "hallucination_risk": "high",
                    "summary": "审核失败",
                }
                audited.append(failed)
        return audited

    def _check_source_quality(self, post, source_text, result):
        source_url = self._get_source_url(post)
        source_name = str(post.get("source", "") or "")
        original_title = (post.get("original_title") or "").strip()
        original_content = (post.get("original_content") or "").strip()
        author = (post.get("author") or "").strip()
        publish_time = (post.get("publish_time") or "").strip()
        media_type = post.get("media_type", "image")

        if media_type == "video":
            media_count = len(post.get("video_frame_paths", []) or [])
            has_media_evidence = self._has_video_source_evidence(post)
        else:
            media_count = len(post.get("original_image_paths", []) or post.get("final_image_paths", []) or post.get("original_image_urls", []) or [])
            has_media_evidence = self._has_visual_source_evidence(post)

        if not any([source_url, source_name, original_title, original_content, media_count]):
            result["source_score"] = 80
            result["source_valid"] = True
            result["source_summary"] = "未提供原帖来源，按独立内容规则审核。"
            result["warnings"].append(
                {
                    "type": "source_context_missing",
                    "message": "未提供原帖来源信息，本次按独立内容审核，建议补充出处以提升可信度。",
                    "severity": "low",
                }
            )
            return

        score = 25
        is_generated = any(source_name.startswith(prefix) for prefix in self.GENERATED_SOURCE_PREFIXES)
        domain_valid = self._is_valid_source_url(source_url)

        if source_url:
            score += 15
        if domain_valid:
            score += 20
        if len(original_title) >= 8:
            score += 12
        if len(original_content) >= 60:
            score += 16
        elif len(original_content) >= 20:
            score += 10
        elif has_media_evidence:
            score += 6
        if author:
            score += 5
        if publish_time:
            score += 4
        if media_count >= 1:
            score += 8
        if media_count >= 3:
            score += 5

        if is_generated:
            score -= 65
            result["issues"].append(
                {
                    "type": "generated_source",
                    "message": "来源标识显示这是兜底或模板内容，不允许作为最终草稿来源。",
                    "severity": "high",
                }
            )

        if not source_url:
            score -= 30
            result["issues"].append(
                {
                    "type": "missing_source_url",
                    "message": "缺少原贴链接，无法确认出处。",
                    "severity": "high",
                }
            )
        elif not domain_valid:
            score -= 28
            result["issues"].append(
                {
                    "type": "invalid_source_domain",
                    "message": "原贴链接不是可信的小红书来源，不能直接发布。",
                    "severity": "high",
                }
            )

        if len(original_title) < 6:
            score -= 18
            result["issues"].append(
                {
                    "type": "missing_original_title",
                    "message": "原贴标题过短或缺失，来源信息不完整。",
                    "severity": "high",
                }
            )

        if len(original_content) < 20:
            if has_media_evidence and domain_valid and len(original_title) >= 6:
                score -= 8
                result["warnings"].append(
                    {
                        "type": "missing_original_content",
                        "message": "原贴正文较短，已用媒体理解结果补强，发布前建议再人工复核一次。",
                        "severity": "medium",
                    }
                )
            else:
                score -= 22
                result["issues"].append(
                    {
                        "type": "missing_original_content",
                        "message": "原贴正文信息不足，无法支持可靠改写。",
                        "severity": "high",
                    }
                )

        if media_count == 0:
            score -= 15
            result["warnings"].append(
                {
                    "type": "missing_original_media",
                    "message": "未拿到原贴媒体素材，信息可能不完整。",
                    "severity": "medium",
                }
            )

        result["source_score"] = max(0, min(100, score))
        result["source_valid"] = (
            not is_generated
            and domain_valid
            and len(original_title) >= 6
            and media_count >= 1
            and (len(original_content) >= 20 or has_media_evidence)
        )
        result["source_summary"] = "来源{}，原贴标题{}字，原贴正文{}字，{}证据{}份。".format(
            "可信" if result["source_valid"] else "待复核",
            len(original_title),
            len(original_content),
            "视频" if media_type == "video" else "图片",
            media_count,
        )

    def _check_citation_alignment(self, post, final_text, source_text, result):
        sparse_source = len((post.get("original_content") or "").strip()) < 20
        media_type = post.get("media_type", "image")
        has_media_evidence = self._has_video_source_evidence(post) if media_type == "video" else self._has_visual_source_evidence(post)

        if not source_text.strip():
            result["citation_score"] = 75
            result["citation_valid"] = True
            return

        source_keywords = self._extract_keywords(source_text)
        final_keywords = self._extract_keywords(final_text)
        overlap = self._keyword_overlap(source_keywords, final_keywords)

        source_numbers = set(re.findall(r"\d+(?:\.\d+)?", source_text))
        final_numbers = set(re.findall(r"\d+(?:\.\d+)?", final_text))
        number_overlap = len(source_numbers & final_numbers) / max(len(source_numbers), 1) if source_numbers else 1.0

        citation_score = 35
        citation_score += min(30, int(round(overlap * 50)))
        citation_score += min(20, int(round(number_overlap * 20)))
        if self._get_source_url(post):
            citation_score += 10
        if post.get("summary"):
            citation_score += 5
        if sparse_source and has_media_evidence:
            citation_score += 8

        overlap_threshold = 0.16 if sparse_source and has_media_evidence else 0.22
        weak_threshold = 0.28 if sparse_source and has_media_evidence else 0.35

        if overlap < overlap_threshold:
            result["issues"].append(
                {
                    "type": "weak_citation_alignment",
                    "message": "改写内容与原贴重合度偏低，容易出现偏题或误引。",
                    "severity": "high",
                }
            )
            citation_score -= 25
        elif overlap < weak_threshold:
            result["warnings"].append(
                {
                    "type": "citation_alignment",
                    "message": "改写内容和原贴的对应关系偏弱，建议补充更直接的事实细节。",
                    "severity": "medium",
                }
            )
            citation_score -= 10

        if source_numbers and number_overlap < 0.35:
            result["warnings"].append(
                {
                    "type": "number_drift",
                    "message": "正文中的数字信息与原贴对齐度不够，建议人工复核。",
                    "severity": "medium",
                }
            )
            citation_score -= 12

        min_length = max(80, int(len(source_text.strip()) * 0.45))
        if sparse_source and has_media_evidence:
            min_length = max(60, int(len(source_text.strip()) * 0.30))
        if len(final_text.strip()) < min_length:
            result["warnings"].append(
                {
                    "type": "detail_loss",
                    "message": "改写后的正文压缩过多，可能遗漏原贴细节。",
                    "severity": "medium",
                }
            )
            citation_score -= 8

        result["citation_score"] = max(0, min(100, citation_score))
        result["citation_valid"] = result["citation_score"] >= 70 and overlap >= overlap_threshold

    def _check_unverified_entities(self, text, result):
        for entity, status in self.known_entities.items():
            if entity.lower() in text.lower() and status == "unverified":
                result["warnings"].append(
                    {
                        "type": "unverified_entity",
                        "message": "提到了仍需核实的实体：{}。".format(entity),
                        "severity": "high",
                    }
                )
                result["reliability_score"] -= 18

    def _check_hallucination_patterns(self, text, result):
        for pattern, message in self.hallucination_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                result["issues"].append(
                    {
                        "type": "potential_hallucination",
                        "message": message,
                        "severity": "medium",
                    }
                )
                result["reliability_score"] -= 12

    def _check_empty_talk(self, text, result):
        hits = [phrase for phrase in self.empty_talk_phrases if phrase in text]
        if hits:
            result["warnings"].append(
                {
                    "type": "empty_talk",
                    "message": "存在偏空泛的表述：{}。".format("、".join(hits[:5])),
                    "severity": "medium",
                }
            )
            result["empty_talk_score"] -= min(40, len(hits) * 8)
            result["substance_score"] -= min(30, len(hits) * 6)

    def _check_detail_and_evidence(self, post, text, result):
        sentences = [item.strip() for item in re.split(r"[。！？?!]", text) if item.strip()]
        number_hits = re.findall(r"\d+(?:\.\d+)?", text)
        has_link = bool(self._get_source_url(post))
        media_type = post.get("media_type", "image")
        has_images = bool(post.get("final_image_paths") or post.get("original_image_paths"))
        has_video = bool(post.get("video_transcript")) and bool(post.get("video_frame_paths"))
        evidence_bonus = 0

        detail_score = 40
        if len(text) >= 180:
            detail_score += 15
        if len(text) >= 320:
            detail_score += 12
        if len(sentences) >= 4:
            detail_score += 10
        if len(sentences) >= 7:
            detail_score += 6
        if len(number_hits) >= 2:
            detail_score += 8
        if media_type == "video" and post.get("video_summary"):
            evidence_bonus += 10
        elif media_type == "image" and post.get("image_summary"):
            evidence_bonus += 8
        if post.get("reading_notes"):
            evidence_bonus += 6
        detail_score += evidence_bonus
        result["detail_score"] = min(100, detail_score)

        reliability_score = result["reliability_score"]
        if has_link:
            reliability_score += 5
        if has_images:
            reliability_score += 6
        if has_video:
            reliability_score += 8
        if len(number_hits) == 0 and len(sentences) < 3:
            reliability_score -= 12
            result["warnings"].append(
                {
                    "type": "low_evidence",
                    "message": "内容缺少足够的事实细节、数据或过程描述，可读但不够扎实。",
                    "severity": "medium",
                }
            )
        result["reliability_score"] = max(0, min(100, reliability_score))

        readability_score = 82
        if len(sentences) >= 3:
            readability_score += 6
        if len(text) > 1000:
            readability_score -= 8
        if "1." in text or "2." in text or "适合人群" in text:
            readability_score += 6
        result["readability_score"] = max(0, min(100, readability_score))

        substance_score = (result["detail_score"] * 0.55) + (result["empty_talk_score"] * 0.45)
        result["substance_score"] = max(0, min(100, round(substance_score, 1)))

    def _check_temporal_consistency(self, post, result):
        current_year = datetime.now().year
        title = post.get("title", "")
        year_matches = re.findall(r"(\d{4})", title)
        for year_str in year_matches:
            year = int(year_str)
            if year > current_year + 1:
                result["issues"].append(
                    {
                        "type": "temporal_inconsistency",
                        "message": "标题包含明显超前的年份：{}。".format(year),
                        "severity": "high",
                    }
                )
                result["reliability_score"] -= 20

    def _check_image_coverage(self, post, result):
        media_type = post.get("media_type", "image")
        if media_type == "video":
            frame_count = len(post.get("video_frame_paths", []) or [])
            insight_count = len(post.get("video_frame_insights", []) or [])
            if frame_count == 0:
                result["image_coverage_score"] = 40
                result["issues"].append(
                    {
                        "type": "video_frames_missing",
                        "message": "视频帖缺少关键帧，无法验证画面内容。",
                        "severity": "high",
                    }
                )
                return
            score = 60
            if frame_count >= 2:
                score += 18
            if frame_count >= 4:
                score += 10
            if insight_count >= min(frame_count, 3):
                score += 12
            else:
                result["warnings"].append(
                    {
                        "type": "video_frame_coverage",
                        "message": "关键帧理解覆盖不足，建议补充更多画面说明。",
                        "severity": "medium",
                    }
                )
            if post.get("video_transcript"):
                score += 8
            result["image_coverage_score"] = max(0, min(100, score))
            return

        original_count = len(post.get("original_image_paths", []) or [])
        final_count = len(post.get("final_image_paths", []) or [])
        insight_count = len(post.get("image_insights", []) or [])

        if original_count == 0 and final_count == 0:
            result["image_coverage_score"] = 30
            result["issues"].append(
                {
                    "type": "image_missing",
                    "message": "图文帖缺少原图，不能作为合格草稿。",
                    "severity": "high",
                }
            )
            return

        score = 65
        if original_count > 0 and final_count >= original_count:
            score += 20
        elif final_count > 0:
            score += 10
        if insight_count >= min(max(original_count, 1), 3):
            score += 15
        else:
            result["warnings"].append(
                {
                    "type": "image_coverage",
                    "message": "图片理解覆盖不足，建议补充更多配图说明。",
                    "severity": "low",
                }
            )
        result["image_coverage_score"] = max(0, min(100, score))

    def _ai_audit(self, post, final_text, source_text):
        try:
            prompt = "\n".join(
                [
                    "请审核这篇改写后的中文图文草稿，重点检查：",
                    "1. 是否正确引用了原贴信息；",
                    "2. 是否出现原贴没有的夸张结论；",
                    "3. 是否存在明显空话或无依据推断；",
                    "4. 是否需要直接丢弃重写。",
                    "",
                    "请只返回 JSON：",
                    '{"issues":[],"warnings":[],"suggestions":[]}',
                    "",
                    "原帖内容：",
                    source_text[:2500],
                    "",
                    "改写内容：",
                    final_text[:2500],
                    "",
                    "来源链接：{}".format(self._get_source_url(post)),
                ]
            )
            response = self.client.chat.completions.create(
                model=self._active_model(),
                messages=[
                    {"role": "system", "content": "你是内容事实核验编辑，只输出 JSON，不要额外解释。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                lines = content.splitlines()
                content = "\n".join(lines[1:-1])
            import json

            return json.loads(content)
        except Exception:
            return None

    def _finalize_scores(self, result, media_type="image"):
        for key in (
            "detail_score",
            "reliability_score",
            "readability_score",
            "image_coverage_score",
            "empty_talk_score",
            "substance_score",
            "source_score",
            "citation_score",
        ):
            result[key] = max(0, min(100, round(result[key], 1)))

        final_score = (
            result["source_score"] * 0.24
            + result["citation_score"] * 0.18
            + result["reliability_score"] * 0.18
            + result["detail_score"] * 0.16
            + result["substance_score"] * 0.12
            + result["image_coverage_score"] * 0.07
            + result["readability_score"] * 0.05
        )

        if result["issues"]:
            final_score -= min(24, len(result["issues"]) * 5)
        high_warning_count = sum(1 for item in result["warnings"] if item.get("severity") == "high")
        if high_warning_count:
            final_score -= min(20, high_warning_count * 8)

        result["confidence_score"] = max(0, min(100, round(final_score, 1)))

        high_severity_issue = any(item.get("severity") == "high" for item in result["issues"])
        source_gate_failed = not result["source_valid"] or result["source_score"] < 75
        citation_gate_failed = not result["citation_valid"] or result["citation_score"] < 70
        detail_gate_failed = result["detail_score"] < 55 or result["substance_score"] < 65
        reliability_gate_failed = result["reliability_score"] < 70
        media_gate_failed = result["image_coverage_score"] < 70

        if media_type == "video":
            transcript_ok = result["source_valid"] and result["image_coverage_score"] >= 72
            media_gate_failed = media_gate_failed or not transcript_ok

        rejection_reasons = []
        if source_gate_failed:
            rejection_reasons.append("来源不可信或原贴信息不完整")
        if citation_gate_failed:
            rejection_reasons.append("改写内容与原贴对齐不足")
        if detail_gate_failed:
            rejection_reasons.append("内容不够详实")
        if reliability_gate_failed:
            rejection_reasons.append("存在较高失真风险")
        if media_gate_failed:
            rejection_reasons.append("媒体证据不足")
        if high_severity_issue:
            rejection_reasons.append("存在高严重度审核问题")

        if not rejection_reasons and result["confidence_score"] >= 85:
            result["hallucination_risk"] = "low"
            result["is_safe"] = True
            result["publish_ready"] = True
        elif not rejection_reasons and result["confidence_score"] >= 72:
            result["hallucination_risk"] = "medium"
            result["is_safe"] = True
            result["publish_ready"] = True
            result["suggestions"].append("建议再补一个明确场景或操作细节，让内容更稳。")
        else:
            result["hallucination_risk"] = "high"
            result["is_safe"] = False
            result["publish_ready"] = False
            result["rejection_reason"] = "；".join(dict.fromkeys(rejection_reasons)) or "综合评分不足"
            result["suggestions"].append("建议直接丢弃并重新抓取原帖，再生成新草稿。")

        result["summary"] = "总分 {score}/100，来源 {source}/100，引用对齐 {citation}/100，详实度 {detail}/100，可靠性 {reliability}/100，媒体覆盖 {image}/100。".format(
            score=result["confidence_score"],
            source=result["source_score"],
            citation=result["citation_score"],
            detail=result["detail_score"],
            reliability=result["reliability_score"],
            image=result["image_coverage_score"],
        )

    def _extract_keywords(self, text, limit=24):
        if not text:
            return []

        candidates = []
        candidates.extend(re.findall(r"[A-Za-z][A-Za-z0-9\-\+\.]{1,24}", text))
        candidates.extend(re.findall(r"[\u4e00-\u9fff]{2,8}", text))

        cleaned = []
        seen = set()
        for token in candidates:
            token = token.strip().lower()
            if len(token) < 2 or token in self.STOPWORDS or token.isdigit():
                continue
            if token not in seen:
                seen.add(token)
                cleaned.append(token)
            if len(cleaned) >= limit:
                break
        return cleaned

    def _keyword_overlap(self, source_keywords, final_keywords):
        source_set = set(source_keywords or [])
        final_set = set(final_keywords or [])
        if not source_set or not final_set:
            return 0.0
        return len(source_set & final_set) / float(len(source_set))

    def _get_source_url(self, post):
        return str(post.get("source_url") or post.get("link") or "").strip()

    def _has_visual_source_evidence(self, post):
        image_count = len(post.get("original_image_paths", []) or post.get("final_image_paths", []) or post.get("original_image_urls", []) or [])
        insight_count = len(post.get("image_insights", []) or [])
        image_summary = bool((post.get("image_summary") or "").strip())
        semantic_summary = bool((post.get("image_semantic_summary") or "").strip())
        image_ocr_text = len((post.get("image_ocr_text") or "").strip()) >= 12
        return image_count >= 1 and (
            image_summary
            or semantic_summary
            or image_ocr_text
            or insight_count >= min(max(image_count, 1), 2)
        )

    def _has_video_source_evidence(self, post):
        has_video = bool((post.get("original_video_url") or "").strip() or post.get("original_video_path"))
        has_transcript = len((post.get("video_transcript") or "").strip()) >= 20
        frame_count = len(post.get("video_frame_paths", []) or [])
        insight_count = len(post.get("video_frame_insights", []) or [])
        has_summary = bool((post.get("video_summary") or "").strip())
        return has_video and has_transcript and frame_count >= 2 and insight_count >= 2 and has_summary

    def _is_valid_source_url(self, url):
        if not url:
            return False
        try:
            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
        except Exception:
            return False
        return any(host.endswith(domain) for domain in self.SOURCE_DOMAINS)
