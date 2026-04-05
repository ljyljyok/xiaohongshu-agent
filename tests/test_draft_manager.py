#!/usr/bin/env python3
"""Basic smoke test for DraftManager."""

import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.ui.draft_manager import DraftManager


def main():
    print("开始测试草稿管理模块...")

    try:
        manager = DraftManager()
        print("草稿管理器实例创建成功")
    except Exception as exc:
        print("创建草稿管理器实例失败:", exc)
        return 1

    test_posts = [
        {
            "title": "ChatGPT 最新功能介绍",
            "content": "OpenAI 发布了 ChatGPT 的新功能，包括语音对话和实时翻译。",
            "analysis": {"is_ai_related": True, "ai_category": "AI资讯"},
            "summary": "OpenAI 发布 ChatGPT 新功能，包括语音对话和实时翻译。",
            "rewritten_content": "OpenAI 最近推出了 ChatGPT 的全新功能，其中包括语音对话能力和实时翻译功能。",
            "optimized_content": "OpenAI 刚刚发布了 ChatGPT 的全新功能，现在支持语音对话和实时翻译。",
            "generated_image_url": "https://example.com/image1.png",
            "generated_image_path": "/path/to/image1.png",
        },
        {
            "title": "如何使用 Midjourney 生成高质量图片",
            "content": "Midjourney 是一款强大的 AI 图像生成工具。",
            "analysis": {"is_ai_related": True, "ai_category": "AI工具"},
            "summary": "Midjourney 是一款强大的 AI 图像生成工具。",
            "rewritten_content": "Midjourney 是一款功能强大的 AI 图像生成工具，可以通过文字描述生成高质量图片。",
            "optimized_content": "Midjourney 很适合快速生成高质量 AI 图片，输入文字描述即可上手。",
            "generated_image_url": "https://example.com/image2.png",
            "generated_image_path": "/path/to/image2.png",
        },
    ]

    draft_ids = []
    try:
        print("开始批量保存草稿...")
        draft_ids = manager.batch_save_drafts(test_posts)
        print("批量保存成功，生成了 {} 个草稿".format(len(draft_ids)))
        print("草稿 ID 列表:", draft_ids)
    except Exception as exc:
        print("批量保存草稿时报错:", exc)

    try:
        print("\n列出所有草稿...")
        drafts = manager.list_drafts()
        print("共找到 {} 个草稿".format(len(drafts)))
        for index, draft in enumerate(drafts[:5], 1):
            print("\n草稿 {}:".format(index))
            print("ID:", draft.get("id"))
            print("标题:", ((draft.get("post") or {}).get("title") or ""))
            print("状态:", draft.get("status"))
            print("创建时间:", draft.get("created_at"))
    except Exception as exc:
        print("列出草稿时报错:", exc)

    if draft_ids:
        try:
            print("\n更新第一个草稿状态为已发布...")
            success = manager.update_draft_status(draft_ids[0], "published")
            print("更新状态:", "成功" if success else "失败")
            published_drafts = manager.list_drafts(status="published")
            print("已发布草稿数量:", len(published_drafts))
        except Exception as exc:
            print("更新草稿状态时报错:", exc)

        try:
            print("\n删除第一个草稿...")
            success = manager.delete_draft(draft_ids[0])
            print("删除草稿:", "成功" if success else "失败")
            drafts = manager.list_drafts()
            print("删除后剩余草稿数量:", len(drafts))
        except Exception as exc:
            print("删除草稿时报错:", exc)

    print("\n测试完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
