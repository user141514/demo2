import html
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont


DOCX_MIMETYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
MARGIN_X = 96
MARGIN_Y = 96
CONTENT_WIDTH = PAGE_WIDTH - MARGIN_X * 2

FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/msyh.ttf"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("C:/Windows/Fonts/simsun.ttc"),
]


def build_leadership_docx_bytes(model):
    paragraphs = _document_paragraphs(model)
    document_xml = _document_xml(paragraphs)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _rels_xml())
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", _styles_xml())
        archive.writestr("word/_rels/document.xml.rels", _empty_rels_xml())
    return buffer.getvalue()


def build_leadership_pdf_bytes(model):
    font_path = _resolve_font_path()
    fonts = {
        "title": ImageFont.truetype(str(font_path), 42),
        "heading": ImageFont.truetype(str(font_path), 30),
        "body": ImageFont.truetype(str(font_path), 21),
        "small": ImageFont.truetype(str(font_path), 18),
    }
    pages = _render_pdf_pages(_pdf_blocks(model), fonts)
    output = BytesIO()
    first, *rest = pages
    first.save(output, "PDF", resolution=150.0, save_all=True, append_images=rest)
    return output.getvalue()


def _document_paragraphs(model):
    context = model.get("context") or {}
    title = "《{} {} 领导力模型》".format(
        context.get("company_name") or "企业",
        context.get("target_group") or "管理者",
    )
    paragraphs = [
        ("title", title),
        ("body", "版本：V1.0"),
        ("body", "适用对象：{}".format(context.get("target_group") or "--")),
        ("heading", "第一章 模型概述"),
        ("body", _background_text(context)),
        ("heading", "第二章 维度详解"),
    ]
    descriptions = {item.get("dimension_id"): item for item in model.get("descriptions") or []}
    anchors = {item.get("dimension_id"): item for item in model.get("anchors") or []}
    for dimension in model.get("dimensions") or []:
        dim_id = dimension.get("id")
        desc = descriptions.get(dim_id) or {}
        anchor = anchors.get(dim_id) or {}
        paragraphs.extend(
            [
                ("heading", "{} {}".format(dim_id, dimension.get("name") or "未命名维度")),
                ("body", "维度定义：{}".format(dimension.get("definition") or "--")),
                ("body", "定位要求：{}".format(desc.get("core_requirement") or "--")),
                ("body", "价值贡献：{}".format(desc.get("value_contribution") or "--")),
                ("body", "优秀行为：{}".format("；".join(anchor.get("excellent") or ["--"]))),
                ("body", "达标行为：{}".format("；".join(anchor.get("pass") or ["--"]))),
                ("body", "不达标表现：{}".format("；".join(anchor.get("negative") or ["--"]))),
            ]
        )
    paragraphs.extend(
        [
            ("heading", "附录A 建模方法说明"),
            ("body", "本模型采用 AI 辅助建模方式，融合企业背景、用户访谈、上传文档与标准库参照形成。"),
            ("heading", "附录B 参照标准库说明"),
            ("body", "本次参照：{}".format("、".join(context.get("standard_refs") or ["综合基线（内置）"]))),
        ]
    )
    return paragraphs


def _background_text(context):
    missing = context.get("missing_fields") or []
    text = (
        "{company}属于{industry}，业务类型为{business}。本模型聚焦{group}，"
        "围绕{strategy}等战略重点，以及{pains}等管理痛点建立。"
    ).format(
        company=context.get("company_name") or "企业",
        industry=context.get("industry") or "未提供行业",
        business=context.get("business_type") or "未提供业务类型",
        group=context.get("target_group") or "目标管理群体",
        strategy="、".join(context.get("strategy_keywords") or ["未提供战略重点"]),
        pains="、".join(context.get("management_pains") or ["未提供管理痛点"]),
    )
    if missing:
        text += " 信息缺口：{}。".format("、".join(missing))
    return text


def _document_xml(paragraphs):
    body = "".join(_paragraph_xml(style, text) for style, text in paragraphs)
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body>
</w:document>""".format(
        body=body
    )


def _paragraph_xml(style, text):
    style_id = {"title": "Title", "heading": "Heading1"}.get(style)
    ppr = "<w:pPr><w:pStyle w:val=\"{}\"/></w:pPr>".format(style_id) if style_id else ""
    return "<w:p>{}<w:r><w:t>{}</w:t></w:r></w:p>".format(ppr, html.escape(str(text)))


def _content_types_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""


def _rels_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _empty_rels_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>"""


def _styles_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>
</w:styles>"""


def _pdf_blocks(model):
    blocks = []
    for style, text in _document_paragraphs(model):
        blocks.append({"style": "heading" if style == "heading" else style, "text": text})
    return blocks


def _render_pdf_pages(blocks, fonts):
    pages = []
    page, draw = _new_page()
    y = MARGIN_Y
    for block in blocks:
        font = fonts.get(block["style"], fonts["body"])
        lines = _wrap(draw, block["text"], font)
        line_height = _line_height(draw, font)
        height = len(lines) * line_height + 16
        if y + height > PAGE_HEIGHT - MARGIN_Y and y > MARGIN_Y:
            pages.append(page)
            page, draw = _new_page()
            y = MARGIN_Y
        fill = "#19131f" if block["style"] != "small" else "#5e5665"
        for line in lines:
            draw.text((MARGIN_X, y), line, fill=fill, font=font)
            y += line_height
        y += 16
    pages.append(page)
    return pages


def _new_page():
    page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "#fffdf8")
    draw = ImageDraw.Draw(page)
    draw.rectangle((54, 54, PAGE_WIDTH - 54, PAGE_HEIGHT - 54), outline="#eadfd5", width=2)
    draw.line((MARGIN_X, 78, PAGE_WIDTH - MARGIN_X, 78), fill="#8a3c87", width=5)
    return page, draw


def _wrap(draw, text, font):
    lines = []
    current = ""
    for char in str(text):
        if char == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + char
        if _text_width(draw, candidate, font) <= CONTENT_WIDTH:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines or [""]


def _resolve_font_path():
    for path in FONT_CANDIDATES:
        if path.exists():
            return path
    raise RuntimeError("No CJK font file was found for PDF export.")


def _text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _line_height(draw, font):
    bbox = draw.textbbox((0, 0), "测试Ag", font=font)
    return bbox[3] - bbox[1] + 8
