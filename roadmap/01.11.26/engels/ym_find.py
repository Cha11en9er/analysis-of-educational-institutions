#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Поиск org-ссылок Яндекс.Карт для школ Энгельса через SSR поисковой выдачи карт."""
import json, re, time, urllib.request, urllib.parse, html as H

schools = json.load(open('/tmp/engels_schools.json', encoding='utf-8'))
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36'}
GEOID = '11147'  # Энгельс

def search(name):
    q = urllib.parse.quote(name)
    url = f'https://yandex.ru/maps/{GEOID}/engels/search/{q}'
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode('utf-8', 'ignore')
    orgs = re.findall(r'org/([a-z0-9_]+)/(\d{9,12})', H.unescape(html))
    return orgs

out = {}
for s in schools:
    num = s['code_oo']
    name = s['name']
    try:
        orgs = search(name)
    except Exception as e:
        orgs = []
        print('ERR', num, str(e)[:60], flush=True)
    out[str(num)] = orgs[:3]
    print(num, name[:45], '->', orgs[:2], flush=True)
    time.sleep(1.2)

json.dump(out, open('/tmp/ym_orgs_engels.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('done', len(out))
