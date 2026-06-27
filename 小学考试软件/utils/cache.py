"""
AI 响应缓存：基于 SQLite，避免重复调用 API，降低成本
缓存键 = SHA256(prompt内容)，TTL 默认 7 天
"""
import sqlite3
import hashlib
import json
import os
import time

CACHE_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache.db")
DEFAULT_TTL = 7 * 24 * 3600  # 7天


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(CACHE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at REAL NOT NULL,
            ttl REAL NOT NULL,
            hit_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def _make_key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def get(prompt: str) -> str | None:
    key = _make_key(prompt)
    with _conn() as conn:
        row = conn.execute(
            "SELECT value, created_at, ttl FROM ai_cache WHERE key=?", (key,)
        ).fetchone()
        if not row:
            return None
        value, created_at, ttl = row
        if time.time() - created_at > ttl:
            conn.execute("DELETE FROM ai_cache WHERE key=?", (key,))
            return None
        conn.execute("UPDATE ai_cache SET hit_count=hit_count+1 WHERE key=?", (key,))
        return value


def set(prompt: str, value: str, ttl: float = DEFAULT_TTL):
    key = _make_key(prompt)
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache (key, value, created_at, ttl) VALUES (?,?,?,?)",
            (key, value, time.time(), ttl),
        )


def clear_expired():
    with _conn() as conn:
        conn.execute("DELETE FROM ai_cache WHERE (created_at + ttl) < ?", (time.time(),))


def clear_all():
    with _conn() as conn:
        conn.execute("DELETE FROM ai_cache")


def stats() -> dict:
    with _conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*), SUM(hit_count) FROM ai_cache WHERE (created_at+ttl) > ?",
            (time.time(),),
        ).fetchone()
        return {"entries": row[0] or 0, "total_hits": row[1] or 0}
