import asyncio
import inspect
from abc import ABC, abstractmethod


class UnsupportedLanguageError(Exception):
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
            text += f"\n可用的源语言如下：{', '.join(sorted(src_available))}"
        if tgt_available:
            text += f"\n可用的目标语言如下：{', '.join(sorted(tgt_available))}"
        return cls(text)


class BaseTranslator(ABC):
    engine_name: str = ""
    friendly_name: str = ""  # 可选的用户友好名称

    options: dict[str, dict[str, str | bool]] = {}

    def __init__(self, config_name: str | None = None):
        self.config_name = config_name

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        opts = cls.__dict__.get("options")
        if opts is None or not isinstance(opts, dict):
            raise TypeError(
                f"{cls.__name__} 必须定义类变量 'options' 且其类型必须是字典"
            )

        for name, meta in opts.items():
            if not isinstance(name, str):
                raise TypeError(f"{cls.__name__}.options 的键必须是字符串")
            if "type" not in meta or meta["type"] not in (
                "str",
                "bool",
                "int",
                "float",
                "list",
                "tuple",
                "set",
                "dict",
            ):
                raise TypeError(
                    f"{cls.__name__}.options['{name}']['type'] 必须是 str、bool、int 或 float"
                )
            if "description" not in meta or not isinstance(meta["description"], str):
                raise TypeError(
                    f"{cls.__name__}.options['{name}']['description'] 必须是字符串"
                )
            if "required" not in meta or not isinstance(meta["required"], bool):
                raise TypeError(
                    f"{cls.__name__}.options['{name}']['required'] 必须是布尔值"
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
    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> str: ...

    async def translate_batch(
        self, texts: list[str], src_lang: str, tgt_lang: str
    ) -> list[str]:
        return await asyncio.gather(*[
            self.translate(t, src_lang, tgt_lang) for t in texts
        ])
