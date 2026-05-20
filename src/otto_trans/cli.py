import typer
import asyncio
import sys
from .config.settings import Settings
from .core.translator import Translator

app = typer.Typer(context_settings={"help_option_names": ["-h", "-?", "--help"]})

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
    if low in ("true", "false", "yes", "no", "on", "off"):
        return low in ("true", "yes", "on")
    # null
    if low in ("null", "none", ""):
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

@app.command()
def main(
    texts: list[str] = typer.Argument([], help="要翻译的文本", show_default=False),
    from_lang: str = typer.Option("auto", "-f", "--from", help="源语言", show_default=True),
    to_lang: str = typer.Option("", "-t", "--to", help="目标语言", show_default=False),
    engine: str = typer.Option("", "-e", "--engine", help="翻译引擎", show_default=False),
    options: list[str] = typer.Option([], "-o", "--option", help="引擎特定选项，格式为 key=value", show_default=False),
    reset_config: bool = typer.Option(False, "--reset-config", help="重置配置文件", show_default=True),
    batch: bool = typer.Option(False, "--batch", help="批量翻译", show_default=True)
    ):
    """otto-trans — 多引擎命令行翻译工具"""
    if reset_config:
        Settings.reset()
        typer.echo("配置文件已重置")
        raise typer.Exit()

    if not texts:
        if not sys.stdin.isatty():
            # stdin 是管道 → 读全部
            texts = [l for l in sys.stdin.read().splitlines() if l]
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

    async def run(from_lang=from_lang, to_lang=to_lang, engine=engine, options=options):
        settings = Settings.load()

        from_lang = from_lang if from_lang else settings.default_from

        to_lang = to_lang if to_lang else settings.default_to
        if not to_lang:
            typer.echo("请指定目标语言（--to）或在配置文件中设置默认目标语言。", err=True)
            raise typer.Exit(1)

        engine = engine if engine else settings.default_engine
        if not engine:
            typer.echo("请指定翻译引擎（--engine）或在配置文件中设置默认翻译引擎。", err=True)
            raise typer.Exit(1)

        base_opts = settings.engines.get(engine, {})
        cli_opts = {k: _parse_value(v) for k, v in (opt.split("=", 1) for opt in options)}

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
            results = await translator.translate_batch(texts, from_lang, to_lang)
            for t, r in zip(texts, results):
                typer.echo(f"{t} -> {r}")
        else:
            result = await translator.translate(texts[0], from_lang, to_lang)
            typer.echo(result)

    asyncio.run(run())

if __name__ == "__main__":
    app()