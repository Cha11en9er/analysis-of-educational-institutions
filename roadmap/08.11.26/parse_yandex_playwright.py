#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Парсер отзывов Яндекс.Карт (org-страница /reviews/) через Playwright DOM.
Отзывы SSR-отрендерены в DOM (не state-JSON): рейтинг в aria-label звёзд,
текст в business-review-view__body.

Запуск: python roadmap/08.11.26/parse_yandex_playwright.py <org_url> [out.json]
"""
import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.8078.76 Safari/537.36'

JS_EXTRACT = r"""
() => {
  const reviews = [];
  // каждый отзыв: блок, содержащий business-review-view__rating
  document.querySelectorAll('.business-review-view__rating').forEach((ratingEl) => {
    const review = {};
    const aria = ratingEl.querySelector('[aria-label]');
    if (aria) {
      const m = aria.getAttribute('aria-label').match(/Оценка\s+(\d+)\s+Из\s+5/i);
      review.rating = m ? Number(m[1]) : null;
    }
    // поднимаемся к контейнеру отзыва (обычно 6-8 уровней до блока с текстом)
    let node = ratingEl.closest('section, article, li') || ratingEl.parentElement.parentElement;
    for (let i = 0; i < 5 && node; i++) {
      const text = node.querySelector('.business-review-view__body');
      if (text) break;
      node = node.parentElement;
    }
    const body = node ? node.querySelector('.business-review-view__body') : null;
    review.text = body ? body.innerText.trim() : null;
    const dateEl = node ? node.querySelector('.business-review-view__date') : null;
    review.date = dateEl ? dateEl.innerText.trim() : null;
    const authorEl = node ? node.querySelector('.business-review-view__author-name') : null;
    review.author = authorEl ? authorEl.innerText.trim() : null;
    if (review.text && review.text.length > 5) {
      reviews.push(review);
    }
  });
  return reviews;
}
"""

MONTHS = {
    'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
    'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
    'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12',
}


def iso_date(s: str):
    """«12 ноября 2026» -> 2026-11-12; «12 ноября» -> (год не указан, берём 2026)."""
    m = re.search(r'(\d{1,2})\s+([а-яё]+)\s*,?\s*(\d{4})?', (s or '').lower())
    if not m:
        return None
    day, mon, year = m.group(1).zfill(2), MONTHS.get(m.group(2)), m.group(3)
    if not mon:
        return None
    return f"{year or '2026'}-{mon}-{day}"


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else \
        'https://yandex.ru/maps/org/srednyaya_obshcheobrazovatelnaya_shkola_33_imeni_p_a_stolypina/1010497567/reviews/'
    out = sys.argv[2] if len(sys.argv) > 2 else None

    with sync_playwright() as p:
        b = p.chromium.launch(channel='chrome', headless=True)
        ctx = b.new_context(user_agent=UA, locale='ru-RU', viewport={'width': 1400, 'height': 900})
        pg = ctx.new_page()
        pg.goto(url, timeout=40000, wait_until='domcontentloaded')
        pg.wait_for_timeout(9000)
        # прокрутка: подгрузка следующих отзывов (лениво по 10)
        last_count = 0
        same = 0
        for _ in range(30):
            pg.mouse.wheel(0, 2500)
            pg.wait_for_timeout(1200)
            cnt = pg.evaluate("() => document.querySelectorAll('.business-review-view__rating').length")
            if cnt == last_count:
                same += 1
                if same >= 3:
                    break
            else:
                same = 0
                last_count = cnt
        reviews_raw = pg.evaluate(JS_EXTRACT)
        b.close()

    reviews = []
    for r in reviews_raw:
        reviews.append({
            'text': r.get('text'),
            'rating': r.get('rating'),
            'date': iso_date(r.get('date')),
            'date_raw': r.get('date'),
            'author': r.get('author'),
        })
    # дедуп по тексту (соседние организации тоже имеют rating-блоки — фильтр по дате/автору)
    seen, uniq = set(), []
    for r in reviews:
        key = (r['text'] or '')[:80]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    result = {'url': url, 'reviews_count': len(uniq), 'reviews': uniq}
    if out:
        json.dump(result, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('reviews:', len(uniq))
    for r in uniq[:4]:
        print(' ', r['rating'], r['date'], (r['text'] or '')[:60].replace(chr(10), ' '))


if __name__ == '__main__':
    main()
