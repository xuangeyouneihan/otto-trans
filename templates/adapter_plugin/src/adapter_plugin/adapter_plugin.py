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
