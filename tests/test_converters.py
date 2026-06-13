from otto_trans.converter.markdown_to_html import MarkdownToHTML
from otto_trans.converter.html_to_markdown import HTMLToMarkdown


def test_markdown_to_html():
    md = b"# Hello\n\nThis is **bold**."
    html = MarkdownToHTML.convert(md)
    text = html.decode("utf-8-sig")
    assert "<h1>Hello</h1>" in text
    assert "<strong>bold</strong>" in text


def test_html_to_markdown():
    html = b"<h1>Hello</h1><p>This is <strong>bold</strong>.</p>"
    md = HTMLToMarkdown.convert(html)
    text = md.decode("utf-8-sig")
    assert "# Hello" in text
    assert "**bold**" in text


def test_markdown_to_html_empty():
    html = MarkdownToHTML.convert(b"")
    assert html.decode("utf-8-sig") == ""


def test_html_to_markdown_empty():
    md = HTMLToMarkdown.convert(b"<p></p>")
    assert isinstance(md, bytes)
