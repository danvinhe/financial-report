import os
import typer
from rich import print
import pdfkit
import asyncio
from pyppeteer import launch
from xhtml2pdf import pisa
from playwright.async_api import async_playwright
from weasyprint import HTML
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.print_page_options import PrintOptions

os.environ["PYPPETEER_DOWNLOAD_HOST"] = "https://cdn.npmmirror.com/binaries"

app = typer.Typer()

# 处理单个html文件
def process_file(file_path, output_dir, engine_flag):
    """
    将单个HTML文件转换为PDF文件

    Args:
        file_path (str): HTML文件路径
        output_dir (str): 输出PDF文件的目录
    """
    print(f"Processing: {file_path}")

    # 生成PDF文件
    file_name = os.path.basename(file_path)
    pdf_file_name = f"{file_name[0: len(file_name) - 5]}.pdf"

    if engine_flag & 1:
        pdf_file_dir = os.path.join(output_dir, 'wp')
        os.makedirs(pdf_file_dir, exist_ok=True)
        pdf_file_path = os.path.join(pdf_file_dir, pdf_file_name)
        save_as_pdf_by_weasyprint(file_path, pdf_file_path)
        print(f"Processed: {file_path} to {pdf_file_path}")

    if engine_flag & 2:
        pdf_file_dir = os.path.join(output_dir, 'pw')
        os.makedirs(pdf_file_dir, exist_ok=True)
        pdf_file_path = os.path.join(pdf_file_dir, pdf_file_name)
        asyncio.run(save_as_pdf_by_playwright(file_path, pdf_file_path))
        print(f"Processed: {file_path} to {pdf_file_path}")

    if engine_flag & 4:
        pdf_file_dir = os.path.join(output_dir, 'pp')
        os.makedirs(pdf_file_dir, exist_ok=True)
        pdf_file_path = os.path.join(pdf_file_dir, pdf_file_name)
        asyncio.run(save_as_pdf_by_pyppeteer(file_path, pdf_file_path))
        print(f"Processed: {file_path} to {pdf_file_path}")

    if engine_flag & 8:
        pdf_file_dir = os.path.join(output_dir, 'xp')
        os.makedirs(pdf_file_dir, exist_ok=True)
        pdf_file_path = os.path.join(pdf_file_dir, pdf_file_name)
        save_as_pdf_by_xhtml2pdf(file_path, pdf_file_path)
        print(f"Processed: {file_path} to {pdf_file_path}")

    if engine_flag & 16:
        pdf_file_dir = os.path.join(output_dir, 's')
        os.makedirs(pdf_file_dir, exist_ok=True)
        pdf_file_path = os.path.join(pdf_file_dir, pdf_file_name)
        save_as_pdf_by_selenium(file_path, pdf_file_path)

    if engine_flag & 32:
        pdf_file_dir = os.path.join(output_dir, 'pk')
        os.makedirs(pdf_file_dir, exist_ok=True)
        pdf_file_path = os.path.join(pdf_file_dir, pdf_file_name)
        save_as_pdf(file_path, pdf_file_path)

def save_as_pdf(file_path, output_pdf):

   pdfkit.from_file(file_path, output_pdf)

async def save_as_pdf_by_pyppeteer(file_path, output_pdf):
    browser = await launch()
    page = await browser.newPage()

    await page.goto(f"file://{file_path}")

    await page.pdf({'path': output_pdf, 'format': 'A4', 'scale': 1.4})

    await browser.close()

def save_as_pdf_by_xhtml2pdf(file_path, output_pdf):
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

     # Generate PDF
    with open(output_pdf, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_file)

    if pisa_status.err:
        raise Exception(f"Error creating PDF: {pisa_status.err}")

async def save_as_pdf_by_playwright(file_path, output_pdf):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"file://{file_path}")
        await page.pdf(scale=1.4, format="A4", path=output_pdf)
        await browser.close()

def save_as_pdf_by_weasyprint(file_path, output_pdf):

    HTML(file_path).write_pdf(output_pdf)

def save_as_pdf_by_selenium(file_path, output_dir):

    # 创建Chrome选项
    chrome_options = Options()
    chrome_options.add_argument('--headless=new') # 无头模式
    chrome_options.add_argument("--no-sandbox")  # 禁用沙盒，提升稳定性
    # chrome_options.add_argument("--disable-dev-shm-usage")  # 解决共享内存问题
    # chrome_options.add_argument("--disable-gpu")  # 禁用GPU，兼容性更好
    chrome_options.add_argument("--disable-extensions")  # 禁用扩展
    # chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    # chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # 禁用图片加载

    # 初始化WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    # driver.set_page_load_timeout(600)  # 设置页面加载超时时间

    # 打开目标网页
    driver.get(f"file://{file_path}")  # 替换为您的HTML文件路径或URL

    print_options = PrintOptions()
    print_options.orientation = 'portrait'  # 页面方向：portrait（纵向）, landscape（横向）
    print_options.background = False  # 是否打印背景
    print_options.scale = 1.2  # 缩放比例
    print_options.shrink_to_fit = True

    # 打印页面并获取Base64编码的PDF内容
    pdf_base64 = driver.print_page(print_options=print_options)
    pdf_bytes = base64.b64decode(pdf_base64)

    file_name = os.path.basename(file_path)
    pdf_file_name = f"{file_name[0: len(file_name) - 5]}.pdf"
    pdf_file_path = os.path.join(output_dir, pdf_file_name)
    with open(pdf_file_path, "wb") as f:
        f.write(pdf_bytes)

    driver.quit()

    return pdf_file_path

# 处理全部html文件
@app.command()
def main(source_path: str = "", output_dir: str = "./", engine_flag: int = 1):
    """
    将指定目录或单个HTML文件转换为PDF文件

    Args:
        source_dir (str): HTML文件或目录路径
        output_dir (str): 输出PDF文件的目录
    """
    # 校验输出目录
    if not output_dir:
        output_dir = os.getcwd()
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # 判断输入是目录还是文件
    source_path = os.path.abspath(source_path)
    if os.path.isdir(source_path):
        # 遍历html文件
        for filename in os.listdir(source_path):
            if not filename.endswith(".html"):
                continue

            # 处理单个html文件
            html_file_path = os.path.join(source_path, filename)
            process_file(html_file_path, output_dir, engine_flag)
    elif os.path.isfile(source_path) and source_path.endswith(".html"):
        # 处理单个html文件
        process_file(source_path, output_dir, engine_flag)
    else:
        raise ValueError("Invalid input path. Must be a directory or an HTML file.")

if __name__ == "__main__":
    app()