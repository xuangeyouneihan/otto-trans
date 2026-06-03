import pytest
from unittest.mock import Mock, AsyncMock
import time
from otto_trans.engine.base import UnsupportedLanguageError
from otto_trans.engine.youdao import YoudaoTranslator
from otto_trans.core.cache import Cache

@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    Cache._instance = None         # ← 清空单例
    Cache._initialized = False     # ← 允许重新初始化
    Cache.db_path = tmp_path / "test_cache.db"
    yield

def test_normalize_lang():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    assert translator._normalize_lang("auto", "zh") == ("auto", "zh-CHS")
    assert translator._normalize_lang("auto", "ZH") == ("auto", "zh-CHS")
    assert translator._normalize_lang("auto", "zh-Hans") == ("auto", "zh-CHS")
    assert translator._normalize_lang("auto", "zh-hans") == ("auto", "zh-CHS")
    assert translator._normalize_lang("auto", "jv") == ("auto", "jw")
    assert translator._normalize_lang("auto", "en") == ("auto", "en")
    with pytest.raises(UnsupportedLanguageError):
        translator._normalize_lang("350234", "350235")

@pytest.mark.asyncio
async def test_translate():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    translator.translate_batch = AsyncMock(return_value=["你好"])
    result = await translator.translate("hello", "en", "zh-Hans")
    assert result == "你好"

@pytest.mark.asyncio
async def test_translate_batch():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    translator._build_payload = Mock(
        return_value={
            "from": "en",
            "to": "zh-CHS",
            "signType": "v3",
            "curtime": "0",
            "appKey": "114514",
            "q": ["hello", "world"],
            "salt": "mocked_salt",
            "sign": "mocked_sign"
        }
    )
    translator._request = AsyncMock(
        return_value=Mock(
            status_code=200,
            json=Mock(
                return_value={
                    'translateResults':[
                        {'query': 'hello', 'translation': '你好', 'type': 'en2zh-CHS'},
                        {'query': 'world', 'translation': '世界', 'type': 'en2zh-CHS'}
                    ],
                    'requestId': 'mocked_request_id',
                    'errorCode': '0',
                    'l': 'en2zh-CHS'
                }
            )
        )
    )
    results = await translator.translate_batch(["hello", "world"], "en", "zh-Hans")
    assert results == ["你好", "世界"]

def test_build_payload():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    translator._sha256 = Mock(return_value="mocked_sign")
    payload = translator._build_payload(["hello", "world"], "en", "zh-CHS")
    assert payload["from"] == "en"
    assert payload["to"] == "zh-CHS"
    assert payload["signType"] == "v3"
    assert 0 <= int(time.time()) - int(payload["curtime"]) <= 1
    assert payload["appKey"] == "114514"
    assert payload["q"] == ["hello", "world"]
    assert "salt" in payload
    assert payload["sign"] == "mocked_sign"

def test_sha256():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    result = translator._sha256("Hello, world!")
    assert result == "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"

def test_truncate():
    translator = YoudaoTranslator(app_key="114514", app_secret="1919810")
    assert translator._truncate("short") == "short"
    long_text = "114514" * 350234 + "1919810" * 350235
    assert translator._truncate(long_text) == "114514114545530498101919810"