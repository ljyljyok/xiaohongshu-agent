# xiaohongshu-agent

面向 Windows 的小红书内容工作流：支持 MCP 登录、真实原贴抓取、图文/视频理解、阅读笔记生成、草稿审核、草稿管理与发布。

## 开发原则

- 优先正向解决：能通过 MCP、真实登录态、真实原贴和真实媒体链路解决的问题，不优先走 mock、占位图或硬编码绕过。
- 兜底方案并存：当上游接口、页面结构或本机环境不稳定时，允许保留 Cookie/浏览器自动化等兼容回退，但默认优先尝试主链路。
- 来源优先：草稿基于原贴详情、原图/原视频、OCR/转写和阅读笔记生成，避免空话和无来源改写。

## 环境准备

### Python

项目默认使用 `LJY` conda 环境：

```powershell
conda activate LJY
python -m pip install -r requirements.txt
```

如果 PowerShell 无法激活 conda，可直接使用环境里的解释器：

```powershell
C:\Users\ljy\miniconda3\envs\LJY\python.exe -m pip install -r requirements.txt
```

### Node / MCP

默认登录与发布后端是 `xhs-mcp`，需要本机已安装 Node.js LTS 和 `npx`：

```powershell
node -v
cmd /c "npx xhs-mcp --help"
```

说明：

- 在部分 Windows PowerShell 环境中，直接执行 `npx` 可能被执行策略拦截，建议优先使用 `cmd /c`。
- 当前 `xhs-mcp` 官方工具集支持登录、状态检查、搜索、详情、评论、发布，但暂不直接提供“收藏到指定收藏夹”的 MCP 工具。
- 本项目已接入“基于 MCP 登录态 + 本地浏览器自动化”的收藏实现：通过稿会优先尝试把原贴收藏到小红书收藏夹 `工作`。

## 配置

在项目根目录创建或更新 `.env`：

```env
OPENAI_API_KEY=
GEMINI_API_KEY=
OPENAI_TRANSCRIBE_MODEL=whisper-1

XHS_BACKEND=mcp
XHS_MCP_CMD=npx
XHS_MCP_ARGS=xhs-mcp
XHS_PROFILE_DIR=data/xhs_profile
XHS_COOKIE_FILE=data/xhs_cookies.json
XHS_FAVORITE_FOLDER=工作
```

后端说明：

- `mcp`：默认后端，浏览器登录、登录状态检查、搜索与发布主链路都优先走 MCP。
- `legacy`：Selenium 兼容回退，仅用于特定场景。

凭证存储：

- 主轨：`data/xhs_profile`
- Cookie 兼容：`data/xhs_cookies.json`
- 老格式兼容：`data/xhs_cookies.pkl`

## 运行

启动网页 Demo：

```powershell
streamlit run web_app.py
```

如果你想强制用 `LJY` 环境启动，也可以直接运行：

```powershell
run_web_app_ljy.bat
```

## 登录流程

1. 打开网页里的“登录授权”页。
2. 点击“启动浏览器登录”。
3. 在 MCP 拉起的浏览器中完成小红书登录。
4. 页面会轮询显式状态文件和 MCP 状态，不再依赖 Cookie 修改时间猜测成功。

## 抓取与草稿流程

抓取主链路：

1. 关键词搜索真实原贴
2. 详情补抓原贴正文、原图、原视频
3. 图文走 OCR + 图片理解，视频走转写 + 关键帧理解
4. 生成阅读笔记
5. 生成润色后的最终待发布文案
6. 做来源、引用、内容详实度审核
7. 保存通过稿，并尝试把原贴收藏到 `工作` 收藏夹

当前草稿字段中，最终发布文案优先使用：

- `publish_content`
- 兼容映射到 `optimized_content`

原始润色稿保留在：

- `optimized_content_raw`

## 原贴自动收藏

通过审核的草稿在保存时会自动执行：

1. 先校验 MCP 登录态是否有效
2. 复用 MCP 保存的 Cookie / 登录态
3. 打开原贴 `source_url`
4. 尝试点击收藏，并加入收藏夹 `工作`

注意：

- 这是“优先正向解决”的实现，优先复用 MCP 登录态和真实原贴链接。
- 由于 `xhs-mcp` 当前没有直接暴露“收藏夹”工具，项目内部使用了浏览器自动化完成最后一步 UI 操作。
- 如果页面结构变化、收藏夹不存在或登录态失效，草稿仍会保存，但会在草稿元数据里记录收藏状态和失败原因。

## 说明

- 爬虫中的 Chrome 启动方式已适配 Selenium 4 `Service(...)`。
- 登录页不会在被动状态检查时偷偷拉起浏览器。
- 如果 MCP 暂时不可用，系统会尽量保留 Cookie/浏览器自动化回退能力，但默认仍优先尝试 MCP 主链路。
