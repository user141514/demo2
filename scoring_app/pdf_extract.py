import re
from io import BytesIO

from pypdf import PdfReader

from .core.text_quality import looks_like_garbled_text


class PdfExtractionError(Exception):
    pass


def extract_text_from_pdf_bytes(data):
    if not data.startswith(b"%PDF"):
        raise PdfExtractionError("上传的文件不是有效的 PDF。")

    return _extract_with_pypdf(data)


def _extract_with_pypdf(data):
    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise PdfExtractionError("PDF 解析失败，请确认文件未损坏或加密。") from exc

    candidates = []
    for page in reader.pages:
        try:
            candidates.append(page.extract_text() or "")
        except Exception:
            continue
    return _clean_extracted_candidates(candidates)


def _clean_extracted_candidates(candidates):
    cleaned = []
    seen = set()
    for candidate in candidates:
        line = _normalize_text(candidate)
        if (
            len(line) < 3
            or _looks_like_binary_garbage(line)
            or looks_like_garbled_text(line, min_suspicious=2, min_ratio=0.35)
            or line in seen
        ):
            continue
        seen.add(line)
        cleaned.append(line)

    merged = "\n".join(cleaned).strip()
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    if len(merged) < 40:
        raise PdfExtractionError(
            "未能从 PDF 提取足够文本，请优先上传文字版 PDF；扫描版或图片版 PDF 可能无法解析。"
        )
    if looks_like_garbled_text(merged, min_suspicious=6, min_ratio=0.12):
        raise PdfExtractionError(
            "PDF 文本提取结果疑似乱码，请优先上传文字版 PDF，或先转换为可复制文本后再上传。"
        )
    return merged


def _normalize_text(value):
    cleaned = _repair_latin1_mojibake(value).replace("\x00", " ")
    cleaned = re.sub(r"\\[rn]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _repair_latin1_mojibake(value):
    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except Exception:
        return value
    if _text_quality_score(repaired) > _text_quality_score(value):
        return repaired
    return value


def _looks_like_binary_garbage(value):
    compact = re.sub(r"\s+", "", value or "")
    if not compact:
        return True
    control_count = sum(1 for char in compact if ord(char) < 32)
    latin1_count = sum(1 for char in compact if 128 <= ord(char) <= 255)
    meaningful = sum(1 for char in compact if char.isascii() and char.isalnum() or "\u4e00" <= char <= "\u9fff")
    if control_count >= 2:
        return True
    if latin1_count >= 8 and meaningful < len(compact) // 3:
        return True
    return False


def _text_quality_score(value):
    compact = re.sub(r"\s+", "", value or "")
    if not compact:
        return 0
    chinese = sum(1 for char in compact if "\u4e00" <= char <= "\u9fff")
    ascii_alnum = sum(1 for char in compact if char.isascii() and char.isalnum())
    suspicious = sum(1 for char in compact if "\u0080" <= char <= "\u00ff")
    return (chinese * 3) + ascii_alnum - suspicious
