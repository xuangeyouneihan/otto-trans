from pathlib import Path
import yaml
from pydantic_settings import BaseSettings
from typing import ClassVar, Any

DEFAULT_CONFIG_YAML = """\
default_engine: ""
default_from: auto
default_to: ""

engines:
  # openai:
  #   your-provider:
  #     endpoint:
  #     api_key:
  #     model:
  #     prompt_template:
  #     thinking:
  #     reasoning_effort:
  #     temperature:
  #     max_tokens:
  #     top_p:

  youdao:
    app_key: ""
    app_secret: ""
"""

class Settings(BaseSettings):
    model_config = {"extra": "allow"}   # 允许 YAML 有未声明的字段

    default_engine: str = ""
    default_from: str = "auto"
    default_to: str = ""
    engines: dict[str, Any] = {}

    config_path: ClassVar[Path] = Path.home() / ".config" / "otto-trans" / "config.yaml"

    @classmethod
    def load(cls) -> "Settings":
        if not cls.config_path.exists():
            cls.config_path.parent.mkdir(parents=True, exist_ok=True)
            cls.config_path.write_text(DEFAULT_CONFIG_YAML)
        config = yaml.safe_load(cls.config_path.read_text()) or {}
        return cls(**config)

    @classmethod
    def reset(cls):
        if cls.config_path.exists():
            cls.config_path.unlink()
        cls.config_path.write_text(DEFAULT_CONFIG_YAML)