import asyncio
import mimetypes
import re
from typing import Any

import httpx

from ..utils.format import (
    JSON,
    LATEX,
    PLAIN_TEXT,
    SRT,
    TYPST,
    XML,
    YAML,
    Format,
    UnsupportedFormatError,
)
from ..utils.html import fix_html
from ..utils.text import detect_encoding
from .base import BaseTranslator, UnsupportedLanguageError


class OpenAIAPIError(Exception):
    """OpenAI API 调用异常"""

    pass


# 纯文本但 MIME 不是 text/* 的格式，OpenAI 都可以翻译
_TEXT_FORMATS: frozenset[Format] = frozenset({JSON, XML, YAML, LATEX, TYPST, SRT})


def _is_html(content: bytes, fmt: Format) -> bool:
    """根据格式名、扩展名或内容判断是否为 HTML。"""
    if (
        fmt.name in ("html", "htm")
        or ".html" in fmt.extensions
        or ".htm" in fmt.extensions
    ):
        return True
    # 检查内容前 500 字节是否含 HTML 标记
    head = content[:500].decode("utf-8", errors="replace").lower()
    return bool(re.search(r"<!doctype\s+html|<html|<head|<body", head))


class OpenAITranslator(BaseTranslator):
    _DEFAULT_PROMPT_TEMPLATE = (
        "你是一个专业的翻译助手。将以下文本从 {src_lang} 翻译成 {tgt_lang}。"
        "对于单个词汇，直接给出最常用的翻译，不要列举多种释义。"
        "只返回翻译后的文本，不要有解释、备注或引号。"
        "严格遵守以下规则："
        "1. 如果文本中包含 HTML/XML/Markdown 标记、代码、占位符、URL、"
        "   邮件地址、数字格式等非自然语言内容，请原样保留不翻译，"
        "   仅翻译标记之间或周围的自然语言文本。"
        "2. 如果是纯文本（无标记），正常翻译全部内容。"
        "3. 保留原文的空白、缩进和换行格式。"
    )

    # 标准语言代码 → 提示词用的中文名称
    _LANG_DISPLAY: dict[str, str] = {
        "zh-Hans": "简体中文",
        "zh-Hant": "繁体中文",
        "zh": "中文",
        "zh-CN": "简体中文",
        "zh-TW": "繁体中文（台湾）",
        "zh-HK": "繁体中文（香港）",
        "en": "英文",
        "ja": "日文",
        "ko": "韩文",
        "fr": "法文",
        "es": "西班牙文",
        "pt": "葡萄牙文",
        "pt-BR": "巴西葡萄牙文",
        "pt-PT": "欧洲葡萄牙文",
        "it": "意大利文",
        "ru": "俄文",
        "vi": "越南文",
        "de": "德文",
        "ar": "阿拉伯文",
        "id": "印尼文",
        "th": "泰文",
        "yue": "粤语",
        "af": "南非荷兰语",
        "bs": "波斯尼亚语",
        "bg": "保加利亚语",
        "ca": "加泰隆语",
        "hr": "克罗地亚语",
        "cs": "捷克语",
        "da": "丹麦语",
        "nl": "荷兰语",
        "et": "爱沙尼亚语",
        "fi": "芬兰语",
        "el": "希腊语",
        "he": "希伯来语",
        "hi": "印地语",
        "hu": "匈牙利语",
        "lv": "拉脱维亚语",
        "lt": "立陶宛语",
        "ms": "马来语",
        "no": "挪威语",
        "fa": "波斯语",
        "pl": "波兰语",
        "ro": "罗马尼亚语",
        "sk": "斯洛伐克语",
        "sl": "斯洛文尼亚语",
        "sv": "瑞典语",
        "tr": "土耳其语",
        "uk": "乌克兰语",
        "ur": "乌尔都语",
        "sq": "阿尔巴尼亚语",
        "am": "阿姆哈拉语",
        "hy": "亚美尼亚语",
        "az": "阿塞拜疆语",
        "bn": "孟加拉语",
        "eu": "巴斯克语",
        "be": "白俄罗斯语",
        "eo": "世界语",
        "tl": "菲律宾语",
        "gl": "加利西亚语",
        "ka": "格鲁吉亚语",
        "gu": "古吉拉特语",
        "ha": "豪萨语",
        "is": "冰岛语",
        "ig": "伊博语",
        "ga": "爱尔兰语",
        "kn": "卡纳达语",
        "kk": "哈萨克语",
        "km": "高棉语",
        "ku": "库尔德语",
        "ky": "柯尔克孜语",
        "lo": "老挝语",
        "la": "拉丁语",
        "lb": "卢森堡语",
        "mk": "马其顿语",
        "mg": "马尔加什语",
        "ml": "马拉雅拉姆语",
        "mi": "毛利语",
        "mr": "马拉地语",
        "mn": "蒙古语",
        "my": "缅甸语",
        "ne": "尼泊尔语",
        "ny": "齐切瓦语",
        "ps": "普什图语",
        "pa": "旁遮普语",
        "sm": "萨摩亚语",
        "gd": "苏格兰盖尔语",
        "st": "塞索托语",
        "sn": "修纳语",
        "sd": "信德语",
        "si": "僧伽罗语",
        "so": "索马里语",
        "su": "巽他语",
        "tg": "塔吉克语",
        "ta": "泰米尔语",
        "te": "泰卢固语",
        "uz": "乌兹别克语",
        "xh": "南非科萨语",
        "yi": "意第绪语",
        "yo": "约鲁巴语",
        "zu": "南非祖鲁语",
        "mww": "白苗语",
        "ceb": "宿务语",
        "haw": "夏威夷语",
        "otq": "克雷塔罗奥托米语",
        "yua": "尤卡坦玛雅语",
        "sr-Cyrl": "塞尔维亚语（西里尔文）",
        "sr-Latn": "塞尔维亚语（拉丁文）",
        "sw": "斯瓦希里语",
        "tlh": "克林贡语",
        "fj": "斐济语",
        "ht": "海地克里奥尔语",
        "ty": "塔希提语",
        "to": "汤加语",
        "cy": "威尔士语",
        "co": "科西嘉语",
        "fy": "弗里西语",
        "jw": "爪哇语",
        "mt": "马耳他语",
        "auto": "自动识别",
    }

    engine_name = "openai"
    friendly_name = "OpenAI 翻译"

    options: dict[str, dict[str, type | str | bool | set[str]]] = {
        "endpoint": {
            "type": str,
            "description": "API 端点地址",
            "required": True,
            "scope": {"text", "file"},
        },
        "api_key": {
            "type": str,
            "description": "API 密钥",
            "required": True,
            "scope": {"text", "file"},
        },
        "model": {
            "type": str,
            "description": "模型名称",
            "required": True,
            "scope": {"text", "file"},
        },
        "prompt_template": {
            "type": str,
            "description": "自定义提示词 模板，支持 {src_lang} 和 {tgt_lang} 占位",
            "required": False,
            "scope": {"text", "file"},
        },
        "thinking": {
            "type": bool,
            "description": "深度思考模式，true 或 false",
            "required": False,
            "scope": {"text", "file"},
        },
        "reasoning_effort": {
            "type": str,
            "description": "推理强度，none、minimal、low、medium、high、xhigh 或 max",
            "required": False,
            "scope": {"text", "file"},
        },
        "temperature": {
            "type": float,
            "description": "采样温度，0~2，越低越确定",
            "required": False,
            "scope": {"text", "file"},
        },
        "max_tokens": {
            "type": int,
            "description": "最大输出 token 数，必须大于或等于 1",
            "required": False,
            "scope": {"text", "file"},
        },
        "top_p": {
            "type": float,
            "description": "核采样概率，0~1，越低越确定",
            "required": False,
            "scope": {"text", "file"},
        },
        "top_k": {
            "type": int,
            "description": "top-k 采样，整数，越大越随机",
            "required": False,
            "scope": {"text", "file"},
        },
        "repetition_penalty": {
            "type": float,
            "description": "重复惩罚，0~2，越大越避免重复",
            "required": False,
            "scope": {"text", "file"},
        },
    }

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        prompt_template: str | None = None,
        thinking: bool | None = None,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        repetition_penalty: float | None = None,
        config_name: str | None = None,
        **kwargs,
    ):
        if kwargs:
            raise ValueError(f"未知参数: {list(kwargs.keys())}")
        super().__init__(config_name=config_name)
        self.endpoint = endpoint
        self.__api_key = api_key
        self.model = model
        self.prompt_template = (
            prompt_template if prompt_template else self._DEFAULT_PROMPT_TEMPLATE
        )
        self.thinking = thinking
        if reasoning_effort is not None and reasoning_effort not in [
            "none",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        ]:
            raise ValueError(
                "reasoning_effort 必须是以下值之一: none、minimal、low、medium、high、xhigh、max"
            )
        self.reasoning_effort = reasoning_effort
        if temperature is not None and not (0 <= temperature <= 2):
            raise ValueError("temperature 必须在 0 到 2 之间")
        self.temperature = temperature
        if max_tokens is not None and max_tokens < 1:
            raise ValueError("max_tokens 必须大于或等于 1")
        self.max_tokens = max_tokens
        if top_p is not None and not (0 <= top_p <= 1):
            raise ValueError("top_p 必须在 0 到 1 之间")
        self.top_p = top_p
        if top_k is not None and top_k < 1:
            raise ValueError("top_k 必须大于或等于 1")
        self.top_k = top_k
        if repetition_penalty is not None and not (0 <= repetition_penalty <= 2):
            raise ValueError("repetition_penalty 必须在 0 到 2 之间")
        self.repetition_penalty = repetition_penalty
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0, read=600.0),
            transport=httpx.AsyncHTTPTransport(retries=2),  # ← 重试
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()  # 用完记得关

    @property
    def name(self) -> str:
        return f"{self.engine_name}:{self.model}"

    def supports_format(self, fmt: Format | str) -> Format | None:
        # 先走默认匹配
        result = super().supports_format(fmt)
        if result:
            return result
        if fmt == PLAIN_TEXT:
            return PLAIN_TEXT
        # Format 对象：白名单或 mime_type 以 text/ 开头
        if isinstance(fmt, Format):
            if fmt.mime_type.startswith("text/") or any(
                fmt == tf for tf in _TEXT_FORMATS
            ):
                return fmt
            return None
        # 字符串：白名单名称 → 直接返回对应 Format
        if isinstance(fmt, str):
            for tf in _TEXT_FORMATS:
                if tf == fmt:  # Format.__eq__ 支持 str
                    return tf
            if fmt == PLAIN_TEXT:
                return PLAIN_TEXT
            if "/" in fmt:
                # MIME 类型格式：text/html → name="html", extensions={".html"}
                if fmt.startswith("text/"):
                    name = fmt.split("/", 1)[1]
                    ext = ".txt" if name == "plain" else f".{name}"
                    return Format(name=name, extensions={ext}, mime_type=fmt)
                return None
            ext = fmt if fmt.startswith(".") else f".{fmt}"
            mime, _ = mimetypes.guess_type(f"file{ext}")
            if mime and mime.startswith("text/"):
                return Format(name=fmt, extensions={ext}, mime_type=mime)
        return None

    def translate_texts(
        self, texts: list[str], src_lang: str, tgt_lang: str
    ) -> list[str]:
        if tgt_lang.lower() == "auto":
            raise UnsupportedLanguageError(
                f"{self.friendly_name}（{self.name}）", src_lang, tgt_lang
            )

        async def run():
            return await asyncio.gather(*[
                self._translate_text(t, src_lang, tgt_lang) for t in texts
            ])

        return asyncio.run(run())

    async def translate_file(
        self, content: bytes, src_lang: str, tgt_lang: str, fmt: Format
    ) -> tuple[bytes, Format]:
        if not self.supports_format(fmt):
            raise UnsupportedFormatError(self.name, fmt)

        text = content.decode(detect_encoding(content), errors="replace")
        result = await self._translate_text(text, src_lang, tgt_lang)

        # HTML 特殊处理：补全 DOCTYPE/charset
        if _is_html(content, fmt):
            result = fix_html(result)
        return result.encode("utf-8-sig"), fmt

    async def _translate_text(
        self,
        content: str | bytes,
        src_lang: str,
        tgt_lang: str,
    ) -> str:
        payload = self._build_payload(content, src_lang, tgt_lang)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.__api_key}",
        }
        response = await self._client.post(self.endpoint, json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise OpenAIAPIError(
                f"OpenAI API 返回错误: {response.status_code} {response.text}"
            ) from e
        body = response.json()
        return body["choices"][0]["message"]["content"].strip()

    def _build_payload(
        self, content: str | bytes, src_lang: str, tgt_lang: str
    ) -> dict:
        text = content.decode() if isinstance(content, bytes) else content
        src_display = self._lang_display(src_lang)
        tgt_display = self._lang_display(tgt_lang)
        prompt = self.prompt_template.format(src_lang=src_display, tgt_lang=tgt_display)
        payload: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "model": self.model,
        }
        if self.thinking is not None:
            payload["thinking"] = {"type": "enabled" if self.thinking else "disabled"}
        if self.reasoning_effort is not None:
            payload["reasoning_effort"] = self.reasoning_effort
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if self.top_k is not None:
            payload["top_k"] = self.top_k
        if self.repetition_penalty is not None:
            payload["repetition_penalty"] = self.repetition_penalty
        return payload

    def _lang_display(self, code: str) -> str:
        """将语言代码转为提示词用的中文名称，未知代码原样返回。"""
        return self._LANG_DISPLAY.get(code, code)
