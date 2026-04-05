#!/usr/bin/env python3
"""测试环境和模块安装情况"""

import sys
import os

print(f"Python版本: {sys.version}")
print(f"Python路径: {sys.executable}")
print(f"当前工作目录: {os.getcwd()}")

# 测试模块导入
try:
    import requests
    print("OK requests模块已安装")
except ImportError:
    print("NO requests模块未安装")

try:
    from bs4 import BeautifulSoup
    print("OK beautifulsoup4模块已安装")
except ImportError:
    print("NO beautifulsoup4模块未安装")

try:
    from selenium import webdriver
    print("OK selenium模块已安装")
except ImportError:
    print("NO selenium模块未安装")

try:
    from webdriver_manager.chrome import ChromeDriverManager
    print("OK webdriver-manager模块已安装")
except ImportError:
    print("NO webdriver-manager模块未安装")

try:
    import openai
    print("OK openai模块已安装")
except ImportError:
    print("NO openai模块未安装")

try:
    from PIL import Image
    print("OK Pillow模块已安装")
except ImportError:
    print("NO Pillow模块未安装")

try:
    import flask
    print("OK Flask模块已安装")
except ImportError:
    print("NO Flask模块未安装")

try:
    import streamlit
    print("OK streamlit模块已安装")
except ImportError:
    print("NO streamlit模块未安装")

try:
    from dotenv import load_dotenv
    print("OK python-dotenv模块已安装")
except ImportError:
    print("NO python-dotenv模块未安装")

try:
    import sqlalchemy
    print("OK SQLAlchemy模块已安装")
except ImportError:
    print("NO SQLAlchemy模块未安装")

try:
    import pandas
    print("OK pandas模块已安装")
except ImportError:
    print("NO pandas模块未安装")
