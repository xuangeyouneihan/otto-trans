package kg.us.xuan.otto_trans.config;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;

import org.junit.jupiter.api.Test;

class SettingsTest {

    @Test
    void testConfigPathIsCorrect() {
        String home = System.getProperty("user.home");
        assertEquals(
                Path.of(home, ".config", "otto-trans", "config.yaml"),
                Settings.CONFIG_PATH
        );
    }

    @Test
    void testSingletonReturnsSameInstance() {
        Settings first = Settings.getInstance();
        Settings second = Settings.getInstance();
        assertSame(first, second);
    }

    @Test
    void testDefaultsWhenConfigAbsent() {
        Settings s = Settings.getInstance();
        // 在没有配置文件时应有合理的默认值
        assertNotNull(s.defaultEngine);
        assertNotNull(s.defaultSource);
        assertNotNull(s.defaultTarget); // 可能为空字符串
        assertNotNull(s.engines);
    }

    @Test
    void testEngineDefaults() {
        Settings s = Settings.getInstance();
        assertEquals("deepl", s.defaultEngine);
        assertEquals("auto", s.defaultSource);
    }

    @Test
    void testEnginesMapIsMutable() {
        Settings s = Settings.getInstance();
        // engines 应该是可写的（用于后续合并 CLI 选项）
        assertDoesNotThrow(() -> s.engines.put("test", new Object()));
    }
}
