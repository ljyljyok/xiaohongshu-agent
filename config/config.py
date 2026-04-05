import json
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip() or "https://api.deepseek.com/v1"
DEEPSEEK_CHAT_MODEL = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-chat").strip() or "deepseek-chat"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1").strip() or "whisper-1"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip() or "http://localhost:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b").strip() or "gemma4:e4b"
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "true").lower() in ("true", "1", "yes")

PUPPETEER_EXECUTABLE_PATH = os.getenv(
    "PUPPETEER_EXECUTABLE_PATH",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
)
if PUPPETEER_EXECUTABLE_PATH and os.path.exists(PUPPETEER_EXECUTABLE_PATH):
    os.environ["PUPPETEER_EXECUTABLE_PATH"] = PUPPETEER_EXECUTABLE_PATH

XIAOHONGSHU_SEARCH_URL = "https://www.xiaohongshu.com/search_result"
XIAOHONGSHU_LOGIN_URL = "https://www.xiaohongshu.com/login"

CRAWLER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
CRAWLER_TIMEOUT = 30
CRAWLER_RETRY_TIMES = 3
XHS_CRAWL_THREADS = max(1, int(os.getenv("XHS_CRAWL_THREADS", "3")))

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DRAFT_DIR = os.path.join(DATA_DIR, "drafts")

XHS_BACKEND = os.getenv("XHS_BACKEND", "mcp").strip().lower() or "mcp"
XHS_MCP_CMD = os.getenv("XHS_MCP_CMD", "npx").strip() or "npx"
XHS_MCP_ARGS = os.getenv("XHS_MCP_ARGS", "xhs-mcp").strip() or "xhs-mcp"
XHS_PROFILE_DIR = os.getenv("XHS_PROFILE_DIR", os.path.join(DATA_DIR, "xhs_profile"))
XHS_COOKIE_FILE = os.getenv("XHS_COOKIE_FILE", os.path.join(DATA_DIR, "xhs_cookies.json"))
XHS_COOKIE_FILE_LEGACY = os.path.join(DATA_DIR, "xhs_cookies.pkl")
XHS_FAVORITE_FOLDER = os.getenv("XHS_FAVORITE_FOLDER", "工作").strip() or "工作"
XHS_STATE_DIR = os.path.join(DATA_DIR, "xhs_state")
XHS_CRAWL_SETTINGS_FILE = os.getenv("XHS_CRAWL_SETTINGS_FILE", os.path.join(XHS_STATE_DIR, "crawl_settings.json"))
XHS_AI_SETTINGS_FILE = os.getenv("XHS_AI_SETTINGS_FILE", os.path.join(XHS_STATE_DIR, "ai_runtime_settings.json"))
MEDIA_DIR = os.path.join(DATA_DIR, "media")

DEFAULT_AI_RUNTIME_SETTINGS = {
    "content_analyzer_mode": "deepseek",
    "content_rewriter_mode": "deepseek",
    "content_auditor_mode": "deepseek",
    "image_processing_mode": "deepseek",
    "video_transcription_mode": "deepseek",
}
VALID_AI_RUNTIME_MODES = {"auto", "deepseek", "openai", "ollama", "local"}

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DRAFT_DIR, exist_ok=True)
os.makedirs(XHS_PROFILE_DIR, exist_ok=True)
os.makedirs(XHS_STATE_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)


def has_valid_openai_api_key(value=None):
    normalized = str(OPENAI_API_KEY if value is None else value).strip()
    return bool(normalized) and normalized != "your_openai_api_key_here"


def has_valid_deepseek_api_key(value=None):
    normalized = str(DEEPSEEK_API_KEY if value is None else value).strip()
    return bool(normalized) and normalized != "your_deepseek_api_key_here"


def has_valid_gemini_api_key(value=None):
    normalized = str(GEMINI_API_KEY if value is None else value).strip()
    return bool(normalized) and normalized != "your_gemini_api_key_here"


def normalize_ai_runtime_mode(value, default="auto"):
    mode = str(value or default).strip().lower()
    return mode if mode in VALID_AI_RUNTIME_MODES else default


def load_ai_runtime_settings():
    settings = dict(DEFAULT_AI_RUNTIME_SETTINGS)
    if not os.path.exists(XHS_AI_SETTINGS_FILE):
        return settings
    try:
        with open(XHS_AI_SETTINGS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return settings
        for key, default in DEFAULT_AI_RUNTIME_SETTINGS.items():
            settings[key] = normalize_ai_runtime_mode(data.get(key, default), default)
    except Exception:
        return dict(DEFAULT_AI_RUNTIME_SETTINGS)
    return settings


def get_ai_runtime_mode(setting_key, default="auto"):
    settings = load_ai_runtime_settings()
    fallback = DEFAULT_AI_RUNTIME_SETTINGS.get(setting_key, default)
    return normalize_ai_runtime_mode(settings.get(setting_key, fallback), fallback)
