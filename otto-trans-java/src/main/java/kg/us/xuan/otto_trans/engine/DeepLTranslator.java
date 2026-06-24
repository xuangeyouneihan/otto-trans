package kg.us.xuan.otto_trans.engine;

import java.io.IOException;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;

class DeepLAPIError extends RuntimeException {

    public DeepLAPIError() {
        super();
    }

    public DeepLAPIError(String message) {
        super(message);
    }
}

public class DeepLTranslator extends BaseTranslator {

    private static final String DEEPL_TEXT_URL = "https://api.deepl.com/v2/translate";
    private static final String DEEPL_TEXT_LANGUAGES_URL = "https://api.deepl.com/v3/languages?resource=translate_text";

    private static final String DEEPL_TEXT_URL_FREE = "https://api-free.deepl.com/v2/translate";
    private static final String DEEPL_TEXT_LANGUAGES_URL_FREE = "https://api-free.deepl.com/v3/languages?resource=translate_text";

    public static final Map<String, OptionMeta> OPTIONS = Map.ofEntries(
            Map.entry("auth_key", new OptionMeta(
                    String.class,
                    "API 密钥",
                    true,
                    Set.of("text", "file"))),
            Map.entry("paid", new OptionMeta(
                    Boolean.class,
                    "是否使用付费端点，true 或 false，默认 false",
                    false,
                    Set.of("text", "file"))),
            Map.entry("formality", new OptionMeta(
                    String.class,
                    "正式程度，default、more、less、prefer_more 或 prefer_less",
                    false,
                    Set.of("text", "file"))),
            Map.entry("glossary_id", new OptionMeta(
                    String.class,
                    "术语表 ID，启用后会使用指定的术语表进行翻译",
                    false,
                    Set.of("text", "file"))),
            Map.entry("context", new OptionMeta(
                    String.class,
                    "上下文信息，帮助模型理解翻译场景",
                    false,
                    Set.of("text"))),
            Map.entry("preserve_formatting", new OptionMeta(
                    Boolean.class,
                    "保留原文格式，true 或 false",
                    false,
                    Set.of("text"))),
            Map.entry("model_type", new OptionMeta(
                    String.class,
                    "模型类型，quality_optimized、latency_optimized 或 prefer_quality_optimized",
                    false,
                    Set.of("text"))),
            Map.entry("tag_handling", new OptionMeta(
                    String.class,
                    "标签处理，xml 或 html，启用后会使用 v2 版本的标签处理",
                    false,
                    Set.of("text"))));

    private static final HashMap<String, String> SRC_LANG_MAP = new HashMap<>() {
        {
            put("DE-DE", "DE");
            put("EN-GB", "EN");
            put("EN-US", "EN");
            put("ES-419", "ES");
            put("FR-FR", "FR");
            put("PT-BR", "PT");
            put("PT-PT", "PT");
            put("ZH-HANS", "ZH");
            put("ZH-HANT", "ZH");
        }
    };

    // private static final HashMap<String, String> TGT_LANG_MAP = new HashMap<>();
    private final Gson gson = new Gson();
    private final OkHttpClient client = new OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(600, TimeUnit.SECONDS)
            .writeTimeout(600, TimeUnit.SECONDS)
            .followRedirects(true)
            .build();

    private final String authKey;
    private final boolean paid;
    private final String formality;
    private final String glossaryID;
    private final String context;
    private final Boolean preserveFormatting;
    private final String modelType;
    private final String tagHandling;

    public DeepLTranslator(Map<String, Object> options, String configName) {
        Object temp = options.get("paid");
        boolean paidOption = temp instanceof Boolean ? (Boolean) temp : false;
        temp = options.get("preserve_formatting");
        Boolean preserveFormattingOption = temp instanceof Boolean ? (Boolean) temp : null;
        this(
                (String) options.get("auth_key"),
                paidOption,
                (String) options.get("formality"),
                (String) options.get("glossary_id"),
                (String) options.get("context"),
                preserveFormattingOption,
                (String) options.get("model_type"),
                (String) options.get("tag_handling"),
                configName
        );
    }

    public DeepLTranslator(String authKey, boolean paid, String formality, String glossaryID, String context,
            Boolean preserveFormatting, String modelType, String tagHandling, String configName) {
        // 引擎固定字段设置
        super(configName);
        this.engineName = "deepl";
        this.friendlyName = "DeepL 翻译";

        // 参数字段设置和参数校验
        this.authKey = authKey;
        this.paid = paid;
        if (formality != null && !formality.isEmpty() && !Set.of(
                "default",
                "more",
                "less",
                "prefer_more",
                "prefer_less").contains(formality)) {
            throw new IllegalArgumentException(
                    String.format("formality 参数值无效：%s，必须是 default、more、less、prefer_more 或 prefer_less", formality));
        }
        this.formality = formality;
        this.glossaryID = glossaryID;
        this.context = context;
        this.preserveFormatting = preserveFormatting;
        this.modelType = modelType;
        if (modelType != null && !modelType.isEmpty() && !Set.of(
                "quality_optimized",
                "latency_optimized",
                "prefer_quality_optimized").contains(modelType)) {
            throw new IllegalArgumentException(
                    String.format(
                            "model_type 参数值无效：%s，必须是 quality_optimized、latency_optimized 或 prefer_quality_optimized",
                            modelType));
        }
        if (tagHandling != null && !tagHandling.isEmpty() && !Set.of("xml", "html").contains(tagHandling)) {
            throw new IllegalArgumentException(
                    String.format("tag_handling 参数值无效：%s，必须是 xml 或 html", tagHandling));
        }
        this.tagHandling = tagHandling;
    }

    @Override
    public List<String> translateTexts(List<String> texts, String srcLang, String tgtLang) {
        List<String> normalizedLangs = normalizeLang(srcLang, tgtLang);
        srcLang = normalizedLangs.get(0);
        tgtLang = normalizedLangs.get(1);

        HashMap<String, Object> payload = buildTextPayload(texts, srcLang, tgtLang);
        String json = gson.toJson(payload);
        String url = paid ? DEEPL_TEXT_URL : DEEPL_TEXT_URL_FREE;

        Request request = new Request.Builder()
                .url(url)
                .post(RequestBody.create(json, MediaType.get("application/json")))
                .addHeader("Authorization", "DeepL-Auth-Key " + authKey)
                .build();

        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                ResponseBody body = response.body();
                String errorBody = body != null ? body.string() : "";
                // 错误处理：语言不支持、其他API错误
                if (response.code() == 400 && ((errorBody.contains("source_lang"))
                        || errorBody.contains("target_lang") && errorBody.contains("not supported"))) {
                    Set<String> srcLanguages = null;
                    Set<String> tgtLanguages = null;
                    try {
                        List<Set<String>> supportedLangs = fetchSupportedLanguages();
                        srcLanguages = supportedLangs.get(0);
                        tgtLanguages = supportedLangs.get(1);
                    } catch (Exception e) {
                        // 忽略 fetchSupportedLanguages 的异常，继续抛出 UnsupportedLanguageError
                    }
                    throw new UnsupportedLanguageError(
                            engineName, srcLang, tgtLang, srcLanguages, tgtLanguages, null, null);
                }
                throw new DeepLAPIError("DeepL API 返回错误：" + response.code() + " " + errorBody);
            }
            // 解析 translations[].text
            ResponseBody responseBody = response.body();
            JsonObject body = gson.fromJson(responseBody != null ? responseBody.string() : "", JsonObject.class);
            return body.getAsJsonArray("translations").asList().stream()
                    .map(t -> t.getAsJsonObject().get("text").getAsString())
                    .collect(Collectors.toList());
        } catch (IOException e) {
            throw new DeepLAPIError("DeepL API 请求失败：" + e.getMessage());
        }
    }

    private HashMap<String, Object> buildTextPayload(List<String> texts, String srcLang, String tgtLang) {
        // Implementation for translating a single text
        // This method should handle the API call to DeepL and return the translated text
        HashMap<String, Object> payload = new HashMap<>();
        payload.put("text", texts);
        payload.put("target_lang", tgtLang);
        if (srcLang != null && !srcLang.isEmpty() && !srcLang.equals("AUTO")) {
            payload.put("source_lang", srcLang);
        }
        if (context != null && !context.isEmpty()) {
            payload.put("context", context);
        }
        if (preserveFormatting != null) {
            payload.put("preserve_formatting", preserveFormatting);
        }
        if (formality != null && !formality.isEmpty()) {
            payload.put("formality", formality);
        }
        if (modelType != null && !modelType.isEmpty()) {
            payload.put("model_type", modelType);
        }
        if (glossaryID != null && !glossaryID.isEmpty()) {
            payload.put("glossary_id", glossaryID);
        }
        if (tagHandling != null && !tagHandling.isEmpty()) {
            payload.put("tag_handling", tagHandling);
            payload.put("tag_handling_version", "v2");
        }
        return payload;
    }

    private List<String> normalizeLang(String srcLang, String tgtLang) {
        String normSrc = SRC_LANG_MAP.getOrDefault(srcLang.toUpperCase(), srcLang.toUpperCase());
        // String normTgt = TGT_LANG_MAP.getOrDefault(tgtLang.toUpperCase(), tgtLang.toUpperCase());
        String normTgt = tgtLang.toUpperCase();
        return List.of(normSrc, normTgt);
    }

    private List<Set<String>> fetchSupportedLanguages() {
        String url = paid ? DEEPL_TEXT_LANGUAGES_URL : DEEPL_TEXT_LANGUAGES_URL_FREE;
        Request request = new Request.Builder()
                .url(url)
                .get()
                .addHeader("Authorization", "DeepL-Auth-Key " + authKey)
                .addHeader("Content-Type", "application/json")
                .build();

        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                ResponseBody body = response.body();
                String errorBody = body != null ? body.string() : "";
                throw new DeepLAPIError("DeepL API 获取支持语言失败：" + response.code() + " " + errorBody);
            }

            ResponseBody responseBody = response.body();
            JsonArray langsArray = gson.fromJson(responseBody != null ? responseBody.string() : "", JsonArray.class);
            Set<String> sourceLangs = new HashSet<>();
            Set<String> targetLangs = new HashSet<>();
            for (JsonElement e : langsArray) {
                JsonObject langObj = e.getAsJsonObject();
                String langCode = langObj.get("lang").getAsString();
                boolean usableAsSource = langObj.get("usable_as_source").getAsBoolean();
                boolean usableAsTarget = langObj.get("usable_as_target").getAsBoolean();
                if (usableAsSource) {
                    sourceLangs.add(langCode);
                }
                if (usableAsTarget) {
                    targetLangs.add(langCode);
                }
            }
            return List.of(sourceLangs, targetLangs);
        } catch (IOException e) {
            throw new DeepLAPIError("DeepL API 获取支持语言失败：" + e.getMessage());
        }
    }
}
