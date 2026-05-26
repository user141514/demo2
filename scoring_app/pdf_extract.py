import re
import zlib

from .core.text_quality import looks_like_garbled_text, looks_like_garbled_fragment


class PdfExtractionError(Exception):
    pass


STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
LITERAL_RE = re.compile(rb"\((?:\\.|[^\\()])*\)")
HEX_RE = re.compile(rb"<([0-9A-Fa-f\s]+)>")


def extract_text_from_pdf_bytes(data):
    if not data.startswith(b"%PDF"):
        raise PdfExtractionError("上传的文件不是有效的 PDF。")

    candidates = []
    for stream in _iter_streams(data):
        candidates.extend(_extract_candidates(stream))

    if not candidates:
        candidates.extend(_extract_candidates(data))

    cleaned = []
    seen = set()
    for candidate in candidates:
        line = _normalize_text(candidate)
        if len(line) < 3 or looks_like_garbled_fragment(line) or line in seen:
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


def _iter_streams(data):
    for match in STREAM_RE.finditer(data):
        stream = match.group(1)
        yield stream
        try:
            yield zlib.decompress(stream)
        except Exception:
            continue


def _extract_candidates(blob):
    candidates = []
    for literal in LITERAL_RE.findall(blob):
        text = _decode_pdf_literal(literal[1:-1])
        if _looks_like_text(text):
            candidates.append(text)

    for match in HEX_RE.findall(blob):
        text = _decode_hex_string(match)
        if _looks_like_text(text):
            candidates.append(text)

    return candidates


def _decode_pdf_literal(raw):
    out = bytearray()
    idx = 0
    while idx < len(raw):
        value = raw[idx]
        if value != 92:
            out.append(value)
            idx += 1
            continue

        idx += 1
        if idx >= len(raw):
            break
        escaped = raw[idx]
        idx += 1
        mapping = {
            ord("n"): b"\n",
            ord("r"): b"\r",
            ord("t"): b"\t",
            ord("b"): b"\b",
            ord("f"): b"\f",
            ord("("): b"(",
            ord(")"): b")",
            ord("\\"): b"\\",
        }
        if escaped in mapping:
            out.extend(mapping[escaped])
            continue
        if 48 <= escaped <= 55:
            octal = bytes([escaped])
            for _ in range(2):
                if idx < len(raw) and 48 <= raw[idx] <= 55:
                    octal += bytes([raw[idx]])
                    idx += 1
                else:
                    break
            out.append(int(octal, 8))
            continue
        out.append(escaped)
    return _decode_text_bytes(bytes(out))


def _decode_hex_string(raw):
    hex_text = re.sub(rb"\s+", b"", raw)
    if len(hex_text) % 2 == 1:
        hex_text = hex_text[:-1]
    if not hex_text:
        return ""
    try:
        payload = bytes.fromhex(hex_text.decode("ascii"))
    except Exception:
        return ""
    return _decode_text_bytes(payload)


def _decode_text_bytes(payload):
    if not payload:
        return ""
    if payload.startswith(b"\xfe\xff"):
        try:
            return payload[2:].decode("utf-16-be")
        except Exception:
            pass
    if payload.startswith(b"\xff\xfe"):
        try:
            return payload[2:].decode("utf-16-le")
        except Exception:
            pass

    if b"\x00" in payload and len(payload) % 2 == 0:
        for encoding in ("utf-16-be", "utf-16-le"):
            try:
                decoded = payload.decode(encoding)
                if _looks_like_text(decoded):
                    return decoded
            except Exception:
                continue

    for encoding in ("utf-8", "gb18030", "latin-1"):
        try:
            decoded = payload.decode(encoding)
            if _looks_like_text(decoded):
                return decoded
        except Exception:
            continue
    return ""


def _looks_like_text(value):
    if not value:
        return False
    trimmed = re.sub(r"\s+", "", value)
    if len(trimmed) < 2:
        return False
    meaningful = sum(1 for char in trimmed if char.isalnum() or "\u4e00" <= char <= "\u9fff")
    return meaningful >= max(2, len(trimmed) // 3)


def _normalize_text(value):
    cleaned = value.replace("\x00", " ")
    cleaned = re.sub(r"\\[rn]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
