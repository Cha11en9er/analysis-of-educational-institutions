#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Батч-сбор отзывов Яндекс.Карт для школ Энгельса (playwright, DOM-SSR).
Вход: roadmap/01.11.26/engels/ym_orgs_engels.json (code_oo -> [slug, org_id])
Выход: roadmap/08.11.26/engels/ym_reviews_engels.json
"""
import json
import os
import re
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.8078.76 Safari/537.36'

MONTHS = {
    'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
    'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
    'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12',
}

JS_EXTRACT = r"""
() => {
  const reviews = [];
  document.querySelectorAll('.business-review-view__rating').forEach((ratingEl) => {
    const review = {};
    const aria = ratingEl.querySelector('[aria-label]');
    if (aria) {
      const m = aria.getAttribute('aria-label').match(/Оценка\s+(\d+)\s+Из\s+5/i);
      review.rating = m ? Number(m[1]) : null;
    }
    let node = ratingEl.closest('section, article, li') || ratingEl.parentElement.parentElement;
    for (let i = 0; i < 5 && node; i++) {
      if (node.querySelector('.business-review-view__body')) break;
      node = node.parentElement;
    }
    const body = node ? node.querySelector('.business-review-view__body') : null;
    review.text = body ? body.innerText.trim() : null;
    const dateEl = node ? node.querySelector('.business-review-view__date') : null;
    review.date = dateEl ? dateEl.innerText.trim() : null;
    const authorEl = node ? node.querySelector('.business-review-view__author-name') : null;
    review.author = authorEl ? authorEl.innerText.trim() : null;
    if (review.text && review.text.length > 5) reviews.push(review);
  });
  return reviews;
}
"""


def iso_date(s):
    m = re.search(r'(\d{1,2})\s+([а-яё]+)\s*,?\s*(\d{4})?', (s or '').lower())
    if not m:
        return None
    mon = MONTHS.get(m.group(2))
    if not mon:
        return None
    return f"{m.group(3) or '2026'}-{mon}-{m.group(1).zfill(2)}"


def main():
    orgs = json.load(open(os.path.join(HERE, '..', '01.11.26', 'engels', 'ym_orgs_engels.json'), encoding='utf-8'))
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel='chrome', headless=True)
        ctx = b.new_context(user_agent=UA, locale='ru-RU', viewport={'width': 1400, 'height': 900})
        pg = ctx.new_page()
        done = 0
        for code, org in orgs.items():
            if not org:
                out[str(code)] = {'reviews': []}
                continue
            slug, oid = org[0]  # org — список пар (slug, org_id)
            url = f'https://yandex.ru/maps/org/{slug}/{oid}/reviews/'
            reviews = []
            for attempt in (1, 2):
                try:
                    pg.goto(url, timeout=40000, wait_until='domcontentloaded')
                    pg.wait_for_timeout(7000)
                    last, same = 0, 0
                    for _ in range(25):
                        pg.mouse.wheel(0, 3000)
                        pg.wait_for_timeout(900)
                        cnt = pg.evaluate("() => document.querySelectorAll('.business-review-view__rating').length")
                        if cnt == last:
                            same += 1
                            if same >= 3:
                                break
                        else:
                            same, last = 0, cnt
                    raw = pg.evaluate(JS_EXTRACT)
                    reviews = [{
                        'text': r.get('text'),
                        'rating': r.get('rating'),
                        'date': iso_date(r.get('date')),
                        'date_raw': r.get('date'),
                        'author': r.get('author'),
                    } for r in raw if r.get('text')]
                    # дедуп
                    seen, uniq = set(), []
                    for r in reviews:
                        k = (r['text'] or '')[:80]
                        if k not in seen:
                            seen.add(k)
                            uniq.append(r)
                    reviews = uniq
                    break
                except Exception as e:
                    print('ERR', code, 'try', attempt, str(e)[:60], flush=True)
                    time.sleep(3)
            out[str(code)] = {'org_url': url, 'reviews': reviews}
            done += 1
            print(f'{done}/{len(orgs)} {code} rev={len(reviews)}', flush=True)
            time.sleep(1.0)
        b.close()

    path = os.path.join(HERE, 'engels', 'ym_reviews_engels.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('DONE: schools', len(out), 'reviews', sum(len(v['reviews']) for v in out.values()))


if __name__ == '__main__':
    main()
