#!/usr/bin/env python3
"""完整工作流运行脚本"""

import sys
import os

# 添加src目录到Python路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)

print("=" * 60)
print("自动化小红书Agent - AIGC搜索工作流")
print("=" * 60)

# 导入模块
print("\n[1/5] 导入模块...")
from config.config import DATA_DIR, DRAFT_DIR
from crawler.xiaohongshu_crawler import XiaohongshuCrawler
from ai.content_analyzer import ContentAnalyzer
from ai.content_rewriter import ContentRewriter
from ai.image_generator import ImageGenerator
from ui.draft_manager import DraftManager
print("[OK] 所有模块导入成功")

# 参数设置
keyword = "AIGC"
max_posts = 3

print("\n" + "=" * 60)
print("工作流参数")
print("=" * 60)
print("搜索关键词: {}".format(keyword))
print("最大帖子数: {}".format(max_posts))
print("数据目录: {}".format(DATA_DIR))
print("草稿目录: {}".format(DRAFT_DIR))

# 初始化模块
print("\n" + "=" * 60)
print("初始化模块")
print("=" * 60)

crawler = XiaohongshuCrawler()
print("[OK] 爬虫模块初始化完成")

analyzer = ContentAnalyzer()
print("[OK] 分析模块初始化完成")

rewriter = ContentRewriter()
print("[OK] 改写模块初始化完成")

generator = ImageGenerator()
print("[OK] 图片生成模块初始化完成")

draft_manager = DraftManager()
print("[OK] 草稿管理模块初始化完成")

# 第1步：搜索帖子
print("\n" + "=" * 60)
print("第1步：搜索帖子")
print("=" * 60)

posts = crawler.search_posts(keyword, max_posts=max_posts)
print("[OK] 搜索完成，找到 {} 个帖子".format(len(posts)))

if not posts:
    print("\n[WARNING] 未获取到帖子")
    print("可能原因：")
    print("1. 小红书有严格的反爬机制")
    print("2. 需要登录才能搜索")
    print("3. 网络连接问题")
    print("\n建议：使用浏览器手动访问小红书进行搜索")
    sys.exit(0)

# 显示搜索到的帖子
print("\n搜索到的帖子:")
for i, post in enumerate(posts):
    print("\n  [{}] {}".format(i+1, post.get('title', '无标题')[:40]))
    print("      作者: {} | 点赞: {}".format(
        post.get('author', '未知'),
        post.get('likes', '0')
    ))

# 第2步：分析帖子
print("\n" + "=" * 60)
print("第2步：AI内容分析")
print("=" * 60)

analyzed_posts = analyzer.batch_analyze(posts)
ai_related_posts = [p for p in analyzed_posts if p.get('analysis', {}).get('is_ai_related', False)]

print("[OK] 分析完成")
print("  - 总帖子数: {}".format(len(analyzed_posts)))
print("  - AI相关帖子: {}".format(len(ai_related_posts)))

if ai_related_posts:
    print("\nAI相关帖子:")
    for i, post in enumerate(ai_related_posts[:3]):
        analysis = post.get('analysis', {})
        print("\n  [{}] {}".format(i+1, post.get('title', '无标题')[:40]))
        print("      类型: {}".format(analysis.get('content_type', '未知')))
        print("      相关性: {}".format(analysis.get('relevance_score', 0)))
else:
    print("\n[WARNING] 未找到AI相关帖子")
    print("将使用所有搜索到的帖子继续处理")
    ai_related_posts = posts

# 第3步：改写内容
print("\n" + "=" * 60)
print("第3步：AI内容改写")
print("=" * 60)

rewritten_posts = rewriter.batch_process(ai_related_posts)
print("[OK] 改写完成，处理了 {} 个帖子".format(len(rewritten_posts)))

print("\n改写后的内容预览:")
for i, post in enumerate(rewritten_posts[:2]):
    print("\n  [{}] {}".format(i+1, post.get('title', '无标题')[:40]))
    rewritten = post.get('rewritten_content', '')
    if rewritten:
        print("      改写内容: {}...".format(rewritten[:80]))
    else:
        print("      改写内容: [无]")

# 第4步：生成图片
print("\n" + "=" * 60)
print("第4步：AI图片生成")
print("=" * 60)

final_posts = generator.batch_process(rewritten_posts)
print("[OK] 图片生成完成，处理了 {} 个帖子".format(len(final_posts)))

print("\n生成的图片:")
for i, post in enumerate(final_posts[:2]):
    image_path = post.get('generated_image_path', '')
    if image_path:
        print("  [{}] {}".format(i+1, image_path))
    else:
        print("  [{}] [未生成图片]".format(i+1))

# 第5步：保存草稿
print("\n" + "=" * 60)
print("第5步：保存草稿")
print("=" * 60)

draft_ids = draft_manager.batch_save_drafts(final_posts)
print("[OK] 草稿保存完成，共保存 {} 个草稿".format(len(draft_ids)))

print("\n草稿列表:")
for i, draft_id in enumerate(draft_ids):
    draft = draft_manager.get_draft(draft_id)
    if draft:
        post = draft.get('post', {})
        print("  [{}] {} - {}".format(
            i+1,
            draft_id[:8],
            post.get('title', '无标题')[:30]
        ))

# 完成
print("\n" + "=" * 60)
print("工作流执行完成！")
print("=" * 60)
print("\n总结:")
print("  - 搜索到 {} 个帖子".format(len(posts)))
print("  - 识别出 {} 个AI相关帖子".format(len(ai_related_posts)))
print("  - 改写了 {} 个帖子".format(len(rewritten_posts)))
print("  - 生成了 {} 个草稿".format(len(draft_ids)))
print("\n您可以在草稿管理页面查看和编辑这些草稿")
print("=" * 60)
