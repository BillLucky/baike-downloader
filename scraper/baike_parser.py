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
    """清理 HTML，移除脚本等，返回 body 内部内容（避免 html/body wrapper）"""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style", "iframe", "noscript"]):
        tag.decompose()
    # 提取 body 内容避免 html/body wrapper
    body = soup.find("body")
    if body:
        return str(body)
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
            div.paraTitle_ag9fe.level-1  # 大节标题
            div.paraTitle_ag9fe.level-2    # 子节标题
            div.para_z4tCL                 # 正文段落

        策略：每个标题都是独立 section
        - level-1: 收集直到下一个 level-1 标题的所有内容（包含 level-2 标题作为嵌入标题）
        - level-2: 收集直属内容（下一个同级或更高优先级标题前）
        """
        sections = []
        content = (
            self.soup.select_one("div.J-lemma-content") or
            self.soup.select_one("div#lemmaBody") or
            self.soup.select_one("div.lemma-lemma")
        )
        if not content:
            return sections

        children = list(content.children)

        def get_level(tag: Tag) -> int:
            cls = tag.get("class", [])
            return _class_level(cls)

        def get_title(tag: Tag) -> str:
            heading_tag = tag.find(["h1", "h2", "h3", "h4"], recursive=False)
            if not heading_tag:
                heading_tag = tag.find(["h1", "h2", "h3", "h4"])
            title = heading_tag.get_text(strip=True) if heading_tag else tag.get_text(strip=True)
            title = re.sub(r'\s*播报\s*$', '', title)
            title = re.sub(r'\s+', ' ', title)
            title = re.sub(r'\[.*?\]', '', title).strip()
            return title

        def make_section(title: str, level: int, content_tags: list[Tag]) -> Section:
            raw_html = "".join(str(t) for t in content_tags)
            cleaned = _clean_html(raw_html)
            soup = BeautifulSoup(cleaned, "html.parser")
            return Section(
                level=level,
                title=title,
                content_html=cleaned,
                text=_get_inline_text(soup),
                images=_extract_images_from_tag(soup),
            )

        i = 0
        while i < len(children):
            child = children[i]
            if not isinstance(child, Tag) or "paraTitle_ag9fe" not in child.get("class", []):
                i += 1
                continue

            level = get_level(child)
            title = get_title(child)

            # level-1: 收集直到下一个 level-1 之前的所有内容
            # level-2+: 收集直到下一个同级或更高优先级之前的内容
            content_tags: list[Tag] = []
            j = i + 1
            while j < len(children):
                next_child = children[j]
                if not isinstance(next_child, Tag):
                    j += 1
                    continue
                next_cls = next_child.get("class", [])
                if "paraTitle_ag9fe" in next_cls:
                    next_level = get_level(next_child)
                    if level == 1:
                        # level-1: 遇到下一个 level-1 就停止（不收集）
                        if next_level == 1:
                            break
                    else:
                        # level-2+: 遇到同级或更高优先级就停止
                        if next_level <= level:
                            break
                if next_child.get_text(strip=True):
                    content_tags.append(next_child)
                j += 1

            # 对于 level-2 及以下：内容可能包含其他子标题（level-3），直接保留原样
            # 这样 level-1 section 的 content_html 会包含子章节标题
            section = make_section(title, level, content_tags)
            # 过滤掉纯子标题的空 section（level-2+ 但几乎没有正文）
            if section.text.strip() or level == 1:
                sections.append(section)
            i = j

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
