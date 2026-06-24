package kg.us.xuan.otto_trans.config;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

import org.yaml.snakeyaml.Yaml;

public class Settings {

    private static Settings instance;

    public static final Path CONFIG_PATH = Path.of(System.getProperty("user.home"), ".config", "otto-trans", "config.yaml");

    public final String defaultEngine;
    public final String defaultSource;
    public final String defaultTarget;
    public final LinkedHashMap<String, Object> engines;

    private Settings() {
        Yaml yaml = new Yaml();
        try {
            if (CONFIG_PATH.toFile().exists()) {
                LinkedHashMap<String, Object> config = yaml.load(Files.readString(CONFIG_PATH));
                if (config != null) {
                    this.defaultEngine = Objects.toString(config.getOrDefault("default_engine", "deepl"), "deepl").strip();

                    this.defaultSource = Objects.toString(config.getOrDefault("default_source", "auto"), "auto").toLowerCase().strip();

                    this.defaultTarget = Objects.toString(config.getOrDefault("default_target", ""), "").toLowerCase().strip();

                    @SuppressWarnings("unchecked")
                    Map<String, Object> enginesConfig = (Map<String, Object>) config.getOrDefault("engines",
                            new LinkedHashMap<String, Object>());
                    this.engines = new LinkedHashMap<>(enginesConfig);
                } else {
                    this.defaultEngine = "deepl";
                    this.defaultSource = "auto";
                    this.defaultTarget = "";
                    this.engines = new LinkedHashMap<>();
                }
            } else {
                this.defaultEngine = "deepl";
                this.defaultSource = "auto";
                this.defaultTarget = "";
                this.engines = new LinkedHashMap<>();
            }
        } catch (IOException e) {
            throw new RuntimeException("配置文件加载失败");
        }
    }

    public static Settings getInstance() {
        if (instance == null) {
            instance = new Settings();
        }
        return instance;
    }
}
