import io
import os
import sys
from unittest.mock import Mock, patch

import httpx
import pytest

from otto_trans.cli import (
    _classify_paths,
    _format_results,
    _paragraphs,
    _parse_converter,
    _resolve_fmt_str,
    _resolve_source,
    _sep_char,
)
from otto_trans.utils.format import Format

# ── _sep_char ───────────────────────────────────────────────


def test_sep_char():
    result = _sep_char("-")
    # 返回 ─ 或 -，取决于 stdout 编码
    assert result in ("─", "-")


# ── _format_results ─────────────────────────────────────────


def test_format_results_single():
    result = _format_results(["hello"])
    assert "hello" in result


def test_format_results_multiple():
    with patch("shutil.get_terminal_size", return_value=os.terminal_size((80, 24))):
        result = _format_results(["first", "second"], sep_char="-")
    assert "first" in result
    assert "second" in result


# ── _paragraphs ─────────────────────────────────────────────


def test_paragraphs_single():
    assert _paragraphs(["hello", "world"]) == ["hello\nworld"]


def test_paragraphs_multiple():
    lines = ["hello", "===", "world"]
    assert _paragraphs(lines) == ["hello", "world"]


def test_paragraphs_empty():
    assert _paragraphs([]) == []


def test_paragraphs_all_separators():
    lines = ["===", "==="]
    assert _paragraphs(lines) == []


# ── _resolve_source ────────────────────────────────────────


def test_resolve_source_path(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    resolved = _resolve_source(str(f))
    assert resolved == f


def test_resolve_source_url(monkeypatch):
    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.headers = {"accept-ranges": "bytes"}
    monkeypatch.setattr(
        "otto_trans.cli.httpx.head",
        lambda *a, **kw: mock_resp,
    )
    resolved = _resolve_source("https://example.com/file.txt")
    assert resolved == "https://example.com/file.txt"


def test_resolve_source_invalid_url(monkeypatch):
    monkeypatch.setattr(
        "otto_trans.cli.httpx.head",
        Mock(side_effect=httpx.HTTPError("no")),
    )
    with pytest.raises(ValueError, match="无法访问"):
        _resolve_source("https://invalid.example.com")


# ── _resolve_fmt_str ────────────────────────────────────────


def test_resolve_fmt_str_name():
    fmt = Format(name="html", extensions={".html"}, mime_type="text/html")
    result = _resolve_fmt_str("html", {fmt})
    assert result == fmt


def test_resolve_fmt_str_extension():
    fmt = Format(name="html", extensions={".html", ".htm"}, mime_type="text/html")
    result = _resolve_fmt_str(".html", {fmt})
    assert result == fmt


def test_resolve_fmt_str_fallback():
    result = _resolve_fmt_str("custom", set())
    assert result.name == "custom"
    assert ".custom" in result.extensions


# ── _classify_paths ─────────────────────────────────────────


def test_classify_paths_smart(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    f = tmp_path / "test.txt"
    f.write_text("hello")
    result = _classify_paths([str(f)], exists_texts=False)
    assert len(result) == 1
    assert result[0][0] == f
    assert result[0][1] is sys.stdout


def test_classify_paths_pair(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    f_in = tmp_path / "in.txt"
    f_out = tmp_path / "out.txt"
    f_in.write_text("hello")
    result = _classify_paths([f"{f_in}::{f_out}"], exists_texts=False)
    assert len(result) == 1
    assert result[0][0] == f_in
    assert result[0][1] == f_out


def test_classify_paths_pipe_to_file(tmp_path):
    f_out = tmp_path / "out.txt"
    with patch.object(sys, "stdin", io.StringIO("hello")):
        result = _classify_paths([f"::{f_out}"], exists_texts=False)
        assert len(result) == 1
        assert result[0][0] is sys.stdin
        assert result[0][1] == f_out


# ── _parse_converter ────────────────────────────────────────


def test_parse_converter_pair():
    """a::b → 输入 a，输出 b"""
    assert _parse_converter("conv1::conv2", native=False) == ("conv1", "conv2")


def test_parse_converter_input_only():
    """a:: → 仅输入 a"""
    assert _parse_converter("conv1::", native=False) == ("conv1", "")


def test_parse_converter_output_only():
    """::b → 仅输出 b"""
    assert _parse_converter("::conv2", native=False) == ("", "conv2")


def test_parse_converter_no_colon_native():
    """无 :: + 引擎原生支持 → 作为输出转换器"""
    assert _parse_converter("conv1", native=True) == ("", "conv1")


def test_parse_converter_no_colon_not_native():
    """无 :: + 引擎不支持 → 作为输入转换器"""
    assert _parse_converter("conv1", native=False) == ("conv1", "")


def test_parse_converter_empty_both():
    """:: → 两边都空"""
    assert _parse_converter("::", native=False) == ("", "")
