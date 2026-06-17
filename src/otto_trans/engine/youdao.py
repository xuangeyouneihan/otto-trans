import asyncio
import base64
import hashlib
import re
import time
import uuid

import httpx

from ..utils.format import Format, UnsupportedFormatError
from ..utils.html import fix_html
from ..utils.text import detect_encoding, utf_8
from .base import BaseTranslator, UnsupportedLanguageError


class YoudaoAPIError(Exception):
    """有道 API 调用异常"""

    pass


class YoudaoTranslator(BaseTranslator):
    # ── API 端点 ─────────────────────────────────────────────

    _youdao_text_url = "https://openapi.youdao.com/v2/api"
    _youdao_file_url = "https://openapi.youdao.com/file_trans"
    _youdao_web_url = "https://openapi.youdao.com/translate_html"
    _youdao_detect_url = "https://openapi.youdao.com/v1/detect"

    # ── 引擎标识 ─────────────────────────────────────────────

    engine_name = "youdao"
    friendly_name = "有道翻译"

    options: dict[str, dict[str, type | str | bool | set[str]]] = {
        "app_key": {
            "type": str,
            "description": "应用 ID",
            "required": True,
            "scope": {"text", "file"},
        },
        "app_secret": {
            "type": str,
            "description": "应用密钥",
            "required": True,
            "scope": {"text", "file"},
        },
    }

    # ── 语言映射 ─────────────────────────────────────────────

    # 标准语言代码 → 有道 API 代码（同时用于校验）
    _TEXT_LANG_MAP: dict[str, str] = {
        # === 非直通映射（key != value） ===
        "zh-hans": "zh-CHS",  # BCP47 → 有道
        "zh-hant": "zh-CHT",
        "jv": "jw",
        "zh-chs": "zh-CHS",  # 有道代码自映射（兼容直接传参）
        "zh-cht": "zh-CHT",
        "jw": "jw",
        "zh": "zh-CHS",  # 常见别名
        "sr-cyrl": "sr-Cyrl",  # 大小写修正
        "sr-latn": "sr-Latn",
        # === 直通（key == value，以下全部原样） ===
        "en": "en",
        "ja": "ja",
        "ko": "ko",
        "fr": "fr",
        "es": "es",
        "pt": "pt",
        "it": "it",
        "ru": "ru",
        "vi": "vi",
        "de": "de",
        "ar": "ar",
        "id": "id",
        "th": "th",
        "af": "af",
        "bs": "bs",
        "bg": "bg",
        "yue": "yue",
        "ca": "ca",
        "hr": "hr",
        "cs": "cs",
        "da": "da",
        "nl": "nl",
        "et": "et",
        "fj": "fj",
        "fi": "fi",
        "el": "el",
        "ht": "ht",
        "he": "he",
        "hi": "hi",
        "mww": "mww",
        "hu": "hu",
        "sw": "sw",
        "tlh": "tlh",
        "lv": "lv",
        "lt": "lt",
        "ms": "ms",
        "mt": "mt",
        "no": "no",
        "fa": "fa",
        "pl": "pl",
        "otq": "otq",
        "ro": "ro",
        "sk": "sk",
        "sl": "sl",
        "sv": "sv",
        "ty": "ty",
        "to": "to",
        "tr": "tr",
        "uk": "uk",
        "ur": "ur",
        "cy": "cy",
        "yua": "yua",
        "sq": "sq",
        "am": "am",
        "hy": "hy",
        "az": "az",
        "bn": "bn",
        "eu": "eu",
        "be": "be",
        "ceb": "ceb",
        "co": "co",
        "eo": "eo",
        "tl": "tl",
        "fy": "fy",
        "gl": "gl",
        "ka": "ka",
        "gu": "gu",
        "ha": "ha",
        "haw": "haw",
        "is": "is",
        "ig": "ig",
        "ga": "ga",
        "kn": "kn",
        "kk": "kk",
        "km": "km",
        "ku": "ku",
        "ky": "ky",
        "lo": "lo",
        "la": "la",
        "lb": "lb",
        "mk": "mk",
        "mg": "mg",
        "ml": "ml",
        "mi": "mi",
        "mr": "mr",
        "mn": "mn",
        "my": "my",
        "ne": "ne",
        "ny": "ny",
        "ps": "ps",
        "pa": "pa",
        "sm": "sm",
        "gd": "gd",
        "st": "st",
        "sn": "sn",
        "sd": "sd",
        "si": "si",
        "so": "so",
        "su": "su",
        "tg": "tg",
        "ta": "ta",
        "te": "te",
        "uz": "uz",
        "xh": "xh",
        "yi": "yi",
        "yo": "yo",
        "zu": "zu",
        # === 特殊 ===
        "auto": "auto",
    }

    # 文档翻译语言映射（子集，仅 16 种语言）
    _DOC_LANG_MAP: dict[str, str] = {
        # === 非直通映射 ===
        "zh-hans": "zh-CHS",
        "zh-chs": "zh-CHS",
        "zh": "zh-CHS",
        # === 直通 ===
        "en": "en",
        "ja": "ja",
        "ko": "ko",
        "fr": "fr",
        "es": "es",
        "pt": "pt",
        "it": "it",
        "ru": "ru",
        "vi": "vi",
        "de": "de",
        "ar": "ar",
        "id": "id",
        "th": "th",
        "nl": "nl",
        "hi": "hi",
        # === 特殊 ===
        "auto": "auto",
    }

    # 文档翻译支持的语言对（方向敏感）
    _DOC_PAIRS: set[tuple[str, str]] = {
        # 中文 ↔ 其他
        ("zh-CHS", "en"),
        ("en", "zh-CHS"),
        ("zh-CHS", "ja"),
        ("ja", "zh-CHS"),
        ("zh-CHS", "ko"),
        ("ko", "zh-CHS"),
        ("zh-CHS", "ru"),
        ("ru", "zh-CHS"),
        ("zh-CHS", "fr"),
        ("fr", "zh-CHS"),
        ("zh-CHS", "th"),
        ("th", "zh-CHS"),
        # X → 中文
        ("vi", "zh-CHS"),
        ("id", "zh-CHS"),
        ("ar", "zh-CHS"),
        ("de", "zh-CHS"),
        ("it", "zh-CHS"),
        ("nl", "zh-CHS"),
        ("es", "zh-CHS"),
        ("pt", "zh-CHS"),
        # 英文 ↔ 其他
        ("en", "fr"),
        ("fr", "en"),
        ("en", "th"),
        ("th", "en"),
        # X → 英文
        ("hi", "en"),
        ("vi", "en"),
        ("ar", "en"),
        ("ja", "en"),
        ("ru", "en"),
        ("ko", "en"),
    }

    # 网页翻译支持的语言对（方向敏感，黑名单模式）
    _WEB_BLOCKED_PAIRS: set[tuple[str, str]] = {
        ("de", "hi"),
        ("en", "pt"),
        ("hi", "de"),
        ("hi", "nl"),
        ("hi", "pt"),
        ("nl", "hi"),
        ("pt", "hi"),
    }

    # 网页翻译支持的语言（子集，16+1 种）
    _WEB_LANG_MAP: dict[str, str] = {
        # === 非直通映射 ===
        "zh-hans": "zh-CHS",
        "zh-chs": "zh-CHS",
        "zh": "zh-CHS",
        "zh-hant": "zh-CHT",
        "zh-cht": "zh-CHT",
        # === 直通 ===
        "en": "en",
        "ja": "ja",
        "ko": "ko",
        "fr": "fr",
        "es": "es",
        "pt": "pt",
        "it": "it",
        "ru": "ru",
        "vi": "vi",
        "de": "de",
        "ar": "ar",
        "id": "id",
        "th": "th",
        "nl": "nl",
    }

    # ── 格式映射 ─────────────────────────────────────────────

    _FILE_TYPE_MAP: dict[str, str] = {
        "ms-word": "docx",
        "ms-word-legacy": "doc",
        "pdf": "pdf",
        "ms-powerpoint": "pptx",
        "ms-powerpoint-legacy": "ppt",
        "ms-excel": "xlsx",
        "jpeg": "jpg",
        "png": "png",
        "bmp": "bmp",
    }

    _FILE_DOWNLOAD_MAP: dict[str, str] = {
        "ms-word": "word",
        "ms-word-legacy": "word",
        "pdf": "pdf",
        "ms-powerpoint": "ppt",
        "ms-powerpoint-legacy": "ppt",
        "ms-excel": "xlsx",
        # 图片格式 downloadFileType 不支持，fallback 到 pdf
        "jpeg": "pdf",
        "png": "pdf",
        "bmp": "pdf",
    }

    formats: set[Format] = {
        Format(
            name="ms-word",
            description="Microsoft Word 格式，适用于 .docx 文件",
            extensions={".docx"},
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        Format(
            name="ms-word-legacy",
            description="Microsoft Word 97-2003 格式，适用于 .doc 文件",
            extensions={".doc"},
            mime_type="application/msword",
        ),
        Format(
            name="pdf",
            description="PDF 格式",
            extensions={".pdf"},
            mime_type="application/pdf",
        ),
        Format(
            name="ms-powerpoint-legacy",
            description="Microsoft PowerPoint 97-2003 格式，适用于 .ppt 文件",
            extensions={".ppt"},
            mime_type="application/vnd.ms-powerpoint",
        ),
        Format(
            name="ms-powerpoint",
            description="Microsoft PowerPoint 格式，适用于 .pptx 文件",
            extensions={".pptx"},
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
        Format(
            name="ms-excel",
            description="Microsoft Excel 格式，适用于 .xlsx 文件",
            extensions={".xlsx"},
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        Format(
            name="jpeg",
            description="JPEG 图像格式",
            extensions={".jpg", ".jpe", ".jpeg"},
            mime_type="image/jpeg",
        ),
        Format(
            name="png",
            description="PNG 图像格式",
            extensions={".png"},
            mime_type="image/png",
        ),
        Format(
            name="bmp",
            description="BMP 位图格式",
            extensions={".bmp"},
            mime_type="image/bmp",
        ),
        Format(
            name="html",
            description="HTML 网页格式，自动识别标签仅翻译文本内容",
            extensions={".html", ".htm"},
            mime_type="text/html",
        ),
    }

    # ── 生命周期 ─────────────────────────────────────────────

    def __init__(
        self, app_key: str, app_secret: str, config_name: str | None = None, **kwargs
    ):
        if kwargs:
            raise ValueError(f"未知参数: {list(kwargs.keys())}")
        super().__init__(config_name=config_name)
        self.__app_key = app_key
        self.__app_secret = app_secret
        self._client = httpx.AsyncClient(follow_redirects=True)  # 一个实例一个客户端

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()  # 用完记得关

    # ── 工具方法 ─────────────────────────────────────────────

    def _sha256(self, sign_str):
        hash_algorithm = hashlib.sha256()
        hash_algorithm.update(sign_str.encode("utf-8"))
        return hash_algorithm.hexdigest()

    def _truncate(self, text: str) -> str:
        size = len(text)
        return text if size <= 20 else text[:10] + str(size) + text[size - 10 :]

    def _build_sign(self, input_str: str) -> tuple[str, str, str]:
        salt = str(uuid.uuid1())
        curtime = str(int(time.time()))
        sign_str = (
            self.__app_key
            + self._truncate(input_str)
            + salt
            + curtime
            + self.__app_secret
        )
        return self._sha256(sign_str), salt, curtime

    # ── 文本翻译 ─────────────────────────────────────────────

    def _normalize_text_lang(self, src_lang: str, tgt_lang: str) -> tuple[str, str]:
        """将标准语言代码转为有道 API 代码，不在表中则报错。"""
        src_code = self._TEXT_LANG_MAP.get(src_lang.lower())
        tgt_code = self._TEXT_LANG_MAP.get(tgt_lang.lower())
        if src_code is None or tgt_code is None or tgt_code == "auto":
            raise UnsupportedLanguageError.for_engine(
                f"{self.friendly_name}（{self.name}）",
                src_lang,
                tgt_lang,
                self._supported_text_languages(),
                self._supported_text_languages(),
            )
        return (src_code, tgt_code)

    def _supported_text_languages(self) -> set[str]:
        """返回可供用户选择的语言代码列表（不含别名）。"""
        return {
            k
            for k in self._TEXT_LANG_MAP
            if k == self._TEXT_LANG_MAP[k] and k != "auto"
        }

    def translate_texts(
        self, texts: list[str], src_lang: str, tgt_lang: str
    ) -> list[str]:
        src_lang, tgt_lang = self._normalize_text_lang(src_lang, tgt_lang)
        return asyncio.run(self._translate_text_batch(texts, src_lang, tgt_lang))

    async def _translate_text_batch(
        self, texts: list[str], src_lang: str, tgt_lang: str
    ) -> list[str]:
        response = await self._text_request(texts, src_lang, tgt_lang)
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise YoudaoAPIError(
                f"有道 API 返回错误: {response.status_code} {response.text}"
            ) from e
        body = response.json()
        if body.get("errorCode") != "0":
            raise YoudaoAPIError(f"有道 API 返回错误: {body.get('errorCode')}")
        return [r["translation"] for r in body["translateResults"]]

    async def _text_request(
        self, texts: list[str], src_lang: str, tgt_lang: str
    ) -> httpx.Response:
        sign, salt, curtime = self._build_sign("".join(texts))
        payload = {
            "from": src_lang,
            "to": tgt_lang,
            "signType": "v3",
            "curtime": curtime,
            "appKey": self.__app_key,
            "q": texts,
            "salt": salt,
            "sign": sign,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        return await self._client.post(
            self._youdao_text_url, data=payload, headers=headers
        )

    # ── 网页翻译 ─────────────────────────────────────────────

    async def _detect_lang(self, content: bytes) -> str:
        """从 HTML 内容中提取纯文本，调用有道语种识别 API 检测语言。"""
        text = content.decode(detect_encoding(content), errors="replace")
        # 去掉 HTML 标签，取前 500 字符用于识别
        text = re.sub(r"<[^>]+>", "", text)
        text = text.strip()[:500]
        if not text:
            raise YoudaoAPIError("有道语种识别失败: HTML 内容为空，无法检测语言")

        sign, salt, curtime = self._build_sign(text)
        payload = {
            "q": text,
            "appKey": self.__app_key,
            "salt": salt,
            "curtime": curtime,
            "sign": sign,
        }
        resp = await self._client.post(
            self._youdao_detect_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise YoudaoAPIError(
                f"有道语种识别失败: {resp.status_code} {resp.text}"
            ) from e
        body = resp.json()
        if body.get("errorCode") != "0":
            raise YoudaoAPIError(f"有道语种识别失败: errorCode={body.get('errorCode')}")
        # 取置信度最高的结果
        results = sorted(
            body.get("data", []), key=lambda r: r.get("confidence", 0), reverse=True
        )
        return results[0]["language"].lower() if results else "en"

    async def _translate_web(
        self, content: bytes, src_lang: str, tgt_lang: str
    ) -> bytes:
        """翻译 HTML 内容，auto 时逐文件检测源语言。"""
        if src_lang == "auto":
            src_lang = await self._detect_lang(content)

        src_code = self._WEB_LANG_MAP.get(src_lang.lower())
        tgt_code = self._WEB_LANG_MAP.get(tgt_lang.lower())
        if src_code is None or tgt_code is None:
            raise UnsupportedLanguageError.for_engine(
                f"{self.friendly_name} 网页翻译",
                src_lang,
                tgt_lang,
                self._supported_web_languages(),
                self._supported_web_languages(),
                blocked_pairs=self._WEB_BLOCKED_PAIRS,
            )
        if (src_code, tgt_code) in self._WEB_BLOCKED_PAIRS:
            raise UnsupportedLanguageError.for_engine(
                f"{self.friendly_name} 网页翻译",
                src_lang,
                tgt_lang,
                self._supported_web_languages(),
                self._supported_web_languages(),
                blocked_pairs=self._WEB_BLOCKED_PAIRS,
            )

        html_str = content.decode(detect_encoding(content), errors="replace")
        sign, salt, curtime = self._build_sign(html_str)
        payload = {
            "q": html_str,
            "from": src_lang,
            "to": tgt_lang,
            "appKey": self.__app_key,
            "salt": salt,
            "curtime": curtime,
            "sign": sign,
            "signType": "v3",
        }
        resp = await self._client.post(
            self._youdao_web_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise YoudaoAPIError(
                f"有道网页翻译失败: {resp.status_code} {resp.text}"
            ) from e
        body = resp.json()
        if body.get("errorCode") != "0":
            raise YoudaoAPIError(f"有道网页翻译失败: errorCode={body.get('errorCode')}")
        translated = body["data"]
        fixed = fix_html(translated)
        return fixed.encode("utf-8-sig")

    # ── 文件翻译 ─────────────────────────────────────────────

    def _normalize_doc_lang(self, src_lang: str, tgt_lang: str) -> tuple[str, str]:
        """将标准语言代码转为有道文档翻译代码，并校验语言对是否支持。"""
        src_code = self._DOC_LANG_MAP.get(src_lang.lower())
        tgt_code = self._DOC_LANG_MAP.get(tgt_lang.lower())
        if src_code is None or tgt_code is None:
            raise UnsupportedLanguageError.for_engine(
                f"{self.friendly_name} 文档翻译",
                src_lang,
                tgt_lang,
                self._supported_doc_languages(),
                self._supported_doc_languages(),
                supported_pairs=self._DOC_PAIRS,
            )
        # auto 源语言匹配所有已注册的目标语言
        if src_code == "auto":
            if tgt_code == "auto":
                raise UnsupportedLanguageError.for_engine(
                    f"{self.friendly_name} 文档翻译",
                    src_lang,
                    tgt_lang,
                    {"auto"},
                    self._supported_doc_languages(),
                    supported_pairs=self._DOC_PAIRS,
                )
            if not any(tgt_code == t for _, t in self._DOC_PAIRS):
                raise UnsupportedLanguageError.for_engine(
                    f"{self.friendly_name} 文档翻译",
                    src_lang,
                    tgt_lang,
                    {"auto"},
                    self._supported_doc_languages(),
                    supported_pairs=self._DOC_PAIRS,
                )
        else:
            if (src_code, tgt_code) not in self._DOC_PAIRS:
                raise UnsupportedLanguageError.for_engine(
                    f"{self.friendly_name} 文档翻译",
                    src_lang,
                    tgt_lang,
                    self._supported_doc_languages(),
                    self._supported_doc_languages(),
                    supported_pairs=self._DOC_PAIRS,
                )
        return (src_code, tgt_code)

    def _supported_doc_languages(self) -> set[str]:
        """返回文档翻译支持的语言代码列表（不含别名和 auto）。"""
        return {
            k for k in self._DOC_LANG_MAP if k == self._DOC_LANG_MAP[k] and k != "auto"
        }

    def _supported_web_languages(self) -> set[str]:
        """返回网页翻译支持的语言代码列表（不含别名）。"""
        return {k for k in self._WEB_LANG_MAP if k == self._WEB_LANG_MAP[k]}

    def _resolve_file_type(self, fmt: Format) -> str:
        if fmt.name in self._FILE_TYPE_MAP:
            return self._FILE_TYPE_MAP[fmt.name]
        raise UnsupportedFormatError.for_engine(self.name, fmt, self.formats)

    async def translate_file(
        self, content: bytes, src_lang: str, tgt_lang: str, fmt: Format
    ) -> tuple[bytes, Format]:
        if not self.supports_format(fmt):
            raise UnsupportedFormatError.for_engine(self.name, fmt)

        if fmt.name == "html":
            translated = await self._translate_web(content, src_lang, tgt_lang)
            return translated, fmt

        src_lang, tgt_lang = self._normalize_doc_lang(src_lang, tgt_lang)
        file_type = self._resolve_file_type(fmt)

        result, content_type = await self._translate_doc(
            content, src_lang, tgt_lang, file_type
        )
        out_fmt = self._format_by_mime(content_type) or fmt
        result = utf_8(result, out_fmt)
        return result, out_fmt

    async def _translate_doc(
        self, content: bytes, src_lang: str, tgt_lang: str, file_type: str
    ) -> tuple[bytes, str]:
        flownumber = await self._file_upload(content, file_type, src_lang, tgt_lang)
        await self._file_poll(flownumber)
        return await self._file_download(flownumber, file_type)

    async def _file_upload(
        self, content: bytes, file_type: str, src_lang: str, tgt_lang: str
    ) -> str:
        q = base64.b64encode(content).decode()
        sign, salt, curtime = self._build_sign(q)
        payload: dict[str, str | int | float] = {
            "q": q,
            "fileName": f"content.{file_type}",
            "fileType": file_type,
            "langFrom": src_lang,
            "langTo": tgt_lang,
            "appKey": self.__app_key,
            "salt": salt,
            "curtime": curtime,
            "sign": sign,
            "docType": "json",
            "signType": "v3",
        }
        resp = await self._client.post(
            self._youdao_file_url + "/upload",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise YoudaoAPIError(
                f"有道文档上传失败: {resp.status_code} {resp.text}"
            ) from e
        body = resp.json()
        if body.get("errorCode") != "0":
            raise YoudaoAPIError(f"有道文档上传失败: errorCode={body.get('errorCode')}")
        return body["flownumber"]

    async def _file_poll(self, flownumber: str) -> None:
        while True:
            sign, salt, curtime = self._build_sign(flownumber)
            payload: dict[str, str | int | float] = {
                "flownumber": flownumber,
                "appKey": self.__app_key,
                "salt": salt,
                "curtime": curtime,
                "sign": sign,
                "docType": "json",
                "signType": "v3",
            }
            resp = await self._client.post(
                self._youdao_file_url + "/query",
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            try:
                resp.raise_for_status()
            except httpx.HTTPError as e:
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "1"))
                    await asyncio.sleep(retry_after)
                    continue  # 回到循环重新查询
                raise YoudaoAPIError(
                    f"有道文档查询失败: {resp.status_code} {resp.text}"
                ) from e
            body = resp.json()
            if body.get("errorCode") != "0":
                error_code = body.get("errorCode")
                if error_code.isnumeric() and (
                    error_code == "412"
                    or (int(error_code) % 1000 == 411 and error_code != "9411")
                ):  # 同 429，查询过于频繁
                    await asyncio.sleep(1)
                    continue
                raise YoudaoAPIError(f"有道文档查询失败: errorCode={error_code}")

            status = int(body.get("status", 0))
            match status:
                case 4:  # 已完成
                    return
                case s if s < 0:  # 错误状态
                    raise YoudaoAPIError(
                        f"有道文档查询失败: status={status}, "
                        f"statusString={body.get('statusString', '')}"
                    )
            await asyncio.sleep(1)  # 轮询间隔

    async def _file_download(
        self, flownumber: str, file_type: str
    ) -> tuple[bytes, str]:
        download_type = self._FILE_DOWNLOAD_MAP.get(file_type, "pdf")
        sign, salt, curtime = self._build_sign(flownumber)
        payload: dict[str, str | int | float] = {
            "flownumber": flownumber,
            "downloadFileType": download_type,
            "appKey": self.__app_key,
            "salt": salt,
            "curtime": curtime,
            "sign": sign,
            "docType": "json",
            "signType": "v3",
        }
        resp = await self._client.post(
            self._youdao_file_url + "/download",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if "application/json" in (resp.headers.get("content-type") or ""):
            body = resp.json()
            raise YoudaoAPIError(f"有道文档下载失败: errorCode={body.get('errorCode')}")
        return resp.content, resp.headers.get("content-type", "")
