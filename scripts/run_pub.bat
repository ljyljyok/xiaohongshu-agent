@echo off
set PUPPETEER_EXECUTABLE_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
xhs-mcp publish --type image --title "Claude评测超越GPT-4o" --content "Claude 2026最新评测：全面超越GPT-4o！长文本理解、代码推理、安全性全面领先。中文处理和多轮对话表现突出。附完整评测数据。" -m "C:\Users\ljy\Documents\Gemini\TRAEtest\多智能体推文\xiaohongshu-agent\data\images\original_7a09142a_0.jpg" --tags "AIGC,Claude,GPT-4o"
echo EXIT_CODE=%ERRORLEVEL%
