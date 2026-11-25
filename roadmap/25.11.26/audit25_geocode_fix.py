#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEO-02 (аудит 25.11): учреждения с одинаковыми координатами при разных адресах.

Сбрасывает координаты таких групп (кроме обоснованно совмещённых объектов в одном
здании с одним адресом-основанием) и заново геокодирует их адреса Яндекс-геокодером
(Referer: https://uchgrad.ru/, лимит учитывается в sa.geocode_log).

Запуск на сервере: .venv/bin/python roadmap/25.11.26/audit25_geocode_fix.py
"""
import json
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict

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

YANDEX_KEY = env.get('YANDEX_API_KEY') or os.environ.get('YANDEX_API_KEY')

conn = psycopg2.connect(
    host=env['DB_HOST'], port=int(env['DB_PORT']), dbname=env['DB_NAME'],
    user=env['DB_USER'], password=env['DB_PASSWORD'], client_encoding='UTF8',
)
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# ---------- 1. группы одинаковых точек при разных адресах ----------
cur.execute("""
    SELECT institution_id, name, address, latitude, longitude, city
    FROM sa.institution
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
""")
rows = cur.fetchall()
groups = defaultdict(list)
for r in rows:
    key = (round(float(r['latitude']), 5), round(float(r['longitude']), 5))
    groups[key].append(r)

def street_of(addr: str) -> str:
    # улица как грубый ключ: слова после "ул./улица/пр-кт" без номеров домов
    import re
    a = (addr or '').lower().replace('ё', 'е')
    a = re.sub(r'[0-9,\.()«»-]+', ' ', a)
    words = [w for w in a.split() if w not in {'г','с','п','д','зд','обл','район','ул','улица','проспект','пр','пркт'}]
    return ' '.join(words[:4])


targets = []
for key, items in groups.items():
    if len(items) < 2:
        continue
    # сбрасываем только группы, где адреса реально на разных улицах:
    # совпадение улицы (один корпус/комплекс) не трогаем
    streets = {street_of(i['address']) for i in items}
    if len(streets) > 1:
        targets.extend(items)

print(f'учреждений в конфликтных группах: {len(targets)}')

# ---------- 2. сброс координат (только необработанные группы) ----------
for r in targets:
    if r['latitude'] is not None:
        cur.execute(
            "UPDATE sa.institution SET latitude=NULL, longitude=NULL, geocode_status='pending', "
            "updated_at=CURRENT_TIMESTAMP WHERE institution_id=%s",
            (r['institution_id'],),
        )
        print(f"  сброшены координаты: {r['institution_id']} {str(r['name'])[:40]} | {r['address']}")
conn.commit()

# ---------- 3. повторное геокодирование: сброшенные ранее и новые ----------
cur.execute(
    "SELECT institution_id, name, address, city FROM sa.institution "
    "WHERE geocode_status='pending' AND latitude IS NULL"
)
targets = cur.fetchall()
def geocode(address: str):
    q = urllib.parse.quote(address)
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={YANDEX_KEY}&geocode={q}&format=json&results=1"
    req = urllib.request.Request(url, headers={'Referer': 'https://uchgrad.ru/', 'User-Agent': 'uchgrad-geocoder'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    obj = data['response']['GeoObjectCollection']['featureMember']
    if not obj:
        return None, None
    pos = obj[0]['GeoObject']['Point']['pos'].split()
    return float(pos[1]), float(pos[0])  # (lat, lon)


def log_spend(kind: str, ok_count: int = 1, fail_count: int = 0):
    cur.execute(
        "INSERT INTO sa.geocode_log (run_date, provider, requests, ok_count, fail_count, note) "
        "VALUES (CURRENT_DATE, %s, 1, %s, %s, %s)",
        ('yandex-http', ok_count, fail_count, kind),
    )


ok = fail = 0
for r in targets:
    addr = (r['address'] or '').strip()
    if not addr:
        continue
    query = f"Россия, {addr}"
    try:
        lat, lon = geocode(query)
    except Exception as e:
        print(f"  ошибка геокодера {r['institution_id']}: {str(e)[:60]}")
        fail += 1
        log_spend('institution-retry', 0, 1)
        time.sleep(0.4)
        continue
    log_spend('institution-retry')
    time.sleep(0.4)
    if lat is None:
        print(f"  не найдено: {r['institution_id']} {addr[:50]}")
        fail += 1
        continue
    cur.execute(
        "UPDATE sa.institution SET latitude=%s, longitude=%s, geocode_status='ok', "
        "updated_at=CURRENT_TIMESTAMP WHERE institution_id=%s",
        (lat, lon, r['institution_id']),
    )
    ok += 1
    print(f"  геокодировано: {r['institution_id']} {str(r['name'])[:34]:36} -> {lat:.6f},{lon:.6f}")

conn.commit()
print(f'готово: геокодировано {ok}, ошибок {fail}')
conn.close()
