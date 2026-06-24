package kg.us.xuan.otto_trans.engine;

import java.util.Set;

public class OptionMeta {
    public final Class<?> type;
    public final String description;
    public final boolean required;
    public final Set<String> scope;

    public OptionMeta(Class<?> type, String description, boolean required, Set<String> scope) {
        this.type = type;
        this.description = description;
        this.required = required;
        this.scope = scope;
    }
}
