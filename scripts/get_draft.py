import sys, os, json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from _bootstrap import ensure_runtime_environment

ensure_runtime_environment(require_selenium=True)
os.chdir(PROJECT_ROOT)
from ui.draft_manager import DraftManager

dm = DraftManager()
drafts = dm.list_drafts()
d = drafts[0]
post = d.get('post', {})

print("TITLE: " + post.get('title', ''))
print("---")
print("CONTENT: " + (post.get('publish_content') or post.get('optimized_content') or post.get('rewritten_content', '')))
print("---")
print("IMAGE: " + post.get('generated_image_path', ''))
