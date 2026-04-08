"""
百度百科页面解析器
从 HTML 中提取标题、章节、图片、段落等结构化内容
"""
import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup, NavigableString, Tag


@dataclass
class ImageItem:
    src: str
    alt: str
    local_path: Optional[str] = None
    hash: str = ""

    def __post_init__(self):
        if not self.hash and self.src:
            self.hash = hashlib.md5(self.src.encode()).hexdigest()[:12]


@dataclass
class Section:
    level: int  # 1=h2, 2=h3, 3=h4
    title: str
    content_html: str  # 原始 HTML
    text: str  # 纯文本
    images: list[ImageItem] = field(default_factory=list)


@dataclass
class BasicInfoItem:
    label: str
    value: str


@dataclass
class BaikeDocument:
    url: str
    title: str
    subtitle: str = ""
    basic_info: list[BasicInfoItem] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    all_images: list[ImageItem] = field(default_factory=list)
    html_content: str = ""  # 完整正文 HTML

    @property
    def text_content(self) -> str:
        parts = [f"# {self.title}\n"]
        if self.subtitle:
            parts.append(f"{self.subtitle}\n")
        if self.basic_info:
            parts.append("\n## 基本信息\n")
            for item in self.basic_info:
                parts.append(f"- **{item.label}**：{item.value}")
            parts.append("\n")
        for section in self.sections:
            parts.append(f"\n## {section.title}\n")
            parts.append(section.text + "\n")
        return "\n".join(parts)


def _extract_images_from_tag(tag: Tag) -> list[ImageItem]:
    """从标签中提取所有图片"""
    images = []
    for img in tag.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        if not src or src.startswith("data:"):
            continue
        if any(x in src for x in ["baidu.com/logo", "tracking", "analytics"]):
            continue
        alt = img.get("alt", "")
        images.append(ImageItem(src=src, alt=alt))
    return images


def _get_inline_text(tag: Tag) -> str:
    """获取标签内所有文字，保留加粗等语义"""
    parts = []
    for child in tag.descendants:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                parts.append(text)
        elif child.name == "br":
            parts.append("\n")
    return "".join(parts).strip()


def _clean_html(html: str) -> str:
    """清理 HTML，移除脚本等"""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style", "iframe", "noscript"]):
        tag.decompose()
    return str(soup)


def _class_level(classes: list[str]) -> int:
    """从 CSS 类名推断标题级别"""
    # level-N in class → h(N)
    for c in classes:
        m = re.search(r'level[-_]?(\d)', c)
        if m:
            return int(m.group(1))
    return 2  # 默认为 h2


class BaikeParser:
    """百度百科页面解析"""

    def __init__(self, html: str, url: str):
        self.html = html
        self.url = url
        self.soup = BeautifulSoup(html, "lxml")

    def parse(self) -> BaikeDocument:
        title = self._extract_title()
        subtitle = self._extract_subtitle()
        basic_info = self._extract_basic_info()
        sections = self._extract_sections()
        all_images = self._extract_all_images()

        return BaikeDocument(
            url=self.url,
            title=title,
            subtitle=subtitle,
            basic_info=basic_info,
            sections=sections,
            all_images=all_images,
            html_content=self._extract_main_content(),
        )

    def _extract_title(self) -> str:
        h1 = self.soup.select_one("h1.lemma-title")
        if h1:
            return h1.get_text(strip=True)
        h1 = self.soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        title_tag = self.soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True).split("_")[0].split("（")[0].strip()
        return "未知词条"

    def _extract_subtitle(self) -> str:
        # 新版百度百科：div.lemmaSummary_zo07Z 或 div.summary_yMVrd
        for sel in ("div.lemmaSummary_zo07Z", "div.summary_yMVrd", "div.lemma-summary"):
            el = self.soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                # 清理 "播报" 等后缀
                text = re.sub(r'[\s\n\r]+', ' ', text)
                return text[:300]
        return ""

    def _extract_basic_info(self) -> list[BasicInfoItem]:
        """提取基本信息栏（dl/dt/dd 表格）"""
        items = []
        info_div = self.soup.select_one("div.basic-info") or \
                   self.soup.find("dl", class_="basic-info")
        if not info_div:
            return items
        current_label = ""
        for child in info_div.children:
            if not isinstance(child, Tag):
                continue
            if child.name == "dt":
                current_label = child.get_text(strip=True)
            elif child.name == "dd" and current_label:
                value = child.get_text(strip=True)
                if value and value != "null":
                    items.append(BasicInfoItem(label=current_label, value=value))
                current_label = ""
        return items

    def _extract_main_content(self) -> str:
        """提取主内容区 HTML"""
        content = (
            self.soup.select_one("div.J-lemma-content") or
            self.soup.select_one("div#lemmaBody") or
            self.soup.select_one("div.lemma-lemma") or
            self.soup.select_one("div#root")
        )
        if content:
            return _clean_html(str(content))
        return _clean_html(str(self.soup.body)) if self.soup.body else ""

    def _extract_sections(self) -> list[Section]:
        """
        按章节提取内容（适配新版百度百科结构）

        页面结构：
          div.J-lemma-content
            div.J-pgc-content        # 子内容
            div.paraTitle_ag9fe.level-1  # h2 章节标题
            div.para_z4tCL           # 段落
            div.paraTitle_ag9fe.level-2  # h3 子章节标题
            div.para_z4tCL           # 段落
        """
        sections = []
        content = (
            self.soup.select_one("div.J-lemma-content") or
            self.soup.select_one("div#lemmaBody") or
            self.soup.select_one("div.lemma-lemma")
        )
        if not content:
            return sections

        current_section: Optional[Section] = None
        current_tags: list[Tag] = []

        def flush_section():
            nonlocal current_section, current_tags
            if current_section is not None:
                current_section.content_html = _clean_html(
                    "".join(str(t) for t in current_tags)
                )
                current_section.text = _get_inline_text(
                    BeautifulSoup(current_section.content_html, "lxml")
                )
                current_section.images = _extract_images_from_tag(
                    BeautifulSoup(current_section.content_html, "lxml")
                )
                sections.append(current_section)
                current_section = None
                current_tags = []

        for child in content.children:
            if not isinstance(child, Tag):
                continue

            cls = child.get("class", [])

            # 章节标题 div
            if "paraTitle_ag9fe" in cls:
                # 保存上一节
                flush_section()

                # 提取标题：找嵌套的 h2/h3/h4
                heading_tag = child.find(["h1", "h2", "h3", "h4"], recursive=False)
                if not heading_tag:
                    heading_tag = child.find(["h1", "h2", "h3", "h4"])
                title = heading_tag.get_text(strip=True) if heading_tag else child.get_text(strip=True)
                # 清理"播报"等后缀
                title = re.sub(r'\s*播报\s*$', '', title)
                title = re.sub(r'\s+', ' ', title)
                title = re.sub(r'\[.*?\]', '', title).strip()

                level = _class_level(cls)

                current_section = Section(
                    level=level,
                    title=title,
                    content_html="",
                    text="",
                    images=[],
                )
                continue

            # 段落 div 或其他内容标签
            if child.get_text(strip=True):
                current_tags.append(child)

        # 保存最后一节
        flush_section()
        return sections

    def _extract_all_images(self) -> list[ImageItem]:
        """提取页面所有图片"""
        images = []
        seen = set()
        for img in self.soup.find_all("img"):
            src = img.get("data-src") or img.get("src") or ""
            if not src or src.startswith("data:") or src in seen:
                continue
            if any(x in src for x in ["baidu.com/logo", "tracking", "analytics"]):
                continue
            seen.add(src)
            alt = img.get("alt", "")
            images.append(ImageItem(src=src, alt=alt))
        return images
