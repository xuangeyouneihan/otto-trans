from dataclasses import dataclass, field


@dataclass
class Format:
    name: str
    description: str = ""
    extensions: set[str] = field(default_factory=set)
    mime_type: str = ""  # 输出端的 MIME 类型，用于匹配下载响应

    def __eq__(self, other):
        if isinstance(other, str):
            return (
                other == self.name
                or other in self.extensions
                or other == self.mime_type
                or other in [e[1:] for e in self.extensions if e.startswith(".")]
            )
        if isinstance(other, Format):
            self_exts = {e if e.startswith(".") else f".{e}" for e in self.extensions}
            other_exts = {e if e.startswith(".") else f".{e}" for e in other.extensions}
            return (
                (self_exts and other_exts)
                and (self_exts.issubset(other_exts) or other_exts.issubset(self_exts))
            ) or (
                (not self_exts and not other_exts)
                and (self.name == other.name or self.mime_type == other.mime_type)
            )
        return super().__eq__(other)

    def __hash__(self):
        return hash((self.name, tuple(sorted(self.extensions)), self.mime_type))


# ── 格式注册表 ──────────────────────────────────────────────

_FORMAT_REGISTRY: dict[str, Format] = {}


def _register(fmt: Format) -> Format:
    _FORMAT_REGISTRY[fmt.name] = fmt
    return fmt


def get_format(name: str) -> Format | None:
    """按名称查找已注册的格式。"""
    return _FORMAT_REGISTRY.get(name)


def all_formats() -> dict[str, Format]:
    """返回所有已注册格式的名称→Format 映射。"""
    return dict(_FORMAT_REGISTRY)


# ── 文本类格式 ──────────────────────────────────────────────

PLAIN_TEXT = _register(
    Format(
        name="plain-text",
        description="纯文本格式，适用于一般文本内容",
        extensions={".txt", ".text"},
        mime_type="text/plain",
    )
)

MARKDOWN = _register(
    Format(
        name="markdown",
        description="Markdown 格式",
        extensions={".md", ".markdown"},
        mime_type="text/markdown",
    )
)

LATEX = _register(
    Format(
        name="latex",
        description="LaTeX 文档格式，适用于 LaTeX 编辑器",
        extensions={".tex"},
        mime_type="application/x-latex",
    )
)

TYPST = _register(
    Format(
        name="typst",
        description="Typst 文档格式，适用于 Typst 编辑器",
        extensions={".typ", ".typst"},
        mime_type="application/x-typst",
    )
)

CSV = _register(
    Format(
        name="csv",
        description="CSV 逗号分隔值格式",
        extensions={".csv"},
        mime_type="text/csv",
    )
)

JSON = _register(
    Format(
        name="json",
        description="JSON 数据格式",
        extensions={".json"},
        mime_type="application/json",
    )
)

XML = _register(
    Format(
        name="xml",
        description="XML 格式",
        extensions={".xml"},
        mime_type="application/xml",
    )
)

YAML = _register(
    Format(
        name="yaml",
        description="YAML 格式",
        extensions={".yaml", ".yml"},
        mime_type="application/x-yaml",
    )
)

# ── 网页类格式 ──────────────────────────────────────────────

HTML = _register(
    Format(
        name="html",
        description="HTML 网页格式，自动识别标签仅翻译文本内容",
        extensions={".html", ".htm"},
        mime_type="text/html",
    )
)

# ── 字幕类格式 ──────────────────────────────────────────────

SRT = _register(
    Format(
        name="srt",
        description="SubRip 字幕格式",
        extensions={".srt"},
        mime_type="application/x-subrip",
    )
)

VTT = _register(
    Format(
        name="vtt",
        description="WebVTT 字幕格式",
        extensions={".vtt"},
        mime_type="text/vtt",
    )
)

ASS = _register(
    Format(
        name="ass",
        description="Advanced Substation Alpha 字幕格式",
        extensions={".ass", ".ssa"},
        mime_type="text/x-ssa",
    )
)

# ── 文档类格式 ──────────────────────────────────────────────

PDF = _register(
    Format(
        name="pdf",
        description="PDF 格式",
        extensions={".pdf"},
        mime_type="application/pdf",
    )
)

MS_WORD = _register(
    Format(
        name="ms-word",
        description="Microsoft Word 格式，适用于 .docx 文件",
        extensions={".docx"},
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
)

MS_WORD_LEGACY = _register(
    Format(
        name="ms-word-legacy",
        description="Microsoft Word 97-2003 格式，适用于 .doc 文件",
        extensions={".doc"},
        mime_type="application/msword",
    )
)

MS_POWERPOINT = _register(
    Format(
        name="ms-powerpoint",
        description="Microsoft PowerPoint 格式，适用于 .pptx 文件",
        extensions={".pptx"},
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
)

MS_POWERPOINT_LEGACY = _register(
    Format(
        name="ms-powerpoint-legacy",
        description="Microsoft PowerPoint 97-2003 格式，适用于 .ppt 文件",
        extensions={".ppt"},
        mime_type="application/vnd.ms-powerpoint",
    )
)

MS_EXCEL = _register(
    Format(
        name="ms-excel",
        description="Microsoft Excel 格式，适用于 .xlsx 文件",
        extensions={".xlsx"},
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
)

MS_EXCEL_LEGACY = _register(
    Format(
        name="ms-excel-legacy",
        description="Microsoft Excel 97-2003 格式，适用于 .xls 文件",
        extensions={".xls"},
        mime_type="application/vnd.ms-excel",
    )
)

XLIFF = _register(
    Format(
        name="xliff",
        description="XLIFF 翻译文件格式",
        extensions={".xlf", ".xliff"},
        mime_type="application/xliff+xml",
    )
)

# ── 图片类格式 ──────────────────────────────────────────────

JPEG = _register(
    Format(
        name="jpeg",
        description="JPEG 图像格式",
        extensions={".jpg", ".jpeg", ".jpe"},
        mime_type="image/jpeg",
    )
)

PNG = _register(
    Format(
        name="png",
        description="PNG 图像格式",
        extensions={".png"},
        mime_type="image/png",
    )
)

GIF = _register(
    Format(
        name="gif",
        description="GIF 图像格式",
        extensions={".gif"},
        mime_type="image/gif",
    )
)

WEBP = _register(
    Format(
        name="webp",
        description="WebP 图像格式",
        extensions={".webp"},
        mime_type="image/webp",
    )
)

BMP = _register(
    Format(
        name="bmp",
        description="BMP 位图格式",
        extensions={".bmp"},
        mime_type="image/bmp",
    )
)


class UnsupportedFormatError(ValueError):
    @classmethod
    def for_engine(
        cls, engine_name: str, fmt: Format | str, formats: set[Format] | None = None
    ) -> "UnsupportedFormatError":
        texts = f"翻译引擎 {engine_name} 不支持格式：{fmt.name if isinstance(fmt, Format) else fmt}。"
        if formats:
            texts += "\n\n支持的格式包括："
            for f in formats:
                exts = ", ".join(sorted(f.extensions)) if f.extensions else None
                texts += f"\n- {f.name}: {exts}" if exts else f"\n- {f.name}"
        return cls(texts)
