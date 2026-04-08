# 百度百科下载器

通过浏览器自动化抓取百度百科词条，保留原文文字、图片和章节结构，输出为 **PDF** 或 **DOCX** 格式。支持批量下载、关键词搜索和 AI 发现模式。

## 安装

```bash
cd baike-downloader
pip install -r requirements.txt
playwright install chromium  # 安装浏览器
```

## 快速开始

```bash
# 单条下载
python -m baike_downloader download "人工智能" --format both

# 批量下载（编辑 keywords.json 后）
python -m baike_downloader batch --format both

# 搜索相关词条并追加到 keywords.json
python -m baike_downloader search "人工智能" --append

# 查看下载状态
python -m baike_downloader status -v

# 重置状态
python -m baike_downloader reset --confirm
```

## 配置

编辑 `keywords.json` 修改关键词列表：

```json
{
  "keywords": ["人工智能", "机器学习", "深度学习"]
}
```

## 输出目录

- **PDF/DOCX**: `output/YYYY-MM-DD/`
- **图片缓存**: `media/`
- **下载状态**: `state.json`

## 架构

```
scraper/
  browser.py      — Playwright 浏览器管理
  baike_parser.py — 页面解析（标题/章节/图片）
  downloader.py   — 图片资源下载
converters/
  pdf_converter.py  — PDF 生成
  docx_converter.py — DOCX 生成
dedup.py          — 去重管理
cli.py            — 命令行入口
```
