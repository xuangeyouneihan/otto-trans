from otto_trans.converter.base import BaseConverter
from otto_trans.utils.format import Format


class ConverterPlugin(BaseConverter):
    """示例格式转换器 —— 请将类名替换为你自己的转换器名称。

    注意：
    1. source 和 target 必须定义为类属性的 Format 对象
    2. convert 必须是 @staticmethod
    3. pyproject.toml 中 entry_points 注册为 otto_trans.converter
    """

    source = Format(
        name="source-format",
        description="源格式的描述",
        extensions={".src"},
        mime_type="text/source-format",
    )
    target = Format(
        name="target-format",
        description="目标格式的描述",
        extensions={".tgt"},
        mime_type="text/target-format",
    )

    @staticmethod
    def convert(content: bytes) -> bytes:
        """将 source 格式的内容转换为 target 格式。"""
        text = content.decode("utf-8-sig")
        # TODO: 在这里实现实际的格式转换逻辑
        result = text  # 占位实现，不做任何转换
        return result.encode("utf-8-sig")
