from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..utils.format import Format


@dataclass
class Segment:
    text: str
    context: Any = None
    children: list["Segment"] = field(default_factory=list)


class BaseAdapter(ABC):
    source: Format  # 适配的文件格式

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "source" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} 必须定义 source 属性")
        if not isinstance(cls.__dict__.get("source"), Format):
            raise TypeError(f"{cls.__name__}.source 必须是 Format 对象")

    @staticmethod
    @abstractmethod
    def extract(content: bytes) -> list[Segment]:
        """提取待翻译的文本片段"""
        ...

    @staticmethod
    @abstractmethod
    def reassemble(content: bytes, translated: list[Segment]) -> bytes:
        """将翻译后的片段组装回原文件"""
        ...
