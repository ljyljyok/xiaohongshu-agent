from __future__ import annotations

from copy import deepcopy


NORMALIZED_LOGIN_STATES = {
    "logged_in",
    "running",
    "expired",
    "timeout",
    "error",
    "unavailable",
    "idle",
}

KNOWN_LOGIN_STATES = NORMALIZED_LOGIN_STATES | {"stopped", "starting", "done"}
ACTIVE_STATUS_FILE_STATES = {"running", "starting"}
TERMINAL_STATUS_FILE_STATES = {"error", "timeout", "stopped", "unavailable", "done"}

LOGIN_STATUS_LABELS = {
    "logged_in": "已登录",
    "running": "登录中",
    "expired": "已过期",
    "timeout": "已超时",
    "error": "登录失败",
    "stopped": "已停止",
    "unavailable": "MCP 不可用",
    "idle": "未登录",
}

_AUTH_SOURCE_BY_RESULT_SOURCE = {
    "mcp": "mcp",
    "process": "process",
    "status_file": "status_file",
    "cookie_fallback": "cookie_fallback",
    "none": "none",
}


def _clone_result(result):
    payload = deepcopy(result or {})
    payload["data"] = dict(payload.get("data") or {})
    status = str(payload.get("status") or "idle").strip().lower()
    payload["status"] = status if status in KNOWN_LOGIN_STATES else "idle"
    payload["message"] = str(payload.get("message") or "").strip()
    payload["success"] = bool(payload.get("success", False))
    return payload


def _normalized_state(status):
    normalized = str(status or "idle").strip().lower()
    if normalized in NORMALIZED_LOGIN_STATES:
        return normalized
    if normalized in ACTIVE_STATUS_FILE_STATES:
        return "running"
    if normalized in {"stopped", "done"}:
        return "idle"
    return "idle"


def _build_reason(message, default_reason):
    message = str(message or "").strip()
    return message or default_reason


def _fallback_summary(fallback_result):
    fallback = _clone_result(fallback_result)
    fallback_state = _normalized_state(fallback["status"])
    return {
        "source": "cookie_fallback",
        "status": fallback["status"],
        "state": fallback_state,
        "message": fallback["message"],
        "reason": _build_reason(fallback["message"], "Validated legacy cookie fallback was evaluated"),
    }


def _finalize_result(base_result, *, state, source, reason, success=None, extra_data=None):
    payload = _clone_result(base_result)
    data = dict(payload.get("data") or {})
    if extra_data:
        data.update(extra_data)
    auth_source = _AUTH_SOURCE_BY_RESULT_SOURCE.get(source, source)
    data.setdefault("backend", "legacy" if source == "cookie_fallback" else "mcp")
    data["auth_source"] = auth_source
    data["source"] = source
    data["reason"] = reason

    payload["status"] = state
    payload["state"] = state
    payload["source"] = source
    payload["reason"] = reason
    payload["message"] = payload.get("message") or reason
    payload["success"] = bool(success if success is not None else state == "logged_in")
    payload["data"] = data
    return payload


def normalize_login_result(primary_result, fallback_result=None):
    primary = _clone_result(primary_result)
    primary_state = _normalized_state(primary["status"])
    primary_data = dict(primary.get("data") or {})
    primary_data.setdefault("backend", "mcp")

    fallback = _clone_result(fallback_result) if fallback_result else None
    if fallback:
        primary_data["fallback"] = _fallback_summary(fallback)

    if primary_state == "logged_in":
        return _finalize_result(
            primary,
            state="logged_in",
            source="mcp",
            reason=_build_reason(primary["message"], "MCP reported an active login session"),
            success=True,
            extra_data=primary_data,
        )

    if primary_state == "expired":
        return _finalize_result(
            primary,
            state="expired",
            source="mcp",
            reason=_build_reason(primary["message"], "MCP reported that the login session expired"),
            success=False,
            extra_data=primary_data,
        )

    if primary_state == "unavailable" and fallback:
        fallback_state = _normalized_state(fallback["status"])
        if fallback_state == "logged_in":
            reason = _build_reason(
                primary["message"] or fallback["message"],
                "MCP unavailable; using validated legacy cookie fallback",
            )
            return _finalize_result(
                primary,
                state="logged_in",
                source="cookie_fallback",
                reason=reason,
                success=True,
                extra_data=primary_data,
            )
        if fallback_state in {"expired", "idle"}:
            fallback_reason = (
                "MCP unavailable; legacy cookies expired"
                if fallback_state == "expired"
                else "MCP unavailable; no valid legacy cookies found"
            )
            return _finalize_result(
                primary,
                state=fallback_state,
                source="cookie_fallback",
                reason=_build_reason(primary["message"] or fallback["message"], fallback_reason),
                success=False,
                extra_data=primary_data,
            )

    return _finalize_result(
        primary,
        state=primary_state,
        source="mcp" if primary_state != "idle" or primary.get("message") else "none",
        reason=_build_reason(primary["message"], "No active login session detected"),
        success=primary.get("success", False),
        extra_data=primary_data,
    )


def _status_file_resolution(status_payload):
    payload = dict(status_payload or {})
    raw_status = str(payload.get("status") or "").strip().lower()
    message = str(payload.get("message") or "").strip()

    if raw_status in ACTIVE_STATUS_FILE_STATES:
        return {
            "state": "running",
            "source": "status_file",
            "reason": _build_reason(message, "Login status file indicates an active login flow"),
        }

    if raw_status == "error":
        return {
            "state": "error",
            "source": "status_file",
            "reason": _build_reason(message, "Login status file recorded an error"),
        }

    if raw_status == "timeout":
        return {
            "state": "timeout",
            "source": "status_file",
            "reason": _build_reason(message, "Login status file recorded a timeout"),
        }

    if raw_status == "unavailable":
        return {
            "state": "unavailable",
            "source": "status_file",
            "reason": _build_reason(message, "Login status file reports that MCP is unavailable"),
        }

    if raw_status in {"stopped", "done"}:
        return {
            "state": "idle",
            "source": "status_file",
            "reason": _build_reason(message, "Login flow finished without an active session"),
        }

    return None


def resolve_login_state(backend_status, status_payload=None, process_running=False, current_status="idle"):
    backend = normalize_login_result(backend_status)
    status_resolution = _status_file_resolution(status_payload)
    current_state = _normalized_state(current_status)

    if backend["state"] == "logged_in" and backend["source"] == "mcp":
        return backend

    if process_running:
        return {
            "state": "running",
            "status": "running",
            "source": "process",
            "reason": "Login process is still running",
            "message": "Login process is still running",
            "success": False,
            "data": {"source": "process", "reason": "Login process is still running", "auth_source": "process"},
        }

    if status_resolution and status_resolution["state"] == "running":
        return {
            "state": "running",
            "status": "running",
            "source": status_resolution["source"],
            "reason": status_resolution["reason"],
            "message": status_resolution["reason"],
            "success": False,
            "data": {
                "source": status_resolution["source"],
                "reason": status_resolution["reason"],
                "auth_source": _AUTH_SOURCE_BY_RESULT_SOURCE[status_resolution["source"]],
            },
        }

    if backend["state"] == "logged_in":
        return backend

    if backend["state"] == "expired" and backend["source"] == "mcp":
        return backend

    if status_resolution and backend["state"] in {"idle", "unavailable"}:
        return {
            "state": status_resolution["state"],
            "status": status_resolution["state"],
            "source": status_resolution["source"],
            "reason": status_resolution["reason"],
            "message": status_resolution["reason"],
            "success": False,
            "data": {
                "source": status_resolution["source"],
                "reason": status_resolution["reason"],
                "auth_source": _AUTH_SOURCE_BY_RESULT_SOURCE[status_resolution["source"]],
            },
        }

    if backend["state"] in NORMALIZED_LOGIN_STATES:
        return backend

    if status_resolution:
        return {
            "state": status_resolution["state"],
            "status": status_resolution["state"],
            "source": status_resolution["source"],
            "reason": status_resolution["reason"],
            "message": status_resolution["reason"],
            "success": False,
            "data": {
                "source": status_resolution["source"],
                "reason": status_resolution["reason"],
                "auth_source": _AUTH_SOURCE_BY_RESULT_SOURCE[status_resolution["source"]],
            },
        }

    if current_state in NORMALIZED_LOGIN_STATES and current_state != "idle":
        reason = "Preserving the last known UI login state while waiting for fresher signals"
        return {
            "state": current_state,
            "status": current_state,
            "source": "none",
            "reason": reason,
            "message": reason,
            "success": current_state == "logged_in",
            "data": {"source": "none", "reason": reason, "auth_source": "none"},
        }

    return {
        "state": "idle",
        "status": "idle",
        "source": "none",
        "reason": "No active login session detected",
        "message": "No active login session detected",
        "success": False,
        "data": {"source": "none", "reason": "No active login session detected", "auth_source": "none"},
    }


def resolve_login_ui_status(backend_status, status_payload=None, process_running=False, current_status="idle"):
    return resolve_login_state(
        backend_status=backend_status,
        status_payload=status_payload,
        process_running=process_running,
        current_status=current_status,
    )["state"]
