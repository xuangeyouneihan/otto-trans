package kg.us.xuan.otto_trans.core;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class CacheTest {

    private Cache cache;

    @BeforeEach
    void setUp() {
        // Cache 是单例，但每次测试前确保状态干净
        // 因为无法重置单例，这里仅测试核心的 query/insert 逻辑
        cache = Cache.getInstance();
        assertNotNull(cache);
    }

    @Test
    void testCacheInstanceIsSingleton() {
        Cache second = Cache.getInstance();
        assertSame(cache, second);
    }

    @Test
    void testDbPathIsCorrect() {
        String home = System.getProperty("user.home");
        assertEquals(
                Path.of(home, ".cache", "otto-trans", "cache.db"),
                Cache.dbPath
        );
    }

    @Test
    void testQueryNonexistentReturnsNull() throws Exception {
        String result = cache.query("nonexistent_key_xyz", "deepl", "en", "zh");
        assertNull(result);
    }

    @Test
    void testInsertAndQueryRoundtrip() throws Exception {
        String original = "Hello, world!";
        String engine = "deepl";
        String src = "EN";
        String tgt = "ZH";

        cache.insert(original, "你好，世界！", engine, src, tgt);
        String cached = cache.query(original, engine, src, tgt);

        assertEquals("你好，世界！", cached);
    }

    @Test
    void testInsertOverwritesExisting() throws Exception {
        String key = "test text";
        String engine = "deepl";
        String src = "EN";
        String tgt = "ZH";

        cache.insert(key, "first translation", engine, src, tgt);
        cache.insert(key, "second translation", engine, src, tgt);

        assertEquals("second translation", cache.query(key, engine, src, tgt));
    }

    @Test
    void testDifferentLanguagesDontCollide() throws Exception {
        String key = "hello";
        String engine = "deepl";

        cache.insert(key, "你好", engine, "EN", "ZH");
        cache.insert(key, "こんにちは", engine, "EN", "JA");

        assertEquals("你好", cache.query(key, engine, "EN", "ZH"));
        assertEquals("こんにちは", cache.query(key, engine, "EN", "JA"));
    }
}
