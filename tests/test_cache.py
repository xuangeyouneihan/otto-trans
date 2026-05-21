import pytest
from otto_trans.core.cache import Cache

@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    Cache._instance = None         # ← 清空单例
    Cache._initialized = False     # ← 允许重新初始化
    Cache._db_path = tmp_path / "test_cache.db"
    yield

def test_singleton():
    cache1 = Cache()
    cache2 = Cache()
    assert cache1 is cache2, "Cache should be a singleton"

def test_insert_and_query():
    cache = Cache()
    cache.insert("hello", "你好", "test", "en", "zh")
    result = cache.query("hello", "test", "en", "zh")
    assert result == "你好", f"Expected '你好', got '{result}'"

def test_query_nonexistent():
    cache = Cache()
    result = cache.query("nonexistent", "test", "en", "zh")
    assert result is None, f"Expected None for nonexistent entry, got '{result}'"

def test_reset():
    cache = Cache()
    cache.insert("hello", "你好", "test", "en", "zh")
    result = cache.query("hello", "test", "en", "zh")
    assert result == "你好", f"Expected '你好', got '{result}'"
    Cache.reset()
    result = cache.query("hello", "test", "en", "zh")
    assert result is None, f"Expected None after reset, got '{result}'"
    cache.insert("hello", "你好", "test", "en", "zh")
    result = cache.query("hello", "test", "en", "zh")
    assert result == "你好", f"Expected '你好' after reset and insert, got '{result}'"