#!/usr/bin/env python3
"""运行AIGC搜索工作流"""

import os
import sys

# 添加src目录到Python路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)

from crawler.xiaohongshu_crawler import XiaohongshuCrawler
from ai.content_analyzer import ContentAnalyzer
from ai.content_rewriter import ContentRewriter
from ai.image_generator import ImageGenerator
from ui.draft_manager import DraftManager


def run_workflow(keyword, max_posts=5):
    """
    运行完整工作流
    
    Args:
        keyword: 搜索关键词
        max_posts: 最大帖子数
    """
    print(f"开始运行工作流，搜索关键词: {keyword}")
    print("=" * 50)
    
    # 初始化各个模块
    crawler = XiaohongshuCrawler()
    analyzer = ContentAnalyzer()
    rewriter = ContentRewriter()
    generator = ImageGenerator()
    draft_manager = DraftManager()
    
    # 1. 搜索帖子
    print("\n1. 正在搜索帖子...")
    posts = crawler.search_posts(keyword, max_posts=max_posts)
    print(f"搜索完成，找到 {len(posts)} 个帖子")
    
    if not posts:
        print("未获取到帖子，可能是因为小红书的反爬机制")
        return
    
    # 2. 分析帖子
    print("\n2. 正在分析帖子...")
    analyzed_posts = analyzer.batch_analyze(posts)
    ai_related_posts = [p for p in analyzed_posts if p.get('analysis', {}).get('is_ai_related', False)]
    print(f"分析完成，找到 {len(ai_related_posts)} 个AI相关帖子")
    
    # 3. 处理帖子
    if ai_related_posts:
        print("\n3. 正在处理帖子...")
        # 改写内容
        rewritten_posts = rewriter.batch_process(ai_related_posts)
        # 生成图片
        final_posts = generator.batch_process(rewritten_posts)
        
        # 4. 保存草稿
        print("\n4. 正在保存草稿...")
        draft_ids = draft_manager.batch_save_drafts(final_posts)
        print(f"处理完成，已保存 {len(draft_ids)} 个草稿")
        
        # 显示生成的草稿
        print("\n" + "=" * 50)
        print("生成的草稿预览:")
        for draft_id in draft_ids[:3]:  # 只显示前3个
            draft = draft_manager.get_draft(draft_id)
            if draft:
                post = draft.get('post', {})
                print(f"\n草稿ID: {draft_id}")
                print(f"标题: {post.get('title', '无标题')}")
                print(f"改写内容: {post.get('rewritten_content', '无内容')[:100]}...")
    else:
        print("未找到AI相关帖子")
    
    print("\n" + "=" * 50)
    print("工作流运行完成")


if __name__ == "__main__":
    run_workflow('AIGC', max_posts=5)
