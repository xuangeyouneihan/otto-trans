from .base import BaseTranslator
import httpx
import uuid
import hashlib
import time

class YoudaoAPIError(Exception):
    """有道 API 调用异常"""
    pass

class YoudaoTranslator(BaseTranslator):
    youdao_url = "https://openapi.youdao.com/v2/api"

    def __init__(self, app_key: str, app_secret: str):
        super().__init__()
        self.app_key = app_key
        self.app_secret = app_secret
        self._client = httpx.AsyncClient()  # 一个实例一个客户端

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()  # 用完记得关

    @property
    def name(self) -> str:
        return "youdao"

    async def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        results = await self.translate_batch([text], from_lang, to_lang)
        return results[0]

    async def translate_batch(self, texts: list[str], from_lang: str, to_lang: str) -> list[str]:
        request = self._build_request(texts, from_lang, to_lang)
        response = await self._request(request)
        body = response.json()
        if body.get("errorCode") != "0":
            raise YoudaoAPIError(f"有道 API 返回错误: {body.get('errorCode')}")
        return [r["translation"] for r in body["translateResults"]]

    def _build_request(self, texts: list[str], from_lang: str, to_lang: str) -> dict:
        # Build the request payload according to Youdao API specifications
        salt = str(uuid.uuid1())
        curtime = str(int(time.time()))
        sign_str = self.app_key + self._truncate(''.join(texts)) + salt + curtime + self.app_secret
        sign = self._sha256(sign_str)
        return {
            "from": from_lang,
            "to": to_lang,
            "signType": "v3",
            "curtime": curtime,
            "appKey": self.app_key,
            "q": texts,
            "salt": salt,
            "sign": sign,
        }

    async def _request(self, request: dict) -> httpx.Response:
        # Placeholder implementation - replace with actual API request logic
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        return await self._client.post(self.youdao_url, data=request, headers=headers)

    def _sha256(self, sign_str):
        hash_algorithm = hashlib.sha256()
        hash_algorithm.update(sign_str.encode('utf-8'))
        return hash_algorithm.hexdigest()
    
    def _truncate(self, text: str) -> str:
        size = len(text)
        return text if size <= 20 else text[:10] + str(size) + text[size - 10:]