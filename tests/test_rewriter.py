#!/usr/bin/env python3
"""测试AI内容总结与改写模块"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.ai.content_rewriter import ContentRewriter

print("开始测试AI内容总结与改写模块...")

# 创建内容改写器实例
try:
    rewriter = ContentRewriter()
    print("内容改写器实例创建成功")
except Exception as e:
    print(f"创建内容改写器实例失败: {e}")
    sys.exit(1)

# 测试数据
test_posts = [
    {
        "title": "ChatGPT最新功能介绍",
        "content": "OpenAI发布了ChatGPT的新功能，包括语音对话和实时翻译，这些功能将大大提升用户体验。",
        "analysis": {"is_ai_related": True, "ai_category": "AI资讯"}
    },
    {
        "title": "如何使用Midjourney生成高质量图片",
        "content": "Midjourney是一款强大的AI图像生成工具，本文将介绍如何使用它生成高质量的图片。",
        "analysis": {"is_ai_related": True, "ai_category": "AI工具"}
    }
]

# 测试批量处理
try:
    print("开始批量处理帖子...")
    processed_posts = rewriter.batch_process(test_posts)
    print(f"处理完成，共处理了 {len(processed_posts)} 个帖子")
    
    # 显示处理结果
    for i, post in enumerate(processed_posts):
        print(f"\n帖子 {i+1}:")
        print(f"原始标题: {post['title']}")
        print(f"原始内容: {post['content']}")
        print(f"总结: {post.get('summary', '无')}")
        print(f"改写后内容: {post.get('rewritten_content', '无')}")
        print(f"优化后内容: {post.get('optimized_content', '无')}")
        
except Exception as e:
    print(f"处理过程中出错: {e}")

print("\n测试完成")
