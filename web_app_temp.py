def show_settings():
    st.markdown("## ⚙️ 系统设置")
    settings = load_ai_settings()
    ollama_available, ollama_message, detected_model = check_ollama_available()

    st.markdown("### 🤖 模型路由配置")
    mode_options = ["ollama", "deepseek", "auto", "openai", "local"]
    labels = {
        "content_analyzer_mode": "📊 内容分析",
        "content_rewriter_mode": "✍️ 内容润色",
        "content_auditor_mode": "🔍 内容审核",
        "image_processing_mode": "🖼️ 图片理解",
        "video_transcription_mode": "🎬 视频转写",
    }

    updated = {}
    label_cols = st.columns(3)
    for idx, (key, label) in enumerate(labels.items()):
        with label_cols[idx % 3]:
            current = settings.get(key, DEFAULT_AI_RUNTIME_SETTINGS.get(key, "deepseek"))
            index = mode_options.index(current) if current in mode_options else 0
            updated[key] = st.selectbox(
                label,
                mode_options,
                index=index,
                format_func=format_mode_label,
                key=f"setting_{key}",
            )

    save_col1, save_col2 = st.columns([1, 4])
    with save_col1:
        if st.button(
            "💾 保存模型设置", type="primary", key="save_ai_settings_btn", use_container_width=True
        ):
            save_ai_settings(updated)
            st.success("✅ 模型设置已保存")
            settings = load_ai_settings()

    st.markdown("---")

    st.markdown("### 📡 服务状态监控")
    col1, col2, col3 = st.columns(3)
    with col1:
        ollama_status = "🟢 可用" if ollama_available else "🔴 不可用"
        st.metric("⚙️ Ollama 状态", ollama_status)
    with col2:
        st.metric("🌐 默认地址", OLLAMA_BASE_URL)
    with col3:
        st.metric("🤖 默认模型", detected_model or OLLAMA_MODEL)

    if ollama_message:
        st.caption(f"ℹ️ {ollama_message}")

    key_cols = st.columns(3)
    with key_cols[0]:
        deepseek_status = "✅ 已配置" if has_valid_deepseek_api_key() else "❌ 未配置"
        st.metric("🔑 DeepSeek Key", deepseek_status)
    with key_cols[1]:
        openai_status = "✅ 已配置" if has_valid_openai_api_key() else "❌ 未配置"
        st.metric("🔑 OpenAI Key", openai_status)
    with key_cols[2]:
        gemini_status = "✅ 已配置" if has_valid_gemini_api_key() else "❌ 未配置"
        st.metric("🔑 Gemini Key", gemini_status)

    st.markdown("---")

    st.markdown("### 📋 当前生效策略")
    strategy_cols = st.columns(2)
    for idx, (key, label) in enumerate(labels.items()):
        with strategy_cols[idx % 2]:
            current_mode = format_mode_label(settings.get(key))
            st.info(f"- **{label}**: {current_mode}")

    st.markdown("---")

    st.markdown("### ℹ️ 使用说明")
    help_items = [
        "💡 ChatGPT Plus 会员不能直接替代 API Key；脚本调用 DeepSeek、OpenAI、Gemini 仍需要各自的 API Key。",
        "🔄 如果选择**「自动选择」**，系统会优先尝试 Ollama，其次 DeepSeek，再其次 OpenAI，最后回退到本地模式。",
        f"📂 当前模型设置文件: `{XHS_AI_SETTINGS_FILE}`",
        f"📂 当前爬取设置文件: `{XHS_CRAWL_SETTINGS_FILE}`",
    ]
    for item in help_items:
        st.write(item)


def show_about():
    st.markdown("## ℹ️ 关于本项目")

    st.markdown(
        """
        ### 📕 小红书 Agent 控制台

        这是当前项目的**稳定版控制台入口**，负责串联登录、抓取、草稿查看与基础设置。

        #### ✨ 核心特性

        - 🔐 **登录授权管理** - 安全的小红书账号登录与状态监控
        - 🕷️ **智能爬取系统** - 自动抓取 AIGC 相关内容并进行 AI 分析
        - 📝 **草稿管理中心** - 完整的草稿生命周期管理（创建、审核、发布）
        - ⚙️ **灵活的 AI 配置** - 支持多种 AI 模型后端（Ollama/DeepSeek/OpenAI/Gemini）

        #### 🎯 设计理念

        当前页面优先保证：
        - ✅ **中文可读性** - 全中文界面，符合国内用户习惯
        - ✅ **结构稳定性** - 清晰的模块划分，易于维护
        - ✅ **核心功能可用** - 聚焦主要工作流，避免功能冗余

        #### 🚀 后续规划

        后续可以继续在这份干净版本上补回更复杂的高级交互，包括：

        - 📊 更丰富的数据可视化图表
        - 🔔 实时消息通知系统
        - 📱 移动端响应式适配
        - 🎨 更多主题定制选项
        - 📈 使用统计与分析面板

        ---
        *Made with ❤️ using Streamlit*
        """
    )
