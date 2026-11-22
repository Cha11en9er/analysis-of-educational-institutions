#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Выгрузка списка организаций (с ссылками Яндекс) из БД — для сбора фото."""
import json
import os

import psycopg2
import psycopg2.extras

REPO = os.environ.get('UCHGRAD_REPO', '/opt/uchgrad')
raw = open(os.path.join(REPO, '.env'), 'rb').read().decode('utf-8', 'replace')
env = {}
for line in raw.splitlines():
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip("'\"")

conn = psycopg2.connect(
    host=env['DB_HOST'], port=int(env['DB_PORT']), dbname=env['DB_NAME'],
    user=env['DB_USER'], password=env['DB_PASSWORD'], client_encoding='UTF8',
)
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cur.execute("""
    SELECT i.code_oo, i.kind, i.city, i.name, l.link_yandex
    FROM sa.institution i
    LEFT JOIN sa.link l ON l.school_id = 100000 + i.code_oo
    WHERE i.code_oo IS NOT NULL
    ORDER BY i.city, i.kind, i.code_oo
""")
rows = [dict(r) for r in cur.fetchall()]
conn.close()

out = os.path.join(REPO, 'roadmap', '22.11.26', 'institutions_list.json')
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('организаций:', len(rows), '| с яндекс-ссылкой:', sum(1 for r in rows if r.get('link_yandex')))
