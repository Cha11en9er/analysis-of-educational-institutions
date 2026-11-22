#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Выгрузка сырых отзывов школ Энгельса из БД — по файлу на школу (для разметки)."""
import json
import os

import psycopg2
import psycopg2.extras

REPO = os.environ.get('UCHGRAD_REPO', '/opt/uchgrad')
OUT = os.path.join(REPO, 'roadmap', '22.11.26', 'reviews_raw')

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
    SELECT r.review_id, r.school_id, r.review_date, r.review_text, r.review_rating
    FROM sa.review r
    WHERE r.school_id >= 100000
    ORDER BY r.school_id, r.review_id
""")
rows = cur.fetchall()
conn.close()

os.makedirs(OUT, exist_ok=True)
by_school = {}
for r in rows:
    by_school.setdefault(r['school_id'], []).append({
        'review_id': str(r['review_id']),
        'school_id': r['school_id'],
        'date': r['review_date'].isoformat() if r['review_date'] else None,
        'text': r['review_text'],
        'rating': r['review_rating'],
    })

n = 0
for sid, revs in by_school.items():
    json.dump({'school_id': sid, 'reviews': revs},
              open(os.path.join(OUT, f'school_{sid}.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    n += len(revs)
print('школ:', len(by_school), '| отзывов:', n, '->', OUT)
