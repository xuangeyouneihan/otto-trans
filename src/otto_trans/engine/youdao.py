from .base import BaseTranslator, UnsupportedLanguageError
import httpx
import uuid
import hashlib
import time

class YoudaoAPIError(Exception):
    """有道 API 调用异常"""
    pass

class YoudaoTranslator(BaseTranslator):
    youdao_url = "https://openapi.youdao.com/v2/api"

    # 标准语言代码 → 有道 API 代码（同时用于校验）
    _LANG_MAP: dict[str, str] = {
        # === 非直通映射（key != value） ===
        "zh-hans": "zh-CHS",   # BCP47 → 有道
        "zh-hant": "zh-CHT",
        "jv": "jw",
        "zh-chs": "zh-CHS",    # 有道代码自映射（兼容直接传参）
        "zh-cht": "zh-CHT",
        "jw": "jw",
        "zh": "zh-CHS",        # 常见别名
        "sr-cyrl": "sr-Cyrl",  # 大小写修正
        "sr-latn": "sr-Latn",
        # === 直通（key == value，以下全部原样） ===
        "en": "en", "ja": "ja", "ko": "ko", "fr": "fr",
        "es": "es", "pt": "pt", "it": "it", "ru": "ru",
        "vi": "vi", "de": "de", "ar": "ar", "id": "id",
        "th": "th", "af": "af", "bs": "bs", "bg": "bg",
        "yue": "yue", "ca": "ca", "hr": "hr", "cs": "cs",
        "da": "da", "nl": "nl", "et": "et", "fj": "fj",
        "fi": "fi", "el": "el", "ht": "ht", "he": "he",
        "hi": "hi", "mww": "mww", "hu": "hu", "sw": "sw",
        "tlh": "tlh", "lv": "lv", "lt": "lt", "ms": "ms",
        "mt": "mt", "no": "no", "fa": "fa", "pl": "pl",
        "otq": "otq", "ro": "ro", "sk": "sk", "sl": "sl",
        "sv": "sv", "ty": "ty", "to": "to", "tr": "tr",
        "uk": "uk", "ur": "ur", "cy": "cy", "yua": "yua",
        "sq": "sq", "am": "am", "hy": "hy", "az": "az",
        "bn": "bn", "eu": "eu", "be": "be", "ceb": "ceb",
        "co": "co", "eo": "eo", "tl": "tl", "fy": "fy",
        "gl": "gl", "ka": "ka", "gu": "gu", "ha": "ha",
        "haw": "haw", "is": "is", "ig": "ig", "ga": "ga",
        "kn": "kn", "kk": "kk", "km": "km", "ku": "ku",
        "ky": "ky", "lo": "lo", "la": "la", "lb": "lb",
        "mk": "mk", "mg": "mg", "ml": "ml", "mi": "mi",
        "mr": "mr", "mn": "mn", "my": "my", "ne": "ne",
        "ny": "ny", "ps": "ps", "pa": "pa", "sm": "sm",
        "gd": "gd", "st": "st", "sn": "sn", "sd": "sd",
        "si": "si", "so": "so", "su": "su", "tg": "tg",
        "ta": "ta", "te": "te", "uz": "uz", "xh": "xh",
        "yi": "yi", "yo": "yo", "zu": "zu",
        # === 特殊 ===
        "auto": "auto",
    }

    def __init__(self, app_key: str, app_secret: str, **kwargs):
        if kwargs:
            raise ValueError(f"未知参数: {list(kwargs.keys())}")
        super().__init__()
        self.app_key = app_key
        self.app_secret = app_secret
        self._client = httpx.AsyncClient(follow_redirects=True)  # 一个实例一个客户端

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()  # 用完记得关

    @property
    def name(self) -> str:
        return "youdao"

    def _normalize_lang(self, from_lang: str, to_lang: str) -> tuple[str, str]:
        """将标准语言代码转为有道 API 代码，不在表中则报错。"""
        from_code = self._LANG_MAP.get(from_lang.lower())
        to_code = self._LANG_MAP.get(to_lang.lower())
        if from_code is None or to_code is None or to_code == "auto":
            raise UnsupportedLanguageError.for_engine(
                self.name, from_lang, to_lang, self._supported_languages(), self._supported_languages()
            )
        return (from_code, to_code)

    def _supported_languages(self) -> list[str]:
        """返回可供用户选择的语言代码列表（不含别名）。"""
        return [k for k in self._LANG_MAP if k == self._LANG_MAP[k] and k != "auto"]

    async def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        (from_lang, to_lang) = self._normalize_lang(from_lang, to_lang)
        results = await self.translate_batch([text], from_lang, to_lang)
        return results[0]

    async def translate_batch(self, texts: list[str], from_lang: str, to_lang: str) -> list[str]:
        (from_lang, to_lang) = self._normalize_lang(from_lang, to_lang)
        payload = self._build_payload(texts, from_lang, to_lang)
        response = await self._request(payload)
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise YoudaoAPIError(f"有道 API 返回错误: {response.status_code} {response.text}") from e
        body = response.json()
        if body.get("errorCode") != "0":
            raise YoudaoAPIError(f"有道 API 返回错误: {body.get('errorCode')}")
        return [r["translation"] for r in body["translateResults"]]

    def _build_payload(self, texts: list[str], from_lang: str, to_lang: str) -> dict:
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

    async def _request(self, payload: dict) -> httpx.Response:
        # Placeholder implementation - replace with actual API request logic
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        return await self._client.post(self.youdao_url, data=payload, headers=headers)

    def _sha256(self, sign_str):
        hash_algorithm = hashlib.sha256()
        hash_algorithm.update(sign_str.encode("utf-8"))
        return hash_algorithm.hexdigest()
    
    def _truncate(self, text: str) -> str:
        size = len(text)
        return text if size <= 20 else text[:10] + str(size) + text[size - 10:]