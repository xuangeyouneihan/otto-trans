from markdownify import markdownify

from ..utils.format import Format
from ..utils.text import detect_encoding
from .base import BaseConverter


class HTMLToMarkdown(BaseConverter):
    """HTML → Markdown 转换器"""

    source = Format(
        name="html",
        extensions={".html", ".htm"},
        mime_type="text/html",
    )
    target = Format(
        name="markdown",
        extensions={".md", ".mdown", ".markdown"},
        mime_type="text/markdown",
    )

    @staticmethod
    def convert(content: bytes) -> bytes:
        text = content.decode(detect_encoding(content))
        md = markdownify(text, heading_style="ATX")
        return md.encode("utf-8-sig")
