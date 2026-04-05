@echo off
setlocal
cd /d "%~dp0.."

set "PYTHON_EXE=C:\Users\ljy\miniconda3\envs\LJY\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo 启动 Git 自动提交与推送监控...
echo 仓库目录: %cd%
start "xiaohongshu-agent auto git sync" "%PYTHON_EXE%" scripts\auto_git_sync.py --repo .

endlocal
