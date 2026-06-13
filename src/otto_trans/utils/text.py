"""文本工具：编码检测等。"""

import chardet


def detect_encoding(data: bytes) -> str:
    """使用 chardet 检测 bytes 数据的编码。"""
    result = chardet.detect(data)
    encoding = result["encoding"]
    return encoding if encoding else "utf-8-sig"
