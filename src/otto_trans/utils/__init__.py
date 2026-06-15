from .format import Format, UnsupportedFormatError
from .html import fix_html
from .text import detect_encoding

__all__ = ["Format", "UnsupportedFormatError", "fix_html", "detect_encoding"]
