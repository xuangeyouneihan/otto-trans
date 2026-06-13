import sys
from importlib.metadata import entry_points
from typing import cast

from ..adapter.base import BaseAdapter, Segment
from ..converter.base import BaseConverter
from ..engine.base import BaseTranslator
from ..utils.format import Format, UnsupportedFormatError
from .cache import Cache


class Translator:
    _engines: dict[str, type[BaseTranslator]] = {}
    _converters: dict[str, type[BaseConverter]] = {}
    _adapters: dict[str, type[BaseAdapter]] = {}

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

    @classmethod
    def converters(cls) -> dict[str, type[BaseConverter]]:
        if cls._converters:
            return cls._converters
        from ..converter.html_to_markdown import HTMLToMarkdown
        from ..converter.markdown_to_html import MarkdownToHTML

        cls._converters["html_to_markdown"] = cast(type[BaseConverter], HTMLToMarkdown)
        cls._converters["markdown_to_html"] = cast(type[BaseConverter], MarkdownToHTML)

        for entry in entry_points(group="otto_trans.converter"):
            try:
                cls._converters[entry.name] = cast(type[BaseConverter], entry.load())
            except Exception as e:
                print(f"加载转换器 {entry.name} 时出错: {e}", file=sys.stderr)

        return cls._converters

    @classmethod
    def adapters(cls) -> dict[str, type[BaseAdapter]]:
        if cls._adapters:
            return cls._adapters
        from ..adapter.srt import SRTAdapter

        cls._adapters["srt"] = cast(type[BaseAdapter], SRTAdapter)

        for entry in entry_points(group="otto_trans.adapter"):
            try:
                cls._adapters[entry.name] = cast(type[BaseAdapter], entry.load())
            except Exception as e:
                print(f"加载适配器 {entry.name} 时出错: {e}", file=sys.stderr)

        return cls._adapters

    def __init__(self, engine: str, options: dict | None = None):
        options = options or {}

        self.engines()
        self.converters()
        self.adapters()

        base_engine_name = engine.split(":", 1)[0] if ":" in engine else engine
        engine_cls = self._engines.get(base_engine_name)
        if not engine_cls:
            raise ValueError(f"未知的翻译引擎：{engine}")

        engine_options = engine_cls.options or {}
        for opt_name, opt_meta in engine_options.items():
            expected_type = cast(type, opt_meta["type"])

            if opt_name not in options or (
                not options[opt_name] and options[opt_name] not in (False, 0, 0.0)
            ):
                if opt_meta["required"]:
                    raise ValueError(f"缺少翻译引擎 {engine} 的必需选项：{opt_name}")
                else:
                    # 可选参数值为空 → 不传给引擎
                    continue

            if not isinstance(options[opt_name], expected_type):
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

    def translate_texts(
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
            engine_results = self.engine.translate_texts(
                [m[1] for m in misses], src_lang, tgt_lang
            )
            for (idx, text), result in zip(misses, engine_results):
                results[idx] = result
                self.cache.insert(text, result, self.engine.name, src_lang, tgt_lang)

        return results

    @staticmethod
    def _flatten_segments(segments: list[Segment]) -> list[Segment]:
        """递归展平 Segment 树（含 children），深度优先。"""
        flat: list[Segment] = []
        for s in segments:
            flat.append(s)
            flat.extend(Translator._flatten_segments(s.children))
        return flat

    def find_reverse_converter(
        self, from_fmt: Format, to_fmt: Format
    ) -> type[BaseConverter] | None:
        """查找能将 from_fmt 转回 to_fmt 的转换器。"""
        for c in self.converters().values():
            if from_fmt == c.source and to_fmt == c.target:
                return c
        return None

    def translate_with_adapter(
        self,
        content: bytes,
        src_lang: str,
        tgt_lang: str,
        adapter: type[BaseAdapter],
    ) -> bytes:
        """通过适配器提取文本、翻译、组装，返回 bytes。"""
        segments = adapter.extract(content)
        flat = self._flatten_segments(segments)
        texts = [s.text for s in flat]
        translated = self.translate_texts(texts, src_lang, tgt_lang)
        for s, t in zip(flat, translated):
            s.text = t
        return adapter.reassemble(content, segments)

    async def translate_file(
        self,
        content: bytes,
        src_lang: str,
        tgt_lang: str,
        fmt: Format,
    ) -> tuple[bytes, Format]:
        format_obj = self.engine.supports_format(fmt)
        if not format_obj:
            converter1 = None
            for c in self.converters().values():
                if fmt == c.source and self.engine.supports_format(c.target):
                    converter1 = c
                    break
            if not converter1:
                # 找不到转换器 → 尝试适配器
                adapter = None
                for a in self.adapters().values():
                    if fmt == a.source:
                        adapter = a
                        break
                if adapter:
                    result = self.translate_with_adapter(
                        content, src_lang, tgt_lang, adapter
                    )
                    return result, adapter.source

                raise UnsupportedFormatError.for_engine(
                    self.engine.name, fmt, self.engine.formats
                )
            converted_content = converter1.convert(content)
            translated_content, translated_format = await self.engine.translate_file(
                converted_content, src_lang, tgt_lang, converter1.target
            )
            src_fmt = converter1.source
            converter2 = self.find_reverse_converter(translated_format, src_fmt)
            if converter2:
                return converter2.convert(content), src_fmt
            return translated_content, translated_format
        translated_content, translated_format = await self.engine.translate_file(
            content, src_lang, tgt_lang, format_obj
        )
        if translated_format != format_obj:
            converter2 = self.find_reverse_converter(translated_format, format_obj)
            if converter2:
                return converter2.convert(content), format_obj
        return translated_content, translated_format
