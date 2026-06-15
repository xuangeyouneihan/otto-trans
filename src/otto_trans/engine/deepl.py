import asyncio
from typing import Any

import httpx

from ..utils.format import Format, UnsupportedFormatError
from ..utils.html import fix_html
from ..utils.text import detect_encoding
from .base import BaseTranslator, UnsupportedLanguageError


class DeepLAPIError(Exception):
    """DeepL API 调用异常"""

    pass


class DeepLTranslator(BaseTranslator):
    _deepl_text_url = "https://api.deepl.com/v2/translate"
    _deepl_text_languages_url = (
        "https://api.deepl.com/v3/languages?resource=translate_text"
    )
    _deepl_file_url = "https://api.deepl.com/v2/document"
    _deepl_file_languages_url = (
        "https://api.deepl.com/v3/languages?resource=translate_document"
    )

    _deepl_text_url_free = "https://api-free.deepl.com/v2/translate"
    _deepl_text_languages_url_free = (
        "https://api-free.deepl.com/v3/languages?resource=translate_text"
    )
    _deepl_file_url_free = "https://api-free.deepl.com/v2/document"
    _deepl_file_languages_url_free = (
        "https://api-free.deepl.com/v3/languages?resource=translate_document"
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

    options: dict[str, dict[str, type | str | bool | set[str]]] = {
        "auth_key": {
            "type": str,
            "description": "API 密钥",
            "required": True,
            "scope": {"text", "file"},
        },
        "paid": {
            "type": bool,
            "description": "是否使用付费端点，true 或 false，默认 false",
            "required": False,
            "scope": {"text", "file"},
        },
        "formality": {
            "type": str,
            "description": "正式程度，default、more、less、prefer_more 或 prefer_less",
            "required": False,
            "scope": {"text", "file"},
        },
        "glossary_id": {
            "type": str,
            "description": "术语表 ID，启用后会使用指定的术语表进行翻译",
            "required": False,
            "scope": {"text", "file"},
        },
        "context": {
            "type": str,
            "description": "上下文信息，帮助模型理解翻译场景",
            "required": False,
            "scope": {"text"},
        },
        "preserve_formatting": {
            "type": bool,
            "description": "保留原文格式，true 或 false",
            "required": False,
            "scope": {"text"},
        },
        "model_type": {
            "type": str,
            "description": "模型类型，quality_optimized、latency_optimized 或 prefer_quality_optimized",
            "required": False,
            "scope": {"text"},
        },
        "tag_handling": {
            "type": str,
            "description": "标签处理，xml 或 html，启用后会使用 v2 版本的标签处理",
            "required": False,
            "scope": {"text"},
        },
    }

    formats: set[Format] = {
        Format(
            name="ms-word",
            description="Microsoft Word 格式，适用于 .docx 文件内容",
            extensions={".docx"},
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        Format(
            name="ms-powerpoint",
            description="Microsoft PowerPoint 格式，适用于 .pptx 文件内容",
            extensions={".pptx"},
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
        Format(
            name="ms-excel",
            description="Microsoft Excel 格式，适用于 .xlsx 文件内容",
            extensions={".xlsx"},
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        Format(
            name="pdf",
            description="PDF 格式，适用于 .pdf 文件内容",
            extensions={".pdf"},
            mime_type="application/pdf",
        ),
        Format(
            name="html",
            description="HTML 格式，适用于包含 HTML 标签的内容，启用 tag_handling 选项后会使用 v2 版本的标签处理",
            extensions={".html", ".htm"},
            mime_type="text/html",
        ),
        Format(
            name="text",
            description="纯文本格式，适用于一般文本内容",
            extensions={".txt", ".text"},
            mime_type="text/plain",
        ),
        Format(
            name="xliff",
            description="XLIFF 格式，适用于翻译文件内容",
            extensions={".xlf", ".xliff"},
            mime_type="application/xliff+xml",
        ),
        Format(
            name="srt",
            description="SubRip 字幕格式，适用于字幕文件内容",
            extensions={".srt"},
            mime_type="application/x-subrip",
        ),
        Format(
            name="jpeg",
            description="JPEG 图像格式，适用于 .jpg 和 .jpeg 图像内容",
            extensions={".jpg", ".jpeg", ".jpe"},
            mime_type="image/jpeg",
        ),
        Format(
            name="png",
            description="PNG 图像格式，适用于 .png 图像内容",
            extensions={".png"},
            mime_type="image/png",
        ),
    }

    def __init__(
        self,
        auth_key: str,
        paid: bool = False,
        context: str | None = None,
        preserve_formatting: bool | None = None,
        formality: str | None = None,
        model_type: str | None = None,
        glossary_id: str | None = None,
        tag_handling: str | None = None,
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
        self.glossary_id = glossary_id
        if tag_handling is not None and tag_handling not in ("xml", "html"):
            raise ValueError(
                f"tag_handling 参数值无效：{tag_handling}，必须是 xml 或 html"
            )
        self.tag_handling = tag_handling
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                600.0, connect=5.0, read=600.0, write=600.0, pool=5.0
            ),
            follow_redirects=True,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    def translate_texts(
        self,
        texts: list[str],
        src_lang: str,
        tgt_lang: str,
    ) -> list[str]:
        src_lang, tgt_lang = self._normalize_lang(src_lang, tgt_lang)
        return asyncio.run(self._translate_text_batch(texts, src_lang, tgt_lang))

    async def _translate_text_batch(
        self, contents: list[str], src_lang: str, tgt_lang: str
    ) -> list[str]:
        payload = self._build_text_payload(contents, src_lang, tgt_lang)
        headers = {
            # "Content-Type": "application/json",
            "Authorization": f"DeepL-Auth-Key {self.__auth_key}",
        }
        response = await self._client.post(
            self._deepl_text_url if self.paid else self._deepl_text_url_free,
            json=payload,
            headers=headers,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            error_msg = response.json().get("message", "")
            if response.status_code == 400 and (
                ("source_lang" in error_msg or "target_lang" in error_msg)
                and "not supported" in error_msg
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

    def _build_text_payload(
        self, contents: list[str], src_lang: str, tgt_lang: str
    ) -> dict:
        payload: dict[str, Any] = {
            "text": contents,
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
        if self.glossary_id:
            payload["glossary_id"] = self.glossary_id
        if self.tag_handling:
            payload["tag_handling"] = self.tag_handling
            payload["tag_handling_version"] = "v2"
        return payload

    async def translate_file(
        self, content: bytes, src_lang: str, tgt_lang: str, fmt: Format
    ) -> tuple[bytes, Format]:
        if fmt not in (self.formats or []):
            raise UnsupportedFormatError.for_engine(self.name, fmt)

        src_lang, tgt_lang = self._normalize_lang(src_lang, tgt_lang)
        upload_result = await self._upload(content, src_lang, tgt_lang, fmt)
        await self._poll(upload_result["document_id"], upload_result["document_key"])
        result = await self._download(
            upload_result["document_id"], upload_result["document_key"]
        )
        if fmt == "html":
            text_result = result.decode(detect_encoding(result), errors="replace")
            fix_html_result = fix_html(text_result)
            if fix_html_result != text_result:
                result = fix_html_result.encode("utf-8-sig")
        return result, fmt

    async def _upload(
        self, content: bytes, src_lang: str, tgt_lang: str, fmt: Format
    ) -> dict[str, str]:
        # 实现文件上传逻辑，返回 document_id
        payload = self._build_file_payload(src_lang, tgt_lang)
        headers = {
            # "Content-Type": "multipart/form-data",
            "Authorization": f"DeepL-Auth-Key {self.__auth_key}",
        }
        file_name = "content" + next(iter(fmt.extensions), "")
        response = await self._client.post(
            self._deepl_file_url if self.paid else self._deepl_file_url_free,
            data=payload,
            files={"file": (file_name, content, "application/octet-stream")},
            headers=headers,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            error_msg = response.json().get("message", "")
            if response.status_code == 400 and (
                ("source_lang" in error_msg or "target_lang" in error_msg)
                and "not supported" in error_msg
            ):
                src_languages = None
                tgt_languages = None
                try:
                    (
                        src_languages,
                        tgt_languages,
                    ) = await self._fetch_supported_languages(fmt)
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
                f"DeepL API 文件上传失败: {response.status_code} {response.text}"
            ) from e

        return response.json()

    async def _poll(self, document_id: str, document_key: str):
        # 实现轮询逻辑，返回翻译结果
        while True:
            headers = {
                # "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"DeepL-Auth-Key {self.__auth_key}",
            }
            response = await self._client.post(
                f"{self._deepl_file_url if self.paid else self._deepl_file_url_free}/{document_id}",
                data={"document_key": document_key},
                headers=headers,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPError as e:
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "1"))
                    await asyncio.sleep(retry_after)
                    continue  # 回到循环重新查询
                if response.json().get("code", "") == "invalid_content_type":
                    raise DeepLAPIError(
                        "DeepL API 轮询失败: Content-Type 不正确"
                    ) from e
                raise DeepLAPIError(
                    f"DeepL API 轮询失败: {response.status_code} {response.text}"
                ) from e
            body = response.json()
            if body["document_id"] != document_id:
                raise DeepLAPIError(
                    f"DeepL API 轮询返回了错误的 document_id: {body['document_id']}，期望 {document_id}"
                )
            match body["status"]:
                case "done":
                    return
                case "error":
                    raise DeepLAPIError(
                        f"DeepL API 翻译失败: {body.get('error_message', '未知错误')}"
                    )
            await asyncio.sleep(1)

    async def _download(self, document_id: str, document_key: str) -> bytes:
        # 实现文件下载逻辑，返回翻译结果
        headers = {
            # "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"DeepL-Auth-Key {self.__auth_key}",
        }
        response = await self._client.post(
            f"{self._deepl_file_url if self.paid else self._deepl_file_url_free}/{document_id}/result",
            data={"document_key": document_key},
            headers=headers,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise DeepLAPIError(
                f"DeepL API 文件下载失败: {response.status_code} {response.text}"
            ) from e
        return response.content

    def _build_file_payload(self, src_lang: str, tgt_lang: str) -> dict:
        payload: dict[str, Any] = {"target_lang": tgt_lang}
        if src_lang != "AUTO":
            payload["source_lang"] = src_lang
        if self.formality:
            payload["formality"] = self.formality
        if self.glossary_id:
            payload["glossary_id"] = self.glossary_id
        return payload

    def _normalize_lang(self, src_lang: str, tgt_lang: str) -> tuple[str, str]:
        """将部分语言代码转为 DeepL API 代码。"""
        src_code = self._SRC_LANG_MAP.get(src_lang.upper())
        tgt_code = self._TGT_LANG_MAP.get(tgt_lang.upper())
        return (src_code or src_lang.upper(), tgt_code or tgt_lang.upper())

    async def _fetch_supported_languages(
        self, fmt: Format | None = None
    ) -> tuple[set[str], set[str]]:
        # Implementation for fetching supported languages
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"DeepL-Auth-Key {self.__auth_key}",
        }
        endpoint = ""
        if fmt:
            if self.paid:
                endpoint = self._deepl_file_languages_url
            else:
                endpoint = self._deepl_file_languages_url_free
        else:
            if self.paid:
                endpoint = self._deepl_text_languages_url
            else:
                endpoint = self._deepl_text_languages_url_free
        response = await self._client.get(
            endpoint,
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
            {item["lang"] for item in body if item["usable_as_source"]},
            {item["lang"] for item in body if item["usable_as_target"]},
        )
