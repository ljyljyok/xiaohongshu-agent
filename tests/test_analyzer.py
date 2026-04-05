#!/usr/bin/env python3
"""测试AI内容分析器"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.ai.content_analyzer import ContentAnalyzer

print("开始测试AI内容分析器...")

# 创建内容分析器实例
try:
    analyzer = ContentAnalyzer()
    print("内容分析器实例创建成功")
except Exception as e:
    print(f"创建内容分析器实例失败: {e}")
    sys.exit(1)

# 测试数据
test_posts = [
    {
        "title": "ChatGPT最新功能介绍",
        "content": "OpenAI发布了ChatGPT的新功能，包括语音对话和实时翻译，这些功能将大大提升用户体验。",
        "likes": "1.2万",
        "author": "AI科技爱好者",
        "images": [],
        "link": "https://example.com/post1"
    },
    {
        "title": "如何使用Midjourney生成高质量图片",
        "content": "Midjourney是一款强大的AI图像生成工具，本文将介绍如何使用它生成高质量的图片。",
        "likes": "8千",
        "author": "设计达人",
        "images": [],
        "link": "https://example.com/post2"
    },
    {
        "title": "夏季旅游攻略",
        "content": "夏季是旅游的好时节，本文为大家推荐几个适合夏季旅游的好去处。",
        "likes": "5千",
        "author": "旅游博主",
        "images": [],
        "link": "https://example.com/post3"
    }
]

# 测试批量分析
try:
    print("开始批量分析帖子...")
    results = analyzer.batch_analyze(test_posts)
    print(f"分析完成，共分析了 {len(results)} 个帖子")
    
    # 显示分析结果
    for i, post in enumerate(results):
        print(f"\n帖子 {i+1}:")
        print(f"标题: {post['title']}")
        print(f"是否AI相关: {post['analysis']['is_ai_related']}")
        print(f"AI类别: {post['analysis']['ai_category']}")
        print(f"置信度: {post['analysis']['confidence']}")
        print(f"关键词: {post['analysis']['keywords']}")
        
except Exception as e:
    print(f"分析过程中出错: {e}")

print("\n测试完成")
