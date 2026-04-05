@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=C:\Users\ljy\miniconda3\envs\LJY\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] 未找到 LJY 环境的 Python: %PYTHON_EXE%
  exit /b 1
)

set "CONDA_DLL_SEARCH_MODIFICATION_ENABLE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "XHS_PYTHON_EXE=%PYTHON_EXE%"

echo [INFO] 使用 LJY 环境启动 Streamlit
echo [INFO] Python: %PYTHON_EXE%

"%PYTHON_EXE%" -m streamlit run web_app.py

