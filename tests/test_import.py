#!/usr/bin/env python3
"""Simple import smoke test for local dependencies and project modules."""

import os
import sys

print("Starting import smoke test...")

# 测试基础模块
try:
    import requests
    print("[OK] requests import")
except Exception as e:
    print(f"[FAIL] requests import: {e}")

try:
    from bs4 import BeautifulSoup
    print("[OK] beautifulsoup4 import")
except Exception as e:
    print(f"[FAIL] beautifulsoup4 import: {e}")

try:
    from selenium import webdriver
    print("[OK] selenium import")
except Exception as e:
    print(f"[FAIL] selenium import: {e}")

try:
    from webdriver_manager.chrome import ChromeDriverManager
    print("[OK] webdriver-manager import")
except Exception as e:
    print(f"[FAIL] webdriver-manager import: {e}")

# Add the project root so local modules can be imported directly.
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Smoke-test project modules.
try:
    from src.crawler.xiaohongshu_crawler import XiaohongshuCrawler
    print("[OK] XiaohongshuCrawler import")
except Exception as e:
    print(f"[FAIL] XiaohongshuCrawler import: {e}")

try:
    from config.config import CRAWLER_HEADERS
    print("[OK] config import")
except Exception as e:
    print(f"[FAIL] config import: {e}")

print("Import smoke test finished.")
