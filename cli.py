#!/usr/bin/env python3
"""
百度百科下载器 — CLI 入口
"""
import argparse
import json
import sys
import time
import re
from pathlib import Path
from datetime import datetime

# 确保包路径可用
sys.path.insert(0, str(Path(__file__).parent))

import config
from scraper.browser import get_browser
from scraper.baike_parser import BaikeParser
from scraper.downloader import ResourceDownloader
from converters.pdf_converter import PDFConverter
from converters.docx_converter import DOCXConverter
from dedup import DedupManager


def normalize_baike_url(url: str) -> str:
    """规范化百度百科 URL"""
    url = url.strip()
    # 已完整 URL
    if url.startswith("http"):
        return url
    # /item/xxx 路径
    if url.startswith("/item/"):
        return f"https://baike.baidu.com{url}"
    # 直接是词条名
    return f"https://baike.baidu.com/item/{url}"


def ensure_output_dir() -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    out = config.OUTPUT_DIR / today
    out.mkdir(exist_ok=True)
    return out


def download_single(
    url: str,
    output_format: str,
    dedup: DedupManager,
    browser_mgr,
    force: bool = False,
) -> bool:
    """
    下载单个词条
    返回 True 表示成功，False 表示跳过或失败
    """
    url = normalize_baike_url(url)
    title_slug = url.split("/item/")[-1].split("?")[0].split("/")[-1]

    print(f"\n{'='*60}")
    print(f"下载: {url}")

    # 去重检查（纯内存操作，无需网络）
    if not force and dedup.is_url_downloaded(url):
        print(f"  ⏭ 已下载过，跳过（使用 --force 强制重新下载）")
        return None  # None = skip，无需等待

    page = browser_mgr.new_page()
    try:
        # 访问页面
        print(f"  → 正在访问页面...")
        page.goto(url, wait_until="load", timeout=config.BROWSER_CONFIG["timeout"])
        # 等待 JS 渲染完成
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        # 滚动页面触发懒加载图片
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
        time.sleep(1)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight * 2 / 3)")
        time.sleep(1)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        # 获取 HTML
        html = page.content()
        if not html or len(html) < 5000:
            print(f"  ✗ 页面内容异常，可能被反爬或页面不存在")
            return False

        # 检测是否为词条页面
        if "百度百科-验证" in html or "验证" in page.title():
            print(f"  ✗ 触发了验证页面，需要手动处理或降低请求频率")
            return False

        title = page.title().split("_")[0].split("（")[0].strip()
        print(f"  ✓ 页面加载成功: {title}")

        # 解析页面
        print(f"  → 解析页面内容...")
        parser = BaikeParser(html, url)
        doc = parser.parse()
        print(f"  ✓ 解析完成: {len(doc.sections)} 个章节, {len(doc.all_images)} 张图片")

        if not doc.title or doc.title == "未知词条":
            print(f"  ✗ 无法解析词条标题")
            return False

        # 下载图片（从已滚动渲染的页面获取 URL）
        print(f"  → 下载图片资源...")
        downloader = ResourceDownloader(config.MEDIA_DIR)
        img_urls = page.evaluate("""
            () => {
                const imgs = document.querySelectorAll('img');
                const seen = new Set();
                const urls = [];
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

        # 生成输出文件名
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', doc.title)[:50]
        output_dir = ensure_output_dir()

        saved_files = []

        # 转换为 PDF
        if output_format in ("pdf", "both"):
            pdf_path = output_dir / f"{safe_title}.pdf"
            try:
                pdf_conv = PDFConverter(browser_mgr)
                pdf_conv.convert(doc, pdf_path, url_to_path)
                saved_files.append(str(pdf_path))
            except Exception as e:
                print(f"  ⚠ PDF 生成失败: {e}")

        # 转换为 DOCX
        if output_format in ("docx", "both"):
            docx_path = output_dir / f"{safe_title}.docx"
            try:
                docx_conv = DOCXConverter()
                docx_conv.convert(doc, docx_path, url_to_path)
                saved_files.append(str(docx_path))
            except Exception as e:
                print(f"  ⚠ DOCX 生成失败: {e}")

        if saved_files:
            dedup.mark_downloaded(
                url=url,
                title=doc.title,
                first_text=doc.subtitle or (doc.sections[0].text if doc.sections else ""),
                files=saved_files,
            )
            print(f"  ✓ 完成！已保存 {len(saved_files)} 个文件")
            return True
        else:
            print(f"  ✗ 未能生成任何文件")
            return False

    except Exception as e:
        print(f"  ✗ 下载过程异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        page.close()


def cmd_download(args):
    dedup = DedupManager()
    browser_mgr = get_browser()

    try:
        browser_mgr.start()
        success = download_single(
            url=args.url,
            output_format=args.format,
            dedup=dedup,
            browser_mgr=browser_mgr,
            force=args.force,
        )
        # None=跳过(不算失败), True=成功, False=失败
        sys.exit(0 if success is not False else 1)
    finally:
        browser_mgr.close()


def cmd_batch(args):
    """批量下载"""
    keywords_file = Path(args.keywords or config.KEYWORDS_FILE)
    if not keywords_file.exists():
        print(f"✗ 关键词文件不存在: {keywords_file}")
        print(f"  请创建 keywords.json，格式：{{\"keywords\": [\"词条1\", \"词条2\", ...]}}")
        sys.exit(1)

    data = json.loads(keywords_file.read_text(encoding="utf-8"))
    keywords = data.get("keywords", [])

    if not keywords:
        print("✗ keywords.json 中没有关键词")
        sys.exit(1)

    print(f"开始批量下载，共 {len(keywords)} 个词条")
    print(f"格式: {args.format}")
    print(f"关键词文件: {keywords_file}")
    print("-" * 40)

    dedup = DedupManager()
    browser_mgr = get_browser()

    try:
        browser_mgr.start()
        success_count = 0
        skip_count = 0
        fail_count = 0

        for i, kw in enumerate(keywords, 1):
            kw = kw.strip()
            if not kw:
                continue

            print(f"\n[{i}/{len(keywords)}] 处理: {kw}")
            ok = download_single(
                url=normalize_baike_url(kw),
                output_format=args.format,
                dedup=dedup,
                browser_mgr=browser_mgr,
                force=args.force,
            )
            if ok is None:
                # 跳过（已下载过）
                skip_count += 1
                # 跳过不需要等待，继续下一条
            elif ok:
                success_count += 1
                if i < len(keywords):
                    print(f"  等待 {config.REQUEST_INTERVAL}s ...")
                    time.sleep(config.REQUEST_INTERVAL)
            else:
                fail_count += 1
                if i < len(keywords):
                    print(f"  等待 {config.REQUEST_INTERVAL}s ...")
                    time.sleep(config.REQUEST_INTERVAL)

        print(f"\n{'='*60}")
        print(f"批量下载完成:")
        print(f"  成功: {success_count}")
        print(f"  跳过: {skip_count}")
        print(f"  失败: {fail_count}")
        print(f"输出目录: {ensure_output_dir()}")

    finally:
        browser_mgr.close()


def cmd_status(args):
    """查看下载状态"""
    dedup = DedupManager()
    count = dedup.get_downloaded_count()
    print(f"已下载词条数: {count}")
    if args.verbose and count > 0:
        for entry in dedup.state.get("downloaded", []):
            print(f"  [{entry.get('downloaded_at', '')[:10]}] {entry.get('title', '')}")
            for f in entry.get("files", []):
                print(f"    - {f}")


def cmd_reset(args):
    """重置下载状态"""
    dedup = DedupManager()
    if args.confirm:
        dedup.reset()
    else:
        print("使用 --confirm 确认重置")


def cmd_search(args):
    """搜索百度百科获取相关词条"""
    keyword = args.keyword
    url = f"https://baike.baidu.com/search?word={keyword}"
    print(f"搜索: {keyword}")
    print(f"URL: {url}")

    browser_mgr = get_browser()
    try:
        browser_mgr.start()
        page = browser_mgr.new_page()
        page.goto(url, wait_until="load", timeout=config.BROWSER_CONFIG["timeout"])
        time.sleep(2)

        # 提取搜索结果链接（排除锚点#/fromModule=等参数）
        result_urls = page.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href*="/item/"]');
                const seen = new Set();
                const results = [];
                links.forEach(a => {
                    // 只取主词条 URL，排除 #锚点 和 fromModule 参数
                    let href = a.href.split('#')[0].split('?fromModule')[0];
                    if (!href || seen.has(href) || !href.includes('/item/')) return;
                    seen.add(href);
                    results.push({title: a.textContent.trim(), url: href});
                });
                return results.slice(0, 20);
            }
        """)

        if not result_urls:
            print("未找到相关词条")
            page.close()
            return

        print(f"\n找到 {len(result_urls)} 个相关词条:")
        for i, r in enumerate(result_urls, 1):
            print(f"  {i}. {r['title']}")
            print(f"     {r['url']}")

        # 可选：追加到 keywords.json
        if args.append:
            kw_file = config.KEYWORDS_FILE
            existing = set()
            if kw_file.exists():
                data = json.loads(kw_file.read_text(encoding="utf-8"))
                existing = set(data.get("keywords", []))

            new_kws = [r["url"] for r in result_urls if r["url"] not in existing]
            if new_kws:
                all_kws = list(existing) + new_kws
                kw_file.write_text(
                    json.dumps({"keywords": all_kws}, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                print(f"\n✓ 已追加 {len(new_kws)} 个词条到 keywords.json")

        page.close()

    finally:
        browser_mgr.close()


def main():
    parser = argparse.ArgumentParser(description="百度百科下载器")
    sub = parser.add_subparsers(dest="command")

    # download
    dl = sub.add_parser("download", help="下载单个词条")
    dl.add_argument("url", help="百度百科 URL 或词条名")
    dl.add_argument("--format", "-f", choices=["pdf", "docx", "both"], default="both",
                    help="输出格式（默认 both）")
    dl.add_argument("--force", action="store_true", help="强制重新下载（跳过去重）")

    # batch
    batch = sub.add_parser("batch", help="批量下载（按 keywords.json）")
    batch.add_argument("--keywords", "-k", help="关键词 JSON 文件路径")
    batch.add_argument("--format", "-f", choices=["pdf", "docx", "both"], default="both")
    batch.add_argument("--force", action="store_true", help="强制重新下载")

    # search
    search = sub.add_parser("search", help="搜索相关词条")
    search.add_argument("keyword", help="搜索关键词")
    search.add_argument("--append", "-a", action="store_true", help="追加结果到 keywords.json")

    # status
    sub.add_parser("status", help="查看下载状态").add_argument("-v", "--verbose", action="store_true")

    # reset
    reset = sub.add_parser("reset", help="重置下载状态")
    reset.add_argument("--confirm", action="store_true", help="确认重置")

    args = parser.parse_args()

    if args.command == "download":
        cmd_download(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "reset":
        cmd_reset(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
