#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сбор каталога ОО sarrcoko.ru (запускать с RU-IP, напр. на сервере uchgrad-vps)."""
import re, json, time, urllib.request

BASE = 'https://sarrcoko.ru'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36'}
MUPS = list(range(201, 260))

def get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode('utf-8', 'ignore')
        except Exception as e:
            if i == retries - 1:
                print('FAIL', url, e, flush=True)
                return ''
            time.sleep(2)

def clean(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s or '')).strip()

CARD_RE = re.compile(
    r'<b class="card-title h3 col-9">(.*?)</b>.*?'
    r'<div class="ribbon bg-\w+ text-lg">\s*(\d{6})\s*</div>(.*?)(?=<!-- /.card -->|Profile Image|$)',
    re.S)

FIELD = lambda icon: re.compile(
    r'fa-' + icon + r'[^>]*></i>(?:</strong>)?\s*<b class="text-muted">(.*?)</b>', re.S)

orgs = {}
for mup in MUPS:
    html = get(f'{BASE}/catalog/?mup={mup}')
    if not html:
        continue
    found = 0
    for m in CARD_RE.finditer(html):
        name_short, code, body = m.group(1), int(m.group(2)), m.group(3)
        director = clean(FIELD('book').search(body).group(1)) if FIELD('book').search(body) else None
        phone_m = re.search(r'href="tel:([^"]+)"', body)
        site_m = re.search(r'fa-link.*?<a class="text-muted" href="([^"]+)"', body, re.S)
        addr_m = FIELD('building').search(body)
        full_m = FIELD('signature').search(body)
        docs = [
            {'url': BASE + d[0], 'title': clean(d[1])}
            for d in re.findall(r'href="(/razbor_catalog/[^"]+|/reports_rgi/\?[^"]*oo=\d+[^"]*)"[^>]*>(.*?)</a>', body, re.S)
        ]
        orgs[code] = {
            'code_oo': code,
            'name_short': clean(name_short),
            'name_full': clean(full_m.group(1)) if full_m else None,
            'director': director,
            'phone': phone_m.group(1) if phone_m else None,
            'site': site_m.group(1) if site_m else None,
            'address': clean(addr_m.group(1)) if addr_m else None,
            'docs': docs,
        }
        found += 1
    print('mup', mup, 'found', found, 'total', len(orgs), flush=True)

json.dump(list(orgs.values()), open('/tmp/rcoko_orgs.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('TOTAL:', len(orgs))
