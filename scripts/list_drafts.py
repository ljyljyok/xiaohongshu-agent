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
print("Total: {}".format(len(drafts)))

for i, d in enumerate(drafts):
    post = d.get('post', {})
    title = post.get('title', '?')[:60]
    content = (post.get('publish_content') or post.get('optimized_content') or post.get('rewritten_content', ''))[:80]
    img = post.get('generated_image_path', '')
    img_exists = "YES" if (img and os.path.exists(img)) else "NO"
    status = d.get('status', '?')
    favorite = " favorite=YES" if d.get('favorite') else ""
    print("\n[{}] status={}{} title={}".format(i, status, favorite, title))
    print("  content: {}...".format(content))
    print("  image: {} ({})".format(img[:60] if img else "(none)", img_exists))
