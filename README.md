# 百度百科下载器

通过 Playwright 浏览器自动化抓取百度百科词条，保留原文文字、图片和章节结构，输出为 **PDF** 或 **DOCX** 格式。支持批量下载、关键词搜索和内置去重机制。

> GitHub: https://github.com/BillLucky/baike-downloader

## 功能特性

- **PDF / DOCX 双格式输出**，所有文字可复制
- **按章节解析**，保留原始标题结构和段落
- **图片自动下载**，支持 WebP / SVG / PNG / JPG 自动识别
- **懒加载图片滚动触发**，最大化合图数量
- **自动去重**（基于 URL hash + 内容 hash）
- **批量下载**（读取 keywords.json 关键词列表）
- **关键词搜索**（搜索相关词条并追加到列表）

## 安装

```bash
pip install -r requirements.txt
playwright install chromium
```

## 快速开始

```bash
# 单条下载（支持 URL 或词条名）
python -m baike_downloader download "人工智能" --format both

# 强制重新下载（跳过去重）
python -m baike_downloader download "https://baike.baidu.com/item/深度学习" --force

# 批量下载（编辑 keywords.json 后）
python -m baike_downloader batch --format both

# 搜索相关词条
python -m baike_downloader search "人工智能" --append

# 查看下载状态
python -m baike_downloader status -v

# 重置状态（重新下载）
python -m baike_downloader reset --confirm
```

## 配置

编辑 `keywords.json` 修改批量下载的关键词列表：

```json
{
  "keywords": ["人工智能", "机器学习", "深度学习"]
}
```

修改全局配置编辑 `config.py`（下载间隔、浏览器设置等）。

## 项目结构

```
baike_downloader/
├── config.py              # 全局配置
├── dedup.py               # 去重管理（state.json）
├── cli.py                 # 命令行入口
├── keywords.json           # 关键词列表
├── scraper/
│   ├── browser.py         # Playwright 浏览器管理
│   ├── baike_parser.py    # 页面解析（章节/图片/摘要）
│   └── downloader.py      # 图片下载（自动识别文件类型）
├── converters/
│   ├── pdf_converter.py    # → PDF（Playwright print_to_pdf）
│   └── docx_converter.py  # → DOCX（python-docx）
├── output/                # 下载文件输出目录（按日期分目录）
├── media/                 # 图片缓存（自动去重）
└── state.json             # 下载记录
```

## 实测清代词条下载

| 类别 | 词条 | 章节数 | 图片数 | PDF 大小 | DOCX 大小 |
|------|------|--------|--------|----------|-----------|
| 历史事件 | 太平天国运动 | 9 | 57 | - | - |
| 历史事件 | 辛亥革命 | 31 | 59 | - | - |
| 历史人物 | 爱新觉罗·弘历（乾隆） | 47 | 119 | - | - |
| 历史人物 | 和珅 | 21 | 63 | - | - |
| 名胜地点 | 圆明园 | 45 | 171 | - | - |
| 名胜地点 | 北京故宫 | 36 | 148 | - | - |

> 注：实际文件存储在 `output/YYYY-MM-DD/` 目录下

## 输出文件

- **PDF**: A4 格式，带页码和来源标注，图片居中嵌入
- **DOCX**: 标题 1/2 样式，段落首行缩进，图片居中，文字可选中复制

## 依赖

```
playwright>=1.40
python-docx>=1.1.0
Pillow>=10.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
pyyaml>=6.0
```

## 后续计划

- P2: AI 发现相关词条（调用 LLM 推测扩展词条）
- P3: GUI 图形界面
- P4: 维基百科适配器（预留接口）
