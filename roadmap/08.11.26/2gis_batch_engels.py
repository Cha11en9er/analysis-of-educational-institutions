#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Батч-сбор отзывов и рейтингов 2ГИС для всех школ Энгельса (playwright, headless).
Выход: roadmap/08.11.26/engels/2gis_reviews_engels.json {code_oo: {name, rating, reviews[]}}.
"""
import json
import re
import time

from playwright.sync_api import sync_playwright

import os
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '2gis_reviews_engels.json')
firms = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '01.11.26', 'engels', 'gis_firms_engels.json'), encoding='utf-8'))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.8078.76 Safari/537.36'

TEXT_RE = re.compile(r'"text"\s*:\s*"((?:\\.|[^"\\])+)"')
RATING_RE = re.compile(r'"rating"\s*:\s*(\d+)')
DATE_RE = re.compile(r'"date_created"\s*:\s*"([^"]{10,40})"')
ID_RE = re.compile(r'"id"\s*:\s*"(\d{8,20})"')


def unescape(s):
    try:
        return json.loads('"' + s + '"')
    except Exception:
        return s


def parse_page(html):
    chunks = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
    big = max(chunks, key=len)
    reviews = []
    for m in TEXT_RE.finditer(big):
        text = unescape(m.group(1))
        before = big[max(0, m.start() - 700):m.start()]
        if '"provider"' not in before and '"official_answer"' not in before:
            continue
        rating_m = RATING_RE.search(before)
        date_m = DATE_RE.search(before)
        id_m = ID_RE.search(before)
        reviews.append({
            'text': text,
            'rating': int(rating_m.group(1)) if rating_m else None,
            'date': date_m.group(1)[:10] if date_m else None,
            'review_id': id_m.group(1) if id_m else None,
        })
    return reviews


def card_fields(html):
    title_m = re.search(r'<title>([^<]+)</title>', html)
    name = None
    if title_m:
        t = title_m.group(1).replace('&nbsp;', ' ')
        t = re.sub(r'^Отзывы о\s*', '', t)
        t = re.split(r'\s+-\s+2ГИС|\s+на карте', t)[0].strip()
        t = re.sub(r'\s*,\s*[^,]*улица.*$', '', t)
        name = t or None
    rating_m = re.search(r'"rating"\s*:\s*"([\d],[\d])"', html)
    addr_m = re.search(r'"address_name"\s*:\s*"([^"]{5,120})"', html)
    return name, rating_m, addr_m


out = {}
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=True)
    ctx = b.new_context(user_agent=UA, locale='ru-RU', viewport={'width': 1400, 'height': 900})
    pg = ctx.new_page()
    done = 0
    for code, url in firms.items():
        if not url:
            out[str(code)] = {'firm': None, 'rating': None, 'reviews': []}
            continue
        name = rating = address = None
        reviews = []
        for attempt in (1, 2):
            try:
                pg.goto(url, timeout=40000, wait_until='domcontentloaded')
                pg.wait_for_timeout(9000)
                html = pg.content()
                reviews = parse_page(html)
                name, rating_m, addr_m = card_fields(html)
                rating = float(rating_m.group(1).replace(',', '.')) if rating_m else None
                address = addr_m.group(1) if addr_m else None
                break
            except Exception as e:
                print('ERR', code, 'attempt', attempt, str(e)[:60], flush=True)
                time.sleep(3)
        out[str(code)] = {
            'firm': url,
            'name': name,
            'address': address,
            'rating': rating,
            'reviews_count': len(reviews),
            'reviews': reviews,
        }
        done += 1
        print(f'{done}/45 {code} {name[:40] if name else "?"} rev={len(reviews)} rating={rating}', flush=True)
        time.sleep(1.2)
    b.close()

json.dump(out, open(OUT_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
total_reviews = sum(len(v['reviews']) for v in out.values())
rated = sum(1 for v in out.values() if v.get('rating'))
print(f'DONE: школ {len(out)}, школ с рейтингом {rated}, всего отзывов {total_reviews}')
