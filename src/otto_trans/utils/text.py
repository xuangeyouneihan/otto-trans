"""文本工具：编码检测等。"""

import chardet

from .format import Format
from .html import fix_html


def detect_encoding(data: bytes) -> str:
    """使用 chardet 检测 bytes 数据的编码。"""
    result = chardet.detect(data)
    encoding = result["encoding"]
    return encoding if encoding else "utf-8-sig"


def utf_8(data: bytes, fmt: Format) -> bytes:
    """将 bytes 数据解码为文本再编码为 utf-8-sig。"""
    if not fmt.mime_type.startswith("text/"):
        return data
    text = data.decode(detect_encoding(data), errors="replace")
    if fmt == "html":
        fixed = fix_html(text)
        if fixed != text:
            text = fixed
    return text.encode("utf-8-sig")
