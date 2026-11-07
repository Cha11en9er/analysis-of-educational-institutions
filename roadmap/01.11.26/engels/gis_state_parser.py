#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Рейтинги 2ГИС школ Энгельса: firm-страница в playwright, данные берём из state-JSON
(script в HTML), не из видимого текста (текст рендерится шрифтом-заглушкой)."""
import json
import re
import time

from playwright.sync_api import sync_playwright

firms = json.load(open('roadmap/01.11.26/engels/gis_firms_engels.json', encoding='utf-8'))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.8078.76 Safari/537.36'

out = {}
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    ctx = browser.new_context(user_agent=UA, locale='ru-RU', viewport={'width': 1400, 'height': 900})
    page = ctx.new_page()
    for code, url in firms.items():
        if not url:
            continue
        firm_id = url.rstrip('/').split('/')[-1]
        rating = name = address = None
        try:
            page.goto(url, timeout=40000, wait_until='domcontentloaded')
            page.wait_for_timeout(9000)
            html = page.content()
            chunks = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
            big = max(chunks, key=len) if chunks else ''
            # данные основной карточки: объект с "id":"<firm_id>"
            pat = re.compile(r'"id"\s*:\s*"' + re.escape(firm_id) + r'"(.{0,4000}?)("adm_div")', re.S)
            m = pat.search(big)
            seg = m.group(1) if m else ''
            def field(f):
                mm = re.search('"' + f + r'"\s*:\s*"?(?:([\d,.]+)|([^"]{1,120}))"?', seg)
                return (mm.group(1) or mm.group(2)) if mm else None
            rating = field('rating')
            if rating:
                rating = float(rating.replace(',', '.'))
            name = field('name')
            address = field('address_name')
        except Exception as e:
            print('ERR', code, str(e)[:60], flush=True)
        out[str(code)] = {'firm_id': firm_id, 'rating': rating, 'name': name, 'address': address}
        print(code, '->', rating, (name or '')[:40], flush=True)
        time.sleep(1.0)
    browser.close()

json.dump(out, open('roadmap/01.11.26/engels/gis_ratings_state.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
got = sum(1 for v in out.values() if v.get('rating'))
print('2gis ratings:', got, '/', len(out))
