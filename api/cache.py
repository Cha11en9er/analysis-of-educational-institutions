#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Кэш ответов API в памяти процесса.

Зачем: при наплыве пользователей каждый GET /api/schools/map бил тяжёлый SQL
(оконные функции RANK). Кэш с коротким TTL снимает основную нагрузку с БД, а
при недоступности БД отдаётся последняя известная копия (stale-on-error) —
сайт продолжает открываться.
"""
import threading
import time
from collections import deque
from typing import Any, Callable

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}
_order: deque[str] = deque()
_MAX_ENTRIES = 1200


def _evict_locked() -> None:
    while len(_store) > _MAX_ENTRIES:
        old = _order.popleft()
        _store.pop(old, None)


def peek(key: str) -> tuple[float, Any] | None:
    with _lock:
        hit = _store.get(key)
        return (hit[0], hit[1]) if hit else None


def cached(key: str, ttl: float, producer: Callable[[], Any]) -> tuple[Any, str]:
    """Значение по ключу с TTL.

    Возвращает (значение, статус): fresh | hit | stale | miss.
    Если producer упал и в кэше есть устаревшая копия — отдаём её (stale).
    """
    now = time.time()
    with _lock:
        hit = _store.get(key)
    if hit and now - hit[0] <= ttl:
        return hit[1], "fresh"
    try:
        value = producer()
    except Exception:
        if hit:
            return hit[1], "stale"
        raise
    with _lock:
        _store[key] = (now, value)
        _order.append(key)
        _evict_locked()
    return value, "miss"


def stats() -> dict[str, int]:
    with _lock:
        return {"entries": len(_store)}
