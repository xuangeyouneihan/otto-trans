import re


def fix_html(html: str) -> str:
    """向 HTML 文档添加 <!DOCTYPE html> 声明，并确保 <head> 部分包含 <meta charset="UTF-8"> 标签。"""
    if not re.match(r"(?i)\s*<\s*!doctype\s+html\s*>", html):
        html = "<!DOCTYPE html>\n" + html
    head_match = re.search(
        r"(?i)(<head[^>]*>)(.*?)(</head>)",
        html,
        re.DOTALL,
    )
    if head_match:
        head_open = head_match.group(1)
        head_inner = head_match.group(2)
        head_close = head_match.group(3)
        if re.search(
            r'(?i)<meta\s+charset\s*=\s*("[^"]*?"|\'[^\']*?\'|[^"\']*?)\s*>',
            head_inner,
        ):
            new_inner = re.sub(
                r"(?i)(<meta\s+charset\s*=\s*)(.*?)(\s*>)",
                r'\1"UTF-8"\3',
                head_inner,
            )
            html = (
                html[: head_match.start()]
                + head_open
                + new_inner
                + head_close
                + html[head_match.end() :]
            )
        else:
            html = re.sub(
                r"(?i)(<head[^>]*>)",
                r'\1\n<meta charset="UTF-8">',
                html,
                count=1,
            )
    else:
        # 无 <head>：只处理 <body> 之前的 charset
        body_start = re.search(r"(?i)<body[^>]*>", html)
        head_zone = html[: body_start.start()] if body_start else html
        if re.search(
            r'(?i)<meta\s+charset\s*=\s*("[^"]*?"|\'[^\']*?\'|[^"\']*?)\s*>',
            head_zone,
        ):
            head_zone = re.sub(
                r"(?i)(<meta\s+charset\s*=\s*)(.*?)(\s*>)",
                r'\1"UTF-8"\3',
                head_zone,
            )
        else:
            if re.search(r"(?i)<html[^>]*>", head_zone):
                head_zone = re.sub(
                    r"(?i)(<html[^>]*>)",
                    r'\1\n<meta charset="UTF-8">',
                    head_zone,
                    count=1,
                    flags=re.DOTALL,
                )
            else:
                head_zone = re.sub(
                    r"(?i)(<\s*!doctype\s+html\s*>)",
                    r'\1\n<meta charset="UTF-8">',
                    head_zone,
                    count=1,
                    flags=re.DOTALL,
                )
        html = head_zone + (html[body_start.start() :] if body_start else "")
    return html
