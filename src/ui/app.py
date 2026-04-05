#!/usr/bin/env python3
"""用户界面模块"""

import os
import sys
import streamlit as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ui.draft_manager import DraftManager
from src.crawler.xiaohongshu_crawler import XiaohongshuCrawler
from src.ai.content_analyzer import ContentAnalyzer
from src.ai.content_rewriter import ContentRewriter
from src.ai.image_generator import ImageGenerator

# 添加项目根目录到Python路径


def run_ui():
    """运行用户界面"""
    st.title("自动化小红书Agent")
    st.write("根据关键词搜索高赞帖子，自动识别AI相关内容，生成原创内容和图片")
    
    # 初始化各个模块
    draft_manager = DraftManager()
    crawler = XiaohongshuCrawler()
    analyzer = ContentAnalyzer()
    rewriter = ContentRewriter()
    generator = ImageGenerator()
    
    # 侧边栏导航
    menu = st.sidebar.selectbox(
        "功能选择",
        ["首页", "搜索帖子", "草稿管理", "关于"]
    )
    
    if menu == "首页":
        st.header("欢迎使用自动化小红书Agent")
        st.write("这个工具可以帮助你：")
        st.write("1. 根据关键词搜索小红书高赞帖子")
        st.write("2. 自动识别AI相关内容")
        st.write("3. AI总结和改写内容，确保原创性")
        st.write("4. 根据内容生成相关图片")
        st.write("5. 管理和发布草稿")
        
        st.write("\n使用流程：")
        st.write("1. 进入 '搜索帖子' 页面，输入关键词搜索相关帖子")
        st.write("2. 系统会自动分析帖子，筛选AI相关内容")
        st.write("3. AI会对内容进行总结和改写，生成原创内容")
        st.write("4. 根据改写后的内容生成相关图片")
        st.write("5. 进入 '草稿管理' 页面，查看和管理生成的草稿")
        st.write("6. 选择要发布的草稿，系统会帮你自动发布到小红书")
    
    elif menu == "搜索帖子":
        st.header("搜索小红书帖子")
        
        # 搜索参数
        keyword = st.text_input("搜索关键词", "AI工具")
        max_posts = st.slider("最大帖子数", 5, 50, 10)
        
        if st.button("开始搜索"):
            with st.spinner("正在搜索帖子..."):
                # 搜索帖子
                posts = crawler.search_posts(keyword, max_posts=max_posts)
                st.success(f"搜索完成，找到 {len(posts)} 个帖子")
                
                if posts:
                    # 分析帖子
                    with st.spinner("正在分析帖子..."):
                        analyzed_posts = analyzer.batch_analyze(posts)
                        ai_related_posts = [p for p in analyzed_posts if p.get('analysis', {}).get('is_ai_related', False)]
                        st.success(f"分析完成，找到 {len(ai_related_posts)} 个AI相关帖子")
                        
                        if ai_related_posts:
                            # 处理帖子
                            with st.spinner("正在处理帖子..."):
                                # 改写内容
                                rewritten_posts = rewriter.batch_process(ai_related_posts)
                                # 生成图片
                                final_posts = generator.batch_process(rewritten_posts)
                                
                                # 保存草稿
                                draft_ids = draft_manager.batch_save_drafts(final_posts)
                                st.success(f"处理完成，已保存 {len(draft_ids)} 个草稿")
                                
                                # 显示处理结果
                                st.subheader("处理结果")
                                for i, post in enumerate(final_posts):
                                    with st.expander(f"帖子 {i+1}: {post.get('title', '无标题')}"):
                                        st.write(f"**原始内容:** {post.get('content', '无')}")
                                        st.write(f"**总结:** {post.get('summary', '无')}")
                                        st.write(f"**改写后内容:** {post.get('rewritten_content', '无')}")
                                        st.write(f"**优化后内容:** {post.get('optimized_content', '无')}")
                                        if post.get('generated_image_url'):
                                            st.image(post['generated_image_url'], caption="生成的图片")
    
    elif menu == "草稿管理":
        st.header("草稿管理")
        
        # 草稿状态筛选
        status_filter = st.selectbox("状态筛选", ["全部", "草稿", "已发布", "已丢弃"])
        status_map = {
            "全部": None,
            "草稿": "draft",
            "已发布": "published",
            "已丢弃": "discarded"
        }
        
        # 列出草稿
        drafts = draft_manager.list_drafts(status=status_map[status_filter])
        st.write(f"共找到 {len(drafts)} 个草稿")
        
        for draft in drafts:
            with st.expander(f"{draft['post'].get('title', '无标题')} (创建时间: {draft['created_at'][:10]})"):
                st.write(f"**状态:** {draft['status']}")
                st.write(f"**原始内容:** {draft['post'].get('content', '无')}")
                st.write(f"**总结:** {draft['post'].get('summary', '无')}")
                st.write(f"**优化后内容:** {draft['post'].get('optimized_content', '无')}")
                
                if draft['post'].get('generated_image_url'):
                    st.image(draft['post']['generated_image_url'], caption="生成的图片")
                
                # 操作按钮
                col1, col2, col3 = st.columns(3)
                
                if draft['status'] == "draft":
                    with col1:
                        if st.button("发布", key=f"publish_{draft['id']}"):
                            draft_manager.update_draft_status(draft['id'], "published")
                            st.success("草稿已标记为已发布")
                            st.experimental_rerun()
                    
                    with col2:
                        if st.button("丢弃", key=f"discard_{draft['id']}"):
                            draft_manager.update_draft_status(draft['id'], "discarded")
                            st.success("草稿已标记为已丢弃")
                            st.experimental_rerun()
                
                with col3:
                    if st.button("删除", key=f"delete_{draft['id']}"):
                        draft_manager.delete_draft(draft['id'])
                        st.success("草稿已删除")
                        st.experimental_rerun()
    
    elif menu == "关于":
        st.header("关于自动化小红书Agent")
        st.write("这是一个自动化小红书内容创作工具，使用AI技术帮助你快速生成高质量的AI相关内容。")
        st.write("\n功能特点：")
        st.write("- 自动搜索小红书高赞帖子")
        st.write("- AI识别和分类AI相关内容")
        st.write("- AI总结和改写内容，确保原创性")
        st.write("- 根据内容生成相关图片")
        st.write("- 草稿管理和发布功能")
        st.write("\n技术栈：")
        st.write("- Python")
        st.write("- Selenium (网页爬虫)")
        st.write("- OpenAI API (内容分析和生成)")
        st.write("- Streamlit (用户界面)")


if __name__ == "__main__":
    run_ui()
