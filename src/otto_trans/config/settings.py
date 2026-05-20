from pathlib import Path
import yaml
from pydantic_settings import BaseSettings
from typing import ClassVar, Any

DEFAULT_CONFIG_YAML = f"""\
default_engine: ""  # 默认翻译引擎
default_from: auto  # 默认源语言，ISO 639 语言代码，支持 -Hans/-Hant/-Cyrl/-Latn 文字标记，如"zh-Hans"、"en"。auto 表示自动检测
default_to: ""  # 默认目标语言，ISO 639 语言代码，支持 -Hans/-Hant/-Cyrl/-Latn 文字标记，"zh-Hans"、"en"

# 引擎配置
engines:
  # # OpenAI 相关配置示例
  # openai:
  #   your-provider:
  #     endpoint:          # API 端点
  #     api_key:           # API 密钥
  #     model:             # 模型名称
  #     prompt_template:   # 自定义提示词模板，支持 {{from_lang}} 和 {{to_lang}} 占位
  #     thinking:          # 深度思考模式，true 或 false
  #     reasoning_effort:  # 推理强度，none、minimal、low、medium、high、xhigh 或 max
  #     temperature:       # 采样温度，0~2，越低越确定
  #     max_tokens:        # 最大输出 token 数
  #     top_p:             # 核采样概率，0~1

  # 有道翻译配置示例
  youdao:
    app_key: ""     # 应用 ID
    app_secret: ""  # 应用密钥
"""

class Settings(BaseSettings):
    model_config = {"extra": "allow"}   # 允许 YAML 有未声明的字段

    default_engine: str = ""
    default_from: str = "auto"
    default_to: str = ""
    engines: dict[str, Any] = {}

    _config_path: ClassVar[Path] = Path.home() / ".config" / "otto-trans" / "config.yaml"

    @classmethod
    def get_config_path(cls) -> Path:
        return cls._config_path

    @classmethod
    def load(cls) -> "Settings":
        config = yaml.safe_load(cls._config_path.read_text()) or {}
        return cls(**config)

    @classmethod
    def reset(cls):
        if cls._config_path.exists():
            cls._config_path.unlink()
        cls._config_path.parent.mkdir(parents=True, exist_ok=True)
        cls._config_path.write_text(DEFAULT_CONFIG_YAML)