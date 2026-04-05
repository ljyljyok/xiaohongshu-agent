#!/usr/bin/env python3
"""简单测试脚本"""

import sys
import os

# 添加src目录到Python路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)

print("开始测试...")
print(f"Python版本: {sys.version}")
print(f"当前目录: {os.getcwd()}")

# 测试导入
try:
    from config.config import DATA_DIR, DRAFT_DIR
    print(f"OK 配置导入成功")
    print(f"数据目录: {DATA_DIR}")
    print(f"草稿目录: {DRAFT_DIR}")
except Exception as e:
    print(f"NO 配置导入失败: {e}")

try:
    from crawler.xiaohongshu_crawler import XiaohongshuCrawler
    print("OK 爬虫模块导入成功")
except Exception as e:
    print(f"NO 爬虫模块导入失败: {e}")

try:
    from ai.content_analyzer import ContentAnalyzer
    print("OK 分析模块导入成功")
except Exception as e:
    print(f"NO 分析模块导入失败: {e}")

try:
    from ai.content_rewriter import ContentRewriter
    print("OK 改写模块导入成功")
except Exception as e:
    print(f"NO 改写模块导入失败: {e}")

try:
    from ai.image_generator import ImageGenerator
    print("OK 图片生成模块导入成功")
except Exception as e:
    print(f"NO 图片生成模块导入失败: {e}")

try:
    from ui.draft_manager import DraftManager
    print("OK 草稿管理模块导入成功")
except Exception as e:
    print(f"NO 草稿管理模块导入失败: {e}")

print("\n测试完成")
