from otto_trans.engine.openai import OpenAITranslator
from otto_trans.utils.format import Format


def make_engine():
    return OpenAITranslator(
        endpoint="https://api.example.com",
        api_key="test-key",
        model="test-model",
    )


def test_supports_format_name():
    engine = make_engine()
    # formats 里没有注册任何格式，但支持任意 text/*
    assert engine.supports_format("text/html") is not None
    assert engine.supports_format("text/markdown") is not None
    assert engine.supports_format("text/plain") is not None


def test_supports_format_extension():
    engine = make_engine()
    assert engine.supports_format(".html") is not None
    assert engine.supports_format(".txt") is not None


def test_supports_format_rejects_binary():
    engine = make_engine()
    assert engine.supports_format("application/pdf") is None
    assert engine.supports_format("image/png") is None


def test_supports_format_object():
    engine = make_engine()
    fmt = Format(name="html", extensions={".html"}, mime_type="text/html")
    result = engine.supports_format(fmt)
    assert result is fmt  # 直接返回传入的 Format

    bad = Format(name="pdf", extensions={".pdf"}, mime_type="application/pdf")
    assert engine.supports_format(bad) is None


def test_supports_format_plain_txt_extension():
    engine = make_engine()
    result = engine.supports_format("text/plain")
    assert result is not None
    assert ".txt" in result.extensions  # 特殊处理
