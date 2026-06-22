from pathlib import Path
from typing import Any, ClassVar

import yaml
from pydantic_settings import BaseSettings

from ..core.translator import Translator
from ..utils.text import detect_encoding


class Settings(BaseSettings):
    _instance = None
    _initialized = False

    model_config = {"extra": "allow"}  # 允许 YAML 有未声明的字段

    default_engine: str = ""
    default_source: str = "auto"
    default_target: str = ""
    engines: dict[str, Any] = {}

    config_path: ClassVar[Path] = Path.home() / ".config" / "otto-trans" / "config.yaml"

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        config = (
            yaml.safe_load(
                self.config_path.read_text(
                    encoding=detect_encoding(self.config_path.read_bytes())
                )
            )
            or {}
        )
        config = {k: v for k, v in config.items() if v is not None}
        if isinstance(config.get("default_engine"), dict):
            bad = config["default_engine"]
            bad_str = ", ".join(f"{k}: {v}" for k, v in bad.items())
            good_str = ", ".join(f"{k}:{v}" for k, v in bad.items())
            raise ValueError(
                f"default_engine 配置格式错误：冒号后不能有空格，"
                f"请使用 {good_str} 而非 {bad_str}"
            )
        super().__init__(**config)
        self.default_engine = self.default_engine.strip()
        self.default_source = self.default_source.lower().strip()
        self.default_target = self.default_target.lower().strip()

        self._initialized = True

    @classmethod
    def reset(cls) -> None:
        if cls._instance is not None:
            # 清空单例实例的属性，以便重新加载配置
            cls._instance.__dict__.clear()
            cls._initialized = False

        if cls.config_path.exists():
            cls.config_path.unlink()
        cls.config_path.parent.mkdir(parents=True, exist_ok=True)

        existing_engines = Translator.engines()

        lines = [
            "default_engine: # 默认翻译引擎",
            'default_source: # 默认源语言，自带的 3 个翻译引擎支持 ISO 639 语言代码，如 "zh-Hans"、"en" 等。auto 表示自动检测',
            'default_target: # 默认目标语言，自带的 3 个翻译引擎支持 ISO 639 语言代码，如 "zh-Hans"、"en" 等',
            "",
            "# 引擎配置",
            "engines:",
        ]

        for name in sorted(existing_engines):
            engine_cls = existing_engines[name]
            if not engine_cls.options:
                continue  # 没有选项的引擎不需要添加到示例配置中
            lines.append("")
            friendly = engine_cls.friendly_name
            if friendly:
                lines.append(f"  {name}: # {friendly}")
            else:
                lines.append(f"  {name}:")
            lines.append("")
            lines.append("    default:")
            for opt_name, opt_meta in engine_cls.options.items():
                desc = opt_meta.get("description", "")
                req = opt_meta.get("required", False)
                scope = opt_meta.get("scope", {"text", "file"})

                # 构建括号内的提醒文本
                parens: list[str] = []
                if req:
                    parens.append("必需")
                if scope == {"text"}:
                    parens.append("仅文本模式")
                elif scope == {"file"}:
                    parens.append("仅文件模式")

                suffix = f"（{'，'.join(parens)}）" if parens else ""

                if desc:
                    lines.append(f"      {opt_name}: # {desc}{suffix}")
                elif suffix:
                    lines.append(f"      {opt_name}: # {suffix}")
                else:
                    lines.append(f"      {opt_name}:")

        cls.config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        if cls._instance is not None:
            cls._instance.__init__()  # 重新加载配置
