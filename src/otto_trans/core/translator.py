from ..engine.base import BaseTranslator
from .cache import Cache

class Translator:
    def __init__(self, engine: BaseTranslator, cache: Cache):
        self.engine = engine
        self.cache = cache
    
    async def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        cached = self.cache.query(text, self.engine.name)
        if cached is not None:
            return cached
        result = await self.engine.translate(text, from_lang, to_lang)
        self.cache.insert(text, result, self.engine.name)
        return result
    
    async def translate_batch(self, texts: list[str], from_lang: str, to_lang: str) -> list[str]:
        results = []
        misses = []    # 哪些没命中

        for idx, text in enumerate(texts):
            cached = self.cache.query(text, self.engine.name)
            if cached is not None:
                results.append(cached)
            else:
                results.append(None)  # 占位
                misses.append((idx, text))

        if misses:
            engine_results = await self.engine.translate_batch(
                [m[1] for m in misses], from_lang, to_lang
            )
            for (idx, text), result in zip(misses, engine_results):
                results[idx] = result
                self.cache.insert(text, result, self.engine.name)

        return results