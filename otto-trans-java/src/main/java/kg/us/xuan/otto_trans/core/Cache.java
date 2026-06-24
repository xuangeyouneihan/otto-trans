package kg.us.xuan.otto_trans.core;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Base64;

public class Cache {

    public static final Path dbPath = Path.of(System.getProperty("user.home"), ".cache", "otto-trans", "cache.db");

    private static final Cache INSTANCE = new Cache();

    private Connection conn = null;

    private Cache() {
        try {
            Files.createDirectories(dbPath.getParent());
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        try {
            Class.forName("org.sqlite.JDBC");
            conn = java.sql.DriverManager.getConnection("jdbc:sqlite:" + dbPath);
            conn.setAutoCommit(false);
        } catch (ClassNotFoundException | SQLException e) {
            throw new RuntimeException(e);
        }
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                if (conn != null && !conn.isClosed()) {
                    conn.close();
                }
            } catch (SQLException e) {
                // 无论如何都不抛出异常了
            }
        }));
    }

    public static Cache getInstance() {
        return INSTANCE;
    }

    public String query(String key, String engine, String srcLang, String tgtLang) throws SQLException {
        String result = null;
        String sql = String.format("SELECT target FROM [%s] WHERE source = ? AND src_lang = ? AND tgt_lang = ?",
                b64Encode(engine));
        try (PreparedStatement stmt = conn.prepareStatement(sql)) {
            stmt.setString(1, b64Encode(key));
            stmt.setString(2, b64Encode(srcLang));
            stmt.setString(3, b64Encode(tgtLang));
            try {
                ResultSet rs = stmt.executeQuery();
                if (rs.next()) {
                    result = b64Decode(rs.getString(1));
                }
            } catch (SQLException e) {
                // 表不存在，啥都不干
            }
        }
        return result;
    }

    public void insert(String key, String value, String engine, String srcLang, String tgtLang) throws SQLException {
        createTable(b64Encode(engine));
        String sql = String.format("INSERT OR REPLACE INTO [%s] (source, target, src_lang, tgt_lang) VALUES (?, ?, ?, ?)",
                b64Encode(engine));
        try (PreparedStatement stmt = conn.prepareStatement(sql)) {
            stmt.setString(1, b64Encode(key));
            stmt.setString(2, b64Encode(value));
            stmt.setString(3, b64Encode(srcLang));
            stmt.setString(4, b64Encode(tgtLang));
            stmt.executeUpdate();
        }
        conn.commit();
    }

    private void createTable(String name) throws SQLException {
        String sql = String.format(
                "CREATE TABLE IF NOT EXISTS [%s] (source TEXT NOT NULL, target TEXT NOT NULL, src_lang TEXT NOT NULL, tgt_lang TEXT NOT NULL, PRIMARY KEY (source, src_lang, tgt_lang))",
                name);
        try (PreparedStatement stmt = conn.prepareStatement(sql)) {
            stmt.execute();
        }
    }

    private String b64Encode(String s) {
        return Base64.getEncoder().encodeToString(s.getBytes(StandardCharsets.UTF_8));
    }

    private String b64Decode(String s) {
        return new String(Base64.getDecoder().decode(s), StandardCharsets.UTF_8);
    }
}
