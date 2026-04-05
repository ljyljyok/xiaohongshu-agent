#!/usr/bin/env python3
"""Regression tests for Ollama endpoint fallback and analyzer model selection."""

from types import SimpleNamespace

import requests

from src.ai.content_analyzer import ContentAnalyzer
from src.ai.text_llm_client import OllamaClient


def _http_error(status_code):
    response = requests.Response()
    response.status_code = status_code
    error = requests.HTTPError(f"{status_code} error")
    error.response = response
    return error


def test_ollama_falls_back_from_chat_to_generate(monkeypatch):
    client = OllamaClient(base_url="http://localhost:11434", default_model="gemma4:e4b")
    monkeypatch.setattr(client, "_preferred_endpoints", lambda: ["/api/chat", "/api/generate", "/v1/chat/completions"])

    calls = []

    def fake_post_json(path, payload, timeout):
        calls.append(path)
        if path == "/api/chat":
            raise _http_error(404)
        if path == "/api/generate":
            return {"response": "ok-from-generate"}
        raise AssertionError("unexpected path")

    monkeypatch.setattr(client, "_post_json", fake_post_json)
    monkeypatch.setattr(client, "_post_openai_compatible", lambda payload, timeout: {"choices": []})

    response = client.chat.completions.create(messages=[{"role": "user", "content": "hi"}])
    assert response.choices[0].message.content == "ok-from-generate"
    assert calls == ["/api/chat", "/api/generate"]


def test_ollama_falls_back_to_openai_compatible(monkeypatch):
    client = OllamaClient(base_url="http://localhost:11434", default_model="gemma4:e4b")
    monkeypatch.setattr(client, "_preferred_endpoints", lambda: ["/api/chat", "/api/generate", "/v1/chat/completions"])

    def fake_post_json(path, payload, timeout):
        raise _http_error(404)

    monkeypatch.setattr(client, "_post_json", fake_post_json)
    monkeypatch.setattr(
        client,
        "_post_openai_compatible",
        lambda payload, timeout: {"choices": [{"message": {"content": "ok-from-v1"}}]},
    )

    response = client.chat.completions.create(messages=[{"role": "user", "content": "hi"}])
    assert response.choices[0].message.content == "ok-from-v1"


def test_ollama_reports_endpoint_chain_on_total_failure(monkeypatch):
    client = OllamaClient(base_url="http://localhost:11434", default_model="gemma4:e4b")
    monkeypatch.setattr(client, "_preferred_endpoints", lambda: ["/api/chat", "/api/generate", "/v1/chat/completions"])
    monkeypatch.setattr(client, "_post_json", lambda path, payload, timeout: (_ for _ in ()).throw(_http_error(404)))
    monkeypatch.setattr(client, "_post_openai_compatible", lambda payload, timeout: (_ for _ in ()).throw(RuntimeError("boom")))

    try:
        client.chat.completions.create(messages=[{"role": "user", "content": "hi"}])
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert "/api/chat" in message
    assert "/api/generate" in message
    assert "/v1/chat/completions" in message


def test_content_analyzer_uses_ollama_default_model(monkeypatch):
    analyzer = ContentAnalyzer()
    analyzer.client = SimpleNamespace(
        default_model="gemma4:e4b",
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    model_used=kwargs.get("model"),
                    choices=[SimpleNamespace(message=SimpleNamespace(content='{"is_ai_related": true, "content_type": "AI工具", "relevance_score": 8, "keywords": ["chatgpt"]}'))],
                )
            )
        ),
    )
    analyzer.use_ai_mode = True
    analyzer.mode = "ollama"
    analyzer.mode_reason = "test ollama"

    result = analyzer.analyze_content({"title": "ChatGPT 工具测评", "content": "一个 AI 工具体验"}, user_keywords=[])
    assert result["is_ai_related"] is True
    assert result["mode"] == "ollama"
    assert "gemma4:e4b" in result["mode_reason"]
