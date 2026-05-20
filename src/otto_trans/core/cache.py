import sqlite3
import base64
import atexit
from pathlib import Path

def b64encode(s: str) -> str:
    return base64.b64encode(s.encode(encoding="utf-8")).decode(encoding="utf-8")

def b64decode(s: str) -> str:
    return base64.b64decode(s.encode(encoding="utf-8")).decode(encoding="utf-8")

class Cache:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_path = Path.home() / ".cache" / "otto-trans" / "cache.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._initialized = True
        atexit.register(self._conn.close)

    def __del__(self):
        self._conn.close()

    def query(self, key: str, engine: str, from_lang: str, to_lang: str) -> str | None:
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                f"SELECT target FROM [{b64encode(engine)}] WHERE source = ? AND from_lang = ? AND to_lang = ?",
                (b64encode(key), b64encode(from_lang), b64encode(to_lang))
            )
        except sqlite3.OperationalError:
            return None          # 表不存在 = 无缓存
        result = cursor.fetchone()
        return b64decode(result[0]) if result else None

    def insert(self, key: str, value: str, engine: str, from_lang: str, to_lang: str):
        cursor = self._conn.cursor()
        self._create_table(b64encode(engine))
        cursor.execute(f"INSERT OR REPLACE INTO [{b64encode(engine)}] (source, target, from_lang, to_lang) VALUES (?, ?, ?, ?)", (b64encode(key), b64encode(value), b64encode(from_lang), b64encode(to_lang)))
        self._conn.commit()

    def _create_table(self, name: str):
        cursor = self._conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS [{name}] (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                from_lang TEXT NOT NULL,
                to_lang TEXT NOT NULL,
                PRIMARY KEY (source, from_lang, to_lang)
            )
        """)
        self._conn.commit()