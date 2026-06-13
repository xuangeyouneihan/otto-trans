import re
from dataclasses import dataclass

from ..utils.format import Format
from .base import BaseAdapter, Segment


@dataclass
class SRTBlock:
    """SRT 字幕块上下文——用于 reassemble 时还原位置"""

    seq: int
    start: str
    end: str


class SRTAdapter(BaseAdapter):
    """SRT 字幕适配器：提取纯文本翻译后原位组装"""

    source = Format(
        name="srt",
        extensions={".srt"},
        mime_type="application/x-subrip",
    )

    @staticmethod
    def extract(content: bytes) -> list[Segment]:
        text = content.decode("utf-8-sig", errors="replace")
        segments: list[Segment] = []
        # 按空行分割 SRT 块
        block_pattern = re.compile(
            r"(\d+)\r?\n"
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\r?\n"
            r"(.+)",
            re.DOTALL,
        )
        for blob in re.split(r"\r?\n\r?\n", text.strip()):
            m = block_pattern.match(blob.strip())
            if not m:
                continue
            seq = int(m.group(1))
            start = m.group(2)
            end = m.group(3)
            sub_text = m.group(4).strip()
            if sub_text:
                segments.append(
                    Segment(
                        text=sub_text,
                        context=SRTBlock(seq=seq, start=start, end=end),
                    )
                )
        return segments

    @staticmethod
    def reassemble(content: bytes, translated: list[Segment]) -> bytes:
        text = content.decode("utf-8-sig", errors="replace")
        trans_texts = [s.text for s in translated]
        # 替换每个字幕块中的文本内容
        i = 0

        def replacer(m: re.Match) -> str:
            nonlocal i
            header = f"{m.group(1)}\n{m.group(2)} --> {m.group(3)}\n"
            new_text = trans_texts[i] if i < len(trans_texts) else ""
            i += 1
            return header + new_text

        result = re.sub(
            r"(\d+)\r?\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\r?\n.+?(?=\r?\n\r?\n|\r?\n*$)",
            replacer,
            text.strip(),
            flags=re.DOTALL,
        )
        return result.encode("utf-8-sig")
