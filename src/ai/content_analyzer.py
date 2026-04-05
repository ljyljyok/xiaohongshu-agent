#!/usr/bin/env python3
"""AI 相关内容识别与分类。"""

import os
import re
import sys
import json
from typing import Iterable, List

from config.config import get_ai_runtime_mode

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from src.ai.text_llm_client import initialize_text_llm


class ContentAnalyzer:
    """识别帖子是否与 AI 相关，并给出基础分类。"""

    def __init__(self):
        self.client = None
        self.use_ai_mode = False
        self.mode = "local"
        self.mode_reason = ""
        requested_mode = get_ai_runtime_mode("content_analyzer_mode")
        try:
            self.client, self.mode, self.mode_reason = initialize_text_llm(requested_mode, "内容分析")
            if self.client:
                self.use_ai_mode = True
                print("[OK] {}".format(self.mode_reason))
            else:
                print("[INFO] {}".format(self.mode_reason))
        except Exception as exc:
            self.mode = "local"
            self.mode_reason = "内容分析初始化失败，已退回本地关键词规则模式：{}".format(str(exc)[:120])
            print("[WARNING] {}".format(self.mode_reason))

        self.ai_keywords = {
            "AI": ["AI", "人工智能", "artificial intelligence", "大模型", "LLM", "GPT", "ChatGPT"],
            "AIGC": ["AIGC", "生成式AI", "generative ai", "内容生成"],
            "工具": ["工具", "软件", "平台", "应用", "service", "tool", "app", "software"],
            "资讯": ["新闻", "资讯", "动态", "更新", "发布", "new", "news", "update", "release"],
            "教程": ["教程", "指南", "使用", "学习", "how to", "guide", "tutorial"],
            "绘画": ["Midjourney", "Stable Diffusion", "DALL-E", "绘画", "图像生成", "image generation"],
            "写作": ["写作", "文案", "生成文本", "text generation", "writing"],
            "编程": ["编程", "代码", "code", "programming", "Copilot", "Cursor", "Claude Code"],
            "效率": ["效率", "自动化", "automation", "productivity", "助手", "assistant", "agentic"],
        }

        self.category_mapping = {
            "AI工具": ["工具", "软件", "平台", "应用", "service", "tool", "app", "software"],
            "AI资讯": ["新闻", "资讯", "动态", "更新", "发布", "new", "news", "update", "release"],
            "AI教程": ["教程", "指南", "使用", "学习", "how to", "guide", "tutorial"],
            "AI绘画": ["Midjourney", "Stable Diffusion", "DALL-E", "绘画", "图像生成", "image generation"],
            "AI写作": ["写作", "文案", "生成文本", "text generation", "writing"],
            "AI编程": ["编程", "代码", "code", "programming", "Copilot", "Cursor", "Claude Code"],
            "AI效率": ["效率", "自动化", "automation", "productivity", "助手", "assistant", "agentic"],
        }

    def is_ai_related(self, content):
        if not content:
            return False

        content_lower = str(content).lower()
        for keywords in self.ai_keywords.values():
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    return True
        return False

    def analyze_content(self, post, user_keywords: Iterable[str] = None):
        analysis_result = {
            "is_ai_related": False,
            "content_type": "",
            "relevance_score": 0,
            "keywords": [],
            "mode": self.mode,
            "mode_reason": self.mode_reason,
            "keyword_forced_ai": False,
            "matched_user_keywords": [],
        }

        title = str(post.get("title") or "").strip()
        content = str(post.get("content") or "").strip()
        full_content = "{} {}".format(title, content).strip()
        matched_user_keywords = self._extract_matched_user_keywords(title, user_keywords)
        forced_ai = bool(matched_user_keywords)

        analysis_result["matched_user_keywords"] = matched_user_keywords
        analysis_result["keyword_forced_ai"] = forced_ai

        if forced_ai or self.is_ai_related(full_content):
            analysis_result["is_ai_related"] = True
            if self.use_ai_mode and self.client:
                ai_result = self._analyze_with_ai(full_content, analysis_result)
                if ai_result:
                    return ai_result
            return self._analyze_locally(full_content, analysis_result)

        return analysis_result

    def _analyze_with_ai(self, content, base_result):
        try:
            model_name = getattr(self.client, "default_model", None)
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一个 AI 内容分析专家。只能输出 1 个 JSON 对象，不要解释，不要 markdown，不要额外文字。"
                            "请输出 JSON："
                            '{"is_ai_related": true/false, "content_type": "AI资讯/AI工具/AI教程/其他", '
                            '"relevance_score": 0-10, "keywords": ["关键词"]}'
                        ),
                    },
                    {
                        "role": "user",
                        "content": "请分析以下内容是否与 AI 强相关：{}".format(content[:800]),
                    },
                ],
                temperature=0.2,
                max_tokens=420,
            )
            ai_response = (response.choices[0].message.content or "").strip()
            clean_response = ai_response
            if clean_response.startswith("```"):
                lines = clean_response.splitlines()
                clean_response = "\n".join(lines[1:-1]).strip()
            ai_result = self._parse_ai_json(clean_response)
            base_result.update(
                {
                    "is_ai_related": bool(ai_result.get("is_ai_related", True)),
                    "content_type": ai_result.get("content_type", "") or base_result.get("content_type", ""),
                    "relevance_score": int(ai_result.get("relevance_score", 0) or 0),
                    "keywords": list(ai_result.get("keywords", []) or []),
                    "mode": self.mode,
                    "mode_reason": "{} | model={}".format(self.mode_reason, model_name or "default"),
                }
            )
            if base_result.get("keyword_forced_ai"):
                base_result["is_ai_related"] = True
            return base_result
        except Exception as exc:
            print("[WARNING] AI analysis failed, fallback to local mode: {}".format(str(exc)[:100]))
            return None

    def _parse_ai_json(self, text: str):
        raw = str(text or "").strip()
        if not raw:
            raise ValueError("empty ai response")
        try:
            return json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(raw[start : end + 1])
        raise ValueError("no valid json object found in ai response")

    def _analyze_locally(self, content, base_result):
        content_lower = str(content).lower()
        best_category = ""
        max_matches = 0
        matched_keywords = []

        for category, keywords in self.category_mapping.items():
            current_matches = [kw for kw in keywords if kw.lower() in content_lower]
            if len(current_matches) > max_matches:
                max_matches = len(current_matches)
                best_category = category
                matched_keywords = current_matches

        total_keywords = sum(len(kws) for kws in self.ai_keywords.values())
        found_keywords = sum(
            1 for keywords in self.ai_keywords.values() for keyword in keywords if keyword.lower() in content_lower
        )
        relevance_score = min(10, int((found_keywords / max(total_keywords, 1)) * 18))

        if not best_category:
            best_category = "AI相关"
        if not matched_keywords and base_result.get("matched_user_keywords"):
            matched_keywords = list(base_result["matched_user_keywords"])
        if base_result.get("keyword_forced_ai") and relevance_score < 6:
            relevance_score = 6

        base_result.update(
            {
                "content_type": best_category,
                "relevance_score": relevance_score,
                "keywords": matched_keywords[:8],
                "mode": "local",
            }
        )
        return base_result

    def _extract_matched_user_keywords(self, title: str, user_keywords: Iterable[str]) -> List[str]:
        if not title or not user_keywords:
            return []

        normalized_title = self._normalize_keyword(title)
        matches = []
        for keyword in user_keywords:
            cleaned = str(keyword or "").strip()
            if not cleaned:
                continue
            normalized_keyword = self._normalize_keyword(cleaned)
            if normalized_keyword and normalized_keyword in normalized_title and cleaned not in matches:
                matches.append(cleaned)
        return matches

    def _normalize_keyword(self, value: str) -> str:
        return re.sub(r"\s+", "", str(value or "").strip().lower())

    def batch_analyze(self, posts, user_keywords: Iterable[str] = None):
        results = []
        normalized_keywords = [str(item).strip() for item in (user_keywords or []) if str(item).strip()]
        for index, post in enumerate(posts):
            try:
                result = self.analyze_content(post, user_keywords=normalized_keywords)
                post["analysis"] = result

                mode = result.get("mode", "unknown")
                content_type = result.get("content_type", "")
                if result.get("is_ai_related", False):
                    force_tag = ""
                    if result.get("keyword_forced_ai"):
                        force_tag = " | keyword_forced_ai={}".format(",".join(result.get("matched_user_keywords", [])))
                    print(
                        "[{}] 分析完成: {} [{}] (mode={}{})".format(
                            index + 1,
                            str(post.get("title", "无标题"))[:30],
                            content_type or "未分类",
                            mode,
                            force_tag,
                        )
                    )
                else:
                    print("[{}] 跳过: {} (非AI相关)".format(index + 1, str(post.get("title", "无标题"))[:30]))
            except Exception as exc:
                print("[ERROR] 分析帖子 {} 失败: {}".format(index + 1, str(exc)[:80]))
                post["analysis"] = {
                    "is_ai_related": False,
                    "content_type": "",
                    "relevance_score": 0,
                    "keywords": [],
                    "mode": "error",
                    "mode_reason": str(exc),
                    "keyword_forced_ai": False,
                    "matched_user_keywords": [],
                    "error": str(exc),
                }
            results.append(post)
        return results


if __name__ == "__main__":
    analyzer = ContentAnalyzer()
    test_posts = [
        {"title": "ChatGPT 最新功能介绍", "content": "OpenAI 发布新能力。"},
        {"title": "Claude Code 实战", "content": "这条标题会命中用户关键词。"},
        {"title": "夏季旅游攻略", "content": "普通生活内容。"},
    ]
    results = analyzer.batch_analyze(test_posts, user_keywords=["Claude Code", "OpenAI"])
    for item in results:
        print(item["title"], item["analysis"])
