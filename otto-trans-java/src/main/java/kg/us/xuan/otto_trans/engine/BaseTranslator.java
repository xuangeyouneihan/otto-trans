package kg.us.xuan.otto_trans.engine;

import java.util.List;

public abstract class BaseTranslator {

    // 类级别默认值（子类覆写）
    protected String engineName = getClass().getSimpleName();

    protected String friendlyName = null;

    // public static final Map<String, OptionMeta> OPTIONS = new HashMap<>();

    // public abstract Set<Format> getFormats();
    // 实例字段
    protected final String configName;

    public BaseTranslator(String configName) {
        this.configName = configName;
    }

    /**
     * 等同于 Python 的 name property
     */
    public String getName() {
        if (configName != null) {
            return engineName + ":" + configName;
        }
        return engineName;
    }

    /**
     * 必须实现的文本翻译
     */
    public abstract List<String> translateTexts(
            List<String> texts, String srcLang, String tgtLang
    );

    /**
     * 可选覆写的文件翻译
     */
    public byte[] translateFile(byte[] content, String srcLang, String tgtLang, String mimeType) {
        throw new UnsupportedOperationException(
                getName() + " 不支持文件翻译"
        );
    }
}
