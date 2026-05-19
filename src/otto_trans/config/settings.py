from pathlib import Path
import yaml
from pydantic_settings import BaseSettings
from typing import ClassVar

DEFAULT_CONFIG_YAML = """\
default_engine: ""
default_from: auto
default_to: ""
engines:
  youdao:
    app_key: ""
    app_secret: ""
"""

class Settings(BaseSettings):
    model_config = {"extra": "allow"}   # 允许 YAML 有未声明的字段

    default_engine: str = ""
    default_from: str = "auto"
    default_to: str = ""
    engines: dict[str, dict[str, str]] = {}

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