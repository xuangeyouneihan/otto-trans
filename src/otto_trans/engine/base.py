from abc import ABC, abstractmethod
import asyncio

class BaseTranslator(ABC):
    @abstractmethod
    async def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        ...

    async def translate_batch(self, texts: list[str], from_lang: str, to_lang: str) -> list[str]:
        return await asyncio.gather(
            *[self.translate(t, from_lang, to_lang) for t in texts]
        )