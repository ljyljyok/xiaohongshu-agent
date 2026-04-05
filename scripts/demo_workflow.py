#!/usr/bin/env python3
"""演示工作流 - 使用模拟数据"""

import sys
import os

# 添加src目录到Python路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)

print("=" * 60)
print("自动化小红书Agent - AIGC搜索演示")
print("=" * 60)

# 导入模块
print("\n[1/5] 导入模块...")
from config.config import DATA_DIR, DRAFT_DIR
from ai.content_analyzer import ContentAnalyzer
from ai.content_rewriter import ContentRewriter
from ai.image_generator import ImageGenerator
from ui.draft_manager import DraftManager
print("[OK] 所有模块导入成功")

# 模拟数据 - AIGC相关内容
mock_posts = [
    {
        'title': '2024年最值得关注的10个AIGC工具',
        'content': '人工智能生成内容(AIGC)正在改变我们的工作和生活方式。今天为大家推荐10个2024年最值得关注的AIGC工具...',
        'author': 'AI科技前沿',
        'likes': '12580',
        'images': ['https://example.com/img1.jpg'],
        'link': 'https://xiaohongshu.com/post/1'
    },
    {
        'title': '用ChatGPT提升工作效率的5个技巧',
        'content': 'ChatGPT作为最强大的AI助手，可以帮助我们大幅提升工作效率。今天分享5个实用技巧...',
        'author': '效率达人',
        'likes': '8932',
        'images': ['https://example.com/img2.jpg'],
        'link': 'https://xiaohongshu.com/post/2'
    },
    {
        'title': 'Midjourney V6新功能详解',
        'content': 'Midjourney V6版本带来了许多令人兴奋的新功能，包括更真实的图像生成、更好的文字理解能力...',
        'author': 'AI绘画师',
        'likes': '15670',
        'images': ['https://example.com/img3.jpg'],
        'link': 'https://xiaohongshu.com/post/3'
    }
]

print("\n" + "=" * 60)
print("工作流参数")
print("=" * 60)
print("搜索关键词: AIGC")
print("模拟帖子数: {}".format(len(mock_posts)))
print("数据目录: {}".format(DATA_DIR))
print("草稿目录: {}".format(DRAFT_DIR))

# 初始化模块
print("\n" + "=" * 60)
print("初始化模块")
print("=" * 60)

analyzer = ContentAnalyzer()
print("[OK] 分析模块初始化完成")

rewriter = ContentRewriter()
print("[OK] 改写模块初始化完成")

generator = ImageGenerator()
print("[OK] 图片生成模块初始化完成")

draft_manager = DraftManager()
print("[OK] 草稿管理模块初始化完成")

# 第1步：显示模拟帖子
print("\n" + "=" * 60)
print("第1步：获取帖子")
print("=" * 60)

posts = mock_posts
print("[OK] 获取到 {} 个帖子".format(len(posts)))

print("\n帖子列表:")
for i, post in enumerate(posts):
    print("\n  [{}] {}".format(i+1, post.get('title', '无标题')))
    print("      作者: {} | 点赞: {}".format(
        post.get('author', '未知'),
        post.get('likes', '0')
    ))

# 第2步：分析帖子
print("\n" + "=" * 60)
print("第2步：AI内容分析")
print("=" * 60)

print("正在分析帖子内容...")
analyzed_posts = analyzer.batch_analyze(posts)
ai_related_posts = [p for p in analyzed_posts if p.get('analysis', {}).get('is_ai_related', False)]

print("[OK] 分析完成")
print("  - 总帖子数: {}".format(len(analyzed_posts)))
print("  - AI相关帖子: {}".format(len(ai_related_posts)))

if ai_related_posts:
    print("\nAI相关帖子详情:")
    for i, post in enumerate(ai_related_posts):
        analysis = post.get('analysis', {})
        print("\n  [{}] {}".format(i+1, post.get('title', '无标题')))
        print("      AI相关: {}".format(analysis.get('is_ai_related', False)))
        print("      内容类型: {}".format(analysis.get('content_type', '未知')))
        print("      相关性评分: {}/10".format(analysis.get('relevance_score', 0)))

# 第3步：改写内容
print("\n" + "=" * 60)
print("第3步：AI内容改写")
print("=" * 60)

print("正在改写内容...")
rewritten_posts = rewriter.batch_process(ai_related_posts)
print("[OK] 改写完成，处理了 {} 个帖子".format(len(rewritten_posts)))

print("\n改写后的内容预览:")
for i, post in enumerate(rewritten_posts):
    print("\n  [{}] {}".format(i+1, post.get('title', '无标题')))
    
    # 显示总结
    summary = post.get('summary', '')
    if summary:
        clean_summary = ''.join(c for c in summary if ord(c) < 128 or c in '\u4e00-\u9fff')
        print("      Summary: {}...".format(clean_summary[:60]))
    
    # 显示改写内容
    rewritten = post.get('rewritten_content', '')
    if rewritten:
        clean_rewritten = ''.join(c for c in rewritten if ord(c) < 128 or c in '\u4e00-\u9fff')
        print("      Rewritten: {}...".format(clean_rewritten[:60]))

# 第4步：生成图片
print("\n" + "=" * 60)
print("第4步：AI图片生成")
print("=" * 60)

print("正在生成图片...")
final_posts = generator.batch_process(rewritten_posts)
print("[OK] 图片生成完成，处理了 {} 个帖子".format(len(final_posts)))

print("\n图片生成结果:")
for i, post in enumerate(final_posts):
    image_path = post.get('generated_image_path', '')
    if image_path:
        print("  [{}] 图片已生成: {}".format(i+1, image_path))
    else:
        print("  [{}] 未生成图片".format(i+1))

# 第5步：保存草稿
print("\n" + "=" * 60)
print("第5步：保存草稿")
print("=" * 60)

print("正在保存草稿...")
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
            post.get('title', '无标题')[:25]
        ))

# 显示草稿详情
print("\n" + "=" * 60)
print("草稿详情预览")
print("=" * 60)

for i, draft_id in enumerate(draft_ids[:2]):  # 只显示前2个
    draft = draft_manager.get_draft(draft_id)
    if draft:
        post = draft.get('post', {})
        print("\n草稿 {}:".format(i+1))
        print("  ID: {}".format(draft_id))
        print("  标题: {}".format(post.get('title', '无标题')))
        print("  状态: {}".format(draft.get('status', '未知')))
        
        rewritten = post.get('rewritten_content', '')
        if rewritten:
            clean_rewritten = ''.join(c for c in rewritten if ord(c) < 128 or '\u4e00' <= c <= '\u9fff')
            print("  Content: {}...".format(clean_rewritten[:80]))
        
        image_path = post.get('generated_image_path', '')
        if image_path:
            print("  图片: {}".format(image_path))

# 完成
print("\n" + "=" * 60)
print("演示工作流执行完成！")
print("=" * 60)
print("\n总结:")
print("  - 获取了 {} 个帖子".format(len(posts)))
print("  - 识别出 {} 个AI相关帖子".format(len(ai_related_posts)))
print("  - 改写了 {} 个帖子".format(len(rewritten_posts)))
print("  - 生成了 {} 个草稿".format(len(draft_ids)))
print("\n您可以使用以下命令启动Web界面来管理草稿:")
print("  streamlit run src/ui/app.py")
print("=" * 60)
