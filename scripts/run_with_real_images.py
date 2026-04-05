#!/usr/bin/env python3
"""带真实图片的完整工作流"""

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)

print("=" * 70)
print("  小红书Agent - 带真实图片的工作流")
print("=" * 70)

from ai.content_analyzer import ContentAnalyzer
from ai.content_rewriter import ContentRewriter
from ai.image_generator import ImageGenerator
from ui.draft_manager import DraftManager

# 使用真实的公开图片URL（高质量AI相关图片）
sample_posts = [
    {
        'title': '2024年最值得关注的10个AIGC工具推荐',
        'content': '人工智能生成内容(AIGC)正在改变我们的工作和生活方式。今天为大家推荐10个2024年最值得关注的AIGC工具，包括ChatGPT、Midjourney、Stable Diffusion、Claude等。这些工具可以帮助你提高工作效率，创造高质量内容。',
        'author': 'AI科技前沿',
        'likes': '12580',
        # 真实的公开图片URL
        'images': [
            'https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800',  # AI/科技相关
            'https://images.unsplash.com/photo-1684369175318-1a70b4da069e?w=800'   # 数字艺术
        ],
        'link': 'https://xiaohongshu.com/post/1'
    },
    {
        'title': 'ChatGPT使用技巧：5个方法让效率翻倍',
        'content': 'ChatGPT作为最强大的AI助手，可以帮助我们大幅提升工作效率。本文分享5个实用技巧：1. 使用提示词模板 2. 批量处理任务 3. 代码辅助编写 4. 文档总结提炼 5. 创意灵感激发。掌握这些技巧，让你的工作事半功倍！',
        'author': '效率达人',
        'likes': '8932',
        # 真实的公开图片URL
        'images': [
            'https://images.unsplash.com/photo-1686191128892-3b37add4c844?w=800',  # Chat/AI助手
            'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800'   # 效率/工作
        ],
        'link': 'https://xiaohongshu.com/post/2'
    },
    {
        'title': 'Midjourney V6新功能完全指南',
        'content': 'Midjourney V6版本带来了革命性的更新！新增功能包括：更真实的图像生成、精准的文字渲染、风格一致性控制等。本文将详细介绍如何使用这些新功能来创作专业级别的AI艺术作品。',
        'author': 'AI绘画师',
        'likes': '15670',
        # 真实的公开图片URL
        'images': [
            'https://images.unsplash.com/photo-1547036967-23d11aacaee0?w=800',  # AI艺术
            'https://images.unsplash.com/photo-1697632970320-bd2b8e2ab308?w=800'   # 创意设计
        ],
        'link': 'https://xiaohongshu.com/post/3'
    }
]

print("\n[步骤1] 初始化模块...")
analyzer = ContentAnalyzer()
rewriter = ContentRewriter()
generator = ImageGenerator()
draft_manager = DraftManager()

print("\n[步骤2] 分析内容...")
analyzed = analyzer.batch_analyze(sample_posts)
ai_posts = [p for p in analyzed if p.get('analysis', {}).get('is_ai_related', False)]
print("      -> 识别出 {} 个AI相关帖子".format(len(ai_posts)))

print("\n[步骤3] 改写内容...")
rewritten = rewriter.batch_process(ai_posts)
print("      -> 完成 {} 个帖子的改写".format(len(rewritten)))

print("\n[步骤4] 生成/下载图片 (3级降级策略)...")
print("      策略优先级: AI生成 > 本地占位图 > 原帖图片下载")
final = generator.batch_process(rewritten)
print("      -> 处理完成")

print("\n[步骤5] 保存草稿...")
draft_ids = draft_manager.batch_save_drafts(final)
print("      -> 保存 {} 个草稿".format(len(draft_ids)))

# 显示结果
print("\n" + "=" * 70)
print("生成的草稿详情:")
print("=" * 70)

for i, did in enumerate(draft_ids):
    d = draft_manager.get_draft(did)
    if d:
        p = d.get('post', {})
        
        print("\n[{}] {}".format(i+1, p.get('title', '')))
        print("    ID: {}".format(did[:12]))
        print("    图片模式: {}".format(p.get('image_mode', 'unknown')))
        
        img_path = p.get('generated_image_path', '')
        if img_path:
            exists = os.path.exists(img_path)
            size_kb = os.path.getsize(img_path) / 1024 if exists else 0
            print("    图片: {} ({:.1f} KB) [{}]".format(
                os.path.basename(img_path), 
                size_kb,
                "OK" if exists else "NOT FOUND"
            ))
        else:
            print("    图片: [无]")

# 统计
print("\n" + "=" * 70)
print("统计信息:")
print("=" * 70)

modes = {}
for did in draft_ids:
    d = draft_manager.get_draft(did)
    if d:
        mode = d.get('post', {}).get('image_mode', 'unknown')
        modes[mode] = modes.get(mode, 0) + 1

for mode, count in modes.items():
    mode_names = {
        'ai': 'AI生成 (DALL-E)',
        'local': '本地占位图',
        'original': '原帖图片下载',
        'failed': '失败'
    }
    print("  {}: {} 个草稿".format(mode_names.get(mode, mode), count))

print("\n" + "=" * 70)
print("完成! 草稿已保存到 data/drafts/")
print("图片已保存到 data/images/")
print("=" * 70)
