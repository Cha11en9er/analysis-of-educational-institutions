#!/usr/bin/env python3
"""Сбор официальных категорий РЦОКО: код ОО -> категория (mup 249-259). Запуск на RU-сервере."""
import re, json, time, urllib.request

BASE = 'https://sarrcoko.ru'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36'}
CATS = {249: 'internat_cadet', 250: 'spo', 251: 'general', 252: 'chou_private',
        253: 'mo_defense', 254: 'vuz', 255: 'other', 256: 'medical', 257: 'sport_do',
        258: 'arts_do', 259: 'fsin'}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode('utf-8', 'ignore')

mapping = {}
for mup, kind in CATS.items():
    html = get(f'{BASE}/catalog/?mup={mup}')
    codes = set(re.findall(r'oo=(\d{6})', html)) | set(re.findall(r'/(\d{6})_thumbs\.jpg', html))
    for c in codes:
        mapping[c] = {'rcoko_category_mup': mup, 'rcoko_kind': kind}
    print(mup, kind, 'codes:', len(codes), 'total:', len(mapping), flush=True)
    time.sleep(0.6)

json.dump(mapping, open('/tmp/rcoko_categories.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('TOTAL:', len(mapping))
