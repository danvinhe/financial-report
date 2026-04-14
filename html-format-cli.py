import os
import typer
from bs4 import BeautifulSoup
from opencc import OpenCC
import re

app = typer.Typer()

def process_file(file_path, title_prefix):

    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, 'html.parser')

    update_title(file_path, soup, title_prefix)

    remove_images(soup)

    add_watermark(soup)

    soup = tc_to_sc(soup)

    new_file_path = file_path.replace(".html", ".sc.html")
    with open(new_file_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))

# 清除文件中的图片
def remove_images(soup: BeautifulSoup):
    svg_images = soup.find_all('img')
    if len(svg_images) == 0:
        print(f"Skipped images: {soup.find('title').string}")
        return

    is_first = True
    for image in svg_images:
        if is_first:
            is_first = False
        else:
            image.decompose()


    print(f"Removed images: {soup.find('title').string}")

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
        print(f"Skipped title: {new_title}")
        return
    title_tag.string = new_title

    print(f"Updated title: {new_title}")

def add_watermark(soup: BeautifulSoup):
    """
    通过 ::before 伪元素为 .pdf24_02 容器添加水印（纯CSS方案）

    pdf2htmlEX 的 DOM 结构：
      div.page_* (class="pdf24_02") → 每个页面的固定外层容器
    水印挂载在 .pdf24_02::before 上，position: relative 通过 CSS 设置。
    """

    watermark_css = (
        '.pdf24_02 {position: relative;}\n'
        '.pdf24_02::before {content: "公众号·价格与价值";position: absolute;top: 0;left: 0;right: 0;bottom: 0;display: flex;justify-content: center;align-items: center;font-size: 88px;font-weight: bold;color: rgba(0, 0, 0, 0.1);transform: rotate(-45deg);pointer-events: none; z-index: 1;}\n'
    )

    pages = soup.find_all('div', id=re.compile(r'^page_\d+$'))
    if len(pages) == 0:
        print(f"Skipped watermark (no pages found): {soup.find('title').string}")
        return

    # 在 <head> 中插入水印样式（不修改任何元素的 style 属性）
    head_tag = soup.find('head')
    if head_tag is None:
        print(f"Skipped watermark (no <head> found): {soup.find('title').string}")
        return

    style_tag = soup.new_tag('style')
    style_tag.string = watermark_css
    first_style = head_tag.find('style')
    if first_style is not None:
        first_style.insert_before(style_tag)
    else:
        head_tag.append(style_tag)

    print(f"Added watermark {soup.find('title').string}")

def tc_to_sc(soup: BeautifulSoup) -> BeautifulSoup:

    cc = OpenCC('t2s')
    new_html_content = cc.convert(str(soup))

    soup = BeautifulSoup(new_html_content, 'html.parser')
    print(f"Converted TC: {soup.find('title').string}")

    return soup

@app.command()
def main(source_dir: str = "", title_prefix: str = ""):
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