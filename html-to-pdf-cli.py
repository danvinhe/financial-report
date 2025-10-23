import os
import re
import typer
from rich import print
from bs4 import BeautifulSoup
import pdfkit
import asyncio
from pyppeteer import launch
import os

os.environ["PYPPETEER_DOWNLOAD_HOST"] = "https://cdn.npmmirror.com/binaries"

app = typer.Typer()

# 处理单个html文件
def process_file(file_path, output_dir):
    """
    将单个HTML文件转换为PDF文件

    Args:
        file_path (str): HTML文件路径
        output_dir (str): 输出PDF文件的目录
    """
    print(f"Processing: {file_path}")

    # 清除文件中的图片
    remove_images(file_path)

    # 提取标题并更新HTML的<title>标签
    update_title(file_path)

    # 添加水印
    add_watermark(file_path)

    # 生成PDF文件

    file_name = os.path.basename(file_path)
    pdf_file_name = f"{file_name[0: len(file_name) - 5]}.pdf"
    pdf_file_path = os.path.join(output_dir, pdf_file_name)

    # save_as_pdf(file_path, pdf_file_path)
    asyncio.get_event_loop().run_until_complete(save_as_pdf_by_pyppeteer(file_path, pdf_file_path))

    print(f"Processed: {file_path} to {pdf_file_path}")

# 清除文件中的图片
def remove_images(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    for svg_image in soup.find_all('image'):
        svg_image.decompose()

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))

# 生成文件的标题
def update_title(file_path):
    """
    从HTML文件路径中提取股票代码和季度信息，生成标题

    Args:
        file_path (str): HTML文件路径

    Returns:
        str: 生成的标题，格式为“股票名称2025年一季报-简体中文版-价格与价值”
    """
    # 股票映射
    stocks_kv = {
        "00700": "腾讯控股",
        "09992": "泡泡玛特",
    }
    # 季度映射
    quarters_kv = {
        "1": "一季报",
        "2": "半年报",
        "3": "三季报",
        "4": "年报"
    }

    # 提取股票代码（目录名）
    symbol = os.path.basename(os.path.dirname(file_path))
    # 提取文件名中的年份和季度（如2025Q1）
    file_name = os.path.basename(file_path)
    year, quarter = "", ""
    if len(file_name) > 6:
        year, quarter = file_name[0:4], file_name[5]

    # 不符合格式，无需处理
    if not year or not quarter or symbol not in stocks_kv or quarter not in quarters_kv:
        print(f"Skipped title: {file_path}")
        return

    # 生成标题
    new_title =  f"{stocks_kv[symbol]}{year}年简体中文版{quarters_kv[quarter]}-价格与价值"

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
        f.write(html_content)

    print(f"Updated title: {file_path}")

# 添加水印
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
    watermark_css = """.page {margin:5px 0; position: relative;}\n.page::before {content: "公众号·价格与价值";position: absolute;top: 0;left: 0;right: 0;bottom: 0;display: flex;justify-content: center;align-items: center;font-size: 88px;font-weight: bold;color: rgba(0, 0, 0, 0.1);transform: rotate(-45deg);pointer-events: none; z-index: 1;}"""
    html_content = html_content.replace(original_css, watermark_css)

    # 写入html文件
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Added watermark: {file_path}")
#
def save_as_pdf(file_path, output_pdf):

   pdfkit.from_file(file_path, output_pdf)

async def save_as_pdf_by_pyppeteer(file_path, output_pdf):
    browser = await launch()
    page = await browser.newPage()

    await page.goto(f"file://{file_path}")

    await page.pdf({'path': output_pdf, 'format': 'A4', 'scale': 1.4})

    await browser.close()

# 处理全部html文件
@app.command()
def main(source_dir: str = "", output_dir: str = ""):
    """
    将指定目录或单个HTML文件转换为PDF文件

    Args:
        source_dir (str): HTML文件或目录路径
        output_dir (str): 输出PDF文件的目录
    """
    # 校验输出目录
    if not output_dir:
        output_dir = os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    # 判断输入是目录还是文件
    if os.path.isdir(source_dir):
        # 遍历html文件
        for filename in os.listdir(source_dir):
            if not filename.endswith(".html"):
                continue

            # 处理单个html文件
            html_file_path = os.path.join(source_dir, filename)
            process_file(html_file_path, output_dir)
    elif os.path.isfile(source_dir) and source_dir.endswith(".html"):
        # 处理单个html文件
        process_file(source_dir, output_dir)
    else:
        raise ValueError("Invalid input path. Must be a directory or an HTML file.")

if __name__ == "__main__":
    app()