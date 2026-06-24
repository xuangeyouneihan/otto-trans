# 电棍翻译器（Java 版）

Java 版[电棍翻译器](https://github.com/xuangeyouneihan/otto-trans)，学习用。

仅实现了 DeepL 引擎的文本翻译，选项校验通过反射读取 `OPTIONS` 静态字段，配置由 SnakeYAML 加载，缓存用 SQLite。

## 快速开始

```shell
# 编译 + 打包
mvn clean package

# 运行（需先配好 ~/.config/otto-trans/config.yaml）
java -jar target/otto-trans-0.0.0.jar -t zh-Hans -e deepl Hello, world!
```

## 配置文件示例

```yaml
# ~/.config/otto-trans/config.yaml
default_engine: deepl
default_source: auto
default_target: zh-Hans
engines:
  deepl:
    default:
      auth_key: "your-deepl-api-key"
```

## 与 Python 原版的技术栈对照

| Python                     | Java              |
| -------------------------- | ----------------- |
| typer                      | picocli           |
| httpx                      | OkHttp            |
| pydantic-settings          | SnakeYAML         |
| sqlite3                    | sqlite-jdbc       |
| ServiceLoader entry_points | ServiceLoader SPI |
