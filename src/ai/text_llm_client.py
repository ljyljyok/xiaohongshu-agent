#!/usr/bin/env python3
"""Unified text and multimodal client for OpenAI, DeepSeek, and Ollama."""

import base64
import json
import os
from types import SimpleNamespace

import requests

from config.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_CHAT_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_ENABLED,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    has_valid_deepseek_api_key,
    has_valid_openai_api_key,
)


class _ChatCompletions:
    def __init__(self, parent):
        self._parent = parent

    def create(self, model=None, messages=None, temperature=0.2, max_tokens=512, response_format=None):
        return self._parent._create_completion(
            model=model,
            messages=messages or [],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )


class _ChatNamespace:
    def __init__(self, parent):
        self.completions = _ChatCompletions(parent)


class TextLLMClient:
    def __init__(self, provider, api_key, base_url, default_model):
        self.provider = provider
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/")
        self.default_model = default_model
        self.chat = _ChatNamespace(self)
        self.session = requests.Session()

    def _create_completion(self, model=None, messages=None, temperature=0.2, max_tokens=512, response_format=None):
        payload = {
            "model": model or self.default_model,
            "messages": messages or [],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        response = self.session.post(
            self.base_url + "/chat/completions",
            headers={
                "Authorization": "Bearer {}".format(self.api_key),
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        content = ""
        if choices:
            content = ((choices[0] or {}).get("message") or {}).get("content") or ""
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class OllamaClient:
    def __init__(self, base_url=None, default_model=None):
        self.provider = "ollama"
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.default_model = default_model or OLLAMA_MODEL
        self.chat = _ChatNamespace(self)
        self.session = requests.Session()
        self._endpoint_order_cache = None

    def _normalize_ollama_image(self, value):
        raw = str(value or "").strip()
        if not raw:
            return ""
        if raw.startswith("data:image") and "," in raw:
            return raw.split(",", 1)[1]
        if os.path.exists(raw):
            with open(raw, "rb") as fh:
                return base64.b64encode(fh.read()).decode("utf-8")
        return ""

    def _convert_messages(self, messages):
        converted = []
        for message in messages or []:
            role = str(message.get("role") or "user")
            content = message.get("content", "")
            if isinstance(content, list):
                text_parts = []
                images = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "text":
                        text_parts.append(str(part.get("text") or "").strip())
                    elif part.get("type") == "image_url":
                        image_data = self._normalize_ollama_image((part.get("image_url") or {}).get("url"))
                        if image_data:
                            images.append(image_data)
                item = {"role": role, "content": "\n".join([x for x in text_parts if x]).strip()}
                if images:
                    item["images"] = images
                converted.append(item)
            else:
                converted.append({"role": role, "content": str(content or "")})
        return converted

    def _messages_to_prompt(self, messages):
        parts = []
        for item in self._convert_messages(messages or []):
            role = str(item.get("role") or "user").strip().upper()
            content = str(item.get("content") or "").strip()
            if content:
                parts.append("{}:\n{}".format(role, content))
        parts.append("ASSISTANT:")
        return "\n\n".join(parts).strip()

    def _extract_generate_images(self, messages):
        converted = self._convert_messages(messages or [])
        for item in reversed(converted):
            images = item.get("images") or []
            if images:
                return images
        return []

    def _post_json(self, path, payload, timeout):
        response = self.session.post(
            self.base_url + path,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    def _post_openai_compatible(self, payload, timeout):
        response = self.session.post(
            self.base_url + "/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    def _extract_chat_content(self, data):
        message = data.get("message") or {}
        content = str(message.get("content") or "").strip()
        reasoning = str(message.get("reasoning") or "").strip()
        return content or reasoning

    def _extract_openai_compatible_content(self, data):
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = (choices[0] or {}).get("message") or {}
        content = str(message.get("content") or "").strip()
        reasoning = str(message.get("reasoning") or "").strip()
        return content or reasoning

    def _probe_endpoint(self, path):
        try:
            response = self.session.options(self.base_url + path, timeout=5)
            return response.status_code != 404
        except Exception:
            return None

    def _preferred_endpoints(self):
        if self._endpoint_order_cache is not None:
            return list(self._endpoint_order_cache)

        candidates = ["/api/chat", "/api/generate", "/v1/chat/completions"]
        supported = []
        unknown = []
        for path in candidates:
            available = self._probe_endpoint(path)
            if available is True:
                supported.append(path)
            elif available is None:
                unknown.append(path)
        ordered = supported + [path for path in candidates if path not in supported and path not in unknown] + unknown
        if not ordered:
            ordered = list(candidates)
        self._endpoint_order_cache = ordered
        return list(ordered)

    def _create_completion(self, model=None, messages=None, temperature=0.2, max_tokens=512, response_format=None):
        converted_messages = self._convert_messages(messages or [])
        chat_payload = {
            "model": model or self.default_model,
            "messages": converted_messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        generate_payload = {
            "model": model or self.default_model,
            "prompt": self._messages_to_prompt(messages or []),
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        generate_images = self._extract_generate_images(messages or [])
        if generate_images:
            generate_payload["images"] = generate_images

        openai_payload = {
            "model": model or self.default_model,
            "messages": messages or [],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "think": False,
        }
        if response_format:
            openai_payload["response_format"] = response_format
        attempted = []
        last_error = None
        for path in self._preferred_endpoints():
            attempted.append(path)
            try:
                if path == "/api/chat":
                    data = self._post_json(path, chat_payload, timeout=180)
                    content = self._extract_chat_content(data)
                elif path == "/api/generate":
                    data = self._post_json(path, generate_payload, timeout=180)
                    content = str(data.get("response") or "").strip()
                else:
                    data = self._post_openai_compatible(openai_payload, timeout=180)
                    content = self._extract_openai_compatible_content(data)
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
                )
            except requests.HTTPError as exc:
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)
                if status_code in (404, 405):
                    last_error = "{} -> HTTP {}".format(path, status_code)
                    continue
                raise
            except Exception as exc:
                last_error = "{} -> {}".format(path, str(exc)[:180])
                continue

        raise RuntimeError(
            "Ollama 接口均不可用，已尝试 {}，最后错误: {}".format(
                " -> ".join(attempted),
                last_error or "unknown",
            )
        )


def check_ollama_available(base_url=None, model_name=None):
    if not OLLAMA_ENABLED:
        return False, "Ollama 已在配置中禁用。", ""

    target_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
    requested_model = (model_name or OLLAMA_MODEL).strip() or OLLAMA_MODEL
    try:
        response = requests.get(target_url + "/api/tags", timeout=5)
        response.raise_for_status()
        models = [str(item.get("name") or "") for item in (response.json().get("models") or [])]
        if requested_model in models:
            return True, "已检测到本地模型 {}".format(requested_model), requested_model
        same_family = [item for item in models if requested_model.split(":", 1)[0] in item]
        if same_family:
            return True, "未找到精确模型，已匹配同系列模型 {}".format(same_family[0]), same_family[0]
        return False, "Ollama 已启动，但未找到模型 {}".format(requested_model), ""
    except Exception as exc:
        return False, "Ollama 不可用：{}".format(str(exc)[:120]), ""


def initialize_text_llm(requested_mode, capability_label):
    mode = str(requested_mode or "deepseek").strip().lower()

    if mode == "local":
        return None, "local", "设置为本地模式，{}不会调用外部模型。".format(capability_label)

    if mode == "ollama":
        available, message, matched_model = check_ollama_available()
        if available:
            return (
                OllamaClient(base_url=OLLAMA_BASE_URL, default_model=matched_model or OLLAMA_MODEL),
                "ollama",
                "已启用 Ollama {}（{}）".format(capability_label, matched_model or OLLAMA_MODEL),
            )
        return None, "local", "已选择 Ollama {}，但{}，已退回本地模式".format(capability_label, message)

    if mode == "deepseek":
        if has_valid_deepseek_api_key(DEEPSEEK_API_KEY):
            return (
                TextLLMClient(
                    provider="deepseek",
                    api_key=DEEPSEEK_API_KEY,
                    base_url=DEEPSEEK_BASE_URL,
                    default_model=DEEPSEEK_CHAT_MODEL,
                ),
                "deepseek",
                "已启用 DeepSeek {}".format(capability_label),
            )
        return None, "local", "已选择 DeepSeek {}，但未配置有效 DEEPSEEK_API_KEY，已退回本地模式".format(capability_label)

    if mode == "openai":
        if has_valid_openai_api_key(OPENAI_API_KEY):
            return (
                TextLLMClient(
                    provider="openai",
                    api_key=OPENAI_API_KEY,
                    base_url=OPENAI_BASE_URL,
                    default_model="gpt-4o-mini",
                ),
                "openai",
                "已启用 OpenAI {}".format(capability_label),
            )
        return None, "local", "已选择 OpenAI {}，但未配置有效 OPENAI_API_KEY，已退回本地模式".format(capability_label)

    available, message, matched_model = check_ollama_available()
    if available:
        return (
            OllamaClient(base_url=OLLAMA_BASE_URL, default_model=matched_model or OLLAMA_MODEL),
            "ollama",
            "自动模式已命中 Ollama {}（{}）".format(capability_label, matched_model or OLLAMA_MODEL),
        )

    if has_valid_deepseek_api_key(DEEPSEEK_API_KEY):
        return (
            TextLLMClient(
                provider="deepseek",
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
                default_model=DEEPSEEK_CHAT_MODEL,
            ),
            "deepseek",
            "自动模式已命中 DeepSeek {}".format(capability_label),
        )

    if has_valid_openai_api_key(OPENAI_API_KEY):
        return (
            TextLLMClient(
                provider="openai",
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                default_model="gpt-4o-mini",
            ),
            "openai",
            "自动模式已命中 OpenAI {}".format(capability_label),
        )

    return None, "local", "未配置可用的 Ollama / DeepSeek / OpenAI，{}使用本地模式".format(capability_label)
