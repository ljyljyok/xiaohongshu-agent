#!/usr/bin/env python3
"""草稿管理模块。"""

import json
import os
import uuid
from datetime import datetime

from config.config import DRAFT_DIR


class DraftManager:
    """负责保存、读取和维护本地草稿。"""

    def __init__(self):
        self.draft_dir = DRAFT_DIR
        os.makedirs(self.draft_dir, exist_ok=True)

    def _normalize_draft(self, draft):
        normalized = dict(draft or {})
        normalized.setdefault("favorite", False)
        normalized.setdefault("favorite_at", "")
        normalized.setdefault("favorite_source", "")
        return normalized

    def _write_draft(self, draft_id, draft):
        draft_path = os.path.join(self.draft_dir, "{}.json".format(draft_id))
        with open(draft_path, "w", encoding="utf-8") as f:
            json.dump(self._normalize_draft(draft), f, ensure_ascii=False, indent=2)

    def save_draft(self, post, favorite=False, favorite_source="manual"):
        """保存单条草稿，支持自动收藏标记。"""
        draft_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        draft = {
            "id": draft_id,
            "created_at": now,
            "updated_at": now,
            "status": "draft",
            "favorite": bool(favorite),
            "favorite_at": now if favorite else "",
            "favorite_source": favorite_source if favorite else "",
            "post": post,
        }
        self._write_draft(draft_id, draft)
        return draft_id

    def get_draft(self, draft_id):
        draft_path = os.path.join(self.draft_dir, "{}.json".format(draft_id))
        if not os.path.exists(draft_path):
            return None
        with open(draft_path, "r", encoding="utf-8") as f:
            return self._normalize_draft(json.load(f))

    def list_drafts(self, status=None):
        drafts = []
        for filename in os.listdir(self.draft_dir):
            if not filename.endswith(".json"):
                continue
            draft_path = os.path.join(self.draft_dir, filename)
            with open(draft_path, "r", encoding="utf-8") as f:
                draft = self._normalize_draft(json.load(f))
            if status and draft.get("status") != status:
                continue
            drafts.append(draft)
        drafts.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return drafts

    def update_draft_status(self, draft_id, status):
        draft = self.get_draft(draft_id)
        if not draft:
            return False
        draft["status"] = status
        draft["updated_at"] = datetime.now().isoformat()
        self._write_draft(draft_id, draft)
        return True

    def update_draft_post(self, draft_id, post):
        draft = self.get_draft(draft_id)
        if not draft:
            return False
        draft["post"] = post
        draft["updated_at"] = datetime.now().isoformat()
        self._write_draft(draft_id, draft)
        return True

    def set_favorite(self, draft_id, favorite=True, favorite_source="manual"):
        draft = self.get_draft(draft_id)
        if not draft:
            return False
        draft["favorite"] = bool(favorite)
        draft["favorite_at"] = datetime.now().isoformat() if favorite else ""
        draft["favorite_source"] = favorite_source if favorite else ""
        draft["updated_at"] = datetime.now().isoformat()
        self._write_draft(draft_id, draft)
        return True

    def delete_draft(self, draft_id):
        draft_path = os.path.join(self.draft_dir, "{}.json".format(draft_id))
        if not os.path.exists(draft_path):
            return False
        os.remove(draft_path)
        return True

    def batch_save_drafts(self, posts, favorite=False, favorite_source="manual"):
        draft_ids = []
        for post in posts:
            draft_ids.append(self.save_draft(post, favorite=favorite, favorite_source=favorite_source))
        return draft_ids

    def list_favorites(self):
        return [draft for draft in self.list_drafts() if draft.get("favorite")]
