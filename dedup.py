"""
去重管理
基于 URL hash + 内容 hash 双重去重
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent))
import config


class DedupManager:
    """去重管理器"""

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or config.STATE_FILE
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                return {"downloaded": []}
        return {"downloaded": []}

    def _save_state(self):
        self.state_file.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def url_key(self, url: str) -> str:
        """计算 URL 的去重 key"""
        return hashlib.md5(url.encode()).hexdigest()[:16]

    def is_url_downloaded(self, url: str) -> bool:
        """检查 URL 是否已下载"""
        key = self.url_key(url)
        return any(
            entry.get("url_key") == key
            for entry in self.state["downloaded"]
        )

    def is_content_downloaded(self, title: str, first_text: str) -> bool:
        """检查内容是否已下载（基于标题+首段 hash）"""
        content_key = hashlib.md5(
            f"{title}::{first_text[:200]}".encode()
        ).hexdigest()[:16]
        return any(
            entry.get("content_key") == content_key
            for entry in self.state["downloaded"]
        )

    def mark_downloaded(
        self,
        url: str,
        title: str,
        first_text: str = "",
        files: Optional[list[str]] = None,
    ):
        """标记为已下载"""
        if self.is_url_downloaded(url):
            return  # 已存在，跳过

        entry = {
            "url": url,
            "url_key": self.url_key(url),
            "title": title,
            "content_key": hashlib.md5(
                f"{title}::{first_text[:200]}".encode()
            ).hexdigest()[:16],
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "files": files or [],
        }
        self.state["downloaded"].append(entry)
        self._save_state()

    def update_files(self, url: str, files: list[str]):
        """更新已下载条目的文件列表"""
        key = self.url_key(url)
        for entry in self.state["downloaded"]:
            if entry.get("url_key") == key:
                entry["files"] = files
                self._save_state()
                return

    def get_downloaded_count(self) -> int:
        return len(self.state["downloaded"])

    def reset(self):
        """重置所有状态（慎用）"""
        self.state = {"downloaded": []}
        self._save_state()
        print("✓ 状态已重置")
