import asyncio
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
        text = f"当前翻译引擎（{engine_name}）不支持指定的语言 '{src_code}' -> '{tgt_code}'。"
        if src_available:
            text += f"\n可用的源语言如下：{', '.join(sorted(src_available))}"
        if tgt_available:
            text += f"\n可用的目标语言如下：{', '.join(sorted(tgt_available))}"
        return cls(text)


class BaseTranslator(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> str: ...

    async def translate_batch(
        self, texts: list[str], src_lang: str, tgt_lang: str
    ) -> list[str]:
        return await asyncio.gather(*[
            self.translate(t, src_lang, tgt_lang) for t in texts
        ])
