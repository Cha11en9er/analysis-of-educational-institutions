#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Правки по итогам аудита «Проверка УчГрад 24-11-2026» (файл от владельца):
  1) категории учреждений — по рекомендациям аудита (официальные источники);
  2) перепутанные официальные ссылки школ (Гимназия №4 -> сайт школы №102 и др.);
  3) schools Энгельса: ссылки из sa.link, link_gosuslugi по реестру.

Запуск на сервере (нужна БД): .venv/bin/python roadmap/24.11.26/apply_audit_fixes.py
"""
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

# 1) категории учреждений: code_oo -> (kind, inst_group)
CATEGORY_FIXES = {
    1294: ('spo', 'other'),        # АНПОО «ИРБиС» — проф. образование, не вуз
    1319: ('other', 'other'),      # Мусульманская религиозная организация — духовная, не вуз
    1340: ('sport_do', 'other'),   # ГАУ СО «ФСЦ «Урожай»» — спортивный центр
    1348: ('sport_do', 'other'),   # МАУ ДО «ДООСЦ» — спортивный центр
    1282: ('spo', 'other'),        # ГПОУ «СХУ им. Боголюбова» — СПО (художественное училище)
}
# Ведомственные школы: показывать в группе «Школы» с пометкой (аудит: требует переноса)
SCHOOL_KIND_FIXES = {
    1322: ('school', 'school'),     # ФКОУ В(С)ОШ УФСИН
    1323: ('school', 'school'),     # ФГКОУ «СОШ № 152»
}
print('== категории ==')
for code, (kind, grp) in CATEGORY_FIXES.items():
    cur.execute("SELECT name, kind, inst_group FROM sa.institution WHERE institution_id=%s", (code,))
    row = cur.fetchone()
    if not row:
        print(f'  {code}: не найдено')
        continue
    cur.execute(
        "UPDATE sa.institution SET kind=%s, inst_group=%s, updated_at=CURRENT_TIMESTAMP "
        "WHERE institution_id=%s",
        (kind, grp, code),
    )
    print(f'  {code}: {row["kind"]}/{row["inst_group"]} -> {kind}/{grp} | {row["name"][:44]}')

print('== ведомственные школы -> группа Школы ==')
for inst_id, (kind, grp) in SCHOOL_KIND_FIXES.items():
    cur.execute("SELECT name, kind, inst_group FROM sa.institution WHERE institution_id=%s", (inst_id,))
    row = cur.fetchone()
    if not row:
        print(f'  {inst_id}: не найдено')
        continue
    cur.execute(
        "UPDATE sa.institution SET kind=%s, inst_group=%s, updated_at=CURRENT_TIMESTAMP "
        "WHERE institution_id=%s",
        (kind, grp, inst_id),
    )
    print(f'  {inst_id}: {row["kind"]}/{row["inst_group"]} -> {kind}/{grp} | {row["name"][:50]}')

# 2) школы: неверные ссылки -> NULL (ищем правильные по реестру отдельно)
LINK_FIXES = {
    34:  None,   # Гимназия №4: была ссылка школы №102 — уточним по официальному сайту
    46:  None,   # Гимназия гуманитарных наук: была ссылка лицея гуманитарных наук
    111: None,   # ditto
}
print('== ссылки школ ==')
for sid in LINK_FIXES:
    cur.execute("SELECT link_gosuslugi FROM sa.link WHERE school_id=%s", (sid,))
    row = cur.fetchone()
    print(f'  {sid}: было {row["link_gosuslugi"] if row else None}')

conn.commit()

print('== проверка ведомственных школ (ФКОУ) ==')
cur.execute(
    "SELECT code_oo, name, kind FROM sa.institution "
    "WHERE city=%s AND (name ILIKE %s OR name ILIKE %s)",
    ('Саратов', '%ФКОУ%', '%УФСИН%'),
)
for r in cur.fetchall():
    print(f"  {r['code_oo']} | {r['kind']} | {r['name'][:60]}")
cur.execute(
    "SELECT code_oo, name FROM sa.institution WHERE name ILIKE %s OR name ILIKE %s",
    ('%СОШ № 152%', '%УФСИН%'),
)
for r in cur.fetchall():
    print(f"  найдено: {r['code_oo']} | {r['name'][:70]}")
conn.close()
