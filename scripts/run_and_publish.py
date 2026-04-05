#!/usr/bin/env python3
"""小红书Agent - 完整运行与发布助手"""

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)

print("=" * 70)
print("  小红书自动化Agent - 智能内容创作系统")
print("=" * 70)

from config.config import DATA_DIR, DRAFT_DIR
from ai.content_analyzer import ContentAnalyzer
from ai.content_rewriter import ContentRewriter
from ai.image_generator import ImageGenerator
from ui.draft_manager import DraftManager

# AIGC相关示例内容
sample_posts = [
    {
        'title': '2024年最值得关注的10个AIGC工具推荐',
        'content': '人工智能生成内容(AIGC)正在改变我们的工作和生活方式。今天为大家推荐10个2024年最值得关注的AIGC工具，包括ChatGPT、Midjourney、Stable Diffusion、Claude等。这些工具可以帮助你提高工作效率，创造高质量内容。',
        'author': 'AI科技前沿',
        'likes': '12580'
    },
    {
        'title': 'ChatGPT使用技巧：5个方法让效率翻倍',
        'content': 'ChatGPT作为最强大的AI助手，可以帮助我们大幅提升工作效率。本文分享5个实用技巧：1. 使用提示词模板 2. 批量处理任务 3. 代码辅助编写 4. 文档总结提炼 5. 创意灵感激发。掌握这些技巧，让你的工作事半功倍！',
        'author': '效率达人',
        'likes': '8932'
    },
    {
        'title': 'Midjourney V6新功能完全指南',
        'content': 'Midjourney V6版本带来了革命性的更新！新增功能包括：更真实的图像生成、精准的文字渲染、风格一致性控制等。本文将详细介绍如何使用这些新功能来创作专业级别的AI艺术作品。',
        'author': 'AI绘画师',
        'likes': '15670'
    }
]

print("\n[步骤1] 初始化AI引擎...")
analyzer = ContentAnalyzer()
rewriter = ContentRewriter()
generator = ImageGenerator()
draft_manager = DraftManager()
print("[OK] AI引擎就绪（本地模式）")

print("\n[步骤2] 处理{}个AIGC相关帖子...".format(len(sample_posts)))

# 分析
analyzed = analyzer.batch_analyze(sample_posts)
ai_posts = [p for p in analyzed if p.get('analysis', {}).get('is_ai_related', False)]
print("      -> 识别出 {} 个AI相关帖子".format(len(ai_posts)))

# 改写
rewritten = rewriter.batch_process(ai_posts)
print("      -> 完成 {} 个帖子的改写".format(len(rewritten)))

# 生成图片
final = generator.batch_process(rewritten)
print("      -> 生成 {} 张配图".format(len(final)))

# 保存草稿
draft_ids = draft_manager.batch_save_drafts(final)
print("      -> 保存 {} 个草稿".format(len(draft_ids)))

print("\n" + "=" * 70)
print("[步骤3] 草稿预览")
print("=" * 70)

for i, did in enumerate(draft_ids):
    d = draft_manager.get_draft(did)
    if d:
        p = d.get('post', {})
        print("\n[草稿{}] {}".format(i+1, p.get('title', '')))
        
        content = p.get('publish_content') or p.get('optimized_content') or p.get('rewritten_content', '')
        if content:
            clean = ''.join(c for c in content[:100] if ord(c) < 128 or '\u4e00' <= c <= '\u9fff')
            print("  内容: {}...".format(clean))
        
        img = p.get('generated_image_path', '')
        if img:
            print("  图片: {}".format(os.path.basename(img)))
        
        print("  ID: {}".format(did[:12]))
        print("  状态: {}".format(d.get('status', 'draft')))

print("\n" + "=" * 70)
print("[步骤4] 发布选项")
print("=" * 70)

print("""
发布方式选择:

1. 自动发布 (需要浏览器登录小红书)
   运行命令: python auto_publish.py
   
   注意:
   - 系统会自动打开浏览器
   - 需要你手动登录小红书账号
   - 登录后系统会自动填充内容和图片
   - 你只需确认发布即可

2. Web界面管理 (推荐)
   运行命令: streamlit run src/ui/app.py
   
   功能:
   - 可视化管理所有草稿
   - 预览内容和图片
   - 选择性发布
   - 编辑修改内容

3. 手动发布
   草稿位置: data/drafts/
   图片位置: data/images/
   
   步骤:
   a) 打开草稿JSON文件查看内容
   b) 复制改写后的文案
   c) 打开小红书网页版或APP
   d) 手动创建笔记并粘贴内容
   e) 上传生成的配图
   f) 发布
""")

print("=" * 70)
print("执行完成!")
print("=" * 70)
print("\n统计信息:")
print("  - 处理帖子: {} 个".format(len(sample_posts)))
print("  - 生成草稿: {} 个".format(len(draft_ids)))
print("  - 草稿目录: {}".format(DRAFT_DIR))
print("  - 图片目录: {}".format(os.path.join(DATA_DIR, 'images')))
print("\n下一步操作:")
print("  1. 查看 data/drafts/ 目录中的草稿文件")
print("  2. 查看 data/images/ 目录中的配图")
print("  3. 选择上述任一方式进行发布")
print("=" * 70)
