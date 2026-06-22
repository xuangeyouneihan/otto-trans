import atexit
import base64
import sqlite3
from pathlib import Path


class Cache:
    _instance = None
    _initialized = False
    db_path = Path.home() / ".cache" / "otto-trans" / "cache.db"

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._initialized = True
        atexit.register(self._conn.close)

    def __del__(self):
        self._conn.close()

    def query(self, key: str, engine: str, src_lang: str, tgt_lang: str) -> str | None:
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                f"SELECT target FROM [{self._b64encode(engine)}] WHERE source = ? AND src_lang = ? AND tgt_lang = ?",
                (
                    self._b64encode(key),
                    self._b64encode(src_lang),
                    self._b64encode(tgt_lang),
                ),
            )
        except sqlite3.OperationalError:
            return None  # 表不存在 = 无缓存
        result = cursor.fetchone()
        return self._b64decode(result[0]) if result else None

    def insert(self, key: str, value: str, engine: str, src_lang: str, tgt_lang: str):
        cursor = self._conn.cursor()
        self._create_table(self._b64encode(engine))
        cursor.execute(
            f"INSERT OR REPLACE INTO [{self._b64encode(engine)}] (source, target, src_lang, tgt_lang) VALUES (?, ?, ?, ?)",
            (
                self._b64encode(key),
                self._b64encode(value),
                self._b64encode(src_lang),
                self._b64encode(tgt_lang),
            ),
        )
        self._conn.commit()

    def _create_table(self, name: str):
        cursor = self._conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS [{name}] (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                src_lang TEXT NOT NULL,
                tgt_lang TEXT NOT NULL,
                PRIMARY KEY (source, src_lang, tgt_lang)
            )
        """)

    @staticmethod
    def _b64encode(s: str) -> str:
        return base64.b64encode(s.encode(encoding="utf-8")).decode(encoding="utf-8")

    @staticmethod
    def _b64decode(s: str) -> str:
        return base64.b64decode(s.encode(encoding="utf-8")).decode(encoding="utf-8")

    @classmethod
    def reset(cls):
        if cls._instance is not None:
            cls._instance._conn.close()
        cls.db_path.unlink(missing_ok=True)
        if cls._instance is not None:
            cls._instance._conn = sqlite3.connect(str(cls.db_path))
