#!/usr/bin/env python3
"""自动化小红书Agent主入口"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)

from config.config import DATA_DIR, DRAFT_DIR

from crawler.xiaohongshu_crawler import XiaohongshuCrawler
from ai.content_analyzer import ContentAnalyzer
from ai.content_rewriter import ContentRewriter
from ai.image_generator import ImageGenerator
from ui.draft_manager import DraftManager
from publisher.xiaohongshu_publisher import XiaohongshuPublisher


def main():
    """主函数"""
    print("自动化小红书Agent启动中...")
    
    # 检查目录结构
    print(f"数据存储目录: {DATA_DIR}")
    print(f"草稿存储目录: {DRAFT_DIR}")
    
    # 启动用户界面
    print("启动用户界面...")
    from ui.app import run_ui
    run_ui()


def run_workflow(keyword, max_posts=10):
    """
    运行完整工作流
    
    Args:
        keyword: 搜索关键词
        max_posts: 最大帖子数
    """
    print(f"开始运行工作流，搜索关键词: {keyword}")
    
    # 初始化各个模块
    crawler = XiaohongshuCrawler()
    analyzer = ContentAnalyzer()
    rewriter = ContentRewriter()
    generator = ImageGenerator()
    draft_manager = DraftManager()
    
    # 1. 搜索帖子
    print("1. 正在搜索帖子...")
    posts = crawler.search_posts(keyword, max_posts=max_posts)
    print(f"搜索完成，找到 {len(posts)} 个帖子")
    
    # 2. 分析帖子
    print("2. 正在分析帖子...")
    analyzed_posts = analyzer.batch_analyze(posts)
    ai_related_posts = [p for p in analyzed_posts if p.get('analysis', {}).get('is_ai_related', False)]
    print(f"分析完成，找到 {len(ai_related_posts)} 个AI相关帖子")
    
    # 3. 处理帖子
    if ai_related_posts:
        print("3. 正在处理帖子...")
        # 改写内容
        rewritten_posts = rewriter.batch_process(ai_related_posts)
        # 生成图片
        final_posts = generator.batch_process(rewritten_posts)
        
        # 4. 保存草稿
        print("4. 正在保存草稿...")
        draft_ids = draft_manager.batch_save_drafts(final_posts)
        print(f"处理完成，已保存 {len(draft_ids)} 个草稿")
    
    print("工作流运行完成")


if __name__ == "__main__":
    main()

