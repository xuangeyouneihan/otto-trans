package kg.us.xuan.otto_trans;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;

import kg.us.xuan.otto_trans.config.Settings;
import kg.us.xuan.otto_trans.core.Translator;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;
import picocli.CommandLine.Parameters;

@Command(name = "otto")
public class Main implements Callable<Integer> {

    @Parameters(arity = "0..*", description = "要翻译的文本")
    List<String> texts = null;

    @Option(names = {"-s", "--source"}, description = "源语言，自带的 DeepL 支持 ISO 639 语言代码，如 \"zh-Hans\"、\"en\" 等")
    String srcLang = "auto";

    @Option(names = {"-t", "--target"}, description = "目标语言，自带的 DeepL 支持 ISO 639 语言代码，如 \"zh-Hans\"、\"en\" 等")
    String tgtLang = null;

    @Option(names = {"-e", "--engine"}, description = "支持 engine:config 语法指定配置方案")
    String engine = "deepl";

    @Option(names = {"-o", "--option"}, description = "引擎特定选项，格式为 key=value")
    List<String> options;

    @Override
    public Integer call() {
        Settings settings;
        try {
            settings = Settings.getInstance();
        } catch (Exception e) {
            if (e.getMessage() != null && !e.getMessage().isEmpty()) {
                System.err.println("配置文件加载失败: " + e.getClass().getSimpleName() + ": " + e.getMessage());
            } else {
                System.err.println("配置文件加载失败: " + e.getClass().getSimpleName());
            }
            return 1;
        }

        srcLang = srcLang != null && !srcLang.isEmpty() ? srcLang : settings.defaultSource;

        tgtLang = tgtLang != null && !tgtLang.isEmpty() ? tgtLang : settings.defaultTarget;
        if (tgtLang == null || tgtLang.isEmpty()) {
            System.err.println("请指定目标语言（-t / --target）或在配置文件中设置默认目标语言");
            return 1;
        }

        engine = engine != null && !engine.isEmpty() ? engine : settings.defaultEngine;
        if (engine == null || engine.isEmpty()) {
            System.err.println("请指定翻译引擎（-e / --engine）或在配置文件中设置默认翻译引擎");
            return 1;
        }

        Map<String, Object> CLIOpts = new HashMap<>();
        if (options != null) {
            for (String opt : options) {
                String[] parts = opt.split("=", 2);
                if (parts.length == 2) {
                    CLIOpts.put(parts[0], parts[1]);
                }
            }
        }

        String[] engineName = engine.split(":", 2);
        String baseName = engineName[0];
        String configName = engineName.length > 1 ? engineName[1] : null;

        Map<String, Object> baseOpts = null;
        Object tempBaseOpts = settings.engines != null ? settings.engines.get(baseName) : null;
        if (tempBaseOpts != null && tempBaseOpts instanceof Map
                && ((Map<?, ?>) tempBaseOpts).entrySet().stream().allMatch(e -> e.getKey() instanceof String)) {
            @SuppressWarnings("unchecked")
            Map<String, Object> temp = (Map<String, Object>) tempBaseOpts;
            baseOpts = temp;
        }

        if (baseOpts != null) {
            if (configName != null && !configName.isEmpty()) {
                Object tempConfigOpts = baseOpts.get(configName);
                if (tempConfigOpts != null && tempConfigOpts instanceof Map && ((Map<?, ?>) tempConfigOpts).entrySet()
                        .stream().allMatch(e -> e.getKey() instanceof String)) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> temp = (Map<String, Object>) tempConfigOpts;
                    baseOpts = temp;
                }
            } else {
                for (Map.Entry<String, Object> entry : baseOpts.entrySet()) {
                    if (entry.getValue() instanceof Map && !((Map<?, ?>) entry.getValue()).isEmpty()
                            && ((Map<?, ?>) entry.getValue()).entrySet().stream()
                                    .allMatch(e -> e.getKey() instanceof String)) {
                        @SuppressWarnings("unchecked")
                        Map<String, Object> temp = (Map<String, Object>) entry.getValue();
                        baseOpts = temp;
                        configName = entry.getKey();
                        break;
                    }
                }
            }
        }

        Map<String, Object> engineOpts = new HashMap<>();
        if (baseOpts != null) {
            for (Map.Entry<String, Object> entry : baseOpts.entrySet()) {
                engineOpts.put(entry.getKey(), entry.getValue());
            }
        }
        engineOpts.putAll(CLIOpts);

        Translator translator;
        try {
            translator = new Translator(baseName, engineOpts, configName, msg -> System.err.println(msg));
        } catch (IllegalArgumentException e) {
            if (e.getMessage() != null && !e.getMessage().isEmpty()) {
                System.err.println("配置错误：" + e.getClass().getSimpleName() + ": " + e.getMessage());
            } else {
                System.err.println("配置错误：" + e.getClass().getSimpleName());
            }
            return 1;
        }

        try {
            if (texts == null || texts.isEmpty()) {
                System.err.println("未读取到任何文本内容，退出");
                return 1;
            }
            String text = String.join(" ", texts);
            List<String> results = translator.translateTexts(List.of(text), srcLang, tgtLang);
            System.out.println(results.get(0));
        } catch (Exception e) {
            if (e.getMessage() != null && !e.getMessage().isEmpty()) {
                System.err.println("翻译失败：" + e.getClass().getSimpleName() + ": " + e.getMessage());
            } else {
                System.err.println("翻译失败：" + e.getClass().getSimpleName());
            }
            return 1;
        }
        return 0;
    }

    public static void main(String[] args) {
        int exitCode = new picocli.CommandLine(new Main()).execute(args);
        System.exit(exitCode);
    }
}
