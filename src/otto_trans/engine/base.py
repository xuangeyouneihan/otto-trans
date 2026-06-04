import asyncio
import inspect
from abc import ABC, abstractmethod

from ..utils.format import Format


class UnsupportedLanguageError(ValueError):
    """引擎不支持的语言代码"""

    @classmethod
    def for_engine(
        cls,
        engine_name: str,
        src_code: str,
        tgt_code: str,
        src_available: list[str] | None = None,
        tgt_available: list[str] | None = None,
    ) -> "UnsupportedLanguageError":
        text = f"当前翻译引擎 {engine_name} 不支持指定的语言 '{src_code}' -> '{tgt_code}'。"
        if src_available:
            text += f"\n\n可用的源语言如下：{', '.join(sorted(src_available))}"
        if tgt_available:
            text += f"\n\n可用的目标语言如下：{', '.join(sorted(tgt_available))}"
        return cls(text)


class BaseTranslator(ABC):
    engine_name: str = ""
    friendly_name: str = ""  # 可选的用户友好名称

    options: dict[
        str, dict[str, type | str | bool]
    ] = {}  # 可选的配置选项定义，其中的键是选项名称，值是一个包含 "type": type、"description": str 和 "required": bool 键的字典
    formats: list[
        Format
    ] = []  # 可选的格式支持列表，其中的元素必须是 Format 对象，且不能重复

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

        fmts = cls.__dict__.get("formats")
        if fmts is not None:
            if not isinstance(fmts, list):
                raise TypeError(
                    f"{cls.__name__}.formats 必须是一个列表，包含不重复的 Format 对象"
                )
            for fmt in fmts:
                if not isinstance(fmt, Format):
                    raise TypeError(
                        f"{cls.__name__}.formats 中的每个元素都必须是 Format 对象"
                    )
            if len(fmts) != len(set(fmts)):
                raise ValueError(f"{cls.__name__}.formats 中存在重复的 Format 对象")

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
    async def translate(
        self, text: str, src_lang: str, tgt_lang: str, fmt: Format | None = None
    ) -> str: ...

    async def translate_batch(
        self,
        texts: list[str],
        src_lang: str,
        tgt_lang: str,
        fmt: Format | None = None,
    ) -> list[str]:
        return await asyncio.gather(*[
            self.translate(t, src_lang, tgt_lang, fmt) for t in texts
        ])
