"""
PDF 转换器
使用 Playwright print_to_pdf 生成高质量 PDF
"""
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from scraper.baike_parser import BaikeDocument


def build_pdf_html(doc: BaikeDocument, url_to_path: dict[str, str]) -> str:
    """
    将 BaikeDocument 渲染为可打印的 HTML
    """
    from bs4 import BeautifulSoup

    # 替换图片路径
    html_content = doc.html_content
    soup = BeautifulSoup(html_content, "lxml")
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if src and src in url_to_path:
            img["src"] = url_to_path[src]

    # 构建基本信息表格 HTML
    basic_info_html = ""
    if doc.basic_info:
        rows = []
        for item in doc.basic_info:
            rows.append(f"<tr><th>{item.label}</th><td>{item.value}</td></tr>")
        basic_info_html = f"""
        <table class="basic-info">
            <tbody>{"".join(rows)}</tbody>
        </table>
        """

    # 构建章节 HTML
    sections_html = ""
    for section in doc.sections:
        # 替换章节中的图片
        sec_soup = BeautifulSoup(section.content_html or "", "lxml")
        for img in sec_soup.find_all("img"):
            src = img.get("data-src") or img.get("src")
            if src and src in url_to_path:
                img["src"] = url_to_path[src]

        sections_html += f"""
        <div class="section">
            <h{section.level}>{section.title}</h{section.level}>
            <div class="section-body">{str(sec_soup)}</div>
        </div>
        """

    download_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{doc.title} — 百度百科</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'SimSun', serif;
    font-size: 11pt;
    line-height: 1.8;
    color: #222;
    background: #fff;
    padding: 2cm 2.5cm;
    max-width: 100%;
  }}

  /* 标题页 */
  .cover {{
    text-align: center;
    padding: 4cm 0;
    border-bottom: 2px solid #333;
    margin-bottom: 1cm;
  }}
  .cover h1 {{
    font-size: 24pt;
    font-weight: bold;
    color: #111;
    margin-bottom: 0.5cm;
  }}
  .cover .subtitle {{
    font-size: 12pt;
    color: #666;
    margin-bottom: 0.5cm;
  }}
  .cover .meta {{
    font-size: 9pt;
    color: #999;
    margin-top: 1cm;
  }}

  /* 基本信息栏 */
  .basic-info {{
    width: 100%;
    border-collapse: collapse;
    margin: 0.5cm 0;
    font-size: 10pt;
  }}
  .basic-info th, .basic-info td {{
    border: 1px solid #ccc;
    padding: 4pt 8pt;
    text-align: left;
  }}
  .basic-info th {{
    background: #f5f5f5;
    font-weight: bold;
    width: 30%;
  }}

  /* 章节 */
  .section {{
    margin: 0.6cm 0;
  }}
  h2 {{
    font-size: 14pt;
    font-weight: bold;
    color: #111;
    border-left: 4px solid #c31;
    padding-left: 8pt;
    margin: 0.6cm 0 0.3cm;
    page-break-after: avoid;
  }}
  h3 {{
    font-size: 12pt;
    font-weight: bold;
    color: #333;
    margin: 0.4cm 0 0.2cm;
    page-break-after: avoid;
  }}
  h4 {{
    font-size: 11pt;
    font-weight: bold;
    color: #555;
    margin: 0.3cm 0 0.2cm;
    page-break-after: avoid;
  }}

  /* 正文段落 */
  .section-body p {{
    text-indent: 2em;
    margin: 0.15cm 0;
    text-align: justify;
  }}

  /* 图片 */
  img {{
    max-width: 80%;
    max-height: 12cm;
    display: block;
    margin: 0.3cm auto;
    object-fit: contain;
  }}

  /* 列表 */
  ul, ol {{
    margin: 0.2cm 0 0.2cm 1.5em;
  }}
  li {{
    margin: 0.1cm 0;
  }}

  /* 表格 */
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 0.3cm 0;
  }}
  th, td {{
    border: 1px solid #ccc;
    padding: 4pt 6pt;
  }}
  th {{
    background: #f5f5f5;
  }}

  /* 参考来源 */
  .source {{
    margin-top: 1cm;
    padding-top: 0.3cm;
    border-top: 1px solid #ddd;
    font-size: 9pt;
    color: #888;
  }}
</style>
</head>
<body>
<div class="cover">
  <h1>{doc.title}</h1>
  <p class="subtitle">{doc.subtitle}</p>
  <p class="meta">来源：<a href="{doc.url}">{doc.url}</a><br>
  下载时间：{download_time}</p>
</div>

{basic_info_html}

{sections_html}

<div class="source">
  <p>本文档由百度百科下载器自动生成 · <a href="{doc.url}">{doc.url}</a></p>
</div>
</body>
</html>"""

    return html


class PDFConverter:
    """PDF 转换器"""

    def __init__(self, browser_manager):
        self.browser_manager = browser_manager

    def convert(
        self,
        doc: BaikeDocument,
        output_path: Path,
        url_to_path: Optional[dict[str, str]] = None,
    ) -> Path:
        """
        将 BaikeDocument 转为 PDF
        """
        url_to_path = url_to_path or {}
        html = build_pdf_html(doc, url_to_path)

        bm = self.browser_manager
        page = bm.new_page()

        try:
            # 设置内容（不用 networkidle，因为本地图片和字体不会产生网络请求）
            page.set_content(html, wait_until="load", timeout=60000)

            # 等待渲染稳定
            time.sleep(2)

            # 生成 PDF
            page.pdf(
                path=str(output_path),
                format=config.PDF_CONFIG["format"],
                margin=config.PDF_CONFIG["margin"],
                print_background=config.PDF_CONFIG["print_background"],
                display_header_footer=True,
                header_template="<span></span>",
                footer_template=(
                    "<div style='font-size:9pt;color:#888;width:100%;text-align:center;"
                    "margin-bottom:0.5cm;'>第 <span class='pageNumber'></span> 页 "
                    "· <span class='totalPages'></span> 页 · 百度百科下载器</div>"
                ),
            )
            print(f"  ✓ PDF 已保存: {output_path.name}")
            return output_path
        finally:
            page.close()
