@echo off
chcp 65001 >nul
echo ========================================
echo   小红书自动化Agent - Web界面启动器
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 激活conda环境...
call conda activate LJY

if errorlevel 1 (
    echo [ERROR] 无法激活conda环境 LJY
    echo 请确保已安装Anaconda/Miniconda并创建了LJY环境
    pause
    exit /b 1
)

echo [OK] Conda环境 LJY 已激活
echo.
echo [2/2] 启动Web界面...
echo.
echo 访问地址: http://localhost:8501
echo 按 Ctrl+C 停止服务
echo.

streamlit run web_app.py --server.port 8501 --server.headless true

pause
