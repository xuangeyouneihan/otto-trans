import asyncio
import os
import re
import shutil
import sys
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Callable, TextIO
from urllib.parse import urlparse

import httpx
import typer

from .config.settings import Settings
from .core.cache import Cache
from .core.translator import Translator
from .utils.format import Format
from .utils.text import detect_encoding

# ── 分隔符工具 ──────────────────────────────────────────────


def _sep_char(alt: str = "-") -> str:
    """返回分隔线字符，stdout 支持 Unicode 时用 '─'，否则用 alt。"""
    try:
        enc = sys.stdout.encoding or ""
    except Exception:
        enc = ""
    return "─" if "utf" in enc.lower() else alt


def _format_results(results: list[str], *, sep_char: str | None = None) -> str:
    """用终端宽度的分隔线连接多段翻译结果，自动管理空行间距。"""
    cols, _ = shutil.get_terminal_size()
    if sep_char is None:
        sep_char = _sep_char("=")
    sep = sep_char * cols
    parts: list[str] = []
    for i, r in enumerate(results):
        if i > 0:
            # 输出分隔线，并根据前后文本自动调整空行数量
            prev_end = "\n" if parts[-1].endswith("\n") else "\n\n"
            next_start = "\n" if r.startswith("\n") else "\n\n"
            parts.append(f"{prev_end}{sep}{next_start}")
        parts.append(r)
    return "".join(parts)


# ── 帮助信息 ────────────────────────────────────────────────


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
        f"缓存文件: {Cache.db_path}",
    ]

    lines += [""] * 3 + [_sep_char() * (cols - 2)] + [""] * 3

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
                lines.append(
                    f"  {name.ljust(max_name)}  {friendly}（需 {'、'.join(req)}）"
                )
            else:
                lines.append(f"  {name.ljust(max_name)}  {friendly}")
        else:
            if req:
                lines.append(f"  {name.ljust(max_name)}  （需 {'、'.join(req)}）")
            else:
                lines.append(f"  {name}")
        lines.append("")

    lines += [""] * 3 + [_sep_char() * (cols - 2)] + [""] * 3

    # 引擎选项
    lines.append("引擎选项（-o key=value），会覆盖配置文件中的对应字段：")
    for name in sorted(engines):
        lines += [""] * 5
        cls = engines[name]
        if not cls.options:
            continue  # 没有选项的引擎不需要展示选项信息
        friendly = cls.friendly_name
        max_opt = max((len(k) for k in cls.options), default=0)
        if friendly:
            lines.append(f"  {friendly}（{name}）：")
        else:
            lines.append(f"  {name}：")
        lines += [""] * 2
        for opt_name, opt_meta in cls.options.items():
            lines.append("")
            desc = opt_meta.get("description", "")
            is_req = opt_meta.get("required", False)
            scope = opt_meta.get("scope", {"text", "file"})

            parens: list[str] = []
            if is_req:
                parens.append("必需")
            if scope == {"text"}:
                parens.append("仅文本模式")
            elif scope == {"file"}:
                parens.append("仅文件模式")
            suffix = f"（{'，'.join(parens)}）" if parens else ""

            if desc:
                lines.append(f"    {opt_name.ljust(max_opt)}  {desc}{suffix}")
            elif suffix:
                lines.append(f"    {opt_name.ljust(max_opt)}  {suffix}")
            else:
                lines.append(f"    {opt_name}")

    lines += [""] * 3 + [_sep_char() * (cols - 2)] + [""] * 3

    # 格式支持
    lines.append("格式支持（-f / --format）：")
    for name in sorted(engines):
        cls = engines[name]
        fmts = cls.formats
        if not fmts:
            continue
        lines += [""] * 5
        friendly = cls.friendly_name
        if friendly:
            lines.append(f"  {friendly}（{name}）：")
        else:
            lines.append(f"  {name}：")
        for f in sorted(fmts, key=lambda x: x.name):
            lines += [""] * 3
            lines.append(f"    名称：{f.name}")
            lines.append("")
            if f.description:
                lines.append(f"    描述：{f.description}")
                lines.append("")
            exts = "、".join(f.extensions) if f.extensions else "无"
            lines.append(f"    扩展名：{exts}")

    lines += [""] * 3 + [_sep_char() * (cols - 2)] + [""] * 3

    # 转换器
    converters = Translator.converters()
    if converters:
        lines.append("转换器（-c / --converter），格式为 [输入::]输出：")
        for cname, ccls in converters.items():
            lines += [""] * 3
            lines.append(f"  {cname}:")
            lines.append("")
            lines.append(
                f"    输入格式：{ccls.source.name}（{'、'.join(sorted(ccls.source.extensions))}）"
            )
            lines.append("")
            lines.append(
                f"    输出格式：{ccls.target.name}（{'、'.join(sorted(ccls.target.extensions))}）"
            )

        lines += [""] * 3 + [_sep_char() * (cols - 2)] + [""] * 3

    # 适配器
    adapters = Translator.adapters()
    if adapters:
        lines.append("适配器（-a / --adapter）：")
        for aname, acls in adapters.items():
            lines += [""] * 3
            lines.append(f"  {aname}:")
            lines.append("")
            lines.append(
                f"    格式：{acls.source.name}（{'、'.join(sorted(acls.source.extensions))}）"
            )

    lines += [""] * 3 + [_sep_char() * (cols - 2)] + [""] * 3

    # 静态尾部
    static1 = [
        "逐行模式：",
        "",
        "",
        "",
        "  不提供文本参数时，程序进入逐行输入模式。",
        "",
        "  多段文本用 '===' 行分隔，空行 Ctrl-Z + 回车（Windows）/ Ctrl-D（Linux / macOS）退出。",
        "",
        "",
        "",
        "",
        "",
        "管道模式：",
        "",
        "",
        "",
        "  可通过管道或 heredoc 传入文本。",
        "",
        "  管道有内容时，将管道内容作为输入进行翻译。",
        "",
        "",
        "",
        "",
        "",
        "文件模式：",
        "",
        "",
        "",
        "  -p 指定输入输出路径，格式为 input::output。",
        "",
        "  支持同时翻译多对文件，支持智能路径、仅输入、仅输出。",
        "",
        "",
        "",
        _sep_char() * (cols - 2),
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
    ]

    # 交互提示根据操作系统动态调整，Windows 上结束提示 Ctrl-Z + 回车，Unix 上提示 Ctrl-D
    interactive_prompt = (
        "请输入要翻译的文本（多段用只包含 '===' 的行分隔，输入 EOF 结束）："
    )
    match os.name:
        case "nt":
            interactive_prompt = "请输入要翻译的文本（多段用只包含 '===' 的行分隔，在空行按下 Ctrl-Z + 回车结束）："
        case "posix":
            interactive_prompt = "请输入要翻译的文本（多段用只包含 '===' 的行分隔，在空行按下 Ctrl-D 结束）："

    interactive_eof = "EOF（Windows：Ctrl-Z + 回车；Linux / macOS：Ctrl-D）"
    match os.name:
        case "nt":
            interactive_eof = "[Ctrl-Z][回车]"
        case "posix":
            interactive_eof = "[Ctrl-D]"

    interactive_texts = [
        "  交互输入：",
        "",
        "  $ otto -t zh-Hans",
        "",
        "  " + interactive_prompt,
        "",
        "  hello",
        "",
        "  ===",
        "",
        "  world",
        "",
        "  " + interactive_eof,
    ]

    static2 = [
        "",
        "",
        "",
        "  管道输入：",
        "",
        "  $ echo hello | otto -t zh-Hans",
        "",
        "",
        "",
        "  文件翻译：",
        "",
        "  $ otto -t zh-Hans -p en.txt::zh.txt",
        "",
        "",
        "",
        "  $ otto --reset-config",
    ]

    lines += static1 + interactive_texts + static2
    return "\n".join(lines)


app = typer.Typer(
    context_settings={"help_option_names": ["-h", "-?", "--help"]},
    epilog=_build_help_epilog(),
    add_completion=False,
)


def _paragraphs(lines: list[str]) -> list[str]:
    """将多行文本按 === 分隔符行拆分为段落列表。"""
    groups = [""]
    for line in lines:
        line_stripped = line.rstrip("\n\r")
        if re.fullmatch(r"\s*(=\s*){3,}", line_stripped):
            # 分隔符行，只能包含空白和至少三个等号，等号之间可以有空白
            # 遇到分隔符行时开始新段落
            groups.append("")
            continue
        if groups[-1]:
            # 当前段落已有内容，把新行追加到当前段落
            groups[-1] += "\n" + line_stripped
        else:
            # 当前段落没有内容，直接设置为新行（避免开头多余的换行）
            groups[-1] = line_stripped
    return [g for g in groups if g]


def _read_lines(prompt: str) -> list[str]:
    """逐行读取，EOF 退出，返回段落列表。"""
    typer.echo(prompt, err=True)
    lines = []
    while True:
        try:
            lines.append(input())
        except EOFError:
            break
    return _paragraphs(lines)  # 按分隔符拆分段落


# ── 翻译流程 ────────────────────────────────────────────────


def _process_texts(
    texts: list[str],
    paths: list[tuple[Path | str | TextIO, Path | TextIO]],
    src_lang: str,
    tgt_lang: str,
    translator: Translator,
):
    if not paths:
        # 无文件路径
        if not texts:
            # 交互模式，提示用户输入文本，支持多段输入和分隔符
            if sys.stdin.isatty():
                prompt = (
                    "请输入要翻译的文本（多段用只包含 '===' 的行分隔，输入 EOF 结束）："
                )
                match os.name:
                    case "nt":
                        prompt = "请输入要翻译的文本（多段用只包含 '===' 的行分隔，在空行按下 Ctrl-Z + 回车结束）："
                    case "posix":
                        prompt = "请输入要翻译的文本（多段用只包含 '===' 的行分隔，在空行按下 Ctrl-D 结束）："
                texts = _read_lines(prompt)
            else:
                # 实际上应该不会走到这里，因为 _classify_paths 已经保证了非交互式 stdin 时 paths 不会空
                texts = _paragraphs([
                    line for line in sys.stdin.read().splitlines() if line
                ])

            if len(texts) <= 0 or all(not t.strip() for t in texts):
                typer.echo("未输入任何文本，退出。", err=True)
                raise typer.Exit(1)
        else:
            # 命令行参数提供了文本，直接使用，按分隔符拆分段落
            texts = _paragraphs([line for line in " ".join(texts).splitlines() if line])

        # 翻译
        results = translator.translate_texts(texts, src_lang, tgt_lang)
        if len(results) > 1:
            # 多段翻译结果用分隔线连接输出，自动管理空行间距
            typer.echo(_format_results(results))
        else:
            # 单段直接输出
            typer.echo(results[0])

    else:
        # 文件路径模式，读取所有文件内容，按路径顺序翻译后写回
        contents: list[str] = []
        for i, _ in paths:
            if isinstance(i, Path):
                # 本地路径，自动检测编码读取文本内容
                raw = i.read_bytes()
                content = raw.decode(detect_encoding(raw))
            elif isinstance(i, str):
                # URL，发起 GET 请求读取文本内容，自动检测编码
                resp = httpx.get(i, follow_redirects=True, timeout=60.0)
                resp.raise_for_status()
                content = resp.content.decode(detect_encoding(resp.content))
            else:
                # Stdin，直接读取文本内容
                content = i.read()
            # 统一换行符为 \n，翻译后再写回时根据目标平台调整为对应的行结束符
            content = content.replace("\r\n", "\n").replace("\r", "\n")
            contents.append(content)

        if len(paths) == 1:
            # 单 path：按 === 拆段落翻译，统一格式化输出
            paragraphs = _paragraphs(contents[0].splitlines())
            results = translator.translate_texts(paragraphs, src_lang, tgt_lang)
            output = paths[0][1]
            if isinstance(output, Path):
                text = _format_results(results, sep_char="=")
                text = text.replace("\n", os.linesep)
                output.write_text(text, encoding="utf-8")
            else:
                typer.echo(_format_results(results))
        else:
            # 多 path：一对一翻译，逐文件写回
            results = translator.translate_texts(contents, src_lang, tgt_lang)
            for idx, (_, output) in enumerate(paths):
                # 多段翻译结果用分隔线连接输出，自动管理空行间距
                if isinstance(output, Path):
                    # 本地文件，写回时统一换行符为对应平台的行结束符
                    results[idx] = results[idx].replace("\n", os.linesep)
                    output.write_text(results[idx], encoding="utf-8")
                else:
                    # Stdout
                    output.write(results[idx])
                    output.flush()


async def _read_file_content(
    source: Path | str | TextIO,
) -> bytes:
    """从 Path / URL / TextIO 读取文件内容。"""
    if isinstance(source, Path):
        # Path
        return source.read_bytes()
    if isinstance(source, str):
        # URL
        resp = httpx.get(source, follow_redirects=True, timeout=120.0)
        resp.raise_for_status()
        return resp.content
    # Stdin
    return source.buffer.read()


def _write_file_content(
    target: Path | TextIO,
    content: bytes,
    out_fmt: Format | str,
    in_fmt: Format | str,
    on_warning: Callable[[str], None] = lambda msg: typer.echo(msg, err=True),
) -> None:
    """写入文件，格式不一致时自动修正扩展名。"""
    if isinstance(target, Path):
        # Path，输出格式与输入格式不一致时自动修正扩展名
        output = target
        if out_fmt != in_fmt:
            ext = ""
            if isinstance(out_fmt, Format):
                ext = next(iter(out_fmt.extensions), "")
            elif out_fmt.startswith("."):
                ext = out_fmt
            else:
                ext = "." + out_fmt
            output = target.with_suffix(ext)

        out_fmt_str = (
            f"{out_fmt.name}（{', '.join(sorted(out_fmt.extensions))}）"
            if isinstance(out_fmt, Format)
            else out_fmt
        )
        in_fmt_str = (
            f"{in_fmt.name}（{', '.join(sorted(in_fmt.extensions))}）"
            if isinstance(in_fmt, Format)
            else in_fmt
        )
        on_warning(
            f"输出格式为 {out_fmt_str}，与输入格式 {in_fmt_str} 不一致，已自动调整输出路径为 {output}"
        )
        output.write_bytes(content)
    else:
        # Stdout
        target.buffer.write(content)
        target.flush()


def _process_files(
    paths: list[tuple[Path | str | TextIO, Path | TextIO]],
    src_lang: str,
    tgt_lang: str,
    translator: Translator,
    fmt: str,
    converter: str | None = None,
    adapter: str | None = None,
    jobs: int = 0,
):
    sem = asyncio.Semaphore(jobs) if jobs > 0 else None

    async def run():
        total = len(paths)
        done = 0

        async def process_one(p):
            nonlocal done
            if sem:
                async with sem:
                    result = await _do_process(p)
            else:
                result = await _do_process(p)
            done += 1
            footer = f"\r已完成 {done} / {total} 项翻译"
            translator.on_warning.footer = footer
            typer.echo(footer, nl=False, err=True)
            if done == total:
                typer.echo("\r\033[K", nl=False, err=True)
                typer.echo("所有翻译已完成！", err=True)
            return result

        async def _do_process(p):
            content = await _read_file_content(p[0])
            result, out_fmt = await translator.translate_file(
                content,
                src_lang,
                tgt_lang,
                fmt,
                converter,
                adapter,
            )
            _write_file_content(p[1], result, out_fmt, fmt, translator.on_warning)
            return out_fmt

        typer.echo(f"开始翻译 {total} 项...", nl=False, err=True)
        return await asyncio.gather(*[process_one(p) for p in paths])

    asyncio.run(run())


# ── 路径工具 ────────────────────────────────────────────────


def _resolve_source(source: str) -> Path | str:
    """将用户输入的路径字符串解析为 Path（本地）或 str（远程 URL）。

    支持：
    - 本地路径（含 file:// URI）
    - http:// / https:// URL（HEAD 预检可达性）
    """
    s = source.strip()
    if not s:
        raise ValueError("路径不能为空")
    if s.startswith(("http://", "https://")):
        try:
            resp = httpx.head(s, follow_redirects=True, timeout=10.0)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise ValueError(f"无法访问 URL: {s} ({e})") from e
        accept_ranges = resp.headers.get("accept-ranges", "").lower()
        if "bytes" not in accept_ranges:
            # 警告但不阻止（部分服务器不支持 Range 请求但仍可 GET）
            typer.echo(
                f"警告：{s} 不支持分块下载，可能导致性能问题或下载失败", err=True
            )
        return s
    if s.startswith("file://"):
        parsed = urlparse(s)
        path = parsed.path
        if os.name == "nt" and path.startswith("/"):
            path = path[1:]  # /C:/... → C:/...
        return Path(path)
    if "://" in s:
        raise ValueError(f"不支持的 URI 协议: {s}")
    return Path(s)


def _ensure_readable(source: Path | str) -> None:
    try:
        if isinstance(source, str):
            return  # URL 已在 _resolve_source 中验证
        if not source.exists():
            raise FileNotFoundError(f"文件不存在：{source}")
        if not source.is_file():
            raise IsADirectoryError(f"不是文件：{source}")
        if not os.access(source, os.R_OK):
            raise PermissionError(f"无读取权限：{source}")
    except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
        typer.echo(f"无法读取：{e}", err=True)
        raise typer.Exit(1)


def _ensure_writable(path: Path) -> None:
    try:
        new_parents = [p for p in path.parents if not p.exists()]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        path.unlink()
        for parent in new_parents:
            shutil.rmtree(parent, ignore_errors=True)
    except (OSError, PermissionError) as e:
        typer.echo(f"无法写入 {path}：{e}", err=True)
        raise typer.Exit(1)


def _classify_paths(
    paths: list[str], exists_texts: bool
) -> list[tuple[Path | str | TextIO, Path | TextIO]]:
    """解析路径参数，返回 (输入, 输出) 对。

    输入可以是 Path（本地）、str（远程 URL）或 TextIO（stdin）。
    """
    both: list[tuple[Path | str | TextIO, Path | TextIO]] = []
    smart: Path | str | None = None
    in_only: Path | str | None = None
    out_only: Path | None = None

    for p in paths:
        p = p.strip()
        if not p:
            continue
        if "::" not in p:
            if smart is not None:
                typer.echo(f"路径参数格式错误：{p}，多个智能路径", err=True)
                raise typer.Exit(1)
            smart = _resolve_source(p)
        elif p.strip() == "::":
            continue
        elif p.strip().startswith("::"):
            if out_only is not None:
                typer.echo(f"路径参数格式错误：{p}，多个仅输出路径", err=True)
                raise typer.Exit(1)
            out_only = Path(p[2:].strip())
            _ensure_writable(out_only)
        elif p.strip().endswith("::"):
            if in_only is not None:
                typer.echo(f"路径参数格式错误：{p}，多个仅输入路径", err=True)
                raise typer.Exit(1)
            in_only = _resolve_source(p[:-2])
            _ensure_readable(in_only)
        else:
            left, right = p.split("::", 1)
            left_src = _resolve_source(left)
            right_path = Path(right.strip())
            _ensure_readable(left_src)
            _ensure_writable(right_path)
            both.append((left_src, right_path))

    # 互斥检查
    specials = sum(x is not None for x in (smart, in_only, out_only))
    if specials > 1:
        typer.echo(
            "路径参数格式错误：智能路径、仅输入路径和仅输出路径不能混用", err=True
        )
        raise typer.Exit(1)
    if out_only:
        if sys.stdin.isatty():
            typer.echo("路径参数格式错误：仅输出路径必须与管道输入同时使用", err=True)
            raise typer.Exit(1)
        if exists_texts:
            typer.echo(
                "同时提供了文本参数和路径参数，请选择一种方式进行翻译。", err=True
            )
            raise typer.Exit(1)
        both.append((sys.stdin, out_only))
    if in_only:
        if not sys.stdin.isatty():
            if exists_texts:
                typer.echo(
                    "同时提供了文本参数和路径参数，请选择一种方式进行翻译。", err=True
                )
                raise typer.Exit(1)
            typer.echo("路径参数格式错误：仅输入路径不能与管道输入同时使用", err=True)
            raise typer.Exit(1)
        both.append((in_only, sys.stdout))
    if smart:
        if sys.stdin.isatty():
            _ensure_readable(smart)
            both.append((smart, sys.stdout))
        else:
            if isinstance(smart, str):
                typer.echo("URL 不能作为输出目标", err=True)
                raise typer.Exit(1)
            if exists_texts:
                typer.echo(
                    "同时提供了文本参数和路径参数，请选择一种方式进行翻译。", err=True
                )
                raise typer.Exit(1)
            both.append((sys.stdin, smart))

    if not sys.stdin.isatty() and not (smart or in_only or out_only or exists_texts):
        both.append((sys.stdin, sys.stdout))

    return both


# ── CLI ─────────────────────────────────────────────────────


class _StickyFooter:
    """确保进度条始终在警告下方的 on_warning。"""

    def __init__(self, footer: str = ""):
        self.footer = footer

    @staticmethod
    def warn(message: str) -> None:
        typer.echo(message, err=True)

    def __call__(self, msg: str) -> None:
        # 擦除当前进度行 → 打印警告 → 重印进度
        if self.footer:
            typer.echo("\r\033[K", nl=False, err=True)
        self.warn(msg)
        if self.footer:
            typer.echo(self.footer, nl=False, err=True)


def _reset_config(value: bool):
    if value:
        Settings.reset()
        typer.echo(f"已重置位于 {Settings.config_path} 的配置文件", err=True)
        raise typer.Exit()


def _reset_cache(value: bool):
    if value:
        Cache.reset()
        typer.echo(f"已重置位于 {Cache.db_path} 的缓存", err=True)
        raise typer.Exit()


def _version_callback(value: bool):
    if value:
        typer.echo(f"♿电棍翻译器 {_pkg_version('otto-trans')}")
        raise typer.Exit()


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
        "",
        "-e",
        "--engine",
        help="翻译引擎，支持 engine:config 语法指定配置方案",
        show_default=False,
    ),
    options: list[str] = typer.Option(
        [], "-o", "--option", help="引擎特定选项，格式为 key=value", show_default=False
    ),
    fmt: str = typer.Option(
        "", "-f", "--format", help="输入文件的格式", show_default=False
    ),
    converter: str = typer.Option(
        "",
        "-c",
        "--converter",
        help="输入文件的格式转换器，格式为 in_conv::out_conv",
        show_default=False,
    ),
    adapter: str = typer.Option(
        "", "-a", "--adapter", help="输入文件的格式适配器", show_default=False
    ),
    paths: list[str] = typer.Option(
        [],
        "-p",
        "--path",
        help="输入输出文件路径，格式为 input::output，支持批量翻译",
        show_default=False,
    ),
    jobs: int = typer.Option(
        0,
        "-j",
        "--jobs",
        help="文件翻译并发数，0 为无限制（仅文件模式生效）",
        show_default=False,
    ),
    reset_config: bool = typer.Option(
        False,
        "--reset-config",
        help="重置配置文件",
        callback=_reset_config,
        is_eager=True,
        show_default=False,
    ),
    reset_cache: bool = typer.Option(
        False,
        "--reset-cache",
        help="重置缓存",
        callback=_reset_cache,
        is_eager=True,
        show_default=False,
    ),
    version: bool = typer.Option(
        False,
        "-v",
        "--version",
        help="显示版本号",
        callback=_version_callback,
        is_eager=True,
        show_default=False,
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

    if fmt and texts:
        # 或许可以考虑允许一些文本格式（如 Markdown）直接翻译，但目前为了避免歧义和复杂性，暂不支持。
        typer.echo("文件模式不支持文本参数，请使用路径参数指定输入文件。", err=True)
        raise typer.Exit(1)

    if not fmt and (converter or adapter):
        typer.echo(
            "格式转换器和适配器需要指定输入文件格式（-f / --format）。", err=True
        )
        raise typer.Exit(1)

    if converter and adapter:
        typer.echo("格式转换器和适配器不能同时使用，请选择一种方式。", err=True)
        raise typer.Exit(1)

    if jobs < 0:
        typer.echo("并发数（-j / --jobs）不能为负数。", err=True)
        raise typer.Exit(1)

    if texts and paths:
        typer.echo("同时提供了文本参数和路径参数，请选择一种方式进行翻译。", err=True)
        raise typer.Exit(1)

    if jobs > 0 and not fmt:
        typer.echo("并发参数（-j / --jobs）仅在文件模式下生效。", err=True)

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
    sticky_footer = _StickyFooter()
    translator = Translator(engine, engine_opts, on_warning=sticky_footer)
    cli_paths = _classify_paths(paths, exists_texts=bool(texts))

    if fmt:
        if not cli_paths:
            typer.echo(
                "文件模式需要指定路径参数（-p / --path）或通过管道输入", err=True
            )
            raise typer.Exit(1)
        _process_files(
            cli_paths,
            src_lang,
            tgt_lang,
            translator,
            fmt,
            converter if converter else None,
            adapter if adapter else None,
            jobs,
        )
    else:
        _process_texts(texts, cli_paths, src_lang, tgt_lang, translator)

    # 将输出编码改回去
    try:
        sys.stdout.reconfigure(encoding=sys_stdout_encoding)  # type: ignore[union-attr]
        sys.stdin.reconfigure(encoding=sys_stdin_encoding)  # type: ignore[union-attr]
    except Exception:
        pass


if __name__ == "__main__":
    app()
