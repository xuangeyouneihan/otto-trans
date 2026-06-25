import pytest

from otto_trans.config.settings import Settings


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch, tmp_path):
    """每个测试前重置单例并指向临时配置文件"""
    # 清空单例
    if Settings._instance is not None:
        Settings._instance.__dict__.clear()
        Settings._instance = None
        Settings._initialized = False

    # 指向临时路径，先创建空文件避免 FileNotFoundError
    config_file = tmp_path / "config.yaml"
    config_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(Settings, "config_path", config_file)

    yield

    # 清理
    if Settings._instance is not None:
        Settings._instance.__dict__.clear()
        Settings._instance = None
        Settings._initialized = False


def write_config(config_path, data: dict):
    """写入 YAML 配置"""
    import yaml

    config_path.write_text(yaml.dump(data), encoding="utf-8")


# ── 默认值 ──


def test_defaults_when_no_config():
    s = Settings()
    assert s.default_engine == ""
    assert s.default_source == "auto"
    assert s.default_target == ""
    assert s.engines == {}


def test_default_engine_from_config():
    write_config(Settings.config_path, {"default_engine": "deepl"})
    s = Settings()
    assert s.default_engine == "deepl"


def test_default_source_lowercased():
    write_config(Settings.config_path, {"default_source": "EN"})
    s = Settings()
    assert s.default_source == "en"


def test_default_target_lowercased():
    write_config(Settings.config_path, {"default_target": "zh-Hans"})
    s = Settings()
    assert s.default_target == "zh-hans"


def test_engines_from_config():
    write_config(
        Settings.config_path, {"engines": {"deepl": {"default": {"auth_key": "abc"}}}}
    )
    s = Settings()
    assert s.engines == {"deepl": {"default": {"auth_key": "abc"}}}


# ── 单例 ──


def test_singleton_same_instance():
    s1 = Settings()
    s2 = Settings()
    assert s1 is s2


def test_singleton_does_not_reread_config():
    write_config(Settings.config_path, {"default_engine": "deepl"})
    s1 = Settings()
    assert s1.default_engine == "deepl"

    # 修改配置文件
    write_config(Settings.config_path, {"default_engine": "youdao"})
    s2 = Settings()  # 单例，不会重新读取
    assert s2.default_engine == "deepl"


# ── 重置 ──


def test_reset_clears_and_reloads():
    write_config(
        Settings.config_path,
        {
            "default_engine": "deepl",
            "default_source": "en",
        },
    )
    s1 = Settings()
    assert s1.default_engine == "deepl"

    # 清除单例状态并写入新配置
    Settings._instance.__dict__.clear()
    Settings._instance = None
    Settings._initialized = False
    write_config(
        Settings.config_path,
        {
            "default_engine": "youdao",
            "default_source": "zh",
        },
    )

    s2 = Settings()
    assert s2.default_engine == "youdao"
    assert s2.default_source == "zh"


def test_reset_without_config_creates_file():
    Settings.reset()
    assert Settings.config_path.exists()
    content = Settings.config_path.read_text(encoding="utf-8")
    assert "default_engine:" in content
    assert "engines:" in content


# ── 错误处理 ──


def test_invalid_default_engine_dict():
    """冒号后有空格时抛出 ValueError"""
    write_config(Settings.config_path, {"default_engine": {"deepl": "my-config"}})
    with pytest.raises(ValueError, match="default_engine 配置格式错误"):
        Settings()


def test_null_values_are_filtered():
    """YAML 中值为 null 的键被过滤"""
    write_config(
        Settings.config_path,
        {
            "default_engine": "deepl",
            "default_target": None,
        },
    )
    s = Settings()
    assert s.default_engine == "deepl"
    assert s.default_target == ""


def test_engines_is_dict():
    """engines 是常规 dict，非嵌套时也能正常工作"""
    write_config(Settings.config_path, {"engines": {"some_key": "some_value"}})
    s = Settings()
    assert isinstance(s.engines, dict)
