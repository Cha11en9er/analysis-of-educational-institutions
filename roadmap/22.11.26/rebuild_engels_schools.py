#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пересборка набора школ ЭНГЕЛЬСА (roadmap/01.11.26/engels/city_schools.json) из
реестра РЦОКО (kind='general', city='Энгельс') + координат sa.institution +
ссылок Яндекс/2ГИС. Запуск на сервере (нужна БД):
  .venv/bin/python roadmap/22.11.26/rebuild_engels_schools.py
"""
import json
import os

import psycopg2
import psycopg2.extras

REPO = '/opt/uchgrad'
EN = os.path.join(REPO, 'roadmap', '01.11.26', 'engels')
OUT = os.path.join(EN, 'city_schools.json')

raw = open(os.path.join(REPO, '.env'), 'rb').read().decode('utf-8', 'replace')
env = {}
for line in raw.splitlines():
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip("'\"")

ym = json.load(open(os.path.join(EN, 'ym_orgs_engels.json'), encoding='utf-8'))
gis = json.load(open(os.path.join(EN, 'gis_firms_engels.json'), encoding='utf-8'))

conn = psycopg2.connect(
    host=env['DB_HOST'], port=int(env['DB_PORT']), dbname=env['DB_NAME'],
    user=env['DB_USER'], password=env['DB_PASSWORD'], client_encoding='UTF8',
)
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cur.execute(
    """
    SELECT code_oo, name, name_full, address, site, phone, latitude, longitude
    FROM sa.institution
    WHERE city = %s AND kind = %s
    ORDER BY code_oo
    """,
    ('Энгельс', 'general'),
)
rows = cur.fetchall()

out = []
for r in rows:
    code = r['code_oo']
    orgs = ym.get(str(code)) or []
    firms = gis.get(str(code)) or []
    site = r['site'] or ''
    if site.startswith('//'):
        site = 'https:' + site
    out.append({
        'school_id': 100000 + code,
        'code_oo': code,
        'name_full': r['name_full'] or r['name'],
        'name_short': r['name'],
        'city': 'Энгельс',
        'ownership': 'public',
        'address': r['address'],
        'site': site or None,
        'link_yandex': f"https://yandex.ru/maps/org/{orgs[0][0]}/{orgs[0][1]}/" if orgs else None,
        'link_2gis': firms[0] if firms else None,
        'latitude': r['latitude'],
        'longitude': r['longitude'],
    })

json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('schools:', len(out))
print('with coords:', sum(1 for x in out if x['latitude']))
print('with yandex:', sum(1 for x in out if x['link_yandex']))
print('with 2gis:', sum(1 for x in out if x['link_2gis']))
conn.close()
