#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

# ---------- настройки ----------
CURRENT_DIR = Path(__file__).parent
PD_ROOT = CURRENT_DIR.parent
PARSING_ROOT = PD_ROOT.parent
DATA_DIR = PD_ROOT / 'pd_data' / 'pd_output'
FILES = {
    'yandex': PARSING_ROOT / 'yandex_maps' / 'ym_data' / 'ym_output' / 'ym_full_school_data.json',
    '2gis': PARSING_ROOT / '2gis' / '2gis_data' / 'tgis_output' / '2gis_all_school_with_info.json'
}
OUT_FILE = DATA_DIR / 'gold_school_data.json'
# --------------------------------

RE_MOVER = re.compile(r'\b(моу|маоу|гоу|гбоу|фгоу|фгбоу|чоу|аноо|мкоу|мбоу|гапоу|гаоу|мау)\b', re.I)

def norm(s: str) -> str:
    """Привести строку к нижнему регистру без лишних пробелов и без МОУ/МАОУ/…"""
    if not s:
        return ''
    s = RE_MOVER.sub(' ', s)          # вырезаем тип учреждения
    s = re.sub(r'[^а-яё0-9\s]', ' ', s)  # оставляем только русские буквы и цифры
    return re.sub(r'\s+', ' ', s).strip().lower()

def norm_addr(raw: str) -> str:
    """Унифицировать адрес: убрать «Саратов,», «Саратовская обл.», индексы, лишние пробелы."""
    if not raw:
        return ''
    # вырезаем всё, что в скобках, и индексы
    raw = re.sub(r'\([^)]*\)', ' ', raw)
    raw = re.sub(r'\b\d{6}\b', ' ', raw)
    raw = re.sub(r'\b(саратовская\s+область|саратовская\s+обл\.?)\b', ' ', raw, flags=re.I)
    raw = re.sub(r'\b(г\.?|город)\s+саратов\b', ' ', raw, flags=re.I)
    raw = re.sub(r'[^а-яё0-9\s]', ' ', raw)
    return re.sub(r'\s+', ' ', raw).strip().lower()

def load_yandex(path: Path) -> List[Dict]:
    with open(path, encoding='utf-8') as f:
        data = json.load(f)['data']
    out = []
    for it in data:
        out.append({
            'name': it['name'],
            'adress': it['adres'],
            'norm_name': norm(it['name']),
            'norm_addr': norm_addr(it['adres']),
            'url': it['url'],
            'source': 'yandex'
        })
    return out

def load_2gis(path: Path) -> List[Dict]:
    with open(path, encoding='utf-8') as f:
        data = json.load(f)['data']
    out = []
    for it in data:
        addr = it.get('adres_part2') or it.get('adres') or ''
        out.append({
            'name': it['name'],
            'adress': addr,
            'norm_name': norm(it['name']),
            'norm_addr': norm_addr(addr),
            'url': it['url'],
            'source': '2gis'
        })
    return out

def merge(ya: List[Dict], dg: List[Dict]) -> List[Dict]:
    """Склеиваем по адресу или по названию+городу."""
    # ключ -> список записей
    by_addr: Dict[str, List[Dict]] = {}
    by_name: Dict[str, List[Dict]] = {}

    def _add(rec):
        by_addr.setdefault(rec['norm_addr'], []).append(rec)
        by_name.setdefault(rec['norm_name'] + '|саратов', []).append(rec)

    for rec in ya + dg:
        _add(rec)

    used = set()
    result: List[Dict] = []

    def _pick(key, bucket):
        """Берём первую неиспользованную запись из bucket и помечаем все с этим ключом как used."""
        for rec in bucket:
            uid = (rec['source'], rec['url'])
            if uid not in used:
                used.add(uid)
                return rec
        return None

    # 1) сначала объединяем по адресу
    for key, bucket in by_addr.items():
        if len(bucket) < 2:
            continue
        ya_rec = next((r for r in bucket if r['source'] == 'yandex'), None)
        dg_rec = next((r for r in bucket if r['source'] == '2gis'), None)
        if ya_rec and dg_rec:
            used.add((ya_rec['source'], ya_rec['url']))
            used.add((dg_rec['source'], dg_rec['url']))
            # Используем название из 2ГИС как основное (или более полное)
            name = dg_rec['name'] if len(dg_rec['name']) >= len(ya_rec['name']) else ya_rec['name']
            # Используем адрес из 2ГИС как основной
            address = dg_rec['adress'] if dg_rec['adress'] else ya_rec['adress']
            result.append({
                'id': len(result) + 1,
                'name': name,
                'adress': address,
                'source': {
                    'yandex_maps_url': ya_rec['url'],
                    '2gis_url': dg_rec['url']
                }
            })

    # 2) остальные «одиночки» и несовпавшие добавляем по name
    for key, bucket in by_name.items():
        for rec in bucket:
            uid = (rec['source'], rec['url'])
            if uid in used:
                continue
            used.add(uid)
            src = {}
            if rec['source'] == 'yandex':
                src['yandex_maps_url'] = rec['url']
            else:
                src['2gis_url'] = rec['url']
            result.append({
                'id': len(result) + 1,
                'name': rec['name'],
                'adress': rec['adress'],
                'source': src
            })
    return result

def main():
    ya = load_yandex(FILES['yandex'])
    dg = load_2gis(FILES['2gis'])
    merged = merge(ya, dg)
    
    # Создаем структуру согласно формату gold_school_data.json
    result = {
        'topic': 'Школы Саратова',
        'total_elements': len(merged),
        'data': merged
    }
    
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    print(f'Слияние завершено. Всего записей: {len(merged)}. Результат в {OUT_FILE}')

if __name__ == '__main__':
    main()