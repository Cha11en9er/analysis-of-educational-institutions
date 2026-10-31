#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сбор рейтингов 2ГИС со карточек школ Энгельса (playwright, chrome-канал)."""
import json
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
        rating = None; reviews = None
        try:
            page.goto(url, timeout=40000, wait_until='domcontentloaded')
            page.wait_for_timeout(4000)
            # рейтинг: элемент с числом вида 4,5 рядом со звёздами/отзывами
            try:
                rating = page.eval_on_selector(
                    '[data-test*="rating"], [class*="rating"] [itemprop="ratingValue"], span[class*="_1lmxa"]',
                    'el => el.textContent.trim()')
            except Exception:
                rating = None
            if not rating:
                m = page.inner_text('body')
                import re
                mm = re.search(r'(\d[,.]\d)\s*\n?\s*(\d+\s*отзыв', m)
                if mm:
                    rating = mm.group(1).replace(',', '.'); reviews = mm.group(2)
            print(code, '->', rating, reviews, flush=True)
        except Exception as e:
            print('ERR', code, str(e)[:60], flush=True)
        out[code] = {'rating': rating, 'reviews': reviews}
        time.sleep(0.8)
    browser.close()

json.dump(out, open('roadmap/01.11.26/engels/gis_ratings_engels.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
got = sum(1 for v in out.values() if v.get('rating'))
print('ratings found:', got, '/', len(out))
