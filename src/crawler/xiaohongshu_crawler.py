#!/usr/bin/env python3
"""Browser-based Xiaohongshu crawler with lightweight detail hydration."""

import json
import os
import pickle
import re
import sys
import time
from typing import Dict, List
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from config.config import (
    CRAWLER_HEADERS,
    CRAWLER_RETRY_TIMES,
    CRAWLER_TIMEOUT,
    XHS_COOKIE_FILE,
    XHS_COOKIE_FILE_LEGACY,
    XHS_PROFILE_DIR,
)


class XiaohongshuCrawler:
    """Browser-based Xiaohongshu crawler."""

    ACCESS_WALL_MARKERS = [
        "登录后查看",
        "登录后查看更多",
        "请先登录",
        "扫码登录",
        "打开小红书app",
        "小红书app内打开",
        "阅读并同意",
        "同意后继续",
        "账号登录",
        "立即登录",
        "验证码登录",
        "手机号登录",
        "继续访问前请登录",
    ]

    def __init__(self):
        self.headers = CRAWLER_HEADERS
        self.timeout = CRAWLER_TIMEOUT
        self.retry_times = CRAWLER_RETRY_TIMES
        self.driver = None
        self.last_warning = ""
        self.cookie_source = ""

    def close(self):
        self._close_driver()

    def search_posts(self, keyword, max_posts=20, hydrate_details=False):
        posts = []
        self.last_warning = ""
        try:
            self._init_driver()
            encoded_keyword = quote(str(keyword or ""))
            search_url = "https://www.xiaohongshu.com/search_result?keyword={}&source=web_explore_feed".format(encoded_keyword)
            print("访问搜索页面: {}".format(search_url))
            self._load_page_best_effort(search_url, allow_retry=True)
            self._wait_for_dom_settle("section[class*='note-item'], div[class*='note-item'], a[href*='/explore/']", attempts=5)

            if self._detect_login_wall():
                print("[WARNING] {}".format(self.last_warning))
                return []

            last_height = self.driver.execute_script("return document.body.scrollHeight")
            for _ in range(6):
                parsed = self._parse_posts()
                posts = self._merge_unique_posts(posts, parsed)
                if len(posts) >= max_posts:
                    break
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.8)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            posts = posts[:max_posts]
            if hydrate_details and posts:
                posts = self.hydrate_posts(posts, close_driver=False)
        except Exception as exc:
            self.last_warning = str(exc)
            print("搜索帖子时出错: {}".format(str(exc)[:120]))
        finally:
            self._close_driver()
        return posts

    def get_post_detail(self, post_url):
        post_detail = {}
        try:
            self._init_driver()
            post_detail = self._get_post_detail_with_driver(post_url)
        except Exception as exc:
            print("获取帖子详情时出错: {}".format(str(exc)[:120]))
        finally:
            self._close_driver()
        return post_detail

    def hydrate_posts(self, posts: List[Dict], close_driver: bool = True) -> List[Dict]:
        hydrated_posts = []
        try:
            self._init_driver()
            total = len(posts or [])
            for index, post in enumerate(posts or []):
                try:
                    detail = self._get_post_detail_with_driver(post.get("link", "") or post.get("source_url", ""))
                    merged = self._merge_post_detail(post, detail)
                    if detail.get("warning"):
                        merged["crawl_warning"] = detail["warning"]
                    hydrated_posts.append(merged)
                    print("详情补抓 {}/{}: {}".format(index + 1, total, self._safe_console_text((merged.get("title") or merged.get("original_title") or "")[:40])))
                except Exception as detail_exc:
                    print("补抓详情失败: {}".format(str(detail_exc)[:120]))
                    fallback = dict(post)
                    fallback["source_url"] = self._normalize_url(post.get("link", "") or post.get("source_url", ""))
                    fallback["original_title"] = post.get("original_title") or post.get("title", "")
                    fallback["original_content"] = post.get("original_content") or post.get("content", "")
                    fallback["hydrate_timeout"] = True
                    fallback["crawl_warning"] = "hydrate_timeout"
                    hydrated_posts.append(fallback)
            return hydrated_posts
        finally:
            if close_driver:
                self._close_driver()

    def _init_driver(self):
        if self.driver:
            return

        chrome_options = Options()
        chrome_options.page_load_strategy = "eager"
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--window-size=1600,2400")
        chrome_options.add_argument(f"user-agent={self.headers['User-Agent']}")

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as exc:
            self.last_warning = "ChromeDriverManager failed; falling back to Selenium default driver resolution."
            print("[WARNING] {} ({})".format(self.last_warning, str(exc)[:100]))
            self.driver = webdriver.Chrome(options=chrome_options)

        self.driver.set_page_load_timeout(self.timeout)
        self._restore_login_state()

    def _close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def _load_page_best_effort(self, url: str, allow_retry: bool = True):
        attempts = 2 if allow_retry else 1
        last_error = ""
        for attempt in range(attempts):
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, self.timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                return {"timed_out": False, "recovered": attempt > 0, "error": ""}
            except TimeoutException as exc:
                last_error = str(exc)
                try:
                    self.driver.execute_script("window.stop();")
                except Exception:
                    pass
                try:
                    WebDriverWait(self.driver, min(6, self.timeout)).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    return {"timed_out": True, "recovered": True, "error": last_error}
                except Exception:
                    if attempt + 1 >= attempts:
                        return {"timed_out": True, "recovered": False, "error": last_error}
                    try:
                        self.driver.get("about:blank")
                    except Exception:
                        pass
                    time.sleep(0.4)
            except Exception as exc:
                last_error = str(exc)
                if attempt + 1 >= attempts:
                    raise
                time.sleep(0.4)
        return {"timed_out": True, "recovered": False, "error": last_error}

    def _wait_for_dom_settle(self, selector: str, attempts: int = 4, sleep_seconds: float = 0.35):
        for _ in range(max(1, attempts)):
            try:
                if self.driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
            except Exception:
                pass
            time.sleep(sleep_seconds)
        return False

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        url = str(url).strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return "https://www.xiaohongshu.com" + url
        return url

    def _safe_console_text(self, text: str) -> str:
        text = str(text or "")
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            text.encode(encoding)
            return text
        except Exception:
            return text.encode(encoding, errors="replace").decode(encoding, errors="replace")

    def _candidate_cookie_files(self) -> List[str]:
        candidates = [
            XHS_COOKIE_FILE,
            XHS_COOKIE_FILE_LEGACY,
            os.path.join(XHS_PROFILE_DIR, "cookies.json"),
            os.path.join(os.path.expanduser("~"), ".xhs-mcp", "cookies.json"),
        ]
        paths = []
        seen = set()
        for path in candidates:
            abs_path = os.path.abspath(str(path or ""))
            if abs_path and abs_path not in seen and os.path.exists(abs_path):
                paths.append(abs_path)
                seen.add(abs_path)
        return paths

    def _load_cookie_bundle(self):
        for path in self._candidate_cookie_files():
            try:
                if path.lower().endswith(".pkl"):
                    with open(path, "rb") as fh:
                        cookies = pickle.load(fh)
                else:
                    with open(path, "r", encoding="utf-8") as fh:
                        cookies = json.load(fh)
                if isinstance(cookies, list) and cookies:
                    return cookies, path
            except Exception:
                continue
        return [], ""

    def _normalize_cookie(self, cookie: Dict) -> Dict:
        cleaned = {}
        for key in ("name", "value", "domain", "path", "secure", "httpOnly", "sameSite"):
            if key in cookie and cookie.get(key) not in (None, ""):
                cleaned[key] = cookie[key]
        expiry = cookie.get("expiry", cookie.get("expires"))
        if expiry not in (None, ""):
            try:
                cleaned["expiry"] = int(float(expiry))
            except Exception:
                pass
        return cleaned

    def _restore_login_state(self) -> bool:
        cookies, source_path = self._load_cookie_bundle()
        if not cookies or not self.driver:
            return False
        try:
            self.driver.get("https://www.xiaohongshu.com/")
            time.sleep(0.8)
            applied = 0
            for cookie in cookies:
                cleaned = self._normalize_cookie(cookie or {})
                if not cleaned.get("name") or "value" not in cleaned:
                    continue
                try:
                    self.driver.add_cookie(cleaned)
                    applied += 1
                except Exception:
                    continue
            if not applied:
                return False
            self.driver.get("https://www.xiaohongshu.com/explore")
            time.sleep(0.8)
            self.cookie_source = source_path
            print("已加载登录 Cookie: {} ({} 条)".format(source_path, applied))
            return True
        except Exception as exc:
            self.last_warning = "Failed to restore Xiaohongshu cookies."
            print("[WARNING] {} ({})".format(self.last_warning, str(exc)[:100]))
            return False

    def _read_body_text(self) -> str:
        try:
            return (self.driver.find_element(By.TAG_NAME, "body").text or "").strip()
        except Exception:
            return ""

    def _contains_access_wall(self, text: str) -> bool:
        normalized = str(text or "").strip().lower()
        return any(marker.lower() in normalized for marker in self.ACCESS_WALL_MARKERS)

    def _detect_login_wall(self) -> bool:
        body_text = self._read_body_text()
        if self._contains_access_wall(body_text):
            self.last_warning = "Search results are blocked by the Xiaohongshu login wall."
            return True
        return False

    def _detect_detail_wall(self, *texts) -> bool:
        merged = "\n".join(str(text or "") for text in texts)
        if self._contains_access_wall(merged):
            self.last_warning = "Post detail is blocked by the Xiaohongshu login wall."
            return True
        return False

    def _first_non_empty_text(self, root, selectors: List[str]) -> str:
        for selector in selectors:
            try:
                elements = root.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            for element in elements:
                try:
                    text = (element.text or element.get_attribute("textContent") or "").strip()
                except Exception:
                    text = ""
                if text:
                    return text
        return ""

    def _parse_posts(self) -> List[Dict]:
        posts = []
        seen = set()
        card_selectors = [
            "section[class*='note-item']",
            "div[class*='note-item']",
            "section.note-item",
            "div.note-item",
        ]
        cards = []
        for selector in card_selectors:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                cards = []
            if cards:
                break

        for card in cards:
            try:
                link_el = None
                for selector in ["a[href*='/explore/']", "a[href*='xiaohongshu.com/explore/']"]:
                    try:
                        link_el = card.find_element(By.CSS_SELECTOR, selector)
                        if link_el:
                            break
                    except Exception:
                        continue
                if not link_el:
                    continue

                source_url = self._normalize_url(link_el.get_attribute("href") or "")
                if not source_url or source_url in seen:
                    continue

                title = self._first_non_empty_text(card, ["[class*='title']", "h1", "h2", "span"])
                card_text = (card.text or "").strip()
                author = self._first_non_empty_text(card, ["[class*='author']", "[class*='user']", "[class*='name']"])
                images = self._collect_images_from_root(card)
                outer_html = (card.get_attribute("outerHTML") or "").lower()
                media_type = "video" if (".mp4" in outer_html or "video" in outer_html) else "image"

                posts.append(
                    {
                        "title": title,
                        "content": card_text,
                        "author": author,
                        "images": images,
                        "original_image_urls": images,
                        "link": source_url,
                        "source_url": source_url,
                        "source": "browser_search",
                        "original_title": title,
                        "original_content": card_text,
                        "media_type": media_type,
                    }
                )
                seen.add(source_url)
            except Exception:
                continue

        if not posts:
            page_source = self.driver.page_source or ""
            matches = re.findall(r"https://www\.xiaohongshu\.com/explore/[A-Za-z0-9]+(?:\?[^\"'<>\\s]+)?", page_source)
            for url in matches:
                normalized = self._normalize_url(url)
                if normalized in seen:
                    continue
                posts.append(
                    {
                        "title": "",
                        "content": "",
                        "author": "",
                        "images": [],
                        "original_image_urls": [],
                        "link": normalized,
                        "source_url": normalized,
                        "source": "browser_search",
                        "original_title": "",
                        "original_content": "",
                        "media_type": "image",
                    }
                )
                seen.add(normalized)
        return posts

    def _collect_images_from_root(self, root) -> List[str]:
        images = []
        seen = set()
        for selector in ["img", "[style*='background-image']"]:
            try:
                elements = root.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            for element in elements:
                src = (
                    element.get_attribute("src")
                    or element.get_attribute("data-src")
                    or element.get_attribute("currentSrc")
                    or ""
                )
                src = self._normalize_url(src)
                if not self._is_probable_content_image(src, element):
                    continue
                if src not in seen:
                    images.append(src)
                    seen.add(src)
        return images

    def _is_probable_content_image(self, src: str, element) -> bool:
        src = self._normalize_url(src).lower()
        if not src.startswith("http"):
            return False
        if "data:image" in src:
            return False
        class_name = ""
        width = 0
        height = 0
        try:
            class_name = (element.get_attribute("class") or "").lower()
            width = int(element.get_attribute("naturalWidth") or element.get_attribute("width") or 0)
            height = int(element.get_attribute("naturalHeight") or element.get_attribute("height") or 0)
        except Exception:
            pass
        if width and height and max(width, height) < 180:
            return False
        if any(token in src or token in class_name for token in ["avatar", "emoji", "icon", "logo", "badge", "profile"]):
            return False
        return True

    def _get_post_detail_with_driver(self, post_url: str) -> Dict:
        post_url = self._normalize_url(post_url)
        post_detail = {
            "source_url": post_url,
            "images": [],
            "video_urls": [],
            "media_type": "image",
            "hydrate_timeout": False,
        }
        if not post_url:
            return post_detail

        load_state = self._load_page_best_effort(post_url, allow_retry=True)
        if load_state.get("timed_out"):
            post_detail["hydrate_timeout"] = True
            post_detail["warning"] = "hydrate_timeout"
        self._wait_for_dom_settle("h1, [class*='title'], [class*='desc'], article, main, img, video", attempts=5)

        title = self._first_non_empty_text(
            self.driver,
            ["h1", "[class*='title']", "[class*='Title']", ".note-content .title", ".note-scroller .title"],
        )
        content = self._first_non_empty_text(
            self.driver,
            ["[class*='desc']", "[class*='content']", "[class*='note-text']", "article", "main"],
        )
        author = self._first_non_empty_text(
            self.driver,
            ["[class*='author']", "[class*='user-name']", "[class*='nickname']"],
        )
        likes = self._first_non_empty_text(
            self.driver,
            ["[class*='like']", "[class*='interact']", "[class*='count']"],
        )
        publish_time = self._first_non_empty_text(
            self.driver,
            ["[class*='date']", "[class*='time']", "time"],
        )

        page_source = self.driver.page_source or ""
        if not title:
            title = self._extract_meta_content("og:title") or self.driver.title or ""
        if not content:
            content = self._extract_meta_content("description") or self._extract_meta_content("og:description") or ""

        if self._detect_detail_wall(title, content, self._read_body_text()):
            post_detail["warning"] = self.last_warning
            return post_detail

        images = self._extract_detail_image_urls(page_source)
        video_urls = self._extract_detail_video_urls(page_source)
        media_type = self._detect_media_type(page_source, video_urls)

        post_detail.update(
            {
                "title": title.strip(),
                "content": content.strip(),
                "author": author.strip(),
                "likes": likes.strip(),
                "publish_time": publish_time.strip(),
                "images": images,
                "original_image_urls": images,
                "video_urls": video_urls,
                "original_video_url": video_urls[0] if video_urls else "",
                "media_type": media_type,
            }
        )
        if post_detail.get("hydrate_timeout") and not post_detail.get("warning"):
            post_detail["warning"] = "hydrate_timeout"
        return post_detail

    def _extract_meta_content(self, name: str) -> str:
        try:
            if name.startswith("og:"):
                return self.driver.execute_script(
                    "return document.querySelector('meta[property=\"{}\"]')?.content || '';".format(name)
                )
            return self.driver.execute_script(
                "return document.querySelector('meta[name=\"{}\"]')?.content || '';".format(name)
            )
        except Exception:
            return ""

    def _extract_detail_image_urls(self, page_source: str) -> List[str]:
        urls = []
        seen = set()

        try:
            dom_images = self.driver.find_elements(By.CSS_SELECTOR, "img")
        except Exception:
            dom_images = []
        for image in dom_images:
            src = self._normalize_url(
                image.get_attribute("src")
                or image.get_attribute("data-src")
                or image.get_attribute("currentSrc")
                or ""
            )
            if src and src not in seen and self._is_probable_content_image(src, image):
                urls.append(src)
                seen.add(src)

        patterns = [
            r"https?://[^\"'\\\s>]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\"'\\\s>]*)?",
            r"//[^\"'\\\s>]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\"'\\\s>]*)?",
            r"\"urlDefault\"\s*:\s*\"([^\"]+)\"",
            r"\"url\"\s*:\s*\"([^\"]+?(?:jpg|jpeg|png|webp)[^\"]*)\"",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, page_source, re.IGNORECASE):
                normalized = self._normalize_url(self._decode_escaped_url(match))
                if normalized and normalized not in seen and "avatar" not in normalized.lower():
                    urls.append(normalized)
                    seen.add(normalized)
        return urls

    def _extract_detail_video_urls(self, page_source: str) -> List[str]:
        urls = []
        seen = set()

        try:
            video_elements = self.driver.find_elements(By.CSS_SELECTOR, "video, source")
        except Exception:
            video_elements = []
        for element in video_elements:
            src = self._normalize_url(
                element.get_attribute("src")
                or element.get_attribute("currentSrc")
                or element.get_attribute("data-src")
                or ""
            )
            if self._is_downloadable_video_url(src) and src not in seen:
                urls.append(src)
                seen.add(src)

        patterns = [
            r"\"masterUrl\"\s*:\s*\"([^\"]+\.mp4[^\"]*)\"",
            r"\"backupUrls\"\s*:\s*\[(.*?)\]",
            r"\"url\"\s*:\s*\"([^\"]+\.mp4[^\"]*)\"",
            r"https?://[^\"'\\\s>]+?\.mp4(?:\?[^\"'\\\s>]*)?",
            r"//[^\"'\\\s>]+?\.mp4(?:\?[^\"'\\\s>]*)?",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, page_source, re.IGNORECASE):
                candidates = re.findall(r"\"([^\"]+\.mp4[^\"]*)\"", match, re.IGNORECASE) if "backupUrls" in pattern else [match]
                for candidate in candidates:
                    normalized = self._normalize_url(self._decode_escaped_url(candidate))
                    if self._is_downloadable_video_url(normalized) and normalized not in seen:
                        urls.append(normalized)
                        seen.add(normalized)
        return urls

    def _decode_escaped_url(self, url: str) -> str:
        return (
            str(url or "")
            .replace("\\u002F", "/")
            .replace("\\/", "/")
            .replace("&amp;", "&")
            .replace("u002F", "/")
        )

    def _detect_media_type(self, page_source: str, video_urls: List[str]) -> str:
        source = page_source.lower()
        if video_urls:
            return "video"
        if '"type":"video"' in source or '"notetype":"video"' in source or ".mp4" in source:
            return "video"
        return "image"

    def _is_downloadable_video_url(self, url: str) -> bool:
        url = str(url or "").strip().lower()
        if not url:
            return False
        if url.startswith(("blob:", "data:", "mediastream:", "filesystem:")):
            return False
        return url.startswith("http://") or url.startswith("https://") or url.startswith("//")

    def _merge_unique_urls(self, *url_lists) -> List[str]:
        merged = []
        seen = set()
        for url_list in url_lists:
            for url in url_list or []:
                normalized = self._normalize_url(url)
                if normalized and normalized not in seen:
                    merged.append(normalized)
                    seen.add(normalized)
        return merged

    def _merge_post_detail(self, post: Dict, detail: Dict) -> Dict:
        merged = dict(post or {})
        for key in ["title", "content", "author", "likes", "publish_time", "media_type", "original_video_url"]:
            if detail.get(key):
                merged[key] = detail[key]
        merged_images = self._merge_unique_urls(
            post.get("original_image_urls", []),
            post.get("images", []),
            detail.get("images", []),
            detail.get("original_image_urls", []),
        )
        if merged_images:
            merged["images"] = merged_images
            merged["original_image_urls"] = merged_images
        if detail.get("video_urls"):
            merged["video_urls"] = detail["video_urls"]
        merged["link"] = detail.get("source_url") or self._normalize_url(post.get("link", ""))
        merged["source_url"] = merged["link"]
        merged["original_title"] = detail.get("title") or post.get("original_title") or post.get("title", "")
        merged["original_content"] = detail.get("content") or post.get("original_content") or post.get("content", "")
        if detail.get("hydrate_timeout"):
            merged["hydrate_timeout"] = True
        return merged

    def _merge_unique_posts(self, existing_posts, new_posts):
        merged = []
        seen = set()
        for post in list(existing_posts or []) + list(new_posts or []):
            key = (post.get("source_url") or post.get("link") or post.get("title") or "").strip()
            if not key or key in seen:
                continue
            merged.append(post)
            seen.add(key)
        return merged


if __name__ == "__main__":
    print("开始测试小红书爬虫...")
    crawler = XiaohongshuCrawler()
    posts = crawler.search_posts("AI 工具", max_posts=5, hydrate_details=True)
    print("共获取到 {} 个帖子".format(len(posts)))
    for index, post in enumerate(posts, 1):
        print(
            "[{}] {} | {} | 图片 {} | 视频 {}".format(
                index,
                post.get("title", "无标题"),
                post.get("media_type", "image"),
                len(post.get("images", []) or []),
                len(post.get("video_urls", []) or []),
            )
        )
