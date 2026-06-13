# ♿电棍翻译器

> 多引擎命令行翻译工具，支持有道、OpenAI 兼容接口和 DeepL 三种翻译后端。

---

## 特性

- **多引擎**：有道 API、OpenAI / DeepSeek / 任何兼容接口、DeepL，一键切换
- **插件系统**：第三方引擎、转换器、适配器可通过 PyPI 安装并自动发现
- **多输入源**：命令行参数、逐行交互、管道/heredoc、本地文件、远程 URL
- **文件翻译**：支持批量文件对翻译，格式转换（Markdown↔HTML）、字幕适配
- **缓存**：SQLite 持久化翻译缓存，相同文本不重复请求 API
- **并发控制**：`-j` 参数控制文件翻译并发数，0 为无限制
- **智能语言代码**：ISO 639 语言代码，支持大小写混写、BCP47 扩展（`zh-Hans` 等）
- **自动发现**：`otto --help` 和 `otto --reset-config` 自动读取已安装的插件，动态生成帮助信息与默认配置

---

## 快速开始

```bash
pip install otto-trans

# 首次运行自动生成配置文件
otto -t zh-Hans Hello, world!

# 使用有道翻译
otto -e youdao -o app_key=xxx -o app_secret=yyy -t zh-Hans hello

# 使用 DeepSeek
otto -e openai:deepseek -t zh-Hans hello

# 使用 DeepL
otto -e deepl -o auth_key=xxx -t zh-Hans hello
```

---

## 使用方式

### 命令行参数

```bash
otto -t zh-Hans Hello world
# → 合并为 "Hello world" 翻译成中文
```

### 交互输入（多段翻译）

输入多段文本，用只含 `===` 的行分隔各段，空行 Ctrl-Z + 回车（Windows）/ Ctrl-D（Linux / macOS）退出：

```bash
otto -t zh-Hans
请输入要翻译的文本（多段用只包含 '===' 的行分隔，输入 EOF 结束）：
hello
===
world
[Ctrl-Z][回车]（Windows）/ [Ctrl-D]（Linux / macOS）
```

### 管道 / Heredoc

```bash
echo hello | otto -t zh-Hans
```

### 文件翻译

```bash
# 基本文件对
otto -t zh-Hans -p en.txt::zh.txt

# 批量文件对
otto -t zh-Hans -p a.txt::a-out.txt -p b.txt::b-out.txt

# 仅输入（文件 → stdout）
otto -t zh-Hans -p en.txt::

# 仅输出（管道 → 文件）
echo hello | otto -t zh-Hans -p ::out.txt

# 智能路径（终端 → 读文件，管道 → 写文件）
otto -t zh-Hans -p doc.txt
cat en.txt | otto -t zh-Hans -p zh.txt

# 远程 URL 输入
otto -t zh-Hans -p https://example.com/doc.txt::translated.txt

# 文件翻译模式（-f 指定格式，自动查找可用的转换器/适配器）
otto -t zh-Hans -f html -p page.html::page-zh.html

# 引擎原生不支持 Markdown？自动通过 markdown↔html 转换
# 无需手动指定 -c，程序会自动发现并串联合适的转换器
otto -e youdao -f md -p doc.md::doc-zh.md

# 引擎不支持 SRT？自动通过字幕适配器处理
# 无需手动指定 -a，程序会自动发现并提取/翻译/组装
otto -e youdao -f srt -p en.srt::zh.srt

# 手动指定转换器（当自动发现结果不符合预期时使用）
otto -e youdao -f md -c markdown_to_html::html_to_markdown -p doc.md::doc-zh.md

# 手动指定适配器
otto -e youdao -f srt -a srt -p en.srt::zh.srt

# 并发控制（最多 3 个文件同时翻译）
otto -e youdao -f html -j 3 -p a.html::zh/a.html -p b.html::zh/b.html -p c.html::zh/c.html
```

---

## 选项

```
-s, --source        源语言（默认 auto）
-t, --target        目标语言
-e, --engine        翻译引擎，支持 engine:config 语法指定配置方案
-o, --option        引擎选项，格式 key=value
-p, --path          文件路径，格式 input::output，支持批量
-f, --format        输入文件格式（html、md、srt 等，需引擎/转换器/适配器支持）
-c, --converter     格式转换器，格式 in_conv::out_conv
-a, --adapter       格式适配器名称
-j, --jobs          文件翻译并发数，0 为无限制（默认 0）
    --reset-config  重置配置文件
    --reset-cache   重置翻译缓存
```

引擎名支持 `:` 分隔配置名称，可用同一引擎的多个配置：

```bash
otto -e deepl:my-config -t zh-Hans hello
```

---

## 格式转换器与适配器

当引擎不原生支持某种文件格式时，程序会**自动发现**合适的转换器或适配器，无需用户干预：

1. 先检查引擎是否原生支持该格式
2. 不支持时，查找能将输入格式转为引擎支持格式的转换器
3. 找不到转换器时，查找能提取/组装该格式的适配器
4. 翻译完成后，自动查找反向转换器将结果转回原格式

整个过程中程序会通过 stderr 输出决策信息（如"适配器不支持该格式，尝试自动发现"），方便用户了解翻译过程。

| 类型             | 作用                                       | 示例                                     |
| ---------------- | ------------------------------------------ | ---------------------------------------- |
| **转换器** | 将文件转为引擎支持的临时格式，翻译后再转回 | Markdown → HTML → 引擎翻译 → Markdown |
| **适配器** | 提取文件中的纯文本翻译后原位组装           | SRT 字幕：提取 → 逐行翻译 → 写回时间轴 |

如果需要覆盖自动发现的结果，可通过 `-c in_conv::out_conv` 或 `-a adapter` 手动指定。
`otto --help` 会列出当前所有可用的转换器和适配器。

---

## 引擎选项

| 引擎                  | 必需参数                             | 可选参数                                                                                                                               |
| --------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| **有道**        | `app_key`、`app_secret`          | —                                                                                                                                     |
| **OpenAI 兼容** | `endpoint`、`api_key`、`model` | `prompt_template`、`thinking`、`reasoning_effort`、`temperature`、`max_tokens`、`top_p`、`top_k`、`repetition_penalty` |
| **DeepL**       | `auth_key`                         | `paid`、`context`、`preserve_formatting`、`formality`、`model_type`、`glossary_id`、`tag_handling`                       |

每个选项需声明 `scope`（`{"text"}` / `{"file"}` / `{"text", "file"}`）以限定生效模式，`otto --help` 会在选项后标注"仅文本模式"或"仅文件模式"。

第三方插件安装后会自动注册，`otto --help` 会动态显示其信息。

---

## 配置

配置文件位于 `~/.config/otto-trans/config.yaml`，首次运行自动生成。

```yaml
default_engine: # 默认翻译引擎
default_source: # 默认源语言
default_target: # 默认目标语言

# 引擎配置
engines:
  youdao: # 有道翻译
    default:
      app_key:    # 应用 ID
      app_secret: # 应用密钥

  openai: # OpenAI 翻译
    default:
      endpoint:           # API 端点地址
      api_key:            # API 密钥
      model:              # 模型名称
      # prompt_template:    # 自定义提示词模板，支持 {src_lang} 和 {tgt_lang} 占位
      # thinking:           # 深度思考模式，true 或 false
      # reasoning_effort:   # 推理强度，none、minimal、low、medium、high、xhigh 或 max
      # temperature:        # 采样温度，0~2，越低越确定
      # max_tokens:         # 最大输出 token 数
      # top_p:              # 核采样概率，0~1
      # top_k:              # top-k 采样，整数，越大越随机
      # repetition_penalty: # 重复惩罚，0~2，越大越避免重复

  deepl: # DeepL 翻译
    default:
      auth_key:            # API 密钥
      # paid:                # 是否使用付费端点，true 或 false，默认 false
      # context:             # 上下文信息，帮助模型理解翻译场景
      # preserve_formatting: # 保留原文格式，true 或 false
      # formality:           # 正式程度，default、more、less、prefer_more 或 prefer_less
      # model_type:          # 模型类型，quality_optimized、latency_optimized 或 prefer_quality_optimized
      # glossary_id:         # 术语表 ID
      # tag_handling:        # XML/HTML 标签处理，xml 或 html
```

引擎配置支持嵌套多个配置项，通过 `:` 指定：

```bash
otto -e deepl:my-config -t zh-Hans hello
```

```yaml
engines:
  deepl:
    my-config:
      auth_key: xxx
      paid: true
    another-config:
      auth_key: yyy
      formality: more
```

通过 `-o key=value` 可在命令行临时覆盖配置文件中的参数。

---

## 插件开发

第三方翻译引擎可通过 PyPI 发布并被 `otto-trans` 自动发现。在插件的 `pyproject.toml` 中声明 entry point：

```toml
[project.entry-points."otto_trans.engine"]
my_engine = "my_package:MyEngine"
```

插件只需继承 `BaseTranslator`、声明 `options`（含 `scope`）、实现 `translate_texts` 和可选的 `async translate_file` 即可。

转换器插件继承 `BaseConverter`，声明 `source` 和 `target` 格式，实现 `convert` 方法。适配器插件继承 `BaseAdapter`，声明 `source` 格式，实现 `extract` 和 `reassemble` 方法。

详见 [`templates/engine_plugin/`](templates/engine_plugin/)、[`templates/converter_plugin/`](templates/converter_plugin/)、[`templates/adapter_plugin/`](templates/adapter_plugin/)。

---

## 架构

```
otto-trans/
├── cli.py                  Typer CLI 入口
├── config/
│   └── settings.py         配置管理（Pydantic + YAML，动态生成默认配置）
├── adapter/
│   ├── base.py              适配器抽象基类（Segment 数据类）
│   └── srt.py               SRT 字幕适配器
├── converter/
│   ├── base.py              转换器抽象基类
│   ├── html_to_markdown.py  HTML → Markdown
│   └── markdown_to_html.py  Markdown → HTML
├── core/
│   ├── cache.py             SQLite 翻译缓存（单例模式）
│   └── translator.py        翻译编排器 + 注册式工厂（Facade 模式）
├── engine/
│   ├── base.py              策略模式抽象基类
│   ├── youdao.py            有道翻译引擎
│   ├── openai.py            OpenAI 兼容接口引擎
│   └── deepl.py             DeepL 翻译引擎
├── utils/
│   ├── format.py            文件格式定义（Format 数据类）
│   └── text.py              文本工具（编码检测等）
templates/
└── engine_plugin/           翻译引擎插件模板
```

### 设计模式

| 模式       | 应用                                                     |
| ---------- | -------------------------------------------------------- |
| 策略模式   | `BaseTranslator` 定义接口，三个引擎各自实现            |
| 外观模式   | `Translator` 隐藏缓存和引擎的协调逻辑                  |
| 单例模式   | `Cache` 全局唯一 SQLite 连接                           |
| 注册式工厂 | `Translator.engines` + entry_points 自动发现第三方引擎 |
| 依赖注入   | `Translator` 接收 engine 和 options 作为依赖           |

---

## 开发

```bash
# 克隆并安装
git clone https://github.com/xuangeyouneihan/otto-trans
cd otto-trans
uv sync

# 运行测试
pytest

# 运行
uv run otto -t zh-Hans hello
```

---

## 测试

87 个测试覆盖：缓存 CRUD、引擎初始化校验、语言代码归一化、签名构造、HTTP 请求验证、翻译编排逻辑、格式转换器、字幕适配器、CLI 路径解析、转换器参数解析、反向转换器查找。

```bash
pytest          # 全部测试
pytest -v       # 详细输出
pytest -k cache # 只跑缓存相关测试
```
