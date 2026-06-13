import mistune  # type: ignore[import-untyped]

from ..utils.format import Format
from ..utils.text import detect_encoding
from .base import BaseConverter


class MarkdownToHTML(BaseConverter):
    """Markdown → HTML 转换器"""

    source = Format(
        name="markdown",
        extensions={".md", ".mdown", ".markdown"},
        mime_type="text/markdown",
    )
    target = Format(
        name="html",
        extensions={".html", ".htm"},
        mime_type="text/html",
    )

    @staticmethod
    def convert(content: bytes) -> bytes:
        text = content.decode(detect_encoding(content))
        html = mistune.html(text)
        return str(html).encode("utf-8-sig")
