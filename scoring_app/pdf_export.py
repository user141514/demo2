from collections import OrderedDict
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


class PdfBuildError(Exception):
    pass


PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
MARGIN_X = 96
MARGIN_Y = 96
CONTENT_WIDTH = PAGE_WIDTH - (MARGIN_X * 2)

FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("C:/Windows/Fonts/msyh.ttf"),
    Path("C:/Windows/Fonts/simsun.ttf"),
    Path("C:/Windows/Fonts/simsun.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
]


def build_pdf_bytes(result):
    font_path = _resolve_font_path()
    fonts = {
        "title": ImageFont.truetype(str(font_path), 42),
        "section": ImageFont.truetype(str(font_path), 30),
        "subsection": ImageFont.truetype(str(font_path), 24),
        "body": ImageFont.truetype(str(font_path), 21),
        "small": ImageFont.truetype(str(font_path), 18),
    }
    pages = _render_pages(_build_blocks(result), fonts)
    if not pages:
        raise PdfBuildError("No content available for PDF export.")

    buffer = BytesIO()
    first_page, *remaining = pages
    first_page.save(
        buffer,
        format="PDF",
        resolution=150.0,
        save_all=True,
        append_images=remaining,
    )
    return buffer.getvalue()


def _resolve_font_path():
    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            return candidate
    raise PdfBuildError("No CJK font file was found for PDF export.")


def _build_blocks(result):
    groups = OrderedDict()
    for dimension in result["dimensions"]:
        groups.setdefault(dimension["group_name"], []).append(dimension)

    blocks = [
        {"style": "title", "text": "汇报评分报告", "before": 0, "after": 22},
        {"style": "section", "text": "被评价人信息", "before": 0, "after": 10},
        {"style": "body", "text": "姓名：{}".format(_safe_text(result.get("name"))), "before": 0, "after": 6},
        {"style": "body", "text": "所属组织/部门：{}".format(_safe_text(result.get("org"))), "before": 0, "after": 6},
        {"style": "body", "text": "汇报类型：{}".format(_safe_text(result.get("report_type"))), "before": 0, "after": 6},
        {"style": "body", "text": "评分日期：{}".format(_safe_text(result.get("date"))), "before": 0, "after": 6},
        {"style": "body", "text": "备注：{}".format(_safe_text(result.get("note"))), "before": 0, "after": 14},
        {
            "style": "section",
            "text": "总分：{} 分（满分100分）".format(_safe_text(result.get("total_score"))),
            "before": 0,
            "after": 10,
        },
        {
            "style": "body",
            "text": "总等级：{}".format(_safe_text(result.get("total_level"))),
            "before": 0,
            "after": 14,
        },
        {"style": "section", "text": "总评", "before": 0, "after": 10},
        {
            "style": "body",
            "text": _safe_text(result.get("overall_comment")),
            "before": 0,
            "after": 18,
        },
        {"style": "section", "text": "各维度评分明细", "before": 0, "after": 12},
    ]

    for group_name, dimensions in groups.items():
        blocks.append(
            {
                "style": "subsection",
                "text": "{}（权重{}%）".format(group_name, _safe_text(dimensions[0].get("group_weight"))),
                "before": 0,
                "after": 10,
            }
        )
        for dimension in dimensions:
            score_text = (
                "{} 分 · {}".format(
                    _safe_text(dimension.get("score")),
                    _safe_text(dimension.get("level_label")),
                )
                if dimension.get("score") is not None
                else "待补充"
            )
            blocks.extend(
                [
                    {
                        "style": "body",
                        "text": "{} | {} | {}".format(
                            _safe_text(dimension.get("name")),
                            _safe_text(dimension.get("material_source")),
                            score_text,
                        ),
                        "before": 0,
                        "after": 6,
                    },
                    {
                        "style": "small",
                        "text": "评分依据：{}".format(_safe_text(dimension.get("evidence"))),
                        "before": 0,
                        "after": 4,
                    },
                    {
                        "style": "small",
                        "text": "维度评价：{}".format(_safe_text(dimension.get("comment"))),
                        "before": 0,
                        "after": 10,
                    },
                ]
            )

    blocks.append({"style": "section", "text": "结论与建议", "before": 6, "after": 10})
    blocks.append({"style": "subsection", "text": "优势亮点", "before": 0, "after": 8})
    for item in result.get("strengths") or []:
        blocks.append({"style": "body", "text": "- {}".format(_safe_text(item)), "before": 0, "after": 5})

    blocks.append({"style": "subsection", "text": "改进方向", "before": 10, "after": 8})
    for item in result.get("improvements") or []:
        blocks.append({"style": "body", "text": "- {}".format(_safe_text(item)), "before": 0, "after": 5})

    blocks.extend(
        [
            {"style": "section", "text": "免责声明", "before": 12, "after": 8},
            {"style": "small", "text": _safe_text(result.get("disclaimer")), "before": 0, "after": 5},
            {
                "style": "small",
                "text": "生成时间：{}".format(_safe_text(result.get("created_at"))),
                "before": 0,
                "after": 0,
            },
        ]
    )
    return blocks


def _render_pages(blocks, fonts):
    pages = []
    page, draw = _new_page()
    y = MARGIN_Y

    for block in blocks:
        font = fonts[block["style"]]
        lines = _wrap_text(draw, block["text"], font, CONTENT_WIDTH)
        line_height = _line_height(draw, font)
        block_height = block["before"] + (len(lines) * line_height) + block["after"]

        if y + block_height > PAGE_HEIGHT - MARGIN_Y and y > MARGIN_Y:
            _draw_footer(draw, len(pages) + 1, fonts["small"])
            pages.append(page)
            page, draw = _new_page()
            y = MARGIN_Y

        y += block["before"]
        fill = "#17121f" if block["style"] != "small" else "#4b4458"
        for line in lines:
            draw.text((MARGIN_X, y), line, font=font, fill=fill)
            y += line_height
        y += block["after"]

    _draw_footer(draw, len(pages) + 1, fonts["small"])
    pages.append(page)
    return pages


def _new_page():
    page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "#fffdf8")
    draw = ImageDraw.Draw(page)
    border = [(48, 40), (PAGE_WIDTH - 48, PAGE_HEIGHT - 40)]
    if hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(border, radius=28, outline="#eadfd5", width=2)
    else:
        draw.rectangle(border, outline="#eadfd5")
    draw.line((MARGIN_X, 74, PAGE_WIDTH - MARGIN_X, 74), fill="#d38a44", width=4)
    return page, draw


def _draw_footer(draw, page_number, font):
    footer = "智能体评分系统  |  第 {} 页".format(page_number)
    width = _text_width(draw, footer, font)
    x = PAGE_WIDTH - MARGIN_X - width
    y = PAGE_HEIGHT - MARGIN_Y + 22
    draw.text((x, y), footer, font=font, fill="#7b728a")


def _wrap_text(draw, text, font, max_width):
    lines = []
    for paragraph in str(text).splitlines() or [""]:
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if _text_width(draw, candidate, font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines or [""]


def _text_width(draw, text, font):
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
    return draw.textsize(text, font=font)[0]


def _line_height(draw, font):
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), "测试Ag", font=font)
        return (bbox[3] - bbox[1]) + 8
    return draw.textsize("测试Ag", font=font)[1] + 8


def _safe_text(value):
    text = str(value).strip() if value is not None else ""
    return text or "--"
