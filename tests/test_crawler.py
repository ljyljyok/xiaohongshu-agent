#!/usr/bin/env python3
"""Simple crawler smoke test."""

import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.crawler.xiaohongshu_crawler import XiaohongshuCrawler

print("Starting Xiaohongshu crawler smoke test...")

crawler = XiaohongshuCrawler()
print("Crawler instance created.")

print("Running search smoke test...")
try:
    posts = crawler.search_posts("AI工具", max_posts=5)
    print(f"Search completed. Retrieved {len(posts)} post(s).")

    if posts:
        print("\nTop results:")
        for i, post in enumerate(posts[:3]):
            print(f"\nPost {i+1}:")
            print(f"Title:  {post.get('title', 'Untitled')}")
            print(f"Likes:  {post.get('likes', '0')}")
            print(f"Author: {post.get('author', 'Unknown')}")
    elif crawler.last_warning:
        print(f"[WARNING] {crawler.last_warning}")
    else:
        print("No posts were returned.")

except Exception as e:
    print(f"Search failed: {e}")

print("\nCrawler smoke test finished.")
