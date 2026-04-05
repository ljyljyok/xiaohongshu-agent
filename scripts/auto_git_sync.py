#!/usr/bin/env python3
"""Poll the repository and automatically commit + push stabilized changes."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
    )


def git_output(repo: Path, *args: str) -> str:
    try:
        return run_git(repo, *args).stdout.strip()
    except subprocess.CalledProcessError as exc:
        return (exc.stdout or exc.stderr or "").strip()


def has_changes(repo: Path) -> bool:
    return bool(git_output(repo, "status", "--porcelain"))


def ensure_git_repo(repo: Path) -> None:
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if probe.returncode != 0:
        raise RuntimeError("当前目录不是 Git 仓库，无法启动自动同步。")


def ensure_remote(repo: Path) -> None:
    remotes = git_output(repo, "remote").splitlines()
    if not [item for item in remotes if item.strip()]:
        raise RuntimeError("当前仓库还没有配置远程地址，请先设置 origin。")


def current_branch(repo: Path) -> str:
    branch = git_output(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return branch or "main"


def has_upstream(repo: Path, branch: str) -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return probe.returncode == 0


def sync_once(repo: Path, message_prefix: str) -> bool:
    if not has_changes(repo):
        return False

    run_git(repo, "add", "-A")

    diff_probe = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if diff_probe.returncode == 0:
        return False

    commit_message = "{} {}".format(message_prefix, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    run_git(repo, "commit", "-m", commit_message)

    branch = current_branch(repo)
    if has_upstream(repo, branch):
        run_git(repo, "push")
    else:
        run_git(repo, "push", "-u", "origin", branch)
    return True


def watch(repo: Path, interval: int, debounce: int, message_prefix: str) -> int:
    ensure_git_repo(repo)
    ensure_remote(repo)

    print("自动同步已启动")
    print("仓库目录:", repo)
    print("轮询间隔:", interval, "秒")
    print("静默提交延迟:", debounce, "秒")

    last_dirty_at = 0.0
    while True:
        dirty = has_changes(repo)
        now = time.time()
        if dirty and not last_dirty_at:
            last_dirty_at = now
            print("[{}] 检测到文件变动，等待稳定后自动提交。".format(datetime.now().strftime("%H:%M:%S")))
        elif dirty and last_dirty_at and (now - last_dirty_at) >= debounce:
            try:
                changed = sync_once(repo, message_prefix)
                if changed:
                    print("[{}] 已自动提交并推送。".format(datetime.now().strftime("%H:%M:%S")))
                else:
                    print("[{}] 变动已消失或无需提交。".format(datetime.now().strftime("%H:%M:%S")))
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or exc.stdout or "").strip()
                print("[{}] 自动同步失败: {}".format(datetime.now().strftime("%H:%M:%S"), detail))
            finally:
                last_dirty_at = 0.0
        elif not dirty:
            last_dirty_at = 0.0

        time.sleep(interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="监控当前仓库并自动 commit + push。")
    parser.add_argument("--repo", default=".", help="仓库根目录，默认当前目录")
    parser.add_argument("--interval", type=int, default=10, help="轮询间隔，默认 10 秒")
    parser.add_argument("--debounce", type=int, default=20, help="静默多久后提交，默认 20 秒")
    parser.add_argument("--message-prefix", default="chore: auto sync", help="提交信息前缀")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    try:
        return watch(repo, max(3, args.interval), max(5, args.debounce), args.message_prefix)
    except KeyboardInterrupt:
        print("自动同步已停止。")
        return 0
    except Exception as exc:
        print("启动失败:", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
