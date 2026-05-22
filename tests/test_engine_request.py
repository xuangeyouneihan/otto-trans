import pytest
from otto_trans.engine.youdao import YoudaoTranslator
from otto_trans.engine.openai import OpenAITranslator


@pytest.mark.asyncio
async def test_youdao_http_request(httpx_mock):
    """验证有道引擎发送的 HTTP 请求符合预期。"""
    # 监听 POST 请求
    httpx_mock.add_response(
        status_code=200,
        json={
            "translateResults": [
                {"query": "hello", "translation": "你好", "type": "en2zh-CHS"},
            ],
            "errorCode": "0",
        },
    )

    async with YoudaoTranslator(app_key="114514", app_secret="1919810") as engine:
        result = await engine.translate("hello", "en", "zh-Hans")

    assert result == "你好"

    # 验证请求内容
    request = httpx_mock.get_request()
    assert request.method == "POST"
    assert "api" in str(request.url)

    # Content-Type 必须为表单
    assert request.headers.get("content-type") == "application/x-www-form-urlencoded"

    # 请求体包含所有必要字段
    body = request.content.decode()
    assert "from=en" in body
    assert "to=zh-CHS" in body
    assert "appKey=114514" in body
    assert "signType=v3" in body
    assert "q=hello" in body
    assert "sign" in body
    assert "salt" in body
    assert "curtime" in body


@pytest.mark.asyncio
async def test_openai_http_request(httpx_mock):
    """验证 OpenAI 引擎发送的 HTTP 请求符合预期。"""
    httpx_mock.add_response(
        status_code=200,
        json={
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "你好",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    )

    async with OpenAITranslator(
        endpoint="https://api.example.com/v1/chat/completions",
        api_key="sk-test",
        model="gpt-4o",
    ) as engine:
        result = await engine.translate("hello", "en", "zh-Hans")

    assert result == "你好"

    request = httpx_mock.get_request()
    assert request.method == "POST"
    assert request.headers.get("authorization") == "Bearer sk-test"
    assert request.headers.get("content-type") == "application/json"

    body = request.content.decode()
    assert "gpt-4o" in body
    assert '"content": "hello"' in body or '"content":"hello"' in body
