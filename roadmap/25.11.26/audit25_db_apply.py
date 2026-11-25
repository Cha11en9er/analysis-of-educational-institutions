#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Правки БД по комплексному аудиту 25.11.2026 (forum/УчГрад_комплексный_аудит_25-11-2026.xlsx).

Волна A (данные):
  CAT-01/02/03/04 — 21 учреждение вне каталога образования (флаг catalog_excluded);
  GEO-01          — ДШИ Мокроус (1373) выведена из выборки Энгельса;
  VUZ-01          — адреса/названия/сайты вузов по официальным реквизитам аудита;
  UX-08           — схема сайта центра допризывной подготовки;
  FACT-05         — link_gosuslugi «нету в excel» -> NULL (школы 49, 66);
  FACT-04         — Аврора (165): официальная ссылка вместо сайта школы № 8;
  UX-06           — декодирование HTML-сущностей в названиях учреждений;
  FACT-01/02      — школа № 30 Энгельса: ЕГЭ 62.82/2026, поступление 91.67%/2026;
  FACT-06         — школа № 3 Энгельса: ЕГЭ без года снят с карточки;
  FACT-03         — добавлены опубликованные ЕГЭ/поступление по школам Энгельса
                    (построчные значения аудита), итог пересчитан по формуле
                    (ЕГЭ + поступление/10 + прочие компоненты строки).

Запуск на сервере: .venv/bin/python roadmap/25.11.26/audit25_db_apply.py
"""
import html
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


def one(sql, args=()):
    cur.execute(sql, args)
    return cur.fetchone()


def run(sql, args=()):
    cur.execute(sql, args)


# ---------- 1. флаг исключения из каталога ----------
run("""
    ALTER TABLE sa.institution ADD COLUMN IF NOT EXISTS catalog_excluded BOOLEAN NOT NULL DEFAULT FALSE;
    ALTER TABLE sa.institution ADD COLUMN IF NOT EXISTS exclusion_reason TEXT;
""")

EXCLUSIONS = {
    # медицинские организации — вне каталога образования (CAT-01)
    1337: 'Медицинская организация (диспансер) — вне каталога образования',
    1342: 'Медицинская организация (больница) — вне каталога образования',
    1347: 'Медицинская организация (дом ребёнка) — вне каталога образования',
    1355: 'Медицинская организация (больница) — вне каталога образования',
    1356: 'Медицинская организация (диспансер) — вне каталога образования',
    1357: 'Медицинская организация (больница) — вне каталога образования',
    1358: 'Медицинская организация (больница) — вне каталога образования',
    1359: 'Медицинская организация (санаторий) — вне каталога образования',
    1360: 'Медицинская организация (диспансер) — вне каталога образования',
    1374: 'Медицинская организация (клиника СГМУ) — вне каталога образования',
    # органы управления образованием/районами (CAT-02)
    786: 'Орган управления (департамент района)',
    957: 'Орган управления (комитет по образованию)',
    961: 'Орган управления (администрация района)',
    1033: 'Орган управления (администрация района)',
    1047: 'Орган управления (администрация района)',
    1083: 'Орган управления (администрация района)',
    1196: 'Орган управления (администрация района)',
    822: 'Орган управления (комитет по образованию Энгельса)',
    # режимные учреждения (CAT-03)
    1338: 'Режимное учреждение (ЦВСНП МВД) — вне каталога',
    1372: 'Режимное учреждение (СИЗО УФСИН) — вне каталога',
    # служба системы образования (CAT-04)
    821: 'Методический/оценочный центр системы образования',
}
print('== исключение из каталога (CAT-01/02/03/04) ==')
for iid, reason in EXCLUSIONS.items():
    run(
        "UPDATE sa.institution SET catalog_excluded=TRUE, exclusion_reason=%s, updated_at=CURRENT_TIMESTAMP "
        "WHERE institution_id=%s",
        (reason, iid),
    )
cur.execute("SELECT count(*) FROM sa.institution WHERE catalog_excluded")
print('  исключено:', cur.fetchone()[0])

# ---------- 2. GEO-01: Мокроус ----------
run("UPDATE sa.institution SET city='Мокроус', updated_at=CURRENT_TIMESTAMP WHERE institution_id=1373")
print('== 1373 Мокроус ->', one("SELECT city FROM sa.institution WHERE institution_id=1373")[0])

# ---------- 3. VUZ-01 / UX-08: реквизиты и сайты ----------
VUZ_FIXES = {
    1328: {
        'address': '410012, г. Саратов, пр-кт им. Петра Столыпина, д. 1',
    },
    1325: {
        'name': 'СВКИ войск национальной гвардии им. Ф.Э. Дзержинского',
        'name_full': 'Федеральное государственное казенное военное образовательное учреждение высшего образования '
                     '«Саратовский военный ордена Жукова Краснознаменный институт имени Ф.Э. Дзержинского '
                     'войск национальной гвардии Российской Федерации»',
        'address': '410012, г. Саратов, ул. Московская, д. 158',
    },
    1333: {
        'address': '410012, г. Саратов, ул. Астраханская, д. 83',
    },
    1326: {
        'address': '410028, Россия, г. Саратов, ул. им. Мичурина И.В., д. 92',
    },
    1327: {
        'name': 'Поволжский институт им. П.А. Столыпина (филиал РАНХиГС)',
        'address': '410012, г. Саратов, ул. Московская, д. 164, в/г 2',
    },
    1332: {
        'site': 'https://www.vavilovsar.ru',
    },
    1371: {
        'site': 'https://xn--64-6kc6a4adipd.xn--p1ai',
    },
}
print('== реквизиты вузов и сайтов (VUZ-01, UX-08) ==')
for iid, patch in VUZ_FIXES.items():
    row = one("SELECT name, address, site FROM sa.institution WHERE institution_id=%s", (iid,))
    if not row:
        print(f'  {iid}: не найдено')
        continue
    sets = ', '.join(f'{k}=%s' for k in patch)
    run(f"UPDATE sa.institution SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE institution_id=%s",
        (*patch.values(), iid))
    print(f"  {iid}: {row['name'][:38]} | {row['address']} -> {patch}")

# ---------- 4. UX-06: HTML-сущности в названиях ----------
cur.execute("SELECT institution_id, name, name_full FROM sa.institution "
            "WHERE name LIKE '%&%' OR name_full LIKE '%&%'")
fixed = 0
for r in cur.fetchall():
    new_name = html.unescape(r['name'] or '')
    new_full = html.unescape(r['name_full'] or '')
    if new_name != r['name'] or new_full != r['name_full']:
        run("UPDATE sa.institution SET name=%s, name_full=%s, updated_at=CURRENT_TIMESTAMP WHERE institution_id=%s",
            (new_name, new_full, r['institution_id']))
        fixed += 1
print('== декодировано названий (UX-06):', fixed)

# ---------- 5. FACT-05 / FACT-04: ссылки школ ----------
run("UPDATE sa.link SET link_gosuslugi=NULL WHERE school_id IN (49, 66) AND link_gosuslugi ILIKE %s",
    ('%нету%',))
run("UPDATE sa.link SET link_gosuslugi='https://avrora-sar.gosuslugi.ru/' WHERE school_id=165")
print('== ссылки школ обновлены (FACT-04/05) ==')

# ---------- 6. FACT-01/02/03/06: показатели школ Энгельса ----------
def adm_rating(percent):
    if percent is None:
        return None
    return round(float(percent) / 10.0, 2)


# (school_id, ege, ege_year, admission, adm_year, mode)
# mode: 'diff' — заменяем два компонента (пересчёт от старого итога),
#       'add'  — добавляем недостающие компоненты к старому итогу
EGE_UPDATES = [
    (338027, 62.82, 2026, 91.67, 2026, 'diff'),   # FACT-01/02
    (338363, None, None, None, None, 'drop_ege'),  # FACT-06: ЕГЭ без года
    (338023, 62.15, 2026, 92.3, 2025, 'add'),
    (338143, 64.89, 2026, 100.0, 2026, 'add'),
    (338183, 25.8, 2021, None, None, 'add'),
    (338193, 60.3, 2024, 100.0, 2024, 'add'),
    (338253, 61.0, 2026, 40.0, 2025, 'add'),
    (338283, 50.95, 2024, 76.9, 2024, 'add'),
    (338293, 56.0, 2025, 54.0, 2025, 'add'),
    (338303, 63.0, 2025, 82.0, 2025, 'add'),
    (338313, 65.0, 2026, 50.0, 2026, 'add'),
    (338353, 54.45, 2025, 89.0, 2025, 'add'),
    (351016, 73.5, 2024, 100.0, 2024, 'add'),
    (338123, None, None, 70.5, 2024, 'add'),
    (338273, None, None, 0.0, 2025, 'add'),
]
print('== показатели школ Энгельса (FACT-01/02/03/06) ==')
for sid, ege, ege_year, adm, adm_year, mode in EGE_UPDATES:
    row = one(
        "SELECT name_ym, rating_total, rating_ege, university_admission_percent "
        "FROM sa.school WHERE school_id=%s",
        (sid,),
    )
    if not row:
        print(f'  {sid}: не найдено')
        continue
    old_total = float(row['rating_total']) if row['rating_total'] is not None else None
    old_ege = float(row['rating_ege']) if row['rating_ege'] is not None else None
    old_adm = float(row['university_admission_percent']) if row['university_admission_percent'] is not None else None

    if mode == 'diff':
        new_total = old_total
        if old_total is not None:
            new_total = old_total
            if old_ege is not None:
                new_total -= old_ege
            if old_adm is not None:
                new_total -= adm_rating(old_adm)
            if ege is not None:
                new_total += ege
            if adm is not None:
                new_total += adm_rating(adm)
            new_total = round(new_total, 2)
        run(
            "UPDATE sa.school SET ege_average_score=%s, ege_year=%s, rating_ege=%s, "
            "university_admission_percent=%s, university_admission_year=%s, rating_total=%s, "
            "updated_at=CURRENT_TIMESTAMP WHERE school_id=%s",
            (ege, ege_year, ege, adm, adm_year, new_total, sid),
        )
    elif mode == 'drop_ege':
        new_total = old_total
        if old_total is not None and old_ege is not None:
            new_total = round(old_total - old_ege, 2)
        run(
            "UPDATE sa.school SET ege_average_score=NULL, ege_year=NULL, rating_ege=NULL, "
            "rating_total=%s, updated_at=CURRENT_TIMESTAMP WHERE school_id=%s",
            (new_total, sid),
        )
    else:  # add
        add_parts = []
        if ege is not None and old_ege is None:
            add_parts.append(ege)
        if adm is not None and old_adm is None:
            add_parts.append(adm_rating(adm))
        if ege is not None and old_ege is None:
            run("UPDATE sa.school SET ege_average_score=%s, ege_year=%s, rating_ege=%s WHERE school_id=%s",
                (ege, ege_year, ege, sid))
        if adm is not None and old_adm is None:
            run("UPDATE sa.school SET university_admission_percent=%s, university_admission_year=%s WHERE school_id=%s",
                (adm, adm_year, sid))
        # итог пересчитываем из фактических компонентов строки (ЕГЭ + поступление/10
        # + олимпиады/спорт/профили, если они есть в БД)
        fresh = one(
            "SELECT rating_ege, rating_olympiads, rating_sports_infrastructure, rating_profiles, "
            "university_admission_percent FROM sa.school WHERE school_id=%s",
            (sid,),
        )
        total = 0.0
        for v in (fresh['rating_ege'], fresh['rating_olympiads'],
                  fresh['rating_sports_infrastructure'], fresh['rating_profiles'],
                  adm_rating(fresh['university_admission_percent'])):
            if v is not None:
                total += float(v)
        new_total = round(total, 2)
        run("UPDATE sa.school SET rating_total=%s, updated_at=CURRENT_TIMESTAMP WHERE school_id=%s",
            (new_total, sid))
    print(f'  {sid} {str(row["name_ym"])[:30]:32} {mode:9} итог {old_total} -> {new_total}')

conn.commit()
conn.close()
print('Готово.')
