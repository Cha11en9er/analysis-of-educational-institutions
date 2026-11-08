#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Парсер отзывов 2ГИС через Playwright (chrome-канал, headless — антибот обходит).
Данные извлекаются из page-state (script-JSON), не из видимого текста.

Запуск: python roadmap/08.11.26/parse_2gis_playwright.py <url или firm_id> [out.json]
"""
import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.8078.76 Safari/537.36'

TEXT_RE = re.compile(r'"text"\s*:\s*"((?:\\.|[^"\\])+)"')
RATING_RE = re.compile(r'"rating"\s*:\s*(\d+)')
DATE_RE = re.compile(r'"date_created"\s*:\s*"([^"]{10,40})"')
ID_RE = re.compile(r'"id"\s*:\s*"(\d{8,20})"')


def unescape(s: str) -> str:
    try:
        return json.loads('"' + s + '"')
    except Exception:
        return s


def parse_reviews_from_state(html: str) -> list[dict]:
    chunks = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
    big = max(chunks, key=len)
    reviews = []
    for m in TEXT_RE.finditer(big):
        text = unescape(m.group(1))
        if len(text) < 10 or 'javascript' in m.group(0)[:30]:
            continue
        before = big[max(0, m.start() - 700):m.start()]
        rating_m = RATING_RE.search(before)
        date_m = DATE_RE.search(before)
        id_m = ID_RE.search(before)
        # отзыв подтверждён, только если это объект с provider 2gis/flamp рядом
        if '"provider"' not in before and '"official_answer"' not in before:
            continue
        reviews.append({
            'text': text,
            'rating': int(rating_m.group(1)) if rating_m else None,
            'date': date_m.group(1)[:10] if date_m else None,
            'review_id': id_m.group(1) if id_m else None,
        })
    return reviews


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else 'https://2gis.ru/engels/firm/6052240280256633'
    out = sys.argv[2] if len(sys.argv) > 2 else None
    if not url.startswith('http'):
        url = f'https://2gis.ru/engels/firm/{url}'

    with sync_playwright() as p:
        b = p.chromium.launch(channel='chrome', headless=True)
        ctx = b.new_context(user_agent=UA, locale='ru-RU', viewport={'width': 1400, 'height': 900})
        pg = ctx.new_page()
        pg.goto(url, timeout=40000, wait_until='domcontentloaded')
        pg.wait_for_timeout(12000)
        html = pg.content()
        b.close()

    reviews = parse_reviews_from_state(html)
    import html as H
    # карточка: имя из <title> («Отзывы о X - 2ГИС» / «X на карте»), рейтинг — среднее отзывов
    title_m = re.search(r'<title>([^<]+)</title>', html)
    name = None
    if title_m:
        t = H.unescape(title_m.group(1)).replace('&nbsp;', ' ')
        t = re.sub(r'^Отзывы о\s*', '', t)
        t = re.split(r'\s+-\s+2ГИС|\s+на карте', t)[0].strip()
        t = re.sub(r'\s*,\s*[^,]*улица.*$', '', t)  # убрать адресный хвост
        name = t or None
    card_rating = re.search(r'"rating"\s*:\s*"([\d],[\d])"', html)
    avg = None
    rated = [r['rating'] for r in reviews if r.get('rating')]
    if rated:
        avg = round(sum(rated) / len(rated), 1)
    addr_m = re.search(r'"address_name"\s*:\s*"([^"]{5,120})"', html)
    result = {
        'url': url,
        'name': name,
        'rating_2gis': float(card_rating.group(1).replace(',', '.')) if card_rating else avg,
        'address': addr_m.group(1) if addr_m else None,
        'reviews_count': len(reviews),
        'reviews': reviews,
    }
    if out:
        json.dump(result, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('name:', result['name'])
    print('rating_2gis:', result['rating_2gis'], '| address:', result['address'])
    print('reviews parsed:', len(reviews))
    for r in reviews[:3]:
        print(' ', r['rating'], r['date'], r['text'][:60])


if __name__ == '__main__':
    main()
