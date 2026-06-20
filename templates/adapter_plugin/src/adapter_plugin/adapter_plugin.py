"""格式适配器插件模板。

适配器 vs 转换器
----------------
- 适配器：从文件中提取纯文本片段翻译，再原位组装回去（如 SRT 字幕）
- 转换器：将整个文件转成另一种格式，翻译后再转回（如 Markdown ↔ HTML）

适配器的优势：
- 实现简单，只需提取文本 → 翻译 → 组装，不依赖引擎对特定格式的支持
- 适合结构固定、上下文独立的格式（字幕、键值对、日志行等）

适配器的局限：
- 每段文本独立翻译，无法利用段落间的上下文关联
- 难以处理内联标记（HTML 中的 `<b>`、Markdown 中的 `**粗体**` 等），翻译后或者标签可能错位或者可能因为缺失上下文被误翻译
- 因此 `translate_file` 的路由优先级为：转换器自动发现 → 适配器自动发现，适配器作为最后的兜底方案，除非用户明确指定 `-a` 使用适配器

集中格式
--------
- `otto_trans.utils.format` 提供了预定义的格式常量（如 `PLAIN_TEXT`、`HTML`、`JSON`、`SRT` 等），可直接导入使用
- 如果你的适配器处理的是常见格式，优先引用这些常量而非内联定义 Format 对象
- 运行 `python -c "from otto_trans.utils.format import all_formats; print(all_formats().keys())"` 可查看当前所有已注册格式

快速开始
--------
1. 将本文件、__init__.py、pyproject.toml 中的 `adapter_plugin` 替换为你的插件名
2. 修改 `source` 的 Format 定义
3. 实现 `extract` 和 `reassemble` 两个静态方法
4. 在 `pyproject.toml` 中确认 `[project.entry-points."otto_trans.adapter"]` 指向你的类
5. `pip install -e .` 后运行 `otto --help` 验证是否出现在适配器列表中

必需声明
--------
- `source: Format`：该适配器能处理的格式

必需实现
--------
- `@staticmethod extract(content: bytes) -> list[Segment]`：提取待翻译文本
- `@staticmethod reassemble(content: bytes, translated: list[Segment]) -> bytes`：组装翻译结果
- 文本格式建议使用 `utf-8-sig` 编码。解码可以考虑使用 `otto_trans.utils.text.detect_encoding`（基于 chardet）辅助自动检测编码

Segment 树
----------
- `Segment(text, context, children=[])` 支持嵌套结构
- 框架会递归展平树、翻译所有文本、再将结果写回原位（同一对象引用）

Segment 结构
------------
`Segment` 是 dataclass，字段：

- `text: str` — 待翻译文本，翻译后会被框架原地更新
- `context: str` — 适配器自用的上下文（如位置标记、原始行号等），框架不读取
- `children: list[Segment]` — 嵌套子片段（可选），框架会递归展平翻译后保持树结构

`extract` 返回的树传给 `reassemble` 时，`text` 已被原地更新为翻译结果。

Format 类
---------
- `Format` 是 dataclass，字段：`name: str`、`description: str`、`extensions: set[str]`、`mime_type: str`。
- 扩展名子集判定：两个 Format 的 extensions 互为子集即视为相等（如 `text({".txt"}) == text({".txt", ".text"})`）。
- 如果适配器处理的是常见格式，可直接从 `otto_trans.utils.format` 导入对应的格式常量，无需内联定义。

错误处理
--------
- `UnsupportedFormatError.for_engine(name, fmt, formats)`：格式不支持时抛出，第二个参数是用户传入的格式（str 或 Format），第三个是支持的格式集合（可选）

命名规则
--------
- 类名任意，entry_points 中注册的名字会成为 CLI 中 `-a` 的参数值
- 建议用格式名命名，如 `srt`、`ass`、`vtt`
"""

from otto_trans.adapter.base import BaseAdapter, Segment
from otto_trans.utils.format import Format


class AdapterPlugin(BaseAdapter):
    """示例格式适配器。

    extract 提取待翻译文本，reassemble 将翻译结果组装回原文件。
    """

    source = Format(
        name="example-format",
        description="示例格式的描述",
        extensions={".example"},
        mime_type="text/example-format",
    )

    @staticmethod
    def extract(content: bytes) -> list[Segment]:
        """提取待翻译的文本片段。

        content 是原始文件的字节流，返回 Segment 列表。
        """
        text = content.decode("utf-8")
        # TODO: 实现实际的提取逻辑
        segments: list[Segment] = []
        for line in text.splitlines():
            if line.strip():
                segments.append(Segment(text=line))
        return segments

    @staticmethod
    def reassemble(content: bytes, translated: list[Segment]) -> bytes:
        """将翻译后的片段组装回原文件。

        content 是原始内容（用作模板），translated 是已翻译的 Segment 列表。
        """
        # TODO: 实现实际的组装逻辑
        lines = [s.text for s in translated]
        return "\n".join(lines).encode("utf-8")
