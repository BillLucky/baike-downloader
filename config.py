"""
全局配置
"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.resolve()

# 下载输出目录
OUTPUT_DIR = PROJECT_ROOT / "output"
MEDIA_DIR = PROJECT_ROOT / "media"
STATE_FILE = PROJECT_ROOT / "state.json"
KEYWORDS_FILE = PROJECT_ROOT / "keywords.json"

# 确保目录存在
OUTPUT_DIR.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)

# 浏览器配置
BROWSER_CONFIG = {
    "headless": True,
    "user_agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "viewport": {"width": 1280, "height": 800},
    "timeout": 30000,
}

# 下载间隔（秒），防止反爬
REQUEST_INTERVAL = 2

# 图片下载配置
IMAGE_CONFIG = {
    "max_width": 800,
    "max_height": 600,
    "user_agent": BROWSER_CONFIG["user_agent"],
}

# PDF 渲染配置
PDF_CONFIG = {
    "format": "A4",
    "margin": {"top": "2cm", "bottom": "2cm", "left": "2cm", "right": "2cm"},
    "print_background": True,
}

# DOCX 样式配置
DOCX_CONFIG = {
    "page_width": 21,  # cm, A4
    "page_height": 29.7,
    "margin_top": 2.5,
    "margin_bottom": 2.5,
    "margin_left": 3.0,
    "margin_right": 3.0,
    "body_font": "宋体",
    "body_size": 11,
    "heading1_font": "黑体",
    "heading1_size": 22,
    "heading2_font": "黑体",
    "heading2_size": 16,
    "line_spacing": 1.5,
}
