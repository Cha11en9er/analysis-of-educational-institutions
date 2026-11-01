#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сбор рейтингов Яндекса для школ Энгельса: SSR org-страниц -> ratingValue + отзывы."""
import json, re, time, urllib.request

orgs = json.load(open('/tmp/ym_orgs_engels.json', encoding='utf-8'))
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36'}

out = {}
for code, orgs_list in orgs.items():
    if not orgs_list:
        continue
    slug, oid = orgs_list[0]
    url = f'https://yandex.ru/maps/org/{slug}/{oid}'
    rating = reviews = None
    try:
        req = urllib.request.Request(url, headers=UA)
        html = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
        m = re.search(r'ratingValue["\']?\s*[:=]\s*([\d.]+)', html)
        if m:
            rating = round(float(m.group(1)), 1)
        r = re.search(r'"(\d{1,4})"\s*,\s*"[а-я]*оценк', html) or re.search(
            r'(\d{1,4})\s*(?:оценк|отзыв)', html)
        if r:
            reviews = int(r.group(1))
    except Exception as e:
        print('ERR', code, str(e)[:60], flush=True)
    out[code] = {'rating': rating, 'reviews': reviews}
    print(code, '->', rating, reviews, flush=True)
    time.sleep(1.0)

json.dump(out, open('/tmp/ym_ratings_engels.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
got = sum(1 for v in out.values() if v.get('rating'))
print('ratings:', got, '/', len(out))
