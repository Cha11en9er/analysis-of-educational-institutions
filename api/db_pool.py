#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пул соединений PostgreSQL для API.

Раньше каждый запрос открывал своё соединение psycopg2 и закрывал его — при
наплыве пользователей это упирается в лимит соединений БД и добавляет latency
на каждый запрос. Теперь соединения переиспользуются.

close() у обёртки возвращает соединение в пул, поэтому существующие обработчики
(conn ... finally: conn.close()) менять не нужно.
"""
import os
import threading
from typing import Any

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

_pool = None
_pool_lock = threading.Lock()


def _db_config() -> dict[str, Any]:
    return {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "database": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "connect_timeout": 5,
    }


def _init_pool() -> ThreadedConnectionPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            maxconn = int(os.getenv("DB_POOL_MAX", "10"))
            _pool = ThreadedConnectionPool(1, maxconn, **_db_config())
        return _pool


def reset_pool() -> None:
    """Закрыть все соединения (например, после падения БД)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.closeall()
            except Exception:
                pass
            _pool = None


class PooledConnection:
    """Обёртка над соединением: close() возвращает его в пул.

    Обычные атрибуты (без __slots__): __getattr__ срабатывает только для
    методов psycopg2 (cursor/commit/...), которых нет у обёртки.
    """

    def __init__(self, pool: ThreadedConnectionPool, conn):
        self._pool = pool
        self._conn = conn

    def close(self) -> None:
        try:
            self._pool.putconn(self._conn)
        except Exception:
            pass

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def get_pooled_connection():
    """Соединение из пула с проверкой живости (БД могла перезапуститься)."""
    pool = _init_pool()
    last_error: Exception | None = None
    for _ in range(2):
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return PooledConnection(pool, conn)
        except Exception as e:
            last_error = e
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
    # пул мог целиком протухнуть — пересоздаём и пробуем ещё раз
    reset_pool()
    pool = _init_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return PooledConnection(pool, conn)
    except Exception as e:
        last_error = e
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
    raise last_error if last_error else RuntimeError("не удалось получить соединение")
