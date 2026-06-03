import asyncio
import shutil
import sys

import typer

from .config.settings import Settings
from .core.cache import Cache
from .core.translator import Translator


def _build_help_epilog() -> str:
    """动态生成帮助信息尾部，包含所有已注册引擎及其选项。"""
    engines = Translator.engines()

    cols, _ = shutil.get_terminal_size()

    lines = [
        f"配置文件: {Settings.config_path}",
        "",
        "首次运行时自动生成默认配置。",
        "",
        "",
        "",
        f"缓存文件: {Cache.db_path}"
    ]

    lines += [""] * 3 + ["─" * (cols - 2)] + [""] * 3

    # 支持的引擎
    max_name = max((len(n) for n in engines), default=0)
    lines.append("支持的引擎：")
    lines += [""] * 3
    for name in sorted(engines):
        cls = engines[name]
        req = [k for k, v in cls.options.items() if v["required"]]
        friendly = cls.friendly_name
        if friendly:
            if req:
                lines.append(f"  {name.ljust(max_name)}  {friendly}（需 {'、'.join(req)}）")
            else:
                lines.append(f"  {name.ljust(max_name)}  {friendly}")
        else:
            if req:
                lines.append(f"  {name.ljust(max_name)}  （需 {'、'.join(req)}）")
            else:
                lines.append(f"  {name.ljust(max_name)}")
        lines.append("")

    lines += [""] * 3 + ["─" * (cols - 2)] + [""] * 3

    # 引擎选项
    lines.append("引擎选项（-o key=value），会覆盖配置文件中的对应字段：")
    for name in sorted(engines):
        lines += [""] * 5
        cls = engines[name]
        friendly = cls.friendly_name
        max_opt = max((len(k) for k in cls.options), default=0)
        if friendly:
            lines.append(f"  {friendly}（{name}）：")
        else:
            lines.append(f"  {name}：")
        lines += [""] * 3
        for opt_name, opt_meta in cls.options.items():
            lines.append(f"    {opt_name.ljust(max_opt)}  {opt_meta['description']}")
            lines.append("")

    lines += [""] * 3 + ["─" * (cols - 2)] + [""] * 3

    # 静态尾部
    static = [
        "逐行模式：",
        "",
        "",
        "",
        "  不提供文本参数时，程序进入逐行输入模式。每行独立对待，",
        "",
        "  输入空行结束。-b / --batch 模式下每行分别翻译，否则合并为一段。",
        "",
        "",
        "",
        "",
        "",
        "管道模式：",
        "",
        "",
        "",
        "  可通过管道或 heredoc 传入文本，每行独立对待。",
        "",
        "  -b / --batch 模式下每行分别翻译，否则合并为一段。",
        "",
        "",
        "",
        "─" * (cols - 2),
        "",
        "",
        "",
        "示例：",
        "",
        "",
        "",
        "",
        "",
        "  $ otto -e youdao -o app_key=xxx -o app_secret=yyy -t zh-Hans hello",
        "",
        "",
        "",
        "  $ otto -e openai:deepseek -s en -t zh-Hans hello",
        "",
        "",
        "",
        "  $ otto -t zh-Hans -b",
        "",
        "  请输入要翻译的文本（输入空行结束）：",
        "",
        "  hello",
        "",
        "  world",
        "",
        "  [回车]",
        "",
        "",
        "",
        "  $ otto -e openai:deepseek -t zh-Hans << EOF",
        "",
        "  > hello",
        "",
        "  > world",
        "",
        "  > EOF",
        "",
        "",
        "",
        "  $ otto --reset-config",
    ]
    lines.extend(static)
    return "\n".join(lines)


app = typer.Typer(
    context_settings={"help_option_names": ["-h", "-?", "--help"]},
    epilog=_build_help_epilog(),
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


@app.command(
    context_settings={"help_option_names": ["-h", "-?", "--help"]},
    epilog=_build_help_epilog(),
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
        typer.echo(f"已重置位于 {Settings.config_path} 的配置文件", err=True)
        raise typer.Exit()

    if reset_cache:
        Cache.reset()
        typer.echo(f"已重置位于 {Cache.db_path} 的缓存", err=True)
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
        if not Settings.config_path.exists():
            Settings.reset()
            typer.echo(f"配置文件已生成在 {Settings.config_path}", err=True)
        settings = Settings.load()

        src_lang = src_lang if src_lang else settings.default_source

        tgt_lang = tgt_lang if tgt_lang else settings.default_target
        if not tgt_lang:
            typer.echo(
                "请指定目标语言（-t / --target）或在配置文件中设置默认目标语言。",
                err=True,
            )
            raise typer.Exit(1)

        engine = engine.lower() if engine else settings.default_engine
        if not engine:
            typer.echo(
                "请指定翻译引擎（-e / --engine）或在配置文件中设置默认翻译引擎。",
                err=True,
            )
            raise typer.Exit(1)

        cli_opts = {k: v for k, v in (opt.split("=", 1) for opt in options)}

        base_opts = settings.engines.get(engine.split(":")[0], {})
        config = engine.split(":", 1)[1] if ":" in engine else None
        if config:
            # 用户指定配置时取对应配置
            base_opts = base_opts.get(config, {}) if isinstance(base_opts, dict) else {}
            base_opts["config_name"] = config
        elif isinstance(base_opts, dict):
            # 用户未指定配置时若有嵌套配置，取第一个非空配置
            configs = {k: v for k, v in base_opts.items() if isinstance(v, dict) and v}
            if configs:
                config = next(iter(configs.keys()))
                base_opts = base_opts[config]
                base_opts["config_name"] = config

        engine_opts = {**base_opts, **cli_opts}

        translator = Translator(engine, engine_opts)

        if batch:
            results = await translator.translate_batch(texts, src_lang, tgt_lang)
            cols, _ = shutil.get_terminal_size()
            for i, (t, r) in enumerate(zip(texts, results)):
                if i > 0:
                    typer.echo("\n\n" + "─" * cols + "\n\n")  # 分隔多条结果
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
