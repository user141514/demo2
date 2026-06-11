import re
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from .core.errors import ApplicationError
from .core.text_quality import looks_like_garbled_text
from .pdf_extract import PdfExtractionError, extract_text_from_pdf_bytes


MAX_SOURCE_FILE_BYTES = 20 * 1024 * 1024
DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract_leadership_source_file(file_storage):
    if file_storage is None or not getattr(file_storage, "filename", ""):
        return None, ""

    filename = file_storage.filename.strip()
    payload = file_storage.read()
    if not payload:
        raise ApplicationError("empty_source_file", "上传的建模材料为空。", 400)
    if len(payload) > MAX_SOURCE_FILE_BYTES:
        raise ApplicationError("source_file_too_large", "建模材料不能超过 20MB。", 400)

    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        text = _extract_pdf(payload)
        mimetype = "application/pdf"
    elif lower_name.endswith(".docx"):
        text = _extract_docx(payload)
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif lower_name.endswith(".txt") or lower_name.endswith(".md"):
        text = _decode_text(payload)
        mimetype = "text/plain; charset=utf-8"
    else:
        raise ApplicationError(
            "invalid_source_file",
            "建模材料仅支持 PDF、DOCX、TXT 或 Markdown 文件。",
            400,
        )

    if looks_like_garbled_text(text, min_suspicious=6, min_ratio=0.12):
        raise ApplicationError("garbled_source_file", "建模材料解析结果疑似乱码。", 422)

    return (
        {
            "filename": filename,
            "mimetype": mimetype,
            "content_bytes": payload,
            "byte_size": len(payload),
        },
        _clean_text(text),
    )


def _extract_pdf(payload):
    try:
        return extract_text_from_pdf_bytes(payload)
    except PdfExtractionError as exc:
        raise ApplicationError("source_pdf_extract_failed", str(exc), 422)


def _extract_docx(payload):
    try:
        with ZipFile(BytesIO(payload)) as archive:
            document_xml = archive.read("word/document.xml")
    except Exception as exc:
        raise ApplicationError("docx_extract_failed", "DOCX 文件解析失败。", 422) from exc

    root = ET.fromstring(document_xml)
    chunks = []
    for paragraph in root.findall(".//w:p", DOCX_NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", DOCX_NS))
        if text.strip():
            chunks.append(text.strip())
    merged = "\n".join(chunks).strip()
    if len(merged) < 10:
        raise ApplicationError("docx_text_too_short", "DOCX 中未提取到足够文本。", 422)
    return merged


def _decode_text(payload):
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            text = payload.decode(encoding).strip()
        except Exception:
            continue
        if text:
            return text
    raise ApplicationError("source_text_decode_failed", "文本材料无法解码。", 400)


def _clean_text(value):
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    return cleaned[:12000]
