# 百度百科下载器 — SPEC.md

## 1. 目标与愿景

一个 AI 驱动的百度百科词条批量下载工具，通过浏览器自动化抓取页面内容，按章节保留原文文字和图片，支持 PDF / DOCX 两种格式输出，内置去重机制。可通过关键词列表或 AI 主动发现相关词条进行下载，目标是积累高质量、可编辑的本地测试数据集。

## 2. 整体架构

```
baike_downloader/
├── SPEC.md
├── README.md
├── requirements.txt
├── config.py              # 全局配置
├── state.json             # 下载状态（去重用，JSON 文件）
├── keywords.json           # 关键词列表（用户编辑）
├── scraper/
│   ├── __init__.py
│   ├── browser.py         # Playwright 浏览器管理
│   ├── baike_parser.py    # 百度百科页面解析
│   └── downloader.py       # 资源下载（图片/音频/视频）
├── converters/
│   ├── __init__.py
│   ├── pdf_converter.py   # → PDF
│   └── docx_converter.py  # → DOCX
├── dedup.py               # 去重逻辑
├── cli.py                 # 命令行入口
├── gui.py                 # 图形界面入口（可选）
└── ai_discovery.py        # AI 发现相关词条（调用 LLM）
```

## 3. 核心流程

### 3.1 单条下载流程

```
输入 URL 或关键词
  → 检查 state.json 是否已下载（去重）
  → 未下载：启动 Playwright 浏览器
  → 访问百度百科页面
  → 解析页面：提取标题、章节、段落文字、图片
  → 下载所有图片到本地 media/ 目录
  → 更新 HTML 中的图片路径为本地路径
  → 选择格式：
      PDF:  用 Playwright print_to_pdf()
      DOCX: 用 python-docx 按章节重建文档
  → 保存到 output/YYYY-MM-DD/ 目录
  → 记录到 state.json
```

### 3.2 批量下载流程

```
读取 keywords.json 中的关键词列表
  → 遍历每个关键词
  → 搜索百度百科：https://baike.baidu.com/search?word={keyword}
  → 解析搜索结果页面，获取相关词条 URL
  → 对每个词条执行单条下载流程
  → 支持进度打印和断点续传（state.json 记录已完成的）
```

### 3.3 AI 发现模式

```
用户输入一个领域种子词（如"人工智能"）
  → 调用 LLM 分析页面内容，推测相关词条
  → 将推测结果追加到 keywords.json
  → 自动触发批量下载
```

## 4. 页面解析规范（百度百科）

目标：从 `https://baike.baidu.com/item/{slug}` 解析出：

- **标题**: `<h1 class="lemma-title">` 或 `h1`
- **副标题/描述**: `<div class="lemma-desc">`
- **基本信息栏**: `<div class="basic-info">`（表格形式，含结构化数据）
- **目录导航**: `<div class="catalog-list">` 或侧边栏目录
- **正文章节**: `<div class="lemma-lemma"` 内按 `<h2>`/`<h3>` 分割
- **图片**: `<img>` 标签，收集 `src`，下载到 `media/{hash}.{ext}`
- **段落文字**: `<p>` 标签内文本

解析策略：
- 主内容区：`.lemma-lemma` 或 `#lemmaBody`
- 章节通过 `<h2 class="title-text">` 分割
- 图片 `data-src` > `src`（懒加载）
- 所有文字节点保留，保留加粗/斜体等 inline 样式文本

## 5. 输出格式规范

### 5.1 PDF
- A4 页面，页边距 2cm
- 标题页：词条名 + 下载时间 + 来源 URL
- 目录页（自动生成书签）
- 正文按章节分页
- 图片居中，最大宽度 80%
- 保留中文字体（Noto Sans CJK / 系统黑体）

### 5.2 DOCX
- 标题 1：词条名
- 标题 2：各章节名
- 正文：宋体/微软雅黑，11pt，1.5 倍行距
- 图片：独立段落，居中，带章节标题作为图注
- 基本信息栏：转为 2 列表格
- 所有文字可选中复制

## 6. 去重机制

- **URL 去重**：计算 `md5(url)` 作为 key，存入 `state.json`
- **内容去重**：首次下载时记录 `title + first_200_chars` hash，后续比较
- **文件去重**：已存在的 `output/` 文件跳过（可强制覆盖）
- **state.json 格式**：
```json
{
  "downloaded": [
    {
      "url": "https://baike.baidu.com/item/...",
      "title": "词条名",
      "downloaded_at": "2026-04-08T11:00:00+08:00",
      "files": ["output/xxx.pdf", "output/xxx.docx"]
    }
  ]
}
```

## 7. CLI 接口

```bash
# 单条下载
python -m baike_downloader.cli download "https://baike.baidu.com/item/人工智能" --format pdf

# 批量下载（按关键词列表）
python -m baike_downloader.cli batch --keywords keywords.json --format both

# AI 发现相关词条
python -m baike_downloader.cli discover "人工智能" --depth 2 --limit 20

# 查看下载状态
python -m baike_downloader.cli status

# 清除状态（重新下载）
python -m baike_downloader.cli reset
```

## 8. 依赖

```
playwright>=1.40
python-docx>=1.1.0
pillow>=10.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
pyyaml>=6.0
人人副词>=0.0.0
```

## 9. 优先级

- **P0**: 单条 URL 下载（PDF + DOCX）+ 去重
- **P1**: 批量关键词下载 + 进度/断点
- **P2**: AI 发现相关词条
- **P3**: GUI 图形界面
- **P4**: 维基百科适配器（预留接口）

## 10. 已知风险与应对

- 百度百科反爬：使用 Playwright 真实浏览器 UA，控制请求间隔 2-3s
- 页面结构变更：解析失败时记录原始 HTML 供调试
- 图片跨域：Playwright 下载时处理 Cookie/Referer
