from ..engine.base import BaseTranslator
from .cache import Cache


class Translator:
    engine: BaseTranslator

    def __init__(self, engine: str, options: dict | None = None):
        options = options or {}

        match engine.lower():
            case "youdao":
                from ..engine.youdao import YoudaoTranslator

                if (
                    "app_key" not in options
                    or "app_secret" not in options
                    or not options["app_key"]
                    or not options["app_secret"]
                ):
                    raise ValueError("使用有道翻译引擎需要提供 app_key 和 app_secret。")
                self.engine = YoudaoTranslator(**options)

            case name if name.startswith("openai"):
                from ..engine.openai import OpenAITranslator

                if (
                    "endpoint" not in options
                    or "api_key" not in options
                    or "model" not in options
                    or not options["endpoint"]
                    or not options["api_key"]
                    or not options["model"]
                ):
                    raise ValueError(
                        "使用 OpenAI 翻译引擎需要提供 endpoint、api_key 和 model。"
                    )
                self.engine = OpenAITranslator(**options)  # type: ignore[assignment]

            case "deepl":
                from ..engine.deepl import DeepLTranslator

                if "auth_key" not in options or not options["auth_key"]:
                    raise ValueError("使用 DeepL 翻译引擎需要提供 auth_key。")
                self.engine = DeepLTranslator(**options)  # type: ignore[assignment]

            case _:
                raise ValueError(f"不支持的翻译引擎：{engine}")

        self.cache = Cache()

    async def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        cached = self.cache.query(text, self.engine.name, from_lang, to_lang)
        if cached is not None:
            return cached
        result = await self.engine.translate(text, from_lang, to_lang)
        self.cache.insert(text, result, self.engine.name, from_lang, to_lang)
        return result

    async def translate_batch(
        self, texts: list[str], from_lang: str, to_lang: str
    ) -> list[str]:
        results: list[str] = []
        misses: list[tuple[int, str]] = []

        for idx, text in enumerate(texts):
            cached = self.cache.query(text, self.engine.name, from_lang, to_lang)
            if cached is not None:
                results.append(cached)
            else:
                results.append("")  # 占位，随后会被覆盖
                misses.append((idx, text))

        if misses:
            engine_results = await self.engine.translate_batch(
                [m[1] for m in misses], from_lang, to_lang
            )
            for (idx, text), result in zip(misses, engine_results):
                results[idx] = result
                self.cache.insert(text, result, self.engine.name, from_lang, to_lang)

        return results
