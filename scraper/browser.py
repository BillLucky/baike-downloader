"""
Playwright 浏览器管理
"""
import asyncio
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class BrowserManager:
    """浏览器生命周期管理"""

    _instance = None
    _playwright = None
    _browser: Browser = None
    _context: BrowserContext = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def start(self):
        if self._browser is not None:
            return
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=config.BROWSER_CONFIG["headless"]
        )
        self._context = self._browser.new_context(
            user_agent=config.BROWSER_CONFIG["user_agent"],
            viewport=config.BROWSER_CONFIG["viewport"],
        )
        # 设置额外请求头
        self._context.set_extra_http_headers({
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def new_page(self) -> Page:
        if self._context is None:
            self.start()
        return self._context.new_page()

    def close(self):
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def screenshot(self, page: Page, path: Path):
        """页面截图"""
        page.screenshot(path=str(path), full_page=True)

    @property
    def browser(self) -> Browser:
        if self._browser is None:
            self.start()
        return self._browser


# 全局单例
_browser_manager = BrowserManager()


def get_browser() -> BrowserManager:
    return _browser_manager
