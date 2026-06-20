"""翻译引擎插件模板。

快速开始
--------
1. 将本文件、__init__.py、pyproject.toml 中的 `engine_plugin` 替换为你的插件名
2. 修改 `engine_name`（CLI 中 `-e` 使用的名称）和 `friendly_name`（帮助信息中显示）
3. 实现 `translate_texts`（文本翻译）和可选的 `translate_file`（文件翻译）
4. 在 `pyproject.toml` 中确认 `[project.entry-points."otto_trans.engine"]` 指向你的类
5. `pip install -e .` 后运行 `otto --help` 验证是否出现在引擎列表中

可选声明
--------
- `engine_name: str`：CLI 中 `-e` 使用的引擎名，最好和你的插件包名一致，保证唯一且不与内置引擎冲突
- `friendly_name: str`：帮助信息中显示的名称
- `formats: set[Format]`：引擎原生支持的格式。默认 `supports_format` 基于此集合匹配，声明后引擎可直接处理这些格式而无需转换器/适配器
- `options: dict`：引擎所需的配置选项，需要名称、类型、描述、是否必需、适用模式等信息，CLI 会据此生成帮助信息并校验用户输入

集中格式
--------
- `otto_trans.utils.format` 提供了预定义的格式常量（如 `PLAIN_TEXT`、`HTML`、`JSON`、`SRT` 等），可直接导入使用
- 如果你的引擎支持的是常见格式，优先引用这些常量而非内联定义 Format 对象
- 运行 `python -c "from otto_trans.utils.format import all_formats; print(all_formats().keys())"` 可查看当前所有已注册格式

必需实现
--------
- `translate_texts(texts, src_lang, tgt_lang) -> list[str]`：同步方法，输入输出列表一一对应

可选实现
--------
- `name` 属性：默认返回 `engine_name:config_name`，如果未声明 `engine_name` 就返回 `类名:config_name`，可覆盖以自定义
- `translate_file(content, src_lang, tgt_lang, fmt) -> tuple[bytes, Format]`：异步方法，处理文件翻译
- `supports_format(fmt) -> Format | None`：格式支持时返回对应的 Format 对象，覆盖以支持动态格式匹配。默认实现基于 `formats` 集合匹配（含扩展名子集判定），覆盖后通常先调 `super().supports_format(fmt)` 再追加自定义逻辑
- 如果需要特殊处理文本格式翻译，建议使用 `utf-8-sig` 编码，可以考虑使用 `otto_trans.utils.text.utf_8` 函数（基于 MIME 类型来判断是否为文本格式，同时特殊处理 HTML）进行处理。解码可以考虑使用 `otto_trans.utils.text.detect_encoding`（基于 chardet）辅助自动检测编码

框架行为
--------
- `options` 由 `Translator` 门面在初始化时校验类型、补齐默认值、必要时转换布尔值
- `options` 中的 `scope` 控制该选项在何种模式下有效，`otto --help` 会据此标注
- `config_name` 参数由框架自动传入（当用户用 `-e engine:config` 时），你的 `__init__` 必须接收并传给 `super().__init__`
- 文本翻译默认走 `translate_texts`，文件翻译走 `translate_file`
- 语言代码归一化由各引擎自行处理，框架不做干预

错误处理
--------
- `UnsupportedFormatError.for_engine(name, fmt, formats)`：引擎不支持该格式时抛出，第二个参数是用户传入的格式（str 或 Format），第三个是本引擎支持的格式集合（可选）
- `UnsupportedLanguageError.for_engine(name, src, tgt, src_set, tgt_set)`：语言不支持时抛出，后两个集合分别是支持的源语言和目标语言（传 `None` 表示不限）
- 通用引擎异常：自定义异常类（如 `EnginePluginError`）

Format 类
---------
- `Format` 是 dataclass，字段：`name: str`、`description: str`、`extensions: set[str]`、`mime_type: str`。
- 扩展名子集判定：两个 Format 的 extensions 互为子集即视为相等（如 `text({".txt"}) == text({".txt", ".text"})`）。
- 引擎支持的格式可直接从 `otto_trans.utils.format` 导入预定义常量，无需内联定义。
"""

import httpx

from otto_trans.engine.base import BaseTranslator, UnsupportedLanguageError
from otto_trans.utils.format import MARKDOWN, PLAIN_TEXT, Format, UnsupportedFormatError


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
        # 定义翻译引擎原生支持的格式（可选），可直接从 otto_trans.utils.format 导入常用格式
        PLAIN_TEXT,
        MARKDOWN,
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
