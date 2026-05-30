from pathlib import Path
from typing import Any, ClassVar

import yaml
from pydantic_settings import BaseSettings

DEFAULT_CONFIG_YAML = """\
default_engine: ""    # 默认翻译引擎
default_source: auto  # 默认源语言，ISO 639 语言代码，支持 -Hans/-Hant/-Cyrl/-Latn 文字标记，如"zh-Hans"、"en"。auto 表示自动检测
default_target: ""    # 默认目标语言，ISO 639 语言代码，支持 -Hans/-Hant/-Cyrl/-Latn 文字标记，"zh-Hans"、"en"

# 引擎配置
engines:
  # 有道翻译配置示例
  youdao:
    app_key:     # 应用 ID
    app_secret:  # 应用密钥

  # OpenAI 相关配置示例
  openai:
    # your-provider:
    #   endpoint:            # API 端点地址
    #   api_key:             # API 密钥
    #   model:               # 模型名称
    #   prompt_template:     # 自定义提示词模板，支持 {{src_lang}} 和 {{tgt_lang}} 占位
    #   thinking:            # 深度思考模式，true 或 false
    #   reasoning_effort:    # 推理强度，none、minimal、low、medium、high、xhigh 或 max
    #   temperature:         # 采样温度，0~2，越低越确定
    #   max_tokens:          # 最大输出 token 数
    #   top_p:               # 核采样概率，0~1
    #   top_k:               # top-k 采样，整数，越大越随机
    #   repetition_penalty:  # 重复惩罚，0~2，越大越避免重复

  # DeepL 配置示例
  deepl:
    auth_key:             # API 密钥
    paid:                 # 是否使用付费端点，true 或 false，默认 false
    context:              # 上下文信息，帮助模型理解翻译场景
    preserve_formatting:  # 保留原文格式，true 或 false
    formality:            # 正式程度，default、more、less、prefer_more 或 prefer_less
    model_type:           # 模型类型，quality_optimized、latency_optimized 或 prefer_quality_optimized
"""


class Settings(BaseSettings):
    model_config = {"extra": "allow"}  # 允许 YAML 有未声明的字段

    default_engine: str = ""
    default_source: str = "auto"
    default_target: str = ""
    engines: dict[str, Any] = {}

    _config_path: ClassVar[Path] = (
        Path.home() / ".config" / "otto-trans" / "config.yaml"
    )

    @classmethod
    def get_config_path(cls) -> Path:
        return Path(cls._config_path)

    @classmethod
    def load(cls) -> "Settings":
        config = yaml.safe_load(cls._config_path.read_text(encoding="utf-8")) or {}
        settings = cls(**config)
        settings.default_engine = settings.default_engine.lower().strip()
        settings.default_source = settings.default_source.lower().strip()
        settings.default_target = settings.default_target.lower().strip()
        return settings

    @classmethod
    def reset(cls):
        if cls._config_path.exists():
            cls._config_path.unlink()
        cls._config_path.parent.mkdir(parents=True, exist_ok=True)
        cls._config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
