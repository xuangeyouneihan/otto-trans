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
