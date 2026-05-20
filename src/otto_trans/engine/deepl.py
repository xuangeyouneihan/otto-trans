from .base import BaseTranslator, UnsupportedLanguageError
import httpx

class DeepLAPIError(Exception):
    """DeepL API 调用异常"""
    pass

class DeepLTranslator(BaseTranslator):
    deepl_url = "https://api.deepl.com/v2/translate"
    deepl_languages_url = "https://api.deepl.com/v3/languages?resource=translate_text"

    deepl_url_free = "https://api-free.deepl.com/v2/translate"
    deepl_languages_url_free = "https://api-free.deepl.com/v3/languages?resource=translate_text"

    _LANG_MAP: dict[str, str] = {
        # 常见别名 → BCP47
        "zh-cn": "ZH-HANS",
        "zh-tw": "ZH-HANT",
        "zh-hk": "ZH-HANT",
        # 以下直通（包括目标专属的变体）
        "zh-hans": "ZH-HANS",
        "zh-hant": "ZH-HANT",
        "pt-br": "PT-BR",
        "pt-pt": "PT-PT",
        "en-gb": "EN-GB",
        "en-us": "EN-US",
        "de-de": "DE-DE",
        "fr-fr": "FR-FR",
        "es-419": "ES-419",
    }

    def __init__(self, api_key: str, paid: bool = False, context: str | None = None, preserve_formatting: bool | None = None, formality: str | None = None, model_type: str | None = None):
        super().__init__()
        self.api_key = api_key
        self.paid = paid
        self.context = context
        self.preserve_formatting = preserve_formatting
        self.formality = formality
        self.model_type = model_type
        self._client = httpx.AsyncClient(follow_redirects=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    @property
    def name(self) -> str:
        return "deepl"

    async def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        return (await self.translate_batch([text], from_lang, to_lang))[0]

    async def translate_batch(self, texts: list[str], from_lang: str, to_lang: str) -> list[str]:
        from_lang = self._normalize_lang(from_lang)
        to_lang = self._normalize_lang(to_lang)
        payload = self._build_payload(texts, from_lang, to_lang)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"DeepL-Auth-Key {self.api_key}"
        }
        response = await self._client.post(self.deepl_url if self.paid else self.deepl_url_free, json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            if response.status_code == 400 and ( "Value for 'source_lang' not supported." in response.json().get("message", "") or "Value for 'target_lang' not supported." in response.json().get("message", "")):
                languages = await self._fetch_supported_languages()
                raise UnsupportedLanguageError.for_engine(
                    self.name, from_lang, to_lang, languages[0], languages[1]
                ) from e
            raise DeepLAPIError(f"DeepL API 返回错误: {response.status_code} {response.text}") from e
        body = response.json()
        return [t["text"] for t in body["translations"]]

    def _build_payload(self, texts: list[str], from_lang: str, to_lang: str) -> dict:
        payload = {
            "text": texts,
            "target_lang": to_lang,
        }
        if from_lang != "AUTO":
            payload["source_lang"] = from_lang
        if self.context:
            payload["context"] = self.context
        if self.preserve_formatting is not None:
            payload["preserve_formatting"] = self.preserve_formatting
        if self.formality:
            payload["formality"] = self.formality
        if self.model_type:
            payload["model_type"] = self.model_type
        return payload
    
    def _normalize_lang(self, raw: str) -> str:
        code = self._LANG_MAP.get(raw.lower())
        return code if code else raw.upper()

    async def _fetch_supported_languages(self) -> tuple[list[str], list[str]]:
        # Implementation for fetching supported languages
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"DeepL-Auth-Key {self.api_key}"
        }
        response = await self._client.get(self.deepl_languages_url if self.paid else self.deepl_languages_url_free, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise DeepLAPIError(f"DeepL API 获取支持语言失败: {response.status_code} {response.text}") from e
        body = response.json()
        return ([l["lang"] for l in body if l["usable_as_source"]], [l["lang"] for l in body if l["usable_as_target"]])