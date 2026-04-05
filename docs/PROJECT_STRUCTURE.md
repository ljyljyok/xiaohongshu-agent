# Xiaohongshu Agent - Project Structure

## 📁 Organized Directory Structure

```
xiaohongshu-agent/
│
├── src/                          # 🔧 Core Source Code (DO NOT MODIFY casually)
│   ├── ai/                     # AI & LLM Modules
│   │   ├── text_llm_client.py  # LLM client (OpenAI/DeepSeek/Ollama/Gemma4)
│   │   ├── content_analyzer.py # Content analysis & classification
│   │   ├── content_rewriter.py  # AI-powered content rewriting
│   │   ├── content_auditor.py   # Quality audit & fact-checking
│   │   ├── image_generator.py   # AI image generation
│   │   └── video_processor.py   # Video/audio processing
│   │
│   ├── crawler/                # Web Scraping Module
│   │   └── xiaohongshu_crawler.py  # XHS post crawler
│   │
│   ├── publisher/              # Publishing Module
│   │   └── xiaohongshu_publisher.py  # Auto-publish to XHS
│   │
│   ├── ui/                     # User Interface
│   │   ├── app.py             # Streamlit main app
│   │   └── draft_manager.py    # Draft management
│   │
│   └── utils/                  # Utilities
│       └── helpers.py          # Helper functions
│
├── config/                      # ⚙️ Configuration
│   └── config.py               # App settings & API keys
│
├── data/                       # 📊 Runtime Data (gitignored)
│   ├── drafts/                 # Generated content drafts
│   ├── images/                 # Downloaded images
│   ├── media/                  # Audio/video files
│   │   ├── audio/
│   │   └── videos/
│   └── xhs_state/             # App state & settings
│
├── tests/                      # 🧪 Test Files
│   ├── test_*.py               # All unit/integration tests
│   └── README.md               # Test documentation
│
├── scripts/                    # 🚀 Run Scripts & Tools
│   ├── run_*.py                # Workflow runners
│   ├── crawl_*.py             # Crawling scripts
│   ├── *.bat                  # Windows batch files
│   └── xhs_direct_publish.js   # JS publisher helper
│
├── logs/                       # 📋 Log Files (gitignored)
│   ├── *.log                   # Application logs
│   ├── crawl_log_*.txt         # Crawl session logs
│   └── crawl_status_*.json     # Crawl status reports
│
├── docs/                       # 📚 Documentation
│   ├── screenshots/            # UI screenshots (_*.png)
│   └── README.md               # Project documentation
│
├── archive/                    # 📦 Archived Files (old versions)
│
├── .vscode/                    # VSCode Settings
│   └── settings.json           # Editor configuration
│
├── .streamlit/                 # Streamlit Config
│   └── config.toml
│
├── .env                        # Environment Variables (gitignored)
├── .gitignore                  # Git Ignore Rules
├── requirements.txt            # Python Dependencies
├── web_app.py                  # Main Application Entry
└── README.md                  # Project README
```

## 🎯 File Categories Explained

| Category | Location | Description |
|----------|----------|-------------|
| **Core Code** | `src/` | Production code, well-organized by module |
| **Config** | `config/` | Settings, API keys, environment variables |
| **Data** | `data/` | Runtime data (images, drafts, state) |
| **Tests** | `tests/` | All test files (test_*.py) |
| **Scripts** | `scripts/` | Run scripts, batch tools, utilities |
| **Logs** | `logs/` | Log files, debug output, crawl history |
| **Docs** | `docs/` | Documentation, guides, screenshots |
| **Archive** | `archive/` | Old/unused files kept for reference |

## 🚀 Quick Start

```bash
# 1. Activate LJY environment
conda activate LJY

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run web application
python web_app.py

# 4. Or run full workflow
cd scripts
python run_full_workflow.py
```

## 📝 Conventions

- **Source code**: Only modify files in `src/`
- **Tests**: All test files go to `tests/`
- **Scripts**: Utility runners go to `scripts/`
- **Logs**: Auto-generated, can be deleted
- **Data**: Runtime data, not committed to git

---
**Reorganized**: 2026-04-05 12:38
**Maintainer**: AI Assistant
