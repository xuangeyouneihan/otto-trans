from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from otto_trans.engine.base import UnsupportedLanguageError
from otto_trans.engine.openai import OpenAIAPIError, OpenAITranslator, _is_html
from otto_trans.utils.format import Format


def make_engine():
    return OpenAITranslator(
        endpoint="https://api.example.com",
        api_key="test-key",
        model="test-model",
    )


def test_translate_texts_auto_target():
    engine = make_engine()
    with pytest.raises(UnsupportedLanguageError):
        engine.translate_texts(["hello"], "en", "auto")


def test_translate_texts():
    engine = make_engine()
    engine._client = AsyncMock()
    engine._client.post = AsyncMock(
        return_value=Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "choices": [{"message": {"content": "你好"}}],
                },
            ),
        )
    )
    results = engine.translate_texts(["hello"], "en", "zh")
    assert results == ["你好"]


def test_translate_texts_api_error():
    engine = make_engine()
    engine._client = AsyncMock()
    engine._client.post = AsyncMock(
        return_value=Mock(
            status_code=500,
            text="Internal Error",
            raise_for_status=Mock(
                side_effect=httpx.HTTPStatusError(
                    "500",
                    request=Mock(),
                    response=Mock(status_code=500, text="Internal Error"),
                )
            ),
        )
    )
    with pytest.raises(OpenAIAPIError):
        engine.translate_texts(["hello"], "en", "zh")


def test_is_html_by_format():
    fmt = Format(name="html", extensions={".html"}, mime_type="text/html")
    assert _is_html(b"anything", fmt) is True

    fmt2 = Format(name="markdown", extensions={".md"}, mime_type="text/markdown")
    assert _is_html(b"anything", fmt2) is False


def test_is_html_by_content():
    fmt = Format(name="text", extensions={".txt"}, mime_type="text/plain")
    assert _is_html(b"<!DOCTYPE html><html>", fmt) is True
    assert _is_html(b"<html><head></head><body></body></html>", fmt) is True
    assert _is_html(b"Just plain text, nothing here.", fmt) is False


def test_prompt_template_contains_formatting_rules():
    engine = make_engine()
    assert (
        "标记" in engine.prompt_template.lower()
        or "markup" in engine.prompt_template.lower()
    )
    assert (
        "纯文本" in engine.prompt_template or "plain" in engine.prompt_template.lower()
    )


def test_build_payload():
    engine = make_engine()
    payload = engine._build_payload("hello", "en", "zh")
    assert payload["model"] == "test-model"
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"] == "hello"


@pytest.mark.asyncio
async def test_translate_file_text_format():
    engine = make_engine()
    engine._client = AsyncMock()
    engine._client.post = AsyncMock(
        return_value=Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "choices": [{"message": {"content": "translated"}}],
                },
            ),
        )
    )
    fmt = Format(name="text", extensions={".txt"}, mime_type="text/plain")
    result, out_fmt = await engine.translate_file(b"hello", "en", "zh", fmt)
    assert result.decode("utf-8-sig") == "translated"
    assert out_fmt == fmt
