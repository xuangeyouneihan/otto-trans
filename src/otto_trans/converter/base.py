from abc import ABC, abstractmethod

from ..utils.format import Format


class BaseConverter(ABC):
    source: Format
    target: Format

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "source" not in cls.__dict__ or "target" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} 必须定义 source 和 target 属性")
        if not isinstance(cls.__dict__.get("source"), Format):
            raise TypeError(f"{cls.__name__}.source 必须是 Format 对象")
        if not isinstance(cls.__dict__.get("target"), Format):
            raise TypeError(f"{cls.__name__}.target 必须是 Format 对象")

    @staticmethod
    @abstractmethod
    def convert(content: bytes) -> bytes: ...
