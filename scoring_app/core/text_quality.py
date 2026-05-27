# Canonical charset (from scoring.py:14)
# Merged from all 4 original definitions (scoring.py, pdf_extract.py, score_service.py)
# plus test fixtures. Each source had a different subset of mojibake characters.
SUSPICIOUS_GARBLED_CHARS = frozenset(
    "锟鈥銆鏈璇鍙鐨褰闂閫浠缁鍚"   # scoring.py + pdf_extract.py canonical
    "閿熼垾閵嗛張鐠囬崣閻ㄨぐ闂傞柅娴犵紒閸"   # score_service.py alternate charset
    "閿焃閸鐠閺閻瑜"                         # test fixture mojibake
)


def looks_like_garbled_text(text, min_suspicious=2, min_ratio=0.15):
    """Unified garbled/mojibake detection."""
    if not text:
        return True
    compact = ''.join(text.split())
    if not compact:
        return True
    suspicious = sum(1 for ch in compact if ch == '\ufffd' or ch in SUSPICIOUS_GARBLED_CHARS)
    ratio = suspicious / len(compact)
    return suspicious >= min_suspicious and ratio >= min_ratio


def looks_like_garbled_fragment(text):
    """Stricter fragment-level check used by pdf_extract.py."""
    return looks_like_garbled_text(text, min_suspicious=2, min_ratio=0.35)
