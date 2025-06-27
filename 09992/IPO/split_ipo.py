import os
import re
from PyPDF2 import PdfReader, PdfWriter

def clean_filename(filename):
    """清理文件名，移除无效字符"""
    # 移除Windows/Unix文件名中的非法字符
    cleaned = re.sub(r'[\\/*?:"<>|]', '', filename)
    # 替换空格为下划线（可选）
    # cleaned = cleaned.replace(' ', '_')
    return cleaned.strip()  # 移除首尾空白字符

def split_pdf_by_chapters(pdf_path, chapters, output_dir):
    """
    根据章节信息分割PDF文件

    :param pdf_path: PDF文件路径
    :param chapters: 章节列表，格式为[(章节名称, 起始页码), ...]
    :param output_dir: 输出目录
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 按起始页码排序
    chapters = sorted(chapters, key=lambda x: x[1])

    # 读取PDF文件
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)

    # 分割PDF
    for i, chapter in enumerate(chapters):
        chapter_name, start_page = chapter

        # 清理文件名
        safe_filename = f"{i+1:02d} " + clean_filename(chapter_name) + '.pdf'
        output_path = os.path.join(output_dir, safe_filename)

        # 确定结束页码（下一章的起始页码-1，如果是最后一章则为文档末尾）
        end_page = chapters[i+1][1] - 1 if i+1 < len(chapters) else total_pages

        # 验证页码范围
        start_page_index = start_page - 1  # 转换为0-based索引
        end_page_index = end_page - 1       # 转换为0-based索引

        # 跳过章节名称为空的情况
        if len(chapter_name) == 0:
            print(f"警告：跳过无效章节 {chapter_name} ({start_page}-{end_page})")
            continue

        # 检查页码范围有效性
        if start_page < 1 or start_page > total_pages or start_page > end_page:
            print(f"警告：跳过无效页码范围 {chapter_name} ({start_page}-{end_page})")
            continue

        # 确保不超过总页数
        if end_page_index >= total_pages:
            end_page_index = total_pages - 1

        # 创建PDF写入器
        writer = PdfWriter()

        # 添加指定页面范围
        for page_num in range(start_page_index, end_page_index + 1):
            writer.add_page(reader.pages[page_num])

        # 写入章节文件
        with open(output_path, 'wb') as out_file:
            writer.write(out_file)

        print(f"成功: {chapter_name} (页码: {start_page}-{end_page})")

# 示例用法
if __name__ == "__main__":
    # 示例章节数据
    chapters = [
        ("概要", 11),
        ("释义", 37),
        ("技术词汇表", 50),
        ("前瞻性陈述", 52),
        ("风险因素", 54),
        ("豁免严格遵守上市规则", 96),
        ("有关本招股章程及全球发售的资料", 106),
        ("董事及参与全球发售的各方", 111),
        ("公司资料", 116),
        ("法规", 118),
        ("行业概览", 155),
        ("历史、重组及公司架构", 170),
        ("业务", 207),
        ("合约安排", 306),
        ("与控股股东的关系", 324),
        ("关联交易", 328),
        ("董事及高级管理层", 334),
        ("主要股东", 346),
        ("股本", 348),
        ("财务资料", 351),
        ("未来计划及所得款项用途", 425),
        ("包销", 436),
        ("全球发售的架构", 448),
        ("如何申请香港发售股份", 459),
        ("附录一 会计师报告", 481),
        ("附录二 未经审核备考财务资料", 569),
        ("附录三 本公司组织章程及开曼公司法概要", 574),
        ("附录四 法定及一般资料", 601),
        ("附录五 送呈公司注册处处长及备查文件", 630),
    ]

    # 输入PDF路径
    input_pdf = "IPO.pdf"
    output_directory = "./"

    # 分割PDF
    split_pdf_by_chapters(input_pdf, chapters, output_directory)
    print(f"PDF分割完成，结果保存在: {output_directory}")