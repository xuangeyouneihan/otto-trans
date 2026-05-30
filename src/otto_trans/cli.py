import asyncio
import sys

import typer

from .config.settings import Settings
from .core.cache import Cache
from .core.translator import Translator

# 帮助后附加文本里留一个占位，运行时填入配置路径
HELP_EPILOG = f"""
配置文件: {Settings.get_config_path()}

首次运行时自动生成默认配置。



支持的引擎：

  youdao              有道翻译（需 app_key + app_secret）

  openai              OpenAI 兼容提供商，优先取配置中第一个

  openai:<provider>   指定 OpenAI 兼容提供商（如 openai:deepseek）

  deepl               DeepL 翻译（需 api_key）



引擎选项（-o key=value），会覆盖配置文件中的对应字段：



  有道：

    app_key              应用 ID

    app_secret           应用密钥



  OpenAI / 兼容接口：

    endpoint             API 端点地址

    api_key              API 密钥

    model                模型名称

    prompt_template      自定义翻译提示词模板，支持 {{src_lang}} 和 {{tgt_lang}} 占位

    thinking             深度思考模式，true 或 false

    reasoning_effort     推理强度，none、minimal、low、medium、high、xhigh 或 max

    temperature          采样温度，0~2，越低越确定

    max_tokens           最大输出 token 数

    top_p                核采样概率，0~1

    top_k                top-k 采样，整数，越大越随机

    repetition_penalty   重复惩罚，0~2，越大越避免重复



  DeepL：

    auth_key             API 密钥

    paid                 是否使用付费端点，true 或 false，默认 false

    context              上下文信息，帮助模型理解翻译场景

    preserve_formatting  保留原文格式，true 或 false

    formality            正式程度，default、more、less、prefer_more 或 prefer_less

    model_type           模型类型，quality_optimized、latency_optimized 或 prefer_quality_optimized



逐行模式：

  不提供文本参数时，程序进入逐行输入模式。每行独立对待，

  输入空行结束。-b / --batch 模式下每行分别翻译，否则合并为一段。



管道模式：

  可通过管道或 heredoc 传入文本，每行独立对待。

  -b / --batch 模式下每行分别翻译，否则合并为一段。



示例：



  $ otto -e youdao -o app_key=xxx -o app_secret=yyy -t zh-Hans hello



  $ otto -e openai:deepseek -s en -t zh-Hans hello



  $ otto -t zh-Hans -b

    请输入要翻译的文本（输入空行结束）：

  > hello

  > world

  > [回车]



  $ otto -e openai:deepseek -t zh-Hans << EOF

  > hello

  > world

  > EOF



  $ otto --reset-config
"""

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "-?", "--help"]},
    epilog=HELP_EPILOG,
    add_completion=False,
)


def _read_lines(prompt: str) -> list[str]:
    """逐行读取，空行结束。返回行列表。"""
    typer.echo(prompt, err=True)
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return lines


def _parse_value(raw: str):
    """将 CLI 字符串转为 Python 类型，模拟 YAML 的类型推断"""
    low = raw.lower()
    # 布尔
    if low in (
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
        "enable",
        "disable",
        "enabled",
        "disabled",
    ):
        return low in ("true", "yes", "on", "enable", "enabled")
    # # null，启用会和 OpenAI API 的参数冲突，暂不启用
    # if low in ("null", "none", ""):
    #     return None
    # null
    if low in (""):
        return None
    # 整数
    try:
        return int(raw)
    except ValueError:
        pass
    # 浮点
    try:
        return float(raw)
    except ValueError:
        pass
    # 兜底：保留字符串
    return raw


@app.command(
    context_settings={"help_option_names": ["-h", "-?", "--help"]},
    epilog=HELP_EPILOG,
)
def main(
    texts: list[str] = typer.Argument([], help="要翻译的文本", show_default=False),
    src_lang: str = typer.Option(
        "auto",
        "-s",
        "--source",
        help='源语言，ISO 639 语言代码，支持 -Hans/-Hant/-Cyrl/-Latn 文字标记，如"zh-Hans"、"en"等',
        show_default=False,
    ),
    tgt_lang: str = typer.Option(
        "",
        "-t",
        "--target",
        help='目标语言，ISO 639 语言代码，支持 -Hans/-Hant/-Cyrl/-Latn 文字标记，如"zh-Hans"、"en"等',
        show_default=False,
    ),
    engine: str = typer.Option(
        "", "-e", "--engine", help="翻译引擎", show_default=False
    ),
    options: list[str] = typer.Option(
        [], "-o", "--option", help="引擎特定选项，格式为 key=value", show_default=False
    ),
    batch: bool = typer.Option(
        False, "-b", "--batch", help="批量翻译", show_default=False
    ),
    reset_config: bool = typer.Option(
        False, "--reset-config", help="重置配置文件", show_default=False
    ),
    reset_cache: bool = typer.Option(
        False, "--reset-cache", help="重置缓存", show_default=False
    ),
):
    """♿电棍翻译器 — 多引擎命令行翻译工具"""
    sys_stdout_encoding = sys.stdout.encoding  # 记录本地输出编码
    sys_stdin_encoding = sys.stdin.encoding  # 记录本地输入编码
    # 更改 std{in,out} 编码为 UTF-8，确保中文正常显示
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        sys.stdin.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

    if reset_config:
        Settings.reset()
        typer.echo(f"已重置位于 {Settings.get_config_path()} 的配置文件", err=True)
        raise typer.Exit()

    if reset_cache:
        Cache.reset()
        typer.echo(f"已重置位于 {Cache.get_db_path()} 的缓存", err=True)
        raise typer.Exit()

    if not texts:
        if not sys.stdin.isatty():
            # stdin 是管道 → 读全部
            texts = [line for line in sys.stdin.read().splitlines() if line]
        else:
            # stdin 是终端 → 交互式输入
            texts = _read_lines("请输入要翻译的文本（输入空行结束）：")

        if len(texts) <= 0:
            typer.echo("未输入任何文本，退出。", err=True)
            raise typer.Exit()
        if not batch:
            # 非批量模式下合并文本，减少 API 调用次数
            texts = ["\n".join(texts)]

    elif not batch:
        texts = [" ".join(texts)]  # 将命令行参数合并为一行

    async def run(src_lang=src_lang, tgt_lang=tgt_lang, engine=engine, options=options):
        if not Settings.get_config_path().exists():
            Settings.reset()
            typer.echo(f"配置文件已生成在 {Settings.get_config_path()}", err=True)
        settings = Settings.load()

        src_lang = src_lang if src_lang else settings.default_source

        tgt_lang = tgt_lang if tgt_lang else settings.default_target
        if not tgt_lang:
            typer.echo(
                "请指定目标语言（-t / --target）或在配置文件中设置默认目标语言。", err=True
            )
            raise typer.Exit(1)

        engine = engine.lower() if engine else settings.default_engine
        if not engine:
            typer.echo(
                "请指定翻译引擎（-e / --engine）或在配置文件中设置默认翻译引擎。", err=True
            )
            raise typer.Exit(1)

        base_opts = settings.engines.get(engine, {})
        cli_opts = {
            k: _parse_value(v) for k, v in (opt.split("=", 1) for opt in options)
        }

        if engine.startswith("openai"):
            provider = engine.split(":", 1)[1] if ":" in engine else None
            yaml_opts = settings.engines.get(engine.split(":")[0], {}) or {}
            if provider:
                base_opts = yaml_opts.get(provider, {})
            else:
                base_opts = next(iter(yaml_opts.values()), {})

        engine_opts = {**base_opts, **cli_opts}

        translator = Translator(engine, engine_opts)

        if batch:
            results = await translator.translate_batch(texts, src_lang, tgt_lang)
            for i, (t, r) in enumerate(zip(texts, results)):
                if i > 0:
                    typer.echo("\n\n" + "=" * 40 + "\n\n")  # 分隔多条结果
                typer.echo(f"原文：\n{t}\n\n翻译：\n{r}")
        else:
            result = await translator.translate(texts[0], src_lang, tgt_lang)
            typer.echo(result)

    asyncio.run(run())

    # 将输出编码改回去
    try:
        sys.stdout.reconfigure(encoding=sys_stdout_encoding)  # type: ignore[union-attr]
        sys.stdin.reconfigure(encoding=sys_stdin_encoding)  # type: ignore[union-attr]
    except Exception:
        pass


if __name__ == "__main__":
    app()
