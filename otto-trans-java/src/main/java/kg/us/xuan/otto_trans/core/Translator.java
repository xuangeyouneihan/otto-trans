package kg.us.xuan.otto_trans.core;

import java.lang.reflect.InvocationTargetException;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.ServiceLoader;
import java.util.function.Consumer;

import kg.us.xuan.otto_trans.engine.BaseTranslator;
import kg.us.xuan.otto_trans.engine.DeepLTranslator;
import kg.us.xuan.otto_trans.engine.OptionMeta;

public class Translator {

    private final Consumer<String> onWarning;

    private static HashMap<String, Class<? extends BaseTranslator>> engines = null;

    public static HashMap<String, Class<? extends BaseTranslator>> getEngines(Consumer<String> onWarning) {
        if (engines != null) {
            return engines;
        }

        if (onWarning == null) {
            onWarning = msg -> System.err.println(msg);
        }

        engines = new HashMap<>();

        engines.put("deepl", DeepLTranslator.class);

        var loader = ServiceLoader.load(BaseTranslator.class);
        for (BaseTranslator translator : loader) {
            try {
                engines.put(translator.getName(), translator.getClass());
            } catch (Exception e) {
                onWarning.accept("加载翻译器 " + translator.getName() + " 失败: " + e.getMessage());
            }
        }

        return engines;
    }

    protected BaseTranslator engine = null;
    protected Cache cache = null;

    public Translator(String engine, Map<String, Object> options, String config, Consumer<String> onWarning) {
        this.onWarning = onWarning != null ? onWarning : msg -> System.err.println(msg);

        getEngines(this.onWarning);

        Class<? extends BaseTranslator> engineClass = engines.getOrDefault(engine, null);
        if (engineClass == null) {
            throw new IllegalArgumentException("不支持的翻译引擎: " + engine);
        }

        Map<String, OptionMeta> engineOptions;
        try {
            Object temp = engineClass.getDeclaredField("OPTIONS").get(null);
            if (!(temp instanceof Map
                    && ((Map<?, ?>) temp).keySet().stream().allMatch(k -> k instanceof String)
                    && ((Map<?, ?>) temp).values().stream().allMatch(v -> v instanceof OptionMeta))) {
                engineOptions = Map.of();
            } else {
                @SuppressWarnings("unchecked")
                Map<String, OptionMeta> opts = (Map<String, OptionMeta>) temp;
                engineOptions = opts;
            }
        } catch (NoSuchFieldException | IllegalAccessException e) {
            engineOptions = Map.of();
        }

        for (String optName : engineOptions.keySet()) {
            OptionMeta optMeta = engineOptions.get(optName);
            if (!options.containsKey(optName) || options.get(optName) == null) {
                if (optMeta.required) {
                    throw new IllegalArgumentException(String.format("缺少翻译引擎 %s 的必需选项：%s", engine, optName));
                } else {
                    continue;
                }
            }
            if (!optMeta.type.isInstance(options.get(optName))) {
                if (options.get(optName) instanceof String && optMeta.type == Boolean.class) {
                    if (List.of("true", "false", "yes", "no", "on", "off", "enable", "disable", "enabled", "disabled")
                            .contains(((String) options.get(optName)).toLowerCase())) {
                        options.put(optName, List.of("true", "yes", "on", "enable", "enabled")
                                .contains(((String) options.get(optName)).toLowerCase()));
                    } else {
                        throw new IllegalArgumentException(String.format(
                                "翻译引擎 %s 的选项 %s 应该是布尔值（true/false）, 实际是字符串: %s",
                                engine, optName, options.get(optName)));
                    }
                } else {
                    try {
                        options.put(optName,
                                optMeta.type.getMethod("valueOf", String.class).invoke(null, options.get(optName)));
                    } catch (NoSuchMethodException | IllegalAccessException | InvocationTargetException e) {
                        throw new IllegalArgumentException(String.format(
                                "翻译引擎 %s 的选项 %s 应该是 %s 类型，实际是 %s 类型",
                                engine, optName, optMeta.type.getSimpleName(),
                                options.get(optName).getClass().getSimpleName()), e);
                    }
                }
            }
        }
        try {
            this.engine = engineClass.getDeclaredConstructor(Map.class, String.class).newInstance(options, config);
        } catch (NoSuchMethodException | InstantiationException | IllegalAccessException
                | InvocationTargetException e) {
            throw new IllegalArgumentException("无法创建翻译引擎 " + engine + " 的实例：" + e.getMessage(), e);
        }

        this.cache = Cache.getInstance();
    }

    public List<String> translateTexts(List<String> texts, String srcLang, String tgtLang) {
        String[] results = new String[texts.size()];
        Map<Integer, String> misses = new LinkedHashMap<>();
        for (int i = 0; i < texts.size(); i++) {
            String text = texts.get(i);
            String cached = null;
            try {
                cached = cache.query(text, this.engine.getName(), srcLang, tgtLang);
            } catch (SQLException e) {
            }
            if (cached != null) {
                results[i] = cached;
            } else {
                misses.put(i, text);
            }
        }
        if (!misses.isEmpty()) {
            List<String> missTexts = new ArrayList<>(misses.values());
            List<String> engineResults = this.engine.translateTexts(missTexts, srcLang, tgtLang);
            if (engineResults.size() != missTexts.size()) {
                throw new RuntimeException(String.format(
                        "翻译引擎 %s 返回的翻译结果数量与请求的文本数量不匹配：%d != %d",
                        this.engine.getName(), engineResults.size(), missTexts.size()));
            }
            int j = 0;
            for (Map.Entry<Integer, String> miss : misses.entrySet()) {
                int idx = miss.getKey();
                String result = engineResults.get(j++);
                results[idx] = result;
                try {
                    cache.insert(miss.getValue(), result, this.engine.getName(), srcLang, tgtLang);
                } catch (SQLException e) {
                }
            }
        }
        return Arrays.asList(results);
    }
}
