@echo off

rem 启动自动化小红书Agent
cd /d %~dp0

rem 运行Streamlit应用
streamlit run src/ui/app.py
