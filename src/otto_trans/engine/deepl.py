from typing import Any

import httpx

from .base import BaseTranslator, UnsupportedLanguageError
from ..utils.format import Format, UnsupportedFormatError


class DeepLAPIError(Exception):
    """DeepL API 调用异常"""

    pass


class DeepLTranslator(BaseTranslator):
    _deepl_url = "https://api.deepl.com/v2/translate"
    _deepl_languages_url = "https://api.deepl.com/v3/languages?resource=translate_text"

    _deepl_url_free = "https://api-free.deepl.com/v2/translate"
    _deepl_languages_url_free = (
        "https://api-free.deepl.com/v3/languages?resource=translate_text"
    )

    _SRC_LANG_MAP: dict[str, str] = {
        "DE-DE": "DE",
        "EN-GB": "EN",
        "EN-US": "EN",
        "ES-419": "ES",
        "FR-FR": "FR",
        "PT-BR": "PT",
        "PT-PT": "PT",
        "ZH-HANS": "ZH",
        "ZH-HANT": "ZH",
    }

    _TGT_LANG_MAP: dict[str, str] = {}

    engine_name = "deepl"
    friendly_name = "DeepL 翻译"

    options: dict[str, dict[str, type | str | bool]] = {
        "auth_key": {"type": str, "description": "API 密钥", "required": True},
        "paid": {
            "type": bool,
            "description": "是否使用付费端点，true 或 false，默认 false",
            "required": False,
        },
        "context": {
            "type": str,
            "description": "上下文信息，帮助模型理解翻译场景",
            "required": False,
        },
        "preserve_formatting": {
            "type": bool,
            "description": "保留原文格式，true 或 false",
            "required": False,
        },
        "formality": {
            "type": str,
            "description": "正式程度，default、more、less、prefer_more 或 prefer_less",
            "required": False,
        },
        "model_type": {
            "type": str,
            "description": "模型类型，quality_optimized、latency_optimized 或 prefer_quality_optimized",
            "required": False,
        },
    }

    def __init__(
        self,
        auth_key: str,
        paid: bool = False,
        context: str | None = None,
        preserve_formatting: bool | None = None,
        formality: str | None = None,
        model_type: str | None = None,
        config_name: str | None = None,
        **kwargs,
    ):
        if kwargs:
            raise ValueError(f"未知参数: {list(kwargs.keys())}")
        super().__init__(config_name=config_name)
        self.__auth_key = auth_key
        self.paid = paid
        self.context = context
        self.preserve_formatting = preserve_formatting
        if formality and formality not in (
            "default",
            "more",
            "less",
            "prefer_more",
            "prefer_less",
        ):
            raise ValueError(
                f"formality 参数值无效：{formality}，必须是 default、more、less、prefer_more 或 prefer_less"
            )
        self.formality = formality
        if model_type and model_type not in (
            "quality_optimized",
            "latency_optimized",
            "prefer_quality_optimized",
        ):
            raise ValueError(
                f"model_type 参数值无效：{model_type}，必须是 quality_optimized、latency_optimized 或 prefer_quality_optimized"
            )
        self.model_type = model_type
        self._client = httpx.AsyncClient(follow_redirects=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    async def translate(self, text: str, src_lang: str, tgt_lang: str, fmt: Format | None = None) -> str:
        return (await self.translate_batch([text], src_lang, tgt_lang, fmt))[0]

    async def translate_batch(
        self, texts: list[str], src_lang: str, tgt_lang: str, fmt: Format | None = None
    ) -> list[str]:
        if fmt and fmt not in (self.formats or []):
            raise UnsupportedFormatError.for_engine(self.name, fmt)
        (src_lang, tgt_lang) = self._normalize_lang(src_lang, tgt_lang)
        payload = self._build_payload(texts, src_lang, tgt_lang)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"DeepL-Auth-Key {self.__auth_key}",
        }
        response = await self._client.post(
            self._deepl_url if self.paid else self._deepl_url_free,
            json=payload,
            headers=headers,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            if response.status_code == 400 and (
                "Value for 'source_lang' not supported."
                in response.json().get("message", "")
                or "Value for 'target_lang' not supported."
                in response.json().get("message", "")
            ):
                src_languages = None
                tgt_languages = None
                try:
                    (
                        src_languages,
                        tgt_languages,
                    ) = await self._fetch_supported_languages()
                except Exception:
                    raise UnsupportedLanguageError.for_engine(
                        f"{self.friendly_name}（{self.name}）",
                        src_lang,
                        tgt_lang,
                    )
                raise UnsupportedLanguageError.for_engine(
                    f"{self.friendly_name}（{self.name}）",
                    src_lang,
                    tgt_lang,
                    src_languages,
                    tgt_languages,
                ) from e

            raise DeepLAPIError(
                f"DeepL API 返回错误: {response.status_code} {response.text}"
            ) from e
        body = response.json()
        return [t["text"] for t in body["translations"]]

    def _build_payload(self, texts: list[str], src_lang: str, tgt_lang: str) -> dict:
        payload: dict[str, Any] = {
            "text": texts,
            "target_lang": tgt_lang,
        }
        if src_lang != "AUTO":
            payload["source_lang"] = src_lang
        if self.context:
            payload["context"] = self.context
        if self.preserve_formatting is not None:
            payload["preserve_formatting"] = self.preserve_formatting
        if self.formality:
            payload["formality"] = self.formality
        if self.model_type:
            payload["model_type"] = self.model_type
        return payload

    def _normalize_lang(self, src_lang: str, tgt_lang: str) -> tuple[str, str]:
        """将部分语言代码转为 DeepL API 代码。"""
        src_code = self._SRC_LANG_MAP.get(src_lang.upper())
        tgt_code = self._TGT_LANG_MAP.get(tgt_lang.upper())
        return (src_code or src_lang.upper(), tgt_code or tgt_lang.upper())

    async def _fetch_supported_languages(self) -> tuple[list[str], list[str]]:
        # Implementation for fetching supported languages
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"DeepL-Auth-Key {self.__auth_key}",
        }
        response = await self._client.get(
            self._deepl_languages_url if self.paid else self._deepl_languages_url_free,
            headers=headers,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise DeepLAPIError(
                f"DeepL API 获取支持语言失败: {response.status_code} {response.text}"
            ) from e
        body = response.json()
        return (
            [item["lang"] for item in body if item["usable_as_source"]],
            [item["lang"] for item in body if item["usable_as_target"]],
        )
