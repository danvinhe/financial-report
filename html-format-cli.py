import os
import re
import typer
from bs4 import BeautifulSoup
from opencc import OpenCC
from playwright.sync_api import sync_playwright

app = typer.Typer()

def process_file(file_path, title_prefix):

    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, 'html.parser')

    update_title(file_path, soup, title_prefix)

    # remove_images(file_path, soup)

    add_watermark(file_path, soup)

    adjust_style(file_path, soup)

    soup = tc_to_sc(file_path, soup)

    replace_fonts(file_path, soup)

    new_file_path = file_path.replace(".html", ".sc.html")
    with open(new_file_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    print(f"Formatted HTML: {new_file_path}")

    html_to_pdf(new_file_path)

# 清除文件中的图片
def remove_images(file_path: str, soup: BeautifulSoup):
    svg_images = soup.find_all('img')
    if len(svg_images) <= 1:
        print(f"Skipped images: {file_path}")
        return

    is_first = True
    for image in svg_images:
        if is_first:
            is_first = False
        else:
            image.decompose()


    print(f"Removed images: {file_path}")

def update_title(file_path: str, soup: BeautifulSoup, title_prefix: str):
    # 季度映射
    quarters_kv = {
        "1": "一季报",
        "2": "中报",
        "3": "三季报",
        "4": "年报"
    }
    file_name = os.path.basename(file_path)
    match = re.fullmatch(r"\d{4}Q[1-4]\.html", file_name)
    if match:
        year, quarter = file_name[0:4], file_name[5]
        new_title =  f"{title_prefix}{year}年简体中文版{quarters_kv[quarter]}"
    else:
        new_title =  f"{title_prefix}{file_name[0:len(file_name)-5]}"
    new_title += " | 价格与价值"

    # 替换<title>标签内容
    title_tag = soup.find('title')
    if title_tag is None or title_tag.string == new_title:
        print(f"Skipped title: {file_path}")
        return
    title_tag.string = new_title

    print(f"Updated title: {file_path}")

def add_watermark(file_path: str, soup: BeautifulSoup):
    """
    通过 ::before 伪元素为 .pdf24_02 容器添加水印（纯CSS方案）

    pdf2htmlEX 的 DOM 结构：
      div.page_* (class="pdf24_02") → 每个页面的固定外层容器
    水印挂载在 .pdf24_02::before 上，position: relative 通过 CSS 设置。
    """

    # 在 <head> 中插入水印样式（不修改任何元素的 style 属性）
    head_tag = soup.find('head')
    if head_tag is None:
        print(f"Skipped watermark (no <head> found): {file_path}")
        return
    first_style = head_tag.find('style')
    if first_style is None:
        print(f"Skipped watermark (no <style> found): {file_path}")
        return

    watermark_css = (
        '.pdf24_02 {position: relative;}\n'
        '.pdf24_02::before {content: "公众号·价格与价值";position: absolute;top: 0;left: 0;right: 0;bottom: 0;display: flex;justify-content: center;align-items: center;font-size: 88px;font-weight: bold;color: rgba(0, 0, 0, 0.1);transform: rotate(-45deg);pointer-events: none; z-index: 1;}\n'
    )
    first_style.string = watermark_css + first_style.string

    print(f"Added watermark {file_path}")

def tc_to_sc(file_path: str, soup: BeautifulSoup) -> BeautifulSoup:

    cc = OpenCC('t2s')
    new_html_content = cc.convert(str(soup))

    soup = BeautifulSoup(new_html_content, 'html.parser')
    print(f"Converted TC: {file_path}")

    return soup

def html_to_pdf(file_path: str):
    """使用 Playwright 将 HTML 文件转换为 PDF"""
    pdf_path = file_path.replace(".html", ".pdf")
    abs_path = os.path.abspath(file_path)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{abs_path}")
        page.pdf(
            path=pdf_path,
            print_background=False,
            format='A4',
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            scale=1.4
        )
        browser.close()

    print(f"Exported PDF: {pdf_path}")

def replace_fonts(file_path: str, soup: BeautifulSoup):
    """
    将 pdf2htmlEX 嵌入字体名替换为 macOS 系统字体，
    粗细从字体名拆出为独立的 font-weight。

    两步：1) 删除所有 @font-face；2) 替换普通规则中的 font-family
    """
    # pdf2htmlEX 内部字体名（去前缀后）→ (macOS 系统字体, font-weight, 是否斜体)
    FONT_MAP = {
        # ── 港版宋体 MSungHK ─────────────────────────────────────
        "MSungHK":                      ("MSung", 400, False),
        "MSungHK-Light":                ("MSung", 300, False),
        "MSungHK-Bold":                 ("MSung", 700, False),
        "MSungHK-Light-ETen-B5-H":      ("MSung", 300, False),
        "MSungHK-Bold-ETen-B5-H":       ("MSung", 700, False),
        # ── 港版黑体 MHeiHK ───────────────────────────────────────
        "MHeiHK":                       ("Heiti SC", 400, False),
        "MHeiHK-Light":                 ("Heiti SC", 300, False),
        "MHeiHK-Bold":                  ("Heiti SC", 700, False),
        "MHeiHK-Bold-ETen-B5-H":        ("Heiti SC", 700, False),
        # ── 西文 Times ────────────────────────────────────────────
        "TimesLTStd-Roman":             ("Times New Roman", 400, False),
        "TimesLTStd-Bold":              ("Times New Roman", 700, False),
        "TimesLTStd-BoldItalic":        ("Times New Roman", 700, True),
        "TimesNewRomanPSMT":            ("Times New Roman", 400, False),
        "TimesNewRomanPS-BoldMT":       ("Times New Roman", 700, False),
        "TimesNewRomanPS-BoldItalicMT": ("Times New Roman", 700, True),
        # ── 思源宋体 ───────────────────────────
        "AdobeSongStd-Light":           ("Source Han Serif CN", 300, False),
        "AdobeMingStd-Light":           ("Source Han Serif CN", 300, False),
    }

    def decode(name: str):
        # 按 key 长度从长到短排序，确保最具体的匹配优先
        for internal, (real, weight, italic) in sorted(FONT_MAP.items(), key=lambda x: -len(x[0])):
            if internal in name:
                return real, weight, italic
        return None, None, False

    def repl_font(m):
        parts = re.split(r',\s*', m.group(1))
        new_parts = []
        new_weight = None
        new_italic = False
        for p in parts:
            p = p.strip().strip('"\'')
            real, weight, italic = decode(p)
            if real:
                new_parts.append(f'"{real}"' if " " in real else real)
                if weight is not None:
                    new_weight = weight
                if italic:
                    new_italic = True
            else:
                new_parts.append(p)
        result = "font-family: " + ", ".join(new_parts) + ";"
        if new_weight is not None:
            result += f" font-weight: {new_weight};"
        if new_italic:
            result += " font-style: italic;"
        return result

    for style_tag in soup.find_all('style'):
        if not style_tag.string:
            continue
        css = style_tag.string
        # 1. 删除 @font-face { ... }
        css = re.sub(r'@font-face\s*\{[^}]*\}', '', css)
        # 2. 替换 font-family（包含末尾分号，一并替换避免双分号）
        css = re.sub(r'font-family\s*:\s*([^;}\n]+?)\s*;', repl_font, css)
        style_tag.string = css

    print(f"Replaced fonts: {file_path}")


def adjust_style(file_path: str, soup: BeautifulSoup):
    """
    调整样式
    """
    head_tag = soup.find('head')
    if head_tag is None:
        print(f"Skipped style (no <head> found): {file_path}")
        return
    first_style = head_tag.find('style')
    if first_style is None:
        print(f"Skipped style (no <style> found): {file_path}")
        return

    # 边框样式可以覆盖
    first_style.string = first_style.string.replace('box-shadow: 0 0 5px rgba(0,0,0,0.3) !important', 'box-shadow: 0 0 5px rgba(0,0,0,0.3)')

    # 打印时的样式
    print_css = (
        '@media print {\n'
        '   body { margin: 0 !important; padding: 0 !important; }\n'
        '   body > div {box-shadow: none !important;}'
        '   .pdf24_02 { page-break-after: always; break-after: page; }\n'
        '   .pdf24_02:last-child { page-break-after: auto; break-after: auto; }\n'
        '}\n'
    )
    first_style.string = print_css + first_style.string

    print(f"Adjusted style: {file_path}")


@app.command()
def main(source_dir: str = typer.Argument(..., help="HTML 文件或目录路径"), title_prefix: str = typer.Argument(..., help="标题前缀")):
    # 判断输入是目录还是文件
    if os.path.isdir(source_dir):
        # 遍历html文件
        for filename in os.listdir(source_dir):
            if not filename.endswith(".html") or filename.endswith(".sc.html"):
                continue

            # 处理单个html文件
            html_file_path = os.path.join(source_dir, filename)
            process_file(html_file_path, title_prefix)
    elif os.path.isfile(source_dir) and source_dir.endswith(".html") and not source_dir.endswith(".sc.html") :
        # 处理单个html文件
        process_file(source_dir, title_prefix)
    else:
        raise ValueError("Invalid input path. Must be a directory or an HTML file.")

if __name__ == "__main__":
    app()