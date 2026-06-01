# ♿电棍翻译器

> 多引擎命令行翻译工具，支持有道、OpenAI 兼容接口和 DeepL 三种翻译后端。

---

## 特性

- **多引擎**：有道 API、OpenAI / DeepSeek / 任何兼容接口、DeepL，一键切换
- **插件系统**：第三方引擎可通过 PyPI 安装并自动发现，无需修改主程序代码
- **多模式**：命令行参数、逐行交互、管道/heredoc，灵活适配各种使用场景
- **缓存**：SQLite 持久化翻译缓存，相同文本不重复请求 API
- **智能语言代码**：ISO 639 语言代码，支持大小写混写、BCP47 扩展（`zh-Hans` 等）
- **异步**：基于 `asyncio` + `httpx`，批量翻译时并发请求，无需等待
- **自动发现**：`otto --help` 和 `otto --reset-config` 自动读取已安装的引擎，动态生成帮助信息与默认配置

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

### 命令行参数（单段）

```bash
otto -t zh-Hans Hello world
# → 合并为 "Hello world" 翻译成中⽂
```

### 逐行模式（多段独立翻译）

```bash
otto -t zh-Hans -b
请输入要翻译的文本（输入空行结束）：
hello
world
[回车]
```

### 管道模式

```bash
echo "hello\nworld" | otto -t zh-Hans
```

### 批量模式

```bash
otto -t zh-Hans -b hello world foo
# → hello、world、foo 分别翻译
```

---

## 选项

```
-s, --source     源语言（默认 auto）
-t, --target     目标语言
-e, --engine     翻译引擎（youdao / openai:provider / deepl / 任意插件）
-o, --option     引擎选项，格式 key=value
-b, --batch      批量模式，每段文本独立翻译
    --reset-config  重置配置文件
    --reset-cache   重置翻译缓存
```

引擎名支持 `:` 分隔配置名称，可用同一引擎的多个配置：

```bash
otto -e deepl:my-config -t zh-Hans hello
```

---

## 引擎选项

| 引擎                  | 必需参数                             | 可选参数                                                                                                                               |
| --------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| **有道**        | `app_key`、`app_secret`          | —                                                                                                                                     |
| **OpenAI 兼容** | `endpoint`、`api_key`、`model` | `prompt_template`、`thinking`、`reasoning_effort`、`temperature`、`max_tokens`、`top_p`、`top_k`、`repetition_penalty` |
| **DeepL**       | `auth_key`                         | `paid`、`context`、`preserve_formatting`、`formality`、`model_type`                                                          |

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

插件只需继承 `BaseTranslator`、声明 `options`、实现 `translate` 即可。详见 [`templates/engine_plugin/`](templates/engine_plugin/)。

---

## 架构

```
otto-trans/
├── cli.py              Typer CLI 入口
├── config/
│   └── settings.py     配置管理（Pydantic + YAML，动态生成默认配置）
├── core/
│   ├── cache.py         SQLite 翻译缓存（单例模式）
│   └── translator.py    翻译编排器 + 注册式工厂（Facade 模式）
└── engine/
    ├── base.py          策略模式抽象基类
    ├── youdao.py        有道翻译引擎
    ├── openai.py        OpenAI 兼容接口引擎
    └── deepl.py         DeepL 翻译引擎
templates/
└── engine_plugin/       翻译引擎插件模板
```

### 设计模式

| 模式       | 应用                                                     |
| ---------- | -------------------------------------------------------- |
| 策略模式   | `BaseTranslator` 定义接口，三个引擎各自实现            |
| 模板方法   | `translate_batch` 基类提供默认并发，子类可覆盖         |
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

23 个测试覆盖：缓存 CRUD、引擎初始化校验、语言代码归一化、签名构造、HTTP 请求验证、翻译编排逻辑。

```bash
pytest          # 全部测试
pytest -v       # 详细输出
pytest -k cache # 只跑缓存相关测试
```
