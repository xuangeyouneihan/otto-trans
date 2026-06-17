"""格式转换器插件模板。

转换器 vs 适配器
----------------
- 转换器：将整个文件转成另一种格式，翻译后再转回（如 Markdown ↔ HTML）
- 适配器：从文件中提取纯文本片段翻译，再原位组装回去（如 SRT 字幕）

转换器的优势：
- 保留原文件的结构信息和上下文，翻译引擎可以看到完整文档
- 适合格式转换链路清晰的场景（Markdown → HTML → 引擎翻译 → HTML → Markdown）
- 在 `translate_file` 的路由中优先级高于适配器自动发现

转换器的局限：
- 需要成对实现（source→target 和 target→source），否则翻译后无法转回原格式
- 依赖引擎原生支持 target 格式，不如适配器灵活
- 格式转换可能损失细节（如 Markdown → HTML 再转回可能丢失原始空行风格）

快速开始
--------
1. 将本文件、__init__.py、pyproject.toml 中的 `converter_plugin` 替换为你的插件名
2. 修改 `source` 和 `target` 的 Format 定义（name、extensions、mime_type 等）
3. 实现 `convert` 静态方法：source → target
4. 在 `pyproject.toml` 中确认 `[project.entry-points."otto_trans.converter"]` 指向你的类
5. `pip install -e .` 后运行 `otto --help` 验证是否出现在转换器列表中

必需声明
--------
- `source: Format`：输入格式
- `target: Format`：输出格式（必须是某个引擎原生支持的格式，否则转换器不会被匹配）

必需实现
--------
- `@staticmethod convert(content: bytes) -> bytes`：将 source 格式转为 target 格式。文本格式建议使用 `utf-8-sig` 编码。解码可以考虑使用 `otto_trans.utils.text.detect_encoding`（基于 chardet）辅助自动检测编码

命名规则
--------
- 类名任意，entry_points 中注册的名字会成为 CLI 中 `-c` 的参数值
- 建议用 `source_to_target` 风格命名，如 `html_to_markdown`、`xml_to_json`

格式匹配
--------
- 引擎通过 `supports_format` 判断是否原生支持 target 格式
- Format 相等采用扩展名子集判定：双方扩展名互为子集即视为一致
- 转换器名称在 `converters()` 注册表中必须全局唯一

Format 类
---------
- `Format` 是 dataclass，字段：`name: str`、`description: str`、`extensions: set[str]`、`mime_type: str`。
- 扩展名子集判定：两个 Format 的 extensions 互为子集即视为相等（如 `text({".txt"}) == text({".txt", ".text"})`）。

错误处理
--------
- `UnsupportedFormatError.for_engine(name, fmt, formats)`：格式不支持时抛出，第二个参数是用户传入的格式（str 或 Format），第三个是支持的格式集合（可选）

示例
----
下面是一个将 XML 转为 JSON 的完整转换器示例。"""

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
