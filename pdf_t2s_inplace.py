"""港股财报 PDF 原位繁转简：只替换文字，不重排版面。

原理：逐 span 提取坐标/字号/颜色 -> 抹掉繁体原文 -> 在同坐标用简体中文字体写回。
表格线、图片、页码、logo 一律不动。适合有文字层的矢量 PDF（腾讯/港交所公告）。

实测状态（2026-11-18，腾讯 2026Q3 财报 50 页，v8 定稿）：
  - 数字 1815 个零丢失、繁体清零、表格线图片页码完好
  - 中西文 span 不重叠（纯数字/英文 span 不重写，保留原 Times 字体）
  - 半角空格用西文字体写回，宽度与原版一致（不被中文字体撑大）
  - 间隔号 ‧(U+2027) -> ·(U+00B7)，修复简中字体缺 U+2027 字形的问题

关键设计（踩过的坑，勿轻易改动）：
  1. apply_redactions 必须用 text=0（text=1 是"忽略文字不删除"）
  2. 字体注册须在 redact 之后（redact 会清页面资源），每页只注册一次 + 末尾 subset_fonts()
  3. 只重写"含繁体字"的 span；纯数字/英文 span 完全不碰——否则中文字体字宽更大，
     会把后面的中文挤重叠（实测 WeChat 用 Times New Roman 重写后压住"的"字）
  4. 含繁体的 span 内的半角空格必须单独拆出来用西文字体写：Hiragino 空格 3.50pt
     vs Times 2.62pt（差33%），整串用中文字体会让 Hy4/AI/WorkBuddy 两侧空格被撑大
  5. 相邻 span 的 bbox 本身可能重叠（如（港幣櫃台）及压在数字 700 上），
     抹繁体时会擦到纯数字 span。检测这类 span 并用 Times New Roman 精确写回（rescue）
  6. 原版字体（MSungHK/MHeiHK, Big5）只有繁体字形，简中字必须换字体——
     这是硬性必需，不是观感妥协；数字/英文因用原字体，观感与繁体原版一致
  7. 验证版面对错必须用 get_pixmap 渲染成图片肉眼看，pdftotext 的文本顺序会假性"碎裂"
  8. 首页公司 logo 是矢量轮廓（非文字层），繁体保留属正常，无法也无需转换

依赖：pymupdf, opencc, typer, rich
用法：python pdf_t2s_inplace.py 输入.pdf [输出.pdf]
      不指定输出时，默认在输入同目录生成 <原名>.sc.pdf
      python pdf_t2s_inplace.py --help 查看完整选项
"""

import os
import time
from pathlib import Path

import opencc
import pymupdf
import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

# 简体中文字体。常规/粗体分开，保持原文粗细层级。
FONT_REGULAR = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
# 西文字体：rescue 数字 span + 繁体 span 内的半角空格（原版是 TimesLTStd，系统无同款）
FONT_NUM = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"
FONT_NUM_REG = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"

cc = opencc.OpenCC("t2s")
app = typer.Typer(add_completion=False, help="港股财报 PDF 原位繁转简（只换字，不重排）。")
console = Console()


def _simplified(text: str) -> str:
    """繁转简；港澳间隔号 ‧ 映射到简中字体有的 ·。"""
    return cc.convert(text).replace("‧", "·")


def _color(span: dict) -> tuple:
    c = span["color"]
    return (((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255)


def _split_runs(chars: list) -> list:
    """把字符序列切成 [(是否空格, 文本, origin)]，连续非空格合并成一段整串写回。"""
    runs, buf, buf_origin = [], [], None
    for c in chars:
        if c["c"] == " ":
            if buf:
                runs.append((False, "".join(buf), buf_origin))
                buf = []
            runs.append((True, " ", c["origin"]))
        else:
            if not buf:
                buf_origin = c["origin"]
            buf.append(c["c"])
    if buf:
        runs.append((False, "".join(buf), buf_origin))
    return runs


def convert(src: str, dst: str, progress: Progress = None, task_id=None) -> dict:
    """转换 PDF。progress/task_id 可选，传入则逐页推进进度条。"""
    doc = pymupdf.open(src)
    t0 = time.time()
    spans_total = spans_changed = rescued = 0

    for page in doc:
        spans = []  # (span, text)
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:  # 跳过图片块
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = "".join(c["c"] for c in span["chars"])
                    if text.strip():
                        spans.append((span, text))
        spans_total += len(spans)

        # 第一遍：只把"含繁体字"的 span 纳入重写
        trad = [(sp, s) for sp, s in spans if _simplified(s) != s]
        if not trad:
            if progress is not None:
                progress.update(task_id, advance=1, changed=spans_changed)
            continue
        trad_texts = {s for _, s in trad}
        rects = [pymupdf.Rect(sp["bbox"]) for sp, _ in trad]

        # 第二遍：找出被繁体 redact 矩形波及的"纯数字/英文" span，rescue 写回
        rescue = []
        for sp, s in spans:
            if s in trad_texts:
                continue
            if _simplified(s) != s:  # 仍是繁体，走正常路径
                continue
            r = pymupdf.Rect(sp["bbox"])
            if any((tr & r).get_area() > 0.15 * r.get_area() for tr in rects):
                rescue.append((sp, s))

        to_write = []  # (origin, text, size, color, fontname)
        for sp, s in trad:
            bold = "bold" in sp["font"].lower()
            col = _color(sp)
            # 中文段整串用中文字体写回；半角空格单独用西文字体，保住原宽度
            for is_space, txt, origin in _split_runs(sp["chars"]):
                if is_space:
                    to_write.append((origin, " ", sp["size"], col, "NUMR"))
                else:
                    to_write.append((origin, _simplified(txt), sp["size"],
                                     col, "SCB" if bold else "SCR"))
        for sp, s in rescue:
            bold = "bold" in sp["font"].lower()
            to_write.append((sp["origin"], s, sp["size"], _color(sp),
                             "NUMB" if bold else "NUMR"))
            rescued += 1

        for r in rects + [pymupdf.Rect(sp["bbox"]) for sp, _ in rescue]:
            page.add_redact_annot(r)
        # text=0 删除文字；images=0/graphics=0 保护表格线与图片。
        page.apply_redactions(images=0, graphics=0, text=0)

        # redact 会清理页面资源，必须在它之后注册字体，每页一次。
        page.insert_font(fontname="SCR", fontfile=FONT_REGULAR)
        page.insert_font(fontname="SCB", fontfile=FONT_BOLD)
        page.insert_font(fontname="NUMB", fontfile=FONT_NUM)
        page.insert_font(fontname="NUMR", fontfile=FONT_NUM_REG)

        for origin, text, size, color, fontname in to_write:
            page.insert_text(origin, text, fontsize=size, fontname=fontname,
                             color=color, overlay=True)
        spans_changed += len(trad)

        if progress is not None:
            progress.update(task_id, advance=1, changed=spans_changed)

    # 字体子集化 + 保存也可能耗时，切换描述让用户知道仍在进行
    if progress is not None:
        progress.update(task_id, description="子集化字体并保存")

    doc.subset_fonts()
    doc.save(dst, garbage=4, deflate=True)
    doc.close()

    return {
        "spans_total": spans_total,
        "spans_changed": spans_changed,
        "rescued": rescued,
        "seconds": round(time.time() - t0, 1),
        "src_size": os.path.getsize(src),
        "dst_size": os.path.getsize(dst),
    }


@app.command()
def main(
    src: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, resolve_path=True,
        help="输入的繁体 PDF 路径",
    ),
    dst: Path = typer.Argument(None, help="输出路径；省略则生成同目录同名 .sc.pdf"),
):
    """把繁体 PDF 原位转为简体 PDF，逐页显示进度。"""
    if dst is None:
        dst = src.with_name(f"{src.stem}.sc{src.suffix}")

    n_pages = len(pymupdf.open(src))
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=32),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]已转 {task.fields[changed]} spans[/dim]"),
        TimeElapsedColumn(),
        TextColumn("/"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"转换 [cyan]{src.name}[/cyan]", total=n_pages, changed=0
        )
        result = convert(str(src), str(dst), progress, task)

    console.print(
        f"[green]✓[/green] 总 span {result['spans_total']}，"
        f"转换 {result['spans_changed']}，数字 rescue {result['rescued']}，"
        f"耗时 {result['seconds']}s"
    )
    console.print(f"输出: [bold]{dst}[/bold]")
    console.print(
        f"体积: {result['src_size']/1024:.0f}K -> {result['dst_size']/1024:.0f}K"
    )


if __name__ == "__main__":
    app()
