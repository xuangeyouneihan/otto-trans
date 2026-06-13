import httpx

from otto_trans.engine.base import BaseTranslator, UnsupportedLanguageError
from otto_trans.utils.format import Format, UnsupportedFormatError


class EnginePluginError(Exception):
    """引擎插件相关的异常"""

    pass


class EnginePlugin(BaseTranslator):
    engine_name = "engine_plugin"  # CLI 中 -e 使用的引擎名，保证唯一且不与内置引擎冲突
    friendly_name = "示例引擎插件"  # 用户友好的显示名称

    options: dict[str, dict[str, type | str | bool | set[str]]] = {
        # 定义插件所需的选项（可选），例如：
        "api_key": {
            "type": str,
            "description": "API 密钥",
            "required": True,
            "scope": {"text", "file"},
        },
        # "type": 可以是 str、bool、int、float 等 Python 内置类型
        # "description": 选项的描述文本，会显示在 CLI 帮助信息中
        # "required": True/False，CLI 会检查必需选项是否已提供
        # "scope": {"text"} | {"file"} | {"text", "file"}，适用模式
    }

    formats: set[Format] = {
        # 定义翻译引擎原生支持的格式（可选）
        Format(
            name="text",
            description="纯文本格式",
            extensions={".txt", ".text"},
            mime_type="text/plain",
        ),
        Format(
            name="markdown",
            description="Markdown 格式",
            extensions={".md", ".mdown", ".markdown"},
            mime_type="text/markdown",
        ),
    }

    def __init__(self, api_key: str, config_name: str | None = None, **kwargs):
        if kwargs:
            raise ValueError(f"未知参数: {list(kwargs.keys())}")
        super().__init__(config_name=config_name)  # 必须接收 config_name 或 **kwargs
        self.__api_key = api_key
        self._client = httpx.AsyncClient(follow_redirects=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    # ── 可选：覆盖 supports_format 以支持动态格式 ─────────

    # def supports_format(self, fmt: Format | str) -> Format | None:
    #     """覆盖此方法可支持任意文本格式（如 OpenAI 风格）。"""
    #     result = super().supports_format(fmt)
    #     if result:
    #         return result
    #     # 示例：接受任意 text/* 格式
    #     if isinstance(fmt, Format) and fmt.mime_type.startswith("text/"):
    #         return fmt
    #     return None

    # ── 文本翻译 ─────────────────────────────────────────────

    def translate_texts(
        self, texts: list[str], src_lang: str, tgt_lang: str
    ) -> list[str]:
        if src_lang not in ("en", "zh") or tgt_lang not in ("en", "zh"):
            raise UnsupportedLanguageError.for_engine(
                self.name,
                src_lang,
                tgt_lang,
                {"en", "zh"},
                {"en", "zh"},
            )
        return [f'Translated "{t}" from {src_lang} to {tgt_lang}' for t in texts]

    # ── 文件翻译 ─────────────────────────────────────────────

    async def translate_file(
        self, content: bytes, src_lang: str, tgt_lang: str, fmt: Format
    ) -> tuple[bytes, Format]:
        if not self.supports_format(fmt):
            raise UnsupportedFormatError.for_engine(self.name, fmt, self.formats)

        await self._upload(content, src_lang, tgt_lang, fmt)
        await self._poll()
        return await self._download(content), fmt

    async def _upload(
        self, content: bytes, src_lang: str, tgt_lang: str, fmt: Format
    ) -> None:
        """将文件上传至翻译服务。通常需要构建请求体并 POST 到文件翻译端点。"""

    async def _poll(self) -> None:
        """轮询翻译状态直至完成。处理 queued / translating / done / error 等状态。"""

    async def _download(self, content: bytes) -> bytes:
        """下载翻译后的文件并以 bytes 返回。
        content 是原始文件内容，可用于校验等辅助判断。
        """
        return content  # TODO: 替换为实际下载逻辑
