#!/usr/bin/env python3
"""测试AI图文生成模块"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.ai.image_generator import ImageGenerator

print("开始测试AI图文生成模块...")

# 创建图像生成器实例
try:
    generator = ImageGenerator()
    print("图像生成器实例创建成功")
except Exception as e:
    print(f"创建图像生成器实例失败: {e}")
    sys.exit(1)

# 测试数据
test_posts = [
    {
        "title": "ChatGPT最新功能介绍",
        "optimized_content": "OpenAI最近发布了ChatGPT的全新功能，包括语音对话和实时翻译能力，这些新功能将极大地提升用户的使用体验，让AI交互更加自然流畅。",
        "analysis": {"is_ai_related": True, "ai_category": "AI资讯"}
    },
    {
        "title": "如何使用Midjourney生成高质量图片",
        "optimized_content": "Midjourney是一款功能强大的AI图像生成工具，通过简单的文字描述就能创建出高质量的图片，本文将详细介绍如何使用它来生成专业级别的图像作品。",
        "analysis": {"is_ai_related": True, "ai_category": "AI工具"}
    }
]

# 测试批量处理
try:
    print("开始批量处理帖子，生成图片...")
    processed_posts = generator.batch_process(test_posts)
    print(f"处理完成，共处理了 {len(processed_posts)} 个帖子")
    
    # 显示处理结果
    for i, post in enumerate(processed_posts):
        print(f"\n帖子 {i+1}:")
        print(f"标题: {post['title']}")
        print(f"生成的图片URL: {post.get('generated_image_url', '无')}")
        print(f"保存的图片路径: {post.get('generated_image_path', '无')}")
        
except Exception as e:
    print(f"处理过程中出错: {e}")

print("\n测试完成")
