from abc import ABC, abstractmethod
import asyncio

class UnsupportedLanguageError(Exception):
    """引擎不支持的语言代码"""

    @classmethod
    def for_engine(cls, engine_name: str, from_code: str, to_code: str, from_available: list[str], to_available: list[str]) -> "UnsupportedLanguageError":
        return cls(
            f"当前翻译引擎（{engine_name}）不支持指定的语言 '{from_code}' -> '{to_code}'。\n"
            f"可用的源语言如下：{', '.join(sorted(from_available))}\n"
            f"可用的目标语言如下：{', '.join(sorted(to_available))}\n"
        )

class BaseTranslator(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        ...

    async def translate_batch(self, texts: list[str], from_lang: str, to_lang: str) -> list[str]:
        return await asyncio.gather(
            *[self.translate(t, from_lang, to_lang) for t in texts]
        )