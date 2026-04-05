#!/usr/bin/env python3
"""调试运行脚本"""

import sys
import os

# 添加src目录到Python路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)

print("=" * 60)
print("开始AIGC搜索工作流")
print("=" * 60)

try:
    print("\n[1/5] 导入配置模块...")
    from config.config import DATA_DIR, DRAFT_DIR
    print("[OK] 配置导入成功")
    print("  数据目录: {}".format(DATA_DIR))
    print("  草稿目录: {}".format(DRAFT_DIR))
except Exception as e:
    print("[ERROR] 配置导入失败: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[2/5] 导入爬虫模块...")
    from crawler.xiaohongshu_crawler import XiaohongshuCrawler
    print("[OK] 爬虫模块导入成功")
except Exception as e:
    print("[ERROR] 爬虫模块导入失败: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[3/5] 导入AI模块...")
    from ai.content_analyzer import ContentAnalyzer
    from ai.content_rewriter import ContentRewriter
    from ai.image_generator import ImageGenerator
    print("[OK] AI模块导入成功")
except Exception as e:
    print("[ERROR] AI模块导入失败: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[4/5] 导入草稿管理模块...")
    from ui.draft_manager import DraftManager
    print("[OK] 草稿管理模块导入成功")
except Exception as e:
    print("[ERROR] 草稿管理模块导入失败: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("开始执行工作流")
print("=" * 60)

keyword = "AIGC"
max_posts = 3

print("\n搜索关键词: {}".format(keyword))
print("最大帖子数: {}".format(max_posts))

# 初始化各个模块
print("\n[1/6] 初始化爬虫...")
try:
    crawler = XiaohongshuCrawler()
    print("[OK] 爬虫初始化成功")
except Exception as e:
    print("[ERROR] 爬虫初始化失败: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[2/6] 初始化分析器...")
try:
    analyzer = ContentAnalyzer()
    print("[OK] 分析器初始化成功")
except Exception as e:
    print("[ERROR] 分析器初始化失败: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[3/6] 初始化改写器...")
try:
    rewriter = ContentRewriter()
    print("[OK] 改写器初始化成功")
except Exception as e:
    print("[ERROR] 改写器初始化失败: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[4/6] 初始化图片生成器...")
try:
    generator = ImageGenerator()
    print("[OK] 图片生成器初始化成功")
except Exception as e:
    print("[ERROR] 图片生成器初始化失败: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[5/6] 初始化草稿管理器...")
try:
    draft_manager = DraftManager()
    print("[OK] 草稿管理器初始化成功")
except Exception as e:
    print("[ERROR] 草稿管理器初始化失败: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 1. 搜索帖子
print("\n" + "=" * 60)
print("[6/6] 开始搜索帖子...")
print("=" * 60)
try:
    posts = crawler.search_posts(keyword, max_posts=max_posts)
    print("[OK] 搜索完成，找到 {} 个帖子".format(len(posts)))
    
    if posts:
        print("\n帖子预览:")
        for i, post in enumerate(posts[:3]):
            print("\n  帖子 {}:".format(i+1))
            title = post.get('title', '无标题')[:50]
            print("    标题: {}...".format(title))
            print("    点赞: {}".format(post.get('likes', '0')))
            print("    作者: {}".format(post.get('author', '未知')))
    else:
        print("[WARNING] 未获取到帖子，可能是因为小红书的反爬机制")
        print("  这是正常现象，小红书有严格的反爬机制")
except Exception as e:
    print("[ERROR] 搜索帖子失败: {}".format(e))
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("工作流执行完成")
print("=" * 60)
