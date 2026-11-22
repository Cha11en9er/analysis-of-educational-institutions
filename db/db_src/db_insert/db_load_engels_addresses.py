#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Импорт зон прикрепления школ ЭНГЕЛЬСА из приказа №136-од (транскрипция) в
sa.address + sa.school_address. Геокодирование этих адресов — отдельным
дневным прогоном (город в запросе: Энгельс, не Саратов).

Входы:
  roadmap/01.11.26/engels/prikaz_136-od_city.json   — городские школы (улицы + дома)
  roadmap/01.11.26/engels/prikaz_136-od_sela.json   — сельские школы (населённые пункты)
  roadmap/01.11.26/engels/city_schools.json         — коды ОО ↔ school_id (100000+code_oo)

Запуск из корня репозитория (на сервере — в venv):
  python db/db_src/db_insert/db_load_engels_addresses.py
Идемпотентен: ON CONFLICT по address_key, связи — DO NOTHING.

Особенности формата приказа:
  - «все дома» / «от ул. X до ул. Y» / «чётная сторона…» — конкретных домов нет,
    такие улицы заводим одной записью с house_norm='*' (улица целиком, 1 геокод);
  - конкретные номера («№№ 185, 187, 189») — отдельная запись на дом;
  - сельские школы — запись на населённый пункт (house_norm='*').
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from psycopg2.extras import execute_batch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db_config_sa import get_connection  # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent.parent.parent
EN = PROJECT / "roadmap" / "01.11.26" / "engels"
CITY = "Энгельс"
DISTRICT = "Энгельсский"
SOURCE_YEAR = 2026

HOUSE_NUM_RE = re.compile(r"(?<![/\\w])(\d{1,4}[а-яА-Яa-z]?(?:/\d{1,3}[а-яА-Яa-z]?)?)(?![/\\w])")


def extract_houses(spec: str) -> list[str]:
    """Конкретные номера домов из формулировки приказа."""
    if not spec:
        return []
    low = spec.lower()
    # «все дома …» / диапазон «от … до …» / «сторона» — домов не выделено
    if 'все дома' in low or re.search(r'\bот\b.*\bдо\b', low) or 'сторона' in low:
        return []
    nums = []
    for m in HOUSE_NUM_RE.finditer(spec):
        tok = m.group(1)
        # отбрасываем номера, являющиеся частью диапазона «118-146»
        before = spec[max(0, m.start() - 4):m.start()]
        after = spec[m.end():m.end() + 5]
        if before.strip().endswith('-') or after.lstrip().startswith('-'):
            continue
        nums.append(tok)
    return nums


def norm_street(s: str) -> str:
    s = (s or '').strip()
    s = re.sub(r'\s*\(.*$', '', s).strip()
    return s


def main() -> None:
    city_json = json.loads((EN / "prikaz_136-od_city.json").read_text(encoding="utf-8"))
    sela_json = json.loads((EN / "prikaz_136-od_sela.json").read_text(encoding="utf-8"))
    catalog = json.loads((EN / "city_schools.json").read_text(encoding="utf-8"))

    # код ОО → school_id (100000+code_oo) по нормализованному имени
    def nkey(s: str) -> str:
        s = (s or '').lower().replace('ё', 'е')
        s = re.sub(r'[«»"\'`.,()№]', ' ', s)
        s = re.sub(r'\b(моу|маоу|гаоу|гбоу|сш|сош|оош|лицей|гимназ\w*)\b', ' ', s)
        s = re.sub(r'[^а-яa-z0-9]+', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    name2sid = {}
    for c in catalog:
        name2sid.setdefault(nkey(c['name_short']), 100000 + c['code_oo'])
        name2sid.setdefault(nkey(c['name_full']), 100000 + c['code_oo'])

    addr_rows: list[tuple] = []
    link_rows: list[tuple] = []
    unmatched: set[str] = set()

    def add(school_name: str, street: str, house: str) -> None:
        sid = name2sid.get(nkey(school_name))
        if sid is None:
            unmatched.add(school_name)
            return
        street_n = norm_street(street)
        if not street_n:
            return
        key = f"{DISTRICT}|{street_n}|{house}"
        addr_rows.append((CITY, DISTRICT, street_n, house, key))
        link_rows.append((sid, key, SOURCE_YEAR))

    # городские школы
    for sch in city_json['schools']:
        for st in sch['streets']:
            street = st['street']
            spec = st.get('houses') or ''
            nums = extract_houses(spec)
            if nums:
                for h in nums:
                    add(sch['name'], street, h)
            else:
                add(sch['name'], street, '*')

    # сельские школы: зона = населённый пункт
    for sch in sela_json['schools']:
        for place in sch['settlements']:
            add(sch['name'], place, '*')

    # уникальные адреса
    uniq: dict[str, tuple] = {}
    for r in addr_rows:
        uniq.setdefault(r[4], r)
    addr_list = list(uniq.values())
    links_uniq = {(sid, key): (sid, key, year) for sid, key, year in link_rows}
    print(f"Адресов: {len(addr_list)}, связей: {len(links_uniq)}, школ без сопоставления: {len(unmatched)}")
    for u in list(unmatched)[:6]:
        print('  ?', u)

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.address (
                        city, district, street_norm, house_norm, address_key, geocode_status
                    ) VALUES (%s,%s,%s,%s,%s,'pending')
                    ON CONFLICT (address_key) DO NOTHING
                    """,
                    addr_list,
                )
                cur.execute("SELECT address_id, address_key FROM sa.address")
                key2id = {k: i for i, k in cur.fetchall()}
                link_batch = [
                    (sid, key2id[key], year)
                    for (sid, key), (_, _, year) in links_uniq.items()
                    if key in key2id
                ]
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.school_address (school_id, address_id, source_year)
                    VALUES (%s,%s,%s)
                    ON CONFLICT (school_id, address_id) DO NOTHING
                    """,
                    link_batch,
                )
        print(f"Загружено адресов: {len(addr_list)}, связей: {len(link_batch)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
