# import asyncio  # 如果取消下方 translate_batch 的注释，请取消本行注释
from otto_trans.engine.base import BaseTranslator, UnsupportedLanguageError


class EnginePluginError(Exception):
    # 引擎插件相关的异常
    ...


class EnginePlugin(BaseTranslator):
    friendly_name = "示例引擎插件"  # 可选的用户友好名称

    options: dict[str, dict[str, str | bool]] = {
        # 定义插件所需的选项，例如：
        "api_key": {
            "type": "str",
            "description": "API 密钥",
            "required": True,
        },
        # 其中 "type" 可以是 "str"、"bool"、"int"、"float"、"list"、"tuple"、"set" 或 "dict"，CLI 会根据这个信息进行类型检查和转换
        # "description" 是选项的描述文本，会在 CLI 的帮助信息中显示
        # "required" 是一个布尔值，表示这个选项是否必需，如果用户没有提供必需的选项，CLI 会报错提示缺少哪个选项
    }

    def __init__(self, api_key: str, config_name: str | None = None, **kwargs):
        # 在这里初始化你的插件，例如创建 API 客户端等
        if kwargs:
            raise ValueError(f"未知参数: {list(kwargs.keys())}")
        super().__init__()
        self.api_key = api_key
        self.config_name = config_name  # CLI 自动传入冒号后的配置名（如 engine_plugin:fast 中的 fast），用于缓存隔离。必须接收此参数，否则会因传入多余参数而报错

    @property
    def name(self) -> str:
        # 返回插件的名称，用于缓存 key 和日志标识。
        # 建议和 pyproject.toml 中 entry_points 的左侧名称保持一致，保证唯一且不与内置引擎冲突。
        if self.config_name:
            return f"engine_plugin:{self.config_name}"
        return "engine_plugin"

    async def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        # 实现翻译逻辑，调用第三方 API 或使用其他方法进行翻译
        # 这里是一个示例实现，你需要根据实际情况进行修改
        if src_lang not in ["en", "zh"] or tgt_lang not in ["en", "zh"]:
            raise UnsupportedLanguageError.for_engine(
                self.name,
                src_lang,
                tgt_lang,
                ["en", "zh"],
                ["en", "zh"],
            )
        return f'Translated "{text}" from {src_lang} to {tgt_lang} using engine_plugin'

    # async def translate_batch(
    #     self, texts: list[str], src_lang: str, tgt_lang: str
    # ) -> list[str]:
    #     # 批量翻译（可选，默认逐条调用 translate，可覆盖为批量 API 请求优化性能）
    #     return await asyncio.gather(*[
    #         self.translate(t, src_lang, tgt_lang) for t in texts
    #     ])
