from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from otto_trans.engine.deepl import DeepLAPIError, DeepLTranslator
from otto_trans.utils.format import Format


def make_engine():
    return DeepLTranslator(auth_key="test-key")


def test_normalize_lang():
    engine = make_engine()
    src, tgt = engine._normalize_lang("en", "de")
    assert src == "EN"
    assert tgt == "DE"


def test_normalize_lang_zh():
    engine = make_engine()
    src, tgt = engine._normalize_lang("zh-HANS", "zh-HANT")
    assert src == "ZH"
    assert tgt == "ZH-HANT"


def test_build_text_payload():
    engine = make_engine()
    # "AUTO" 不传入 source_lang
    payload = engine._build_text_payload(["hello"], "AUTO", "DE")
    assert payload["text"] == ["hello"]
    assert payload["target_lang"] == "DE"
    assert "source_lang" not in payload


def test_build_text_payload_with_source():
    engine = make_engine()
    payload = engine._build_text_payload(["hello"], "FR", "DE")
    assert payload["source_lang"] == "FR"


def test_translate_texts():
    engine = make_engine()
    engine._client = AsyncMock()
    engine._client.post = AsyncMock(
        return_value=Mock(
            status_code=200,
            json=Mock(
                return_value={"translations": [{"text": "Hallo"}]},
            ),
        )
    )
    results = engine.translate_texts(["hello"], "en", "de")
    assert results == ["Hallo"]


def test_translate_texts_error():
    engine = make_engine()
    engine._client = AsyncMock()
    engine._client.post = AsyncMock(
        return_value=Mock(
            status_code=400,
            text="Bad Request",
            json=Mock(return_value={"message": ""}),
            raise_for_status=Mock(
                side_effect=httpx.HTTPStatusError(
                    "400",
                    request=Mock(),
                    response=Mock(status_code=400, text="Bad Request"),
                )
            ),
        )
    )
    with pytest.raises(DeepLAPIError):
        engine.translate_texts(["hello"], "en", "de")


@pytest.mark.asyncio
async def test_translate_file():
    engine = make_engine()
    engine._client = AsyncMock()
    engine._client.post = AsyncMock(
        side_effect=[
            # upload
            Mock(
                status_code=200,
                json=Mock(return_value={"document_id": "abc", "document_key": "key1"}),
            ),
            # poll
            Mock(
                status_code=200,
                json=Mock(
                    return_value={
                        "document_id": "abc",
                        "status": "done",
                    }
                ),
            ),
            # download
            Mock(
                status_code=200,
                content=b"translated content",
            ),
        ]
    )
    fmt = Format(
        name="ms-word",
        extensions={".docx"},
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    result, out_fmt = await engine.translate_file(b"hello", "en", "de", fmt)
    assert result == b"translated content"
    assert out_fmt == fmt


def test_formats_exist():
    engine = make_engine()
    assert engine.formats is not None
    assert len(engine.formats) >= 8  # DeepL supports many formats


def test_invalid_formality():
    with pytest.raises(ValueError, match="formality"):
        DeepLTranslator(auth_key="test", formality="invalid")


def test_invalid_model_type():
    with pytest.raises(ValueError, match="model_type"):
        DeepLTranslator(auth_key="test", model_type="invalid")


def test_invalid_tag_handling():
    with pytest.raises(ValueError, match="tag_handling"):
        DeepLTranslator(auth_key="test", tag_handling="invalid")
