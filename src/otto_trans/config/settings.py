from pathlib import Path
from typing import Any, ClassVar

import yaml
from pydantic_settings import BaseSettings

from ..core.translator import Translator


class Settings(BaseSettings):
    model_config = {"extra": "allow"}  # 允许 YAML 有未声明的字段

    default_engine: str = ""
    default_source: str = "auto"
    default_target: str = ""
    engines: dict[str, Any] = {}

    config_path: ClassVar[Path] = Path.home() / ".config" / "otto-trans" / "config.yaml"

    @classmethod
    def load(cls) -> "Settings":
        config = yaml.safe_load(cls.config_path.read_text(encoding="utf-8")) or {}
        settings = cls(**config)
        settings.default_engine = settings.default_engine.lower().strip()
        if not settings.default_source:
            settings.default_source = "auto"
        settings.default_source = settings.default_source.lower().strip()
        settings.default_target = settings.default_target.lower().strip()
        return settings

    @classmethod
    def reset(cls):
        if cls.config_path.exists():
            cls.config_path.unlink()
        cls.config_path.parent.mkdir(parents=True, exist_ok=True)

        existing_engines = Translator.engines()

        lines = [
            "default_engine: # 默认翻译引擎",
            "default_source: # 默认源语言，ISO 639 语言代码，支持 -Hans/-Hant/-Cyrl/-Latn 文字标记，如\"zh-Hans\"、\"en\"。auto 表示自动检测",
            "default_target: # 默认目标语言，ISO 639 语言代码，支持 -Hans/-Hant/-Cyrl/-Latn 文字标记，\"zh-Hans\"、\"en\"",
            "",
            "# 引擎配置",
            "engines:",
        ]

        for name in sorted(existing_engines):
            engine_cls = existing_engines[name]
            if not engine_cls.options:
                continue  # 没有选项的引擎不需要添加到示例配置中
            friendly = engine_cls.friendly_name
            if friendly:
                lines.append(f"  {name}: # {friendly}")
            else:
                lines.append(f"  {name}:")
            lines.append("    default:")
            for opt_name, opt_meta in engine_cls.options.items():
                if opt_meta["description"]:
                    if opt_meta["required"]:
                        lines.append(
                            f"      {opt_name}: # {opt_meta['description']}（必需）"
                        )
                    else:
                        lines.append(f"      {opt_name}: # {opt_meta['description']}")
                else:
                    if opt_meta["required"]:
                        lines.append(f"      {opt_name}: # （必需）")
                    else:
                        lines.append(f"      {opt_name}:")

        cls.config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
