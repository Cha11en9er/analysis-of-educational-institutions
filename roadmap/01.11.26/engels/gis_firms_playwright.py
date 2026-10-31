#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сбор firm-ссылок 2ГИС для школ Энгельса через Playwright (chrome-канал).
Селениум-парсер 2ГИС заблокирован антиботом (страница-музей) — playwright+chrome проходит.
Запуск из корня репо: python roadmap/01.11.26/engels/gis_firms_playwright.py
"""
import json
import re
import time
from urllib.parse import quote

from playwright.sync_api import sync_playwright

schools = json.load(open('roadmap/01.11.26/engels/schools_rcoko.json', encoding='utf-8'))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.8078.76 Safari/537.36'

out = {}
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    ctx = browser.new_context(user_agent=UA, locale='ru-RU', viewport={'width': 1400, 'height': 900})
    page = ctx.new_page()
    for s in schools:
        code = s['code_oo']
        q = quote(s['name'][:70])
        url = f'https://2gis.ru/engels/search/{q}'
        firm = None
        try:
            page.goto(url, timeout=40000, wait_until='domcontentloaded')
            page.wait_for_timeout(4500)
            links = page.eval_on_selector_all(
                'a[href*="firm/"]', 'els => els.slice(0,3).map(a => a.href.split("?")[0])'
            )
            # берём первую firm-ссылку с городом Энгельс
            for l in links:
                if '/engels/firm/' in l:
                    firm = l
                    break
        except Exception as e:
            print('ERR', code, str(e)[:70], flush=True)
        out[str(code)] = firm
        print(code, s['name'][:42], '->', firm, flush=True)
        time.sleep(1.0)
    browser.close()

json.dump(out, open('roadmap/01.11.26/engels/gis_firms_engels.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
found = sum(1 for v in out.values() if v)
print('done. found:', found, '/', len(out))
