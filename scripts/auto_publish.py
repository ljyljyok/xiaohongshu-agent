#!/usr/bin/env python3
"""自动化小红书Agent - 完整运行与自动发布"""

import sys
import os

# 添加src目录到Python路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)

print("=" * 70)
print("  小红书自动化Agent - 完整工作流 + 自动发布")
print("=" * 70)

# 导入模块
from config.config import DATA_DIR, DRAFT_DIR
from ai.content_analyzer import ContentAnalyzer
from ai.content_rewriter import ContentRewriter
from ai.image_generator import ImageGenerator
from ui.draft_manager import DraftManager
from publisher.xiaohongshu_publisher import XiaohongshuPublisher

# 模拟数据 - AIGC相关内容（用于演示）
mock_posts = [
    {
        'title': '2024年最值得关注的10个AIGC工具',
        'content': '人工智能生成内容(AIGC)正在改变我们的工作和生活方式。今天为大家推荐10个2024年最值得关注的AIGC工具，包括ChatGPT、Midjourney、Stable Diffusion等。这些工具可以帮助你提高工作效率，创造高质量内容。',
        'author': 'AI科技前沿',
        'likes': '12580',
        'images': [],
        'link': 'https://xiaohongshu.com/post/1'
    },
    {
        'title': '用ChatGPT提升工作效率的5个技巧',
        'content': 'ChatGPT作为最强大的AI助手，可以帮助我们大幅提升工作效率。本文分享5个实用技巧：1. 使用提示词模板 2. 批量处理任务 3. 代码辅助编写 4. 文档总结提炼 5. 创意灵感激发。掌握这些技巧，让你的工作效率翻倍！',
        'author': '效率达人',
        'likes': '8932',
        'images': [],
        'link': 'https://xiaohongshu.com/post/2'
    }
]

print("\n[阶段1] 初始化系统...")
analyzer = ContentAnalyzer()
rewriter = ContentRewriter()
generator = ImageGenerator()
draft_manager = DraftManager()
publisher = XiaohongshuPublisher()

print("[OK] 所有模块初始化完成")

# 阶段2：处理内容并生成草稿
print("\n" + "=" * 70)
print("[阶段2] AI内容处理")
print("=" * 70)

posts = mock_posts
print("\n[2.1] 分析内容...")
analyzed_posts = analyzer.batch_analyze(posts)
ai_related_posts = [p for p in analyzed_posts if p.get('analysis', {}).get('is_ai_related', False)]
print("      -> 识别出 {} 个AI相关帖子".format(len(ai_related_posts)))

print("\n[2.2] 改写内容...")
rewritten_posts = rewriter.batch_process(ai_related_posts)
print("      -> 完成 {} 个帖子的改写".format(len(rewritten_posts)))

print("\n[2.3] 生成图片...")
final_posts = generator.batch_process(rewritten_posts)
print("      -> 生成 {} 张配图".format(len(final_posts)))

print("\n[2.4] 保存草稿...")
draft_ids = draft_manager.batch_save_drafts(final_posts)
print("      -> 保存 {} 个草稿到 {}".format(len(draft_ids), DRAFT_DIR))

# 显示草稿信息
print("\n生成的草稿列表:")
for i, draft_id in enumerate(draft_ids):
    draft = draft_manager.get_draft(draft_id)
    if draft:
        post = draft.get('post', {})
        print("\n  [草稿{}] ID: {}".format(i+1, draft_id[:12]))
        print("         标题: {}".format(post.get('title', '')))
        
        # 清理emoji显示
        content = post.get('publish_content') or post.get('optimized_content') or post.get('rewritten_content', '')
        if content:
            clean_content = ''.join(c for c in content[:80] if ord(c) < 128 or '\u4e00' <= c <= '\u9fff')
            print("         内容: {}...".format(clean_content))
        
        image_path = post.get('generated_image_path', '')
        if image_path:
            print("         图片: {}".format(os.path.basename(image_path)))

# 阶段3：自动发布
print("\n" + "=" * 70)
print("[阶段3] 自动发布到小红书")
print("=" * 70)

print("\n准备发布草稿...")
print("注意: 系统将打开浏览器，请确保你已经登录小红书账号")

# 选择要发布的草稿（选择前2个）
drafts_to_publish = []
for i, draft_id in enumerate(draft_ids[:2]):
    draft = draft_manager.get_draft(draft_id)
    if draft:
        drafts_to_publish.append(draft)
        print("\n  [待发布{}] {}".format(i+1, draft.get('post', {}).get('title', '')))

if not drafts_to_publish:
    print("\n[ERROR] 没有可发布的草稿")
    sys.exit(1)

print("\n开始自动发布流程...")

try:
    # 登录小红书
    print("\n[3.1] 启动浏览器并访问小红书...")
    
    # 使用发布器进行批量发布
    publish_results = publisher.batch_publish(drafts_to_publish)
    
    # 检查发布结果
    print("\n" + "=" * 70)
    print("发布结果:")
    print("=" * 70)
    
    success_count = 0
    for i, (draft, result) in enumerate(zip(drafts_to_publish, publish_results)):
        title = draft.get('post', {}).get('title', '未知')
        status = "成功" if result else "失败"
        
        if result:
            success_count += 1
            
            # 更新草稿状态为已发布
            draft_id = draft.get('id', '')
            if draft_id:
                draft_manager.update_draft_status(draft_id, 'published')
            
            print("\n  [{}] {} - 发布{}".format(i+1, title, status))
        else:
            print("\n  [{}] {} - 发布{} (可能需要手动完成)".format(i+1, title, status))
    
    # 总结
    print("\n" + "=" * 70)
    print("执行总结:")
    print("=" * 70)
    print("  - 处理帖子数: {}".format(len(posts)))
    print("  - 生成草稿数: {}".format(len(draft_ids)))
    print("  - 发布成功数: {}/{}".format(success_count, len(drafts_to_publish)))
    print("  - 草稿保存位置: {}".format(DRAFT_DIR))
    print("  - 图片保存位置: {}".format(os.path.join(DATA_DIR, 'images')))
    
    print("\n" + "=" * 70)
    print("自动化流程执行完成！")
    print("=" * 70)
    
except Exception as e:
    print("\n[ERROR] 发布过程中出错: {}".format(str(e)))
    print("\n可能的原因:")
    print("  1. 浏览器未正确启动")
    print("  2. 网络连接问题")
    print("  3. 小红书页面结构变化")
    print("  4. 未登录小红书账号")
    print("\n建议: 手动登录小红书后重试，或使用Web界面管理草稿")
    import traceback
    traceback.print_exc()

print("\n提示: 你也可以使用以下命令启动Web界面来管理和发布草稿:")
print("  streamlit run src/ui/app.py")
print("=" * 70)
