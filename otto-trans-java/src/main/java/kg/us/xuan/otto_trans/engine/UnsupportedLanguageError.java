package kg.us.xuan.otto_trans.engine;

import java.util.Set;
import java.util.stream.Collectors;

public class UnsupportedLanguageError extends IllegalArgumentException {

    protected static String buildMessage(String engineName, String srcCode, String tgtCode, Set<String> srcAvailable,
            Set<String> tgtAvailable, Set<LanguagePair> supportedPairs, Set<LanguagePair> blockedPairs) {
        StringBuilder temp = new StringBuilder();
        temp.append(String.format("当前翻译引擎 %s 不支持指定的语言 '%s' -> '%s'。", engineName, srcCode, tgtCode));
        if (srcAvailable != null && !srcAvailable.isEmpty()) {
            temp.append(String.format("\n\n可用的源语言如下：\n%s。", String.join(", ", srcAvailable)));
        }
        if (tgtAvailable != null && !tgtAvailable.isEmpty()) {
            temp.append(String.format("\n\n可用的目标语言如下：\n%s。", String.join(", ", tgtAvailable)));
        }
        if (supportedPairs != null && !supportedPairs.isEmpty()) {
            String pairs = supportedPairs.stream()
                    .sorted((a, b) -> {
                        int cmp = a.src().compareTo(b.src());
                        return cmp != 0 ? cmp : a.tgt().compareTo(b.tgt());
                    })
                    .map(p -> p.src() + "→" + p.tgt())
                    .collect(Collectors.joining(", "));
            temp.append(String.format("\n\n支持的翻译方向：\n%s。", pairs));
        }
        if (blockedPairs != null && !blockedPairs.isEmpty()) {
            String pairs = blockedPairs.stream()
                    .sorted((a, b) -> {
                        int cmp = a.src().compareTo(b.src());
                        return cmp != 0 ? cmp : a.tgt().compareTo(b.tgt());
                    })
                    .map(p -> p.src() + "→" + p.tgt())
                    .collect(Collectors.joining(", "));
            temp.append(String.format("\n\n不支持的翻译方向：\n%s。", pairs));
        }
        return temp.toString();
    }

    public UnsupportedLanguageError() {
        super();
    }

    public UnsupportedLanguageError(String message) {
        super(message);
    }

    public UnsupportedLanguageError(String engineName, String srcCode, String tgtCode,
            Set<String> srcAvailable, Set<String> tgtAvailable,
            Set<LanguagePair> supportedPairs, Set<LanguagePair> blockedPairs) {
        super(buildMessage(engineName, srcCode, tgtCode, srcAvailable, tgtAvailable, supportedPairs, blockedPairs));
    }

}
