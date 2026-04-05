#!/usr/bin/env python3
"""Shared bootstrap helpers for standalone entry scripts."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from typing import Iterable


PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
SCRIPT_DIR = os.path.join(PROJECT_ROOT, "scripts")
DEFAULT_LJY_PYTHON = r"C:\Users\ljy\miniconda3\envs\LJY\python.exe"


def ensure_project_paths() -> None:
    for path in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "src")):
        if path not in sys.path:
            sys.path.insert(0, path)


def script_path(name: str) -> str:
    return os.path.join(SCRIPT_DIR, name)


def preferred_python_executable() -> str:
    explicit = str(os.environ.get("XHS_PYTHON_EXE", "") or "").strip()
    candidates = []
    if explicit:
        candidates.append(explicit)

    current = os.path.abspath(sys.executable)
    current_dir = os.path.dirname(current)
    candidates.append(os.path.join(current_dir, "envs", "LJY", "python.exe"))
    candidates.append(os.path.join(os.path.dirname(current_dir), "envs", "LJY", "python.exe"))
    candidates.append(DEFAULT_LJY_PYTHON)
    candidates.append(current)

    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if os.path.exists(candidate):
            return candidate
    return current


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def ensure_runtime_environment(*, require_selenium: bool = False) -> None:
    """Ensure project paths are present and optionally re-exec into LJY Python."""
    ensure_project_paths()

    if not require_selenium:
        return

    if _has_module("selenium"):
        return

    if os.environ.get("XHS_REEXECUTED_FOR_DEPS") == "1":
        return

    current = os.path.abspath(sys.executable)
    candidate = preferred_python_executable()
    if not candidate or os.path.abspath(candidate) == current:
        return

    env = os.environ.copy()
    env["XHS_REEXECUTED_FOR_DEPS"] = "1"
    env["XHS_PYTHON_EXE"] = candidate
    print(
        f"[INFO] 当前 Python 缺少 selenium，已自动切换到 LJY 环境继续执行：{candidate}",
        file=sys.stderr,
    )
    completed = subprocess.run([candidate] + sys.argv, env=env)
    raise SystemExit(completed.returncode)
