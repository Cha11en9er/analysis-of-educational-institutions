#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор структуры отзывов Яндекса из сохранённой SSR-страницы (школа 33 Энгельса)."""
import re
import json

html = open('roadmap/08.11.26/ym33_reviews.html', encoding='utf-8').read()
chunks = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
big = max(chunks, key=len)
print('big script:', len(big))

# Найти JSON-массив отзывов: рядом с отзывами Яндекса бывают ключи
# "author", "review", "text", "rating", "publishDate"/"created"/"date"
# Посмотрим все ключи в окрестности первых текстов
TEXT_RE = re.compile(r'"text"\s*:\s*"((?:\\.|[^"\\]){15,})"')
found = list(TEXT_RE.finditer(big))
print('text fields:', len(found))
for m in found[:5]:
    before = big[max(0, m.start() - 600):m.start()]
    keys = re.findall(r'"([a-zA-Z_]{3,25})"\s*:', before)
    print('KEYS near text:', keys[-12:])

# отдельно: есть ли даты/авторы/рейтинги в тех же окрестностях
for m in found[:3]:
    after = big[m.end():m.end() + 400]
    keys_a = re.findall(r'"([a-zA-Z_]{3,25})"\s*:', after)
    print('AFTER:', keys_a[:10])
