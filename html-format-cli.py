import os
import typer
from bs4 import BeautifulSoup
from opencc import OpenCC
import re

app = typer.Typer()

def process_file(file_path, title_prefix):

    remove_images(file_path)

    add_watermark(file_path)

    update_title(file_path, title_prefix)

    tc_to_sc(file_path)

# 清除文件中的图片
def remove_images(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    svg_images = soup.find_all('image')
    if len(svg_images) == 0:
        print(f"Skipped images: {file_path}")
        return

    for image in svg_images:
        image.decompose()

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))

    print(f"Removed images: {file_path}")

def update_title(file_path, title_prefix):
    # 季度映射
    quarters_kv = {
        "1": "一季报",
        "2": "中报",
        "3": "三季报",
        "4": "年报"
    }
    file_name = os.path.basename(file_path)
    match = re.fullmatch(r"\d{4}Q[1-4]\.sc\.html", file_name)
    if match:
        year, quarter = file_name[0:4], file_name[5]
        new_title =  f"{title_prefix}{year}年简体中文版{quarters_kv[quarter]}"
    else:
        new_title =  f"{title_prefix}{file_name[0:len(file_name)-8]}"
    new_title += " | 价格与价值"

    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # 替换<title>标签内容
    soup = BeautifulSoup(html_content, 'html.parser')
    title_tag = soup.find('title')
    if title_tag is None or title_tag.string == new_title:
        print(f"Skipped title: {file_path}")
        return
    title_tag.string = new_title

    # 写入html文件
    with open(file_path, "w", encoding="utf-8") as f:
        n = f.write(str(soup))

    print(f"Updated title: {file_path}")

def add_watermark(file_path):
    """
    为html文件添加水印

    Args:
        file_path (str): html文件路径
    """
    # 读取html文件内容
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # 判断是否有旧的样式
    original_css = ".page {margin:5px 0}"
    if html_content.find(original_css) == -1:
        print(f"Skipped watermark: {file_path}")
        return

    # 替换样式
    watermark_css = """@page {size:A4; margin: 0;}\n.page {margin:5px 0; position: relative;}\n.page::before {content: "公众号·价格与价值";position: absolute;top: 0;left: 0;right: 0;bottom: 0;display: flex;justify-content: center;align-items: center;font-size: 88px;font-weight: bold;color: rgba(0, 0, 0, 0.1);transform: rotate(-45deg);pointer-events: none; z-index: 1;}"""
    html_content = html_content.replace(original_css, watermark_css)

    # 写入html文件
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Added watermark: {file_path}")

def tc_to_sc(file_path):

    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    cc = OpenCC('t2s')
    new_html_content = cc.convert(html_content)

    # 写入html文件
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_html_content)

    print(f"Converted TC: {file_path}")

@app.command()
def main(source_dir: str = "", title_prefix: str = ""):
    # 判断输入是目录还是文件
    if os.path.isdir(source_dir):
        # 遍历html文件
        for filename in os.listdir(source_dir):
            if not filename.endswith(".html"):
                continue

            # 处理单个html文件
            html_file_path = os.path.join(source_dir, filename)
            process_file(html_file_path, title_prefix)
    elif os.path.isfile(source_dir) and source_dir.endswith(".html"):
        # 处理单个html文件
        process_file(source_dir, title_prefix)
    else:
        raise ValueError("Invalid input path. Must be a directory or an HTML file.")

if __name__ == "__main__":
    app()