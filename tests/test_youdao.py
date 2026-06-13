import time
from unittest.mock import AsyncMock, Mock

import pytest

from otto_trans.core.cache import Cache
from otto_trans.engine.base import UnsupportedLanguageError
from otto_trans.engine.youdao import YoudaoTranslator


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    Cache._instance = None  # ← 清空单例
    Cache._initialized = False  # ← 允许重新初始化
    Cache.db_path = tmp_path / "test_cache.db"
    yield


def test_normalize_lang():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    assert translator._normalize_text_lang("auto", "zh") == ("auto", "zh-CHS")
    assert translator._normalize_text_lang("auto", "ZH") == ("auto", "zh-CHS")
    assert translator._normalize_text_lang("auto", "zh-Hans") == ("auto", "zh-CHS")
    assert translator._normalize_text_lang("auto", "zh-hans") == ("auto", "zh-CHS")
    assert translator._normalize_text_lang("auto", "jv") == ("auto", "jw")
    assert translator._normalize_text_lang("auto", "en") == ("auto", "en")
    with pytest.raises(UnsupportedLanguageError):
        translator._normalize_text_lang("350234", "350235")


@pytest.mark.asyncio
async def test_translate_texts():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    translator._translate_text_batch = AsyncMock(return_value=["你好"])
    result = await translator._translate_text_batch(["hello"], "en", "zh-CHS")
    assert result == ["你好"]


@pytest.mark.asyncio
async def test_translate_texts_batch():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    translator._text_request = AsyncMock(
        return_value=Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "translateResults": [
                        {"query": "hello", "translation": "你好", "type": "en2zh-CHS"},
                        {"query": "world", "translation": "世界", "type": "en2zh-CHS"},
                    ],
                    "requestId": "mocked_request_id",
                    "errorCode": "0",
                    "l": "en2zh-CHS",
                }
            ),
        )
    )
    results = await translator._translate_text_batch(["hello", "world"], "en", "zh-CHS")
    assert results == ["你好", "世界"]


def test_build_sign():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    translator._sha256 = Mock(return_value="mocked_sign")
    sign, salt, curtime = translator._build_sign("hello")
    assert sign == "mocked_sign"
    assert 0 <= int(time.time()) - int(curtime) <= 1
    assert len(salt) == 36  # UUID 格式


def test_sha256():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    result = translator._sha256("Hello, world!")
    assert result == "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"


def test_truncate():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    assert translator._truncate("short") == "short"
    long_text = "114514" * 350234 + "1919810" * 350235
    assert translator._truncate(long_text) == "114514114545530498101919810"
