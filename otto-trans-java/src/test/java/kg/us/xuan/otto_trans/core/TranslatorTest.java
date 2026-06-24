package kg.us.xuan.otto_trans.core;

import static org.junit.jupiter.api.Assertions.*;

import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.Test;

class TranslatorTest {

    // ── 引擎查找 ──
    @Test
    void testValidEngineDoesNotThrow() {
        Map<String, Object> opts = new HashMap<>();
        opts.put("auth_key", "test-key");
        assertDoesNotThrow(() -> new Translator("deepl", opts, null, null));
    }

    @Test
    void testUnknownEngineThrows() {
        Map<String, Object> opts = new HashMap<>();
        IllegalArgumentException e = assertThrows(
                IllegalArgumentException.class,
                () -> new Translator("nonexistent_engine", opts, null, null)
        );
        assertTrue(e.getMessage().contains("不支持的翻译引擎"));
    }

    // ── 选项校验：必需参数 ──
    @Test
    void testMissingRequiredOptionThrows() {
        Map<String, Object> opts = new HashMap<>(); // 没有 auth_key
        IllegalArgumentException e = assertThrows(
                IllegalArgumentException.class,
                () -> new Translator("deepl", opts, null, null)
        );
        assertTrue(e.getMessage().contains("auth_key"));
    }

    @Test
    void testNullRequiredOptionThrows() {
        Map<String, Object> opts = new HashMap<>();
        opts.put("auth_key", null);
        IllegalArgumentException e = assertThrows(
                IllegalArgumentException.class,
                () -> new Translator("deepl", opts, null, null)
        );
        assertTrue(e.getMessage().contains("auth_key"));
    }

    // ── 选项校验：布尔值转换 ──
    @Test
    void testBooleanTrueStringIsAccepted() {
        Map<String, Object> opts = new HashMap<>();
        opts.put("auth_key", "test-key");
        opts.put("paid", "true");
        assertDoesNotThrow(() -> new Translator("deepl", opts, null, null));
    }

    @Test
    void testBooleanYesStringIsAccepted() {
        Map<String, Object> opts = new HashMap<>();
        opts.put("auth_key", "test-key");
        opts.put("paid", "yes");
        assertDoesNotThrow(() -> new Translator("deepl", opts, null, null));
    }

    @Test
    void testBooleanInvalidStringThrows() {
        Map<String, Object> opts = new HashMap<>();
        opts.put("auth_key", "test-key");
        opts.put("paid", "not-a-boolean");
        IllegalArgumentException e = assertThrows(
                IllegalArgumentException.class,
                () -> new Translator("deepl", opts, null, null)
        );
        assertTrue(e.getMessage().contains("布尔值"));
    }

    @Test
    void testBooleanActualBooleanIsAccepted() {
        Map<String, Object> opts = new HashMap<>();
        opts.put("auth_key", "test-key");
        opts.put("paid", true);
        assertDoesNotThrow(() -> new Translator("deepl", opts, null, null));
    }

    // ── onWarning 默认值 ──
    @Test
    void testNullOnWarningUsesDefault() {
        Map<String, Object> opts = new HashMap<>();
        opts.put("auth_key", "test-key");
        assertDoesNotThrow(() -> new Translator("deepl", opts, null, null));
    }

    // ── config 传递 ──
    @Test
    void testConfigNameIsPassedToEngine() {
        Map<String, Object> opts = new HashMap<>();
        opts.put("auth_key", "test-key");
        Translator t = new Translator("deepl", opts, "my-config", null);
        assertEquals("deepl:my-config", t.engine.getName());
    }

    @Test
    void testNullConfigNameYieldsPlainEngineName() {
        Map<String, Object> opts = new HashMap<>();
        opts.put("auth_key", "test-key");
        Translator t = new Translator("deepl", opts, null, null);
        assertEquals("deepl", t.engine.getName());
    }
}
