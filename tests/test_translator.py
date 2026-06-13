from unittest.mock import Mock

import pytest

from otto_trans.adapter.base import Segment
from otto_trans.core.cache import Cache
from otto_trans.core.translator import Translator
from otto_trans.utils.format import Format


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    Cache._instance = None  # ← 清空单例
    Cache._initialized = False  # ← 允许重新初始化
    Cache.db_path = tmp_path / "test_cache.db"
    yield


def test_init_invalid_engine():
    with pytest.raises(ValueError, match="未知的翻译引擎"):
        Translator("invalid_engine", {"app_key": "114514", "app_secret": "1919810"})


def test_init_youdao_invalid_options():
    with pytest.raises(ValueError, match="缺少翻译引擎 youdao 的必需选项"):
        Translator("youdao", {})

    with pytest.raises(ValueError, match="未知参数"):
        Translator(
            "youdao",
            {"app_key": "114514", "app_secret": "1919810", "model": "model_name"},
        )


def test_init_youdao_valid_options():
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    assert translator.engine is not None, "Translator engine should be initialized"
    assert translator.engine.name == "youdao", (
        f"Expected engine name 'youdao', got '{translator.engine.name}'"
    )


def test_init_openai_invalid_options():
    with pytest.raises(ValueError, match="缺少翻译引擎 openai 的必需选项"):
        Translator("openai", {})

    with pytest.raises(ValueError, match="未知参数"):
        Translator(
            "openai:example",
            {
                "endpoint": "https://api.example.com/chat/completions",
                "api_key": "350234",
                "model": "model_name",
                "auth_key": "350235",
            },
        )


def test_init_openai_valid_options():
    translator = Translator(
        "openai:example",
        {
            "endpoint": "https://api.example.com/chat/completions",
            "api_key": "350234",
            "model": "model_name",
        },
    )
    assert translator.engine is not None, "Translator engine should be initialized"
    assert translator.engine.name == "openai:model_name", (
        f"Expected engine name 'openai:model_name', got '{translator.engine.name}'"
    )


def test_init_deepl_invalid_options():
    with pytest.raises(ValueError, match="缺少翻译引擎 deepl 的必需选项"):
        Translator("deepl", {})

    with pytest.raises(ValueError, match="未知参数"):
        Translator("deepl", {"auth_key": "350235", "app_secret": "1919810"})


def test_init_deepl_valid_options():
    translator = Translator("deepl", {"auth_key": "350235"})
    assert translator.engine is not None, "Translator engine should be initialized"
    assert translator.engine.name == "deepl", (
        f"Expected engine name 'deepl', got '{translator.engine.name}'"
    )


@pytest.mark.asyncio
async def test_translate_texts_cache_hit():
    """缓存命中 → 返回缓存结果，不调引擎"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    translator.engine.translate_texts = Mock(return_value=["不应被调用"])

    translator.cache.insert("hello", "你好", "youdao", "en", "zh")

    result = translator.translate_texts(["hello"], "en", "zh")
    assert result == ["你好"]
    translator.engine.translate_texts.assert_not_called()


@pytest.mark.asyncio
async def test_translate_texts_cache_miss():
    """缓存未命中 → 调引擎，存缓存，返回结果"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    translator.engine.translate_texts = Mock(return_value=["你好"])

    result = translator.translate_texts(["hello"], "en", "zh")
    assert result == ["你好"]

    # 存入了缓存
    cached = translator.cache.query("hello", "youdao", "en", "zh")
    assert cached == "你好"


@pytest.mark.asyncio
async def test_translate_texts_batch_cache_hit():
    """缓存命中 → 返回缓存结果，不调引擎"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    translator.engine.translate_texts = Mock(return_value=["不应被调用", "不应被调用"])

    translator.cache.insert("hello", "你好", "youdao", "en", "zh")
    translator.cache.insert("world", "世界", "youdao", "en", "zh")

    result = translator.translate_texts(["hello", "world"], "en", "zh")
    assert result == ["你好", "世界"]
    translator.engine.translate_texts.assert_not_called()

    translator = Translator(
        "openai",
        {
            "endpoint": "https://api.example.com/chat/completions",
            "api_key": "350234",
            "model": "model_name",
        },
    )
    translator.engine.translate_texts = Mock(return_value=["不应被调用"])

    translator.cache.insert("hello", "你好", "openai:model_name", "en", "zh")
    translator.cache.insert("world", "世界", "openai:model_name", "en", "zh")

    result = translator.translate_texts(["hello", "world"], "en", "zh")
    assert result == ["你好", "世界"]
    translator.engine.translate_texts.assert_not_called()


@pytest.mark.asyncio
async def test_translate_texts_batch_cache_miss():
    """缓存未命中 → 调引擎，存缓存，返回结果"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    translator.engine.translate_texts = Mock(return_value=["你好", "世界"])

    result = translator.translate_texts(["hello", "world"], "en", "zh")
    assert result == ["你好", "世界"]

    # 存入了缓存
    cached = translator.cache.query("hello", "youdao", "en", "zh")
    assert cached == "你好"
    cached = translator.cache.query("world", "youdao", "en", "zh")
    assert cached == "世界"

    translator = Translator(
        "openai",
        {
            "endpoint": "https://api.example.com/chat/completions",
            "api_key": "350234",
            "model": "model_name",
        },
    )
    translator.engine.translate_texts = Mock(return_value=["你好", "你好"])

    result = translator.translate_texts(["hello", "world"], "en", "zh")
    assert result == ["你好", "你好"]

    # 存入了缓存
    cached = translator.cache.query("hello", "openai:model_name", "en", "zh")
    assert cached == "你好"
    cached = translator.cache.query("world", "openai:model_name", "en", "zh")
    assert cached == "你好"


# ── find_reverse_converter ──────────────────────────────────


def test_find_reverse_converter_found():
    """能找到反向转换器"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    converters = Translator.converters()
    assert "markdown_to_html" in converters
    assert "html_to_markdown" in converters

    md_to_html = converters["markdown_to_html"]
    html_to_md = converters["html_to_markdown"]

    # html → md 的反向是 md → html
    rev = translator.find_reverse_converter(html_to_md.target, html_to_md.source)
    assert rev is not None
    assert rev.source == md_to_html.source
    assert rev.target == md_to_html.target


def test_find_reverse_converter_not_found():
    """找不到反向转换器时返回 None"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    html_fmt = Format(name="html", extensions={".html"}, mime_type="text/html")
    unknown_fmt = Format(name="unknown", extensions={".unk"})
    rev = translator.find_reverse_converter(html_fmt, unknown_fmt)
    assert rev is None


# ── translate_with_adapter ──────────────────────────────────


def test_translate_with_adapter():
    """适配器提取文本 → 翻译 → 组装"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    translator.engine.translate_texts = Mock(return_value=["你好"])

    from otto_trans.adapter.srt import SRTAdapter

    srt_content = b"1\n00:00:01,000 --> 00:00:02,000\nhello\n"
    result = translator.translate_with_adapter(srt_content, "en", "zh", SRTAdapter)
    assert "你好".encode() in result


def test_translate_with_adapter_nested_segments():
    """适配器处理嵌套 Segment（含 children）"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    translator.engine.translate_texts = Mock(return_value=["你好", "世界"])

    from otto_trans.adapter.base import BaseAdapter

    class NestedAdapter(BaseAdapter):
        source = Format(name="test", extensions={".test"})

        @staticmethod
        def extract(content: bytes) -> list[Segment]:
            return [Segment(text="hello", children=[Segment(text="world")])]

        @staticmethod
        def reassemble(content: bytes, translated: list[Segment]) -> bytes:
            result = translated[0].text
            if translated[0].children:
                result += "|" + translated[0].children[0].text
            return result.encode()

    result = translator.translate_with_adapter(b"", "en", "zh", NestedAdapter)
    assert result == "你好|世界".encode()
