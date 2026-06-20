import sys
from importlib.metadata import entry_points
from typing import Callable, cast

from ..adapter.base import BaseAdapter, Segment
from ..converter.base import BaseConverter
from ..engine.base import BaseTranslator
from ..utils.format import PLAIN_TEXT, Format, UnsupportedFormatError
from ..utils.text import detect_encoding
from .cache import Cache


class Translator:
    """翻译门面（Facade），聚合引擎、转换器、适配器、缓存。

    职责：
    - 管理插件注册表（引擎 / 转换器 / 适配器），支持 entry_points 自动发现
    - 文本翻译（带缓存）
    - 文件翻译（自动路由：引擎原生 → 转换器 → 适配器 → 报错）
    - 通过 `on_warning` 回调将警告交由调用方处理（解耦输出方式）

    用法::

        translator = Translator("openai", {"api_key": "..."}, on_warning=my_logger)
        results = translator.translate_texts(["hello"], "en", "zh")
        result_bytes, fmt = await translator.translate_file(b"...", "en", "zh", html_fmt)
    """

    _engines: dict[str, type[BaseTranslator]] = {}
    _converters: dict[str, type[BaseConverter]] = {}
    _adapters: dict[str, type[BaseAdapter]] = {}

    @classmethod
    def engines(
        cls, on_warning: Callable[[str], None] = lambda msg: print(msg, file=sys.stderr)
    ) -> dict[str, type[BaseTranslator]]:
        """注册内置翻译引擎并动态发现可用的翻译引擎，返回它们的名称列表。"""

        if cls._engines:
            # 已注册过了就直接返回，避免重复导入和加载插件
            return cls._engines

        # ── 注册内置引擎 ──
        from ..engine.deepl import DeepLTranslator
        from ..engine.openai import OpenAITranslator
        from ..engine.youdao import YoudaoTranslator

        cls._engines["youdao"] = cast(type[BaseTranslator], YoudaoTranslator)
        cls._engines["openai"] = cast(type[BaseTranslator], OpenAITranslator)
        cls._engines["deepl"] = cast(type[BaseTranslator], DeepLTranslator)

        # ── 通过 entry_points 动态发现插件 ──
        for entry in entry_points(group="otto_trans.engine"):
            try:
                cls._engines[entry.name] = cast(type[BaseTranslator], entry.load())
            except Exception as e:
                on_warning(f"加载翻译引擎 {entry.name} 时出错: {e}")

        return cls._engines

    @classmethod
    def converters(
        cls, on_warning: Callable[[str], None] = lambda msg: print(msg, file=sys.stderr)
    ) -> dict[str, type[BaseConverter]]:
        """注册内置格式转换器并动态发现插件，返回名称→类的映射。"""
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
                on_warning(f"加载转换器 {entry.name} 时出错: {e}")

        return cls._converters

    @classmethod
    def adapters(
        cls, on_warning: Callable[[str], None] = lambda msg: print(msg, file=sys.stderr)
    ) -> dict[str, type[BaseAdapter]]:
        """注册内置格式适配器并动态发现插件，返回名称→类的映射。"""
        if cls._adapters:
            return cls._adapters
        from ..adapter.srt import SRTAdapter

        cls._adapters["srt"] = cast(type[BaseAdapter], SRTAdapter)

        for entry in entry_points(group="otto_trans.adapter"):
            try:
                cls._adapters[entry.name] = cast(type[BaseAdapter], entry.load())
            except Exception as e:
                on_warning(f"加载适配器 {entry.name} 时出错: {e}")

        return cls._adapters

    def __init__(
        self,
        engine: str,
        options: dict | None = None,
        on_warning: Callable[[str], None] = lambda msg: print(msg, file=sys.stderr),
    ):
        """初始化翻译门面。

        Args:
            engine: 引擎名称，支持 `"name:config"` 语法指定配置方案
            options: 引擎选项，会与配置文件合并并进行类型校验与转换
            on_warning: 警告回调，默认 print 到 stderr，
                        传 `None` 可静默所有警告

        Raises:
            ValueError: 引擎不存在或缺少必需选项
            TypeError: 选项类型不匹配
        """
        options = options or {}

        self.engines(on_warning=on_warning)
        self.converters(on_warning=on_warning)
        self.adapters(on_warning=on_warning)

        base_engine_name = engine.split(":", 1)[0] if ":" in engine else engine
        engine_cls = self._engines.get(base_engine_name)
        if not engine_cls:
            raise ValueError(f"未知的翻译引擎：{engine}")

        engine_options = engine_cls.options or {}
        # ── 选项校验与类型转换 ──
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
        self.on_warning = on_warning

        self.cache = Cache()

    def translate_texts(
        self, texts: list[str], src_lang: str, tgt_lang: str
    ) -> list[str]:
        """批量翻译纯文本（带缓存）。

        先查缓存，命中的直接返回；未命中的批量提交给引擎，结果写入缓存。
        """
        # ── 查缓存 ──
        results: list[str] = []
        misses: list[tuple[int, str]] = []

        for idx, text in enumerate(texts):
            cached = self.cache.query(text, self.engine.name, src_lang, tgt_lang)
            if cached is not None:
                results.append(cached)
            else:
                results.append("")  # 占位
                misses.append((idx, text))

        # ── 批量翻译未命中 ──
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

    def _find_in_converter(
        self, src_fmt: str | Format, in_conv: str | type[BaseConverter] | None = None
    ) -> type[BaseConverter] | None:
        """查找输入转换器：将 src_fmt 转为引擎支持的中间格式。

        Args:
            src_fmt: 源格式
            in_conv: 用户指定的转换器名称或类，为 None 时自动发现

        Returns:
            匹配的转换器类，找不到返回 None
        """
        if in_conv is not None:
            # 优先通过名称匹配转换器
            conv_cls = None
            if isinstance(in_conv, type):
                conv_cls = in_conv
            else:
                conv_cls = self.converters().get(in_conv)
            if (
                conv_cls
                and conv_cls.source == src_fmt
                and self.engine.supports_format(conv_cls.target)
            ):
                return conv_cls
            self.on_warning(
                "指定的输入转换器"
                + (" '" + in_conv + "' " if isinstance(in_conv, str) else "")
                + f"不存在或不适用于翻译器 {self.engine.name}，将尝试其他转换器或适配器",
            )
        # 名称匹配失败或未指定名称 → 遍历查找转换器
        for c in self.converters().values():
            if src_fmt == c.source and self.engine.supports_format(c.target):
                return c
        return None

    def _find_out_converter(
        self,
        src_fmt: str | Format,
        out_fmt: str | Format,
        out_conv: str | type[BaseConverter] | None = None,
    ) -> type[BaseConverter] | None:
        """查找输出转换器（反向）：将引擎输出的 out_fmt 转回 src_fmt。

        Args:
            src_fmt: 期望恢复的目标格式
            out_fmt: 引擎实际输出的格式
            out_conv: 用户指定的转换器名称或类，为 None 时自动发现

        Returns:
            匹配的转换器类，找不到返回 None
        """
        if out_conv is not None:
            # 优先通过名称匹配转换器
            conv_cls = None
            if isinstance(out_conv, type):
                conv_cls = out_conv
            else:
                conv_cls = self.converters().get(out_conv)
            if conv_cls and conv_cls.source == out_fmt and conv_cls.target == src_fmt:
                return conv_cls
            self.on_warning(
                "指定的输出转换器"
                + (" '" + out_conv + "' " if isinstance(out_conv, str) else "")
                + f"不存在或不适用于翻译器 {self.engine.name} 的输出格式 {out_fmt}，将尝试其他转换器"
            )
        # 名称匹配失败或未指定名称 → 遍历查找转换器
        for c in self.converters().values():
            if out_fmt == c.source and src_fmt == c.target:
                return c
        return None

    def _find_adapter(
        self, src_fmt: str | Format, adp: str | type[BaseAdapter] | None = None
    ) -> type[BaseAdapter] | None:
        """查找格式适配器：能直接处理 src_fmt（提取文本→翻译→组装）。

        Args:
            src_fmt: 源格式
            adp: 用户指定的适配器名称或类，为 None 时自动发现

        Returns:
            匹配的适配器类，找不到返回 None
        """
        if adp is not None:
            adp_cls = None
            if isinstance(adp, type):
                adp_cls = adp
            else:
                adp_cls = self.adapters().get(adp)
            if adp_cls and adp_cls.source == src_fmt:
                return adp_cls
            self.on_warning(
                "指定的适配器"
                + (" '" + adp + "' " if isinstance(adp, str) else "")
                + f"不存在或不适用于格式 {src_fmt}，将尝试其他转换器或适配器"
            )
            return None
        for a in self.adapters().values():
            if src_fmt == a.source:
                return a
        return None

    def _translate_with_adapter(
        self,
        content: bytes,
        src_lang: str,
        tgt_lang: str,
        adapter: type[BaseAdapter],
    ) -> bytes:
        """通过适配器提取文本、翻译、组装，返回 bytes。"""
        segments = adapter.extract(content)
        flat = self._flatten_segments(
            segments
        )  # 这里的 segment 和 segments 里的是同一批对象，修改 segment.text 会影响 segments 中的文本
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
        fmt: str | Format,
        converter: str | None = None,
        adapter: str | type[BaseAdapter] | None = None,
    ) -> tuple[bytes, Format]:
        """翻译文件内容，自动路由转换器/适配器。

        路由优先级（非原生格式）::

            用户指定 adapter → adapter
            → 用户指定 in_converter → converter chain
            → 自动发现 converter → converter chain
            → 自动发现 adapter → adapter
            → 抛出 UnsupportedFormatError

        converter 字符串格式::

            "a::b"   → 输入 a，输出 b
            "a::"    → 仅输入 a
            "::b"    → 仅输出 b
            "a"      → 引擎不支持时为输入，原生支持时为输出

        Args:
            content: 文件原始字节
            src_lang: 源语言
            tgt_lang: 目标语言
            fmt: 输入格式
            converter: 转换器字符串（见格式说明）
            adapter: 适配器名称或类

        Returns:
            (翻译后字节, 输出格式)

        Raises:
            UnsupportedFormatError: 引擎不支持该格式且无法通过转换器/适配器处理
        """
        # ── 1. 解析 converter 字符串 ──
        in_converter: str | None = None
        out_converter: str | None = None
        if converter:
            if "::" in converter:
                # 1a. 明确指定输入输出转换器
                left, right = converter.split("::", 1)
                in_converter = left.strip() or None
                out_converter = right.strip() or None
            elif self.engine.supports_format(fmt):
                # 1b. 引擎原生支持该格式 → converter 视为输出转换器
                out_converter = converter.strip() or None
            else:
                # 1c. 引擎不支持该格式 → converter 视为输入转换器
                in_converter = converter.strip() or None

        # ── 2. 非原生格式：converter → adapter 降级链路 ──
        format_obj = self.engine.supports_format(fmt)
        if not format_obj:
            # 2a. 用户指定了适配器 → 优先尝试
            if adapter:
                adp_cls = self._find_adapter(fmt, adapter)
                if adp_cls:
                    result = self._translate_with_adapter(
                        content, src_lang, tgt_lang, adp_cls
                    )
                    return result, adp_cls.source

            # 2b. 查找输入转换器（用户指定或自动发现）
            in_conv_cls = self._find_in_converter(fmt, in_converter)

            if not in_conv_cls:
                # 2c. 无转换器 → 尝试自动发现适配器
                adp_cls = self._find_adapter(fmt)
                if adp_cls:
                    result = self._translate_with_adapter(
                        content, src_lang, tgt_lang, adp_cls
                    )
                    return result, adp_cls.source
                if fmt == PLAIN_TEXT:
                    # 2d. 纯文本走文本翻译
                    result = self.translate_texts(
                        [content.decode(detect_encoding(content))], src_lang, tgt_lang
                    )[0].encode("utf-8-sig")
                    return result, PLAIN_TEXT
                # 2e. 彻底无法处理
                raise UnsupportedFormatError.for_engine(
                    self.engine.name, fmt, self.engine.formats
                )

            # 2f. 转换 → 翻译 → 反向转换
            converted_content = in_conv_cls.convert(content)
            translated_content, translated_format = await self.engine.translate_file(
                converted_content, src_lang, tgt_lang, in_conv_cls.target
            )

            if translated_format != in_conv_cls.source:
                out_conv_cls = self._find_out_converter(
                    in_conv_cls.source, translated_format, out_converter
                )
                if out_conv_cls:
                    return out_conv_cls.convert(translated_content), in_conv_cls.source
            return translated_content, translated_format

        # ── 3. 原生格式：直接翻译，可选输出转换 ──
        if in_converter or adapter:
            self.on_warning(
                "引擎原生支持该格式，但指定了输入转换器或适配器，将忽略它们"
            )
        translated_content, translated_format = await self.engine.translate_file(
            content, src_lang, tgt_lang, format_obj
        )
        if translated_format != format_obj:
            # 3a. 尝试反向转换回原格式（用户指定或自动发现）
            out_conv_cls = self._find_out_converter(
                format_obj, translated_format, out_converter
            )
            if out_conv_cls:
                return out_conv_cls.convert(translated_content), format_obj
        return translated_content, translated_format
