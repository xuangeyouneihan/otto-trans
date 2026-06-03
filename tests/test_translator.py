from unittest.mock import AsyncMock

import pytest

from otto_trans.core.cache import Cache
from otto_trans.core.translator import Translator


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
async def test_translate_cache_hit():
    """缓存命中 → 返回缓存结果，不调引擎"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    translator.engine.translate = AsyncMock(return_value="不应被调用")

    translator.cache.insert("hello", "你好", "youdao", "en", "zh")

    result = await translator.translate("hello", "en", "zh")
    assert result == "你好"
    translator.engine.translate.assert_not_called()


@pytest.mark.asyncio
async def test_translate_cache_miss():
    """缓存未命中 → 调引擎，存缓存，返回结果"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    translator.engine.translate = AsyncMock(return_value="你好")

    result = await translator.translate("hello", "en", "zh")
    assert result == "你好"

    # 存入了缓存
    cached = translator.cache.query("hello", "youdao", "en", "zh")
    assert cached == "你好"


@pytest.mark.asyncio
async def test_translate_batch_cache_hit():
    """缓存命中 → 返回缓存结果，不调引擎"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    translator.engine.translate_batch = AsyncMock(
        return_value=["不应被调用", "不应被调用"]
    )

    translator.cache.insert("hello", "你好", "youdao", "en", "zh")
    translator.cache.insert("world", "世界", "youdao", "en", "zh")

    result = await translator.translate_batch(["hello", "world"], "en", "zh")
    assert result == ["你好", "世界"]
    translator.engine.translate_batch.assert_not_called()

    translator = Translator(
        "openai",
        {
            "endpoint": "https://api.example.com/chat/completions",
            "api_key": "350234",
            "model": "model_name",
        },
    )
    translator.engine.translate = AsyncMock(return_value="不应被调用")

    translator.cache.insert("hello", "你好", "openai:model_name", "en", "zh")
    translator.cache.insert("world", "世界", "openai:model_name", "en", "zh")

    result = await translator.translate_batch(["hello", "world"], "en", "zh")
    assert result == ["你好", "世界"]
    translator.engine.translate.assert_not_called()


@pytest.mark.asyncio
async def test_translate_batch_cache_miss():
    """缓存未命中 → 调引擎，存缓存，返回结果"""
    translator = Translator("youdao", {"app_key": "114514", "app_secret": "1919810"})
    translator.engine.translate_batch = AsyncMock(return_value=["你好", "世界"])

    result = await translator.translate_batch(["hello", "world"], "en", "zh")
    assert result == ["你好", "世界"]

    # 存入了缓存
    cached = translator.cache.query("hello", "youdao", "en", "zh")
    assert cached == "你好"
    cached = translator.cache.query("world", "youdao", "en", "zh")
    assert cached == "世界"

    print(translator.cache.query("world", "youdao", "en", "zh"))
    print(translator.cache.query("world", "openai:model_name", "en", "zh"))
    print(translator.cache.query("world", "deepl", "en", "zh"))

    translator = Translator(
        "openai",
        {
            "endpoint": "https://api.example.com/chat/completions",
            "api_key": "350234",
            "model": "model_name",
        },
    )
    translator.engine.translate = AsyncMock(return_value="你好")

    result = await translator.translate_batch(["hello", "world"], "en", "zh")
    assert result == ["你好", "你好"]

    # 存入了缓存
    cached = translator.cache.query("hello", "openai:model_name", "en", "zh")
    assert cached == "你好"
    cached = translator.cache.query("world", "openai:model_name", "en", "zh")
    assert cached == "你好"
