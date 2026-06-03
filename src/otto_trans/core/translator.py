import sys
from importlib.metadata import entry_points
from typing import cast

from ..engine.base import BaseTranslator
from .cache import Cache


class Translator:
    _engines: dict[str, type[BaseTranslator]] = {}

    _TYPE_CHECKERS = {
        "str": str,
        "bool": bool,
        "int": int,
        "float": float,
        "list": list,
        "tuple": tuple,
        "set": set,
        "dict": dict,
    }

    @classmethod
    def engines(cls) -> dict[str, type[BaseTranslator]]:
        """注册内置翻译引擎并动态发现可用的翻译引擎，返回它们的名称列表。"""

        if cls._engines:
            return cls._engines

        from ..engine.deepl import DeepLTranslator
        from ..engine.openai import OpenAITranslator
        from ..engine.youdao import YoudaoTranslator

        cls._engines["youdao"] = cast(type[BaseTranslator], YoudaoTranslator)
        cls._engines["openai"] = cast(type[BaseTranslator], OpenAITranslator)
        cls._engines["deepl"] = cast(type[BaseTranslator], DeepLTranslator)

        for entry in entry_points(group="otto_trans.engine"):
            try:
                cls._engines[entry.name] = cast(type[BaseTranslator], entry.load())
            except Exception as e:
                print(f"加载翻译引擎 {entry.name} 时出错: {e}", file=sys.stderr)

        return cls._engines

    def __init__(self, engine: str, options: dict | None = None):
        options = options or {}

        self.engines()

        base_engine_name = engine.split(":", 1)[0] if ":" in engine else engine
        engine_cls = self._engines.get(base_engine_name)
        if not engine_cls:
            raise ValueError(f"未知的翻译引擎：{engine}")

        for opt_name, opt_meta in engine_cls.options.items():
            if opt_meta["required"] and opt_name not in options:
                raise ValueError(f"缺少翻译引擎 {engine} 的必需选项：{opt_name}")

            expected_type = self._TYPE_CHECKERS.get(str(opt_meta["type"]))
            if expected_type is None:
                raise ValueError(
                    f"翻译引擎 {engine} 的选项 {opt_name} 定义了未知的类型：{opt_meta['type']}"
                )
            if opt_name in options and options[opt_name] is None:
                # 可选参数值为 None → 不传给引擎
                if not opt_meta.get("required", False):
                    continue
            if opt_name in options and not isinstance(options[opt_name], expected_type):
                if isinstance(options[opt_name], str) and expected_type is bool:
                    # 特殊处理字符串转换为布尔值
                    if options[opt_name].lower() in (
                        "true",
                        "false",
                        "yes",
                        "no",
                        "on",
                        "off",
                        "enable",
                        "disable",
                        "enabled",
                        "disabled",
                    ):
                        options[opt_name] = options[opt_name].lower() in (
                            "true",
                            "yes",
                            "on",
                            "enable",
                            "enabled",
                        )
                    else:
                        raise TypeError(
                            f"翻译引擎 {engine} 的选项 {opt_name} 应该是布尔值（True/False），实际是字符串：{options[opt_name]}"
                        )
                else:
                    try:
                        options[opt_name] = expected_type(options[opt_name])
                    except Exception:
                        raise TypeError(
                            f"翻译引擎 {engine} 的选项 {opt_name} 应该是 {expected_type.__name__} 类型，实际是 {type(options[opt_name]).__name__} 类型"
                        )

        self.engine = engine_cls(**options)  # type: ignore[call-arg]

        self.cache = Cache()

    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        cached = self.cache.query(text, self.engine.name, src_lang, tgt_lang)
        if cached is not None:
            return cached
        result = await self.engine.translate(text, src_lang, tgt_lang)
        self.cache.insert(text, result, self.engine.name, src_lang, tgt_lang)
        return result

    async def translate_batch(
        self, texts: list[str], src_lang: str, tgt_lang: str
    ) -> list[str]:
        results: list[str] = []
        misses: list[tuple[int, str]] = []

        for idx, text in enumerate(texts):
            cached = self.cache.query(text, self.engine.name, src_lang, tgt_lang)
            if cached is not None:
                results.append(cached)
            else:
                results.append("")  # 占位，随后会被覆盖
                misses.append((idx, text))

        if misses:
            engine_results = await self.engine.translate_batch(
                [m[1] for m in misses], src_lang, tgt_lang
            )
            for (idx, text), result in zip(misses, engine_results):
                results[idx] = result
                self.cache.insert(text, result, self.engine.name, src_lang, tgt_lang)

        return results
