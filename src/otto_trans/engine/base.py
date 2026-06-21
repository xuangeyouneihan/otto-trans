import inspect
from abc import ABC, abstractmethod

from ..utils.format import Format


class UnsupportedLanguageError(ValueError):
    """引擎不支持的语言代码"""

    def __init__(
        self,
        engine_name: str = "",
        src_code: str = "",
        tgt_code: str = "",
        src_available: set[str] | None = None,
        tgt_available: set[str] | None = None,
        supported_pairs: set[tuple[str, str]] | None = None,
        blocked_pairs: set[tuple[str, str]] | None = None,
    ):
        if not src_code:
            if not engine_name:
                super().__init__()
            else:
                super().__init__(engine_name)
        else:
            text = f"当前翻译引擎 {engine_name} 不支持指定的语言 '{src_code}' -> '{tgt_code}'。"
            if src_available:
                text += f"\n\n可用的源语言如下：\n{', '.join(sorted(src_available))}"
            if tgt_available:
                text += f"\n\n可用的目标语言如下：\n{', '.join(sorted(tgt_available))}"
            if supported_pairs:
                pairs = ", ".join(f"{s}→{t}" for s, t in sorted(supported_pairs))
                text += f"\n\n支持的翻译方向：\n{pairs}"
            if blocked_pairs:
                pairs = ", ".join(f"{s}→{t}" for s, t in sorted(blocked_pairs))
                text += f"\n\n不支持的翻译方向：\n{pairs}"
            super().__init__(text)


class BaseTranslator(ABC):
    engine_name: str = ""
    friendly_name: str = ""  # 可选的用户友好名称

    options: dict[
        str, dict[str, type | str | bool | set[str]]
    ] = {}  # 可选的配置选项定义，其中的键是选项名称，值是一个包含 "type": type、"description": str 和 "required": bool 键的字典
    formats: set[Format] = (
        set()
    )  # 可选的格式支持列表，其中的元素必须是 Format 对象，且不能重复

    def __init__(self, config_name: str | None = None):
        self.config_name = config_name

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        opts = cls.__dict__.get("options")
        if opts is not None:
            if not isinstance(opts, dict):
                raise TypeError(f"{cls.__name__}.options 必须是一个字典")
            for name, meta in opts.items():
                if not isinstance(name, str):
                    raise TypeError(f"{cls.__name__}.options 的键必须是字符串")
                if not isinstance(meta, dict):
                    raise TypeError(
                        f"{cls.__name__}.options['{name}'] 必须是一个字典，包含 'type'、'description' 和 'required' 键"
                    )
                if (
                    "type" not in meta
                    or not isinstance(meta["type"], type)
                    or meta["type"].__module__ != "builtins"
                ):
                    raise TypeError(
                        f"{cls.__name__}.options['{name}']['type'] 必须是一个 Python 内置类型对象"
                    )
                if "description" not in meta or not isinstance(
                    meta["description"], str
                ):
                    raise TypeError(
                        f"{cls.__name__}.options['{name}']['description'] 必须是字符串"
                    )
                if "required" not in meta or not isinstance(meta["required"], bool):
                    raise TypeError(
                        f"{cls.__name__}.options['{name}']['required'] 必须是布尔值"
                    )
                if (
                    "scope" not in meta
                    or not isinstance(meta["scope"], set)
                    or not meta["scope"]
                    or not meta["scope"].issubset({"text", "file"})
                ):
                    raise TypeError(
                        f"{cls.__name__}.options['{name}']['scope'] 必须是一个集合，包含 'text' 和/或 'file'"
                    )

        fmts = cls.__dict__.get("formats")
        if fmts is not None:
            if not isinstance(fmts, set):
                raise TypeError(
                    f"{cls.__name__}.formats 必须是一个集合，包含不重复的 Format 对象"
                )
            for fmt in fmts:
                if not isinstance(fmt, Format):
                    raise TypeError(
                        f"{cls.__name__}.formats 中的每个元素都必须是 Format 对象"
                    )

        # 验证子类的 __init__ 支持 config_name 参数
        sig = inspect.signature(cls.__init__)
        has_config_name = "config_name" in sig.parameters
        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        if not has_config_name and not has_kwargs:
            raise TypeError(
                f"{cls.__name__}.__init__ 必须接受 config_name 参数或 **kwargs"
            )

    @property
    def name(self) -> str:
        engine_name = self.engine_name if self.engine_name else type(self).__name__
        if self.config_name:
            return f"{engine_name}:{self.config_name}"
        return engine_name

    @abstractmethod
    def translate_texts(
        self,
        texts: list[str],
        src_lang: str,
        tgt_lang: str,
    ) -> list[str]: ...

    async def translate_file(
        self,
        content: bytes,
        src_lang: str,
        tgt_lang: str,
        fmt: Format,
    ) -> tuple[bytes, Format]:
        raise NotImplementedError(
            f"{self.friendly_name + '（' + self.engine_name + '）' if self.friendly_name else self.engine_name} 不支持文件翻译"
        )

    def supports_format(self, fmt: Format | str) -> Format | None:
        """检查引擎是否支持该格式，支持则返回对应的 Format 对象，否则返回 None。

        子类可重写以实现动态格式支持（如 OpenAI 支持任意文本格式）。
        """
        for f in self.formats or []:
            if f == fmt:  # Format.__eq__ 支持 str（name/extension/mime_type）
                return f
        return None
