"""
资源下载器（图片等）
"""
import hashlib
import time
import requests
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def _get_ext_from_url(url: str) -> str:
    """从 URL 提取文件扩展名"""
    parsed = urlparse(url)
    path = parsed.path
    ext = Path(path).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        return ext
    # 默认 png
    return ".jpg"


def _detect_ext(content: bytes) -> Optional[str]:
    """根据文件魔数检测真实文件类型"""
    if len(content) < 4:
        return None
    # PNG
    if content[:8] == b'\x89PNG\r\n\x1a\n':
        return ".png"
    # JPEG
    if content[:3] == b'\xff\xd8\xff':
        return ".jpg"
    # GIF
    if content[:6] in (b'GIF87a', b'GIF89a'):
        return ".gif"
    # WebP (RIFF...WEBP)
    if content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        return ".webp"
    # SVG (XML)
    if content[:5] == b'<?xml' or content[:4] == b'<svg':
        return ".svg"
    # BMP
    if content[:2] == b'BM':
        return ".bmp"
    return None


def _is_valid_url(url: str) -> bool:
    """检查是否为有效的图片 URL"""
    if not url:
        return False
    if url.startswith("data:"):
        return False
    parsed = urlparse(url)
    return bool(parsed.scheme in ("http", "https") and parsed.netloc)


class ResourceDownloader:
    """资源下载器"""

    def __init__(self, media_dir: Optional[Path] = None):
        self.media_dir = media_dir or config.MEDIA_DIR
        self.media_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.IMAGE_CONFIG["user_agent"],
            "Referer": "https://baike.baidu.com/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self._local_paths: dict[str, str] = {}

    def download_image(self, url: str, hash_key: str) -> Optional[str]:
        """
        下载单个图片，返回本地路径
        根据内容自动检测真实文件类型
        """
        if not _is_valid_url(url):
            return None

        if url in self._local_paths:
            return self._local_paths[url]

        try:
            resp = self.session.get(url, timeout=15, stream=True)
            resp.raise_for_status()
            content = resp.content

            # 跳过太小（<1KB）的响应
            if len(content) < 1024:
                return None

            # 自动检测文件类型（魔数）
            ext = _detect_ext(content) or _get_ext_from_url(url)
            final_name = f"{hash_key}{ext}"
            final_path = self.media_dir / final_name

            with open(final_path, "wb") as f:
                f.write(content)

            self._local_paths[url] = str(final_path)
            return str(final_path)
        except Exception as e:
            print(f"  ⚠ 图片下载失败: {url} -> {e}")
            return None

    def download_images(self, urls: list[str]) -> dict[str, str]:
        """
        并发下载多张图片，返回 {url: local_path}
        """
        results = {}
        hash_keys = {
            url: hashlib.md5(url.encode()).hexdigest()[:12]
            for url in urls
        }

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self.download_image, url, hash_keys[url]): url
                for url in urls
            }
            for future in as_completed(futures):
                url = futures[future]
                try:
                    local_path = future.result()
                    if local_path:
                        results[url] = local_path
                except Exception as e:
                    print(f"  ⚠ 图片处理异常: {url} -> {e}")

        return results

    def replace_html_images(self, html: str, url_to_path: dict[str, str]) -> str:
        """
        将 HTML 中的图片 URL 替换为本地路径
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("src")
            if src and src in url_to_path:
                img["src"] = url_to_path[src]
                img["data-src"] = ""  # 清除懒加载属性

        return str(soup)


def download_page_resources(page, media_dir: Optional[Path] = None) -> dict[str, str]:
    """
    从 Playwright 页面提取并下载所有图片
    页面应该已经完成滚动触发懒加载
    """
    downloader = ResourceDownloader(media_dir)

    # 获取所有图片 URL（优先取 data-src）
    img_urls = page.evaluate("""
        () => {
            const imgs = document.querySelectorAll('img');
            const urls = [];
            const seen = new Set();
            imgs.forEach(img => {
                const src = img.dataset.src || img.src;
                if (src && !src.startsWith('data:') && src.startsWith('http') && !seen.has(src)) {
                    seen.add(src);
                    urls.push(src);
                }
            });
            return urls;
        }
    """)

    print(f"  发现 {len(img_urls)} 张图片，开始下载...")
    url_to_path = downloader.download_images(img_urls)
    print(f"  成功下载 {len(url_to_path)} 张图片")

    return url_to_path
