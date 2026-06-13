from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from otto_trans.engine.youdao import YoudaoAPIError, YoudaoTranslator


def make_translator():
    return YoudaoTranslator(app_key="114514", app_secret="1919810")


@pytest.mark.asyncio
async def test_translate_web_html():
    t = make_translator()
    t._client = AsyncMock()
    t._client.post = AsyncMock(
        return_value=Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "errorCode": "0",
                    "data": "<!DOCTYPE html>\n<html><head></head><body>hello</body></html>",
                }
            ),
        )
    )
    html = b"<html><body>hello</body></html>"
    result = await t._translate_web(html, "en", "zh")
    assert result.decode("utf-8-sig").startswith("<!DOCTYPE html>")


@pytest.mark.asyncio
async def test_translate_web_adds_doctype():
    t = make_translator()
    t._client = AsyncMock()
    t._client.post = AsyncMock(
        return_value=Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "errorCode": "0",
                    "data": "<html><head></head><body>hello</body></html>",
                }
            ),
        )
    )
    result = await t._translate_web(b"<html>hello</html>", "en", "zh")
    text = result.decode("utf-8-sig")
    assert text.startswith("<!DOCTYPE html>")


@pytest.mark.asyncio
async def test_translate_web_fixes_charset():
    t = make_translator()
    t._client = AsyncMock()
    t._client.post = AsyncMock(
        return_value=Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "errorCode": "0",
                    "data": '<html><head><meta charset="gbk"></head><body>hello</body></html>',
                }
            ),
        )
    )
    result = await t._translate_web(b"<html>hello</html>", "en", "zh")
    text = result.decode("utf-8-sig")
    assert 'charset="UTF-8"' in text or "charset=UTF-8" in text


@pytest.mark.asyncio
async def test_translate_web_adds_charset():
    t = make_translator()
    t._client = AsyncMock()
    t._client.post = AsyncMock(
        return_value=Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "errorCode": "0",
                    "data": "<html><head></head><body>hello</body></html>",
                }
            ),
        )
    )
    result = await t._translate_web(b"<html>hello</html>", "en", "zh")
    text = result.decode("utf-8-sig")
    assert 'charset="UTF-8"' in text


@pytest.mark.asyncio
async def test_web_api_error():
    t = make_translator()
    t._client = AsyncMock()
    t._client.post = AsyncMock(
        return_value=Mock(
            status_code=400,
            text="Bad Request",
            raise_for_status=Mock(
                side_effect=httpx.HTTPStatusError(
                    "400",
                    request=Mock(),
                    response=Mock(status_code=400, text="Bad Request"),
                )
            ),
        )
    )
    with pytest.raises(YoudaoAPIError, match="网页翻译失败"):
        await t._translate_web(b"<html>hello</html>", "en", "zh")


@pytest.mark.asyncio
async def test_web_error_code():
    t = make_translator()
    t._client = AsyncMock()
    t._client.post = AsyncMock(
        return_value=Mock(
            status_code=200,
            json=Mock(return_value={"errorCode": "101", "data": ""}),
        )
    )
    with pytest.raises(YoudaoAPIError, match="网页翻译失败"):
        await t._translate_web(b"<html>hello</html>", "en", "zh")
