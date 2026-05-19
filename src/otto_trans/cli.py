import typer
import asyncio
from .config.settings import Settings
from .core.translator import Translator

app = typer.Typer(context_settings={"help_option_names": ["-h", "-?", "--help"]})

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
        typer.echo("请提供要翻译的文本。", err=True)
        raise typer.Exit(1)
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
        engine_opts = dict(opt.split("=", 1) for opt in options) if options else settings.engines.get(engine, {})
        translator = Translator(engine, engine_opts)
        if batch:
            results = await translator.translate_batch(texts, from_lang, to_lang)
            for t, r in zip(texts, results):
                typer.echo(f"{t} -> {r}")
        else:
            combined = " ".join(texts)
            result = await translator.translate(combined, from_lang, to_lang)
            typer.echo(result)
    asyncio.run(run())

if __name__ == "__main__":
    app()
