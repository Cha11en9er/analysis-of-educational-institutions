#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сверка официальных ссылок школ (Госуслуги) с названием школы.
Для каждой школы: открыть link_gosuslugi, взять <title>/<h1> и сравнить с названием.
Результат: roadmap/24.11.26/link_check.json {school_id, name, url, page_title, ok, reason}

Запуск из корня репозитория:
  python roadmap/24.11.26/check_official_links.py
"""
import json
import os
import re
import time

from playwright.sync_api import sync_playwright

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.8078.76 Safari/537.36'
OUT = os.path.join(REPO, 'roadmap', '24.11.26', 'link_check.json')

TOKEN_RE = re.compile(r'[а-яёa-z0-9]+')


def tokens(s):
    return set(TOKEN_RE.findall((s or '').lower().replace('ё', 'е')))


STOP = {'муниципальное', 'муниципальное', 'образовательное', 'учреждение', 'общеобразовательная',
        'средняя', 'школа', 'номер', 'государственное', 'автономное', 'бюджетное',
        'саратов', 'области', 'российской', 'федерации', 'имени', 'город', 'г', 'с', 'по', 'на',
        'муниципальн', 'государственн', 'автономн', 'бюджетн', 'образовательн', 'общеобразовательн',
        'средне', 'обще', 'муниципальн', 'государственн', 'автономн', 'бюджетн', 'учреждение',
        'саратовской', 'российской', ' Федерации'}


def main():
    final = json.load(open(os.path.join(REPO, 'school_data', 'final_school_data.json'), encoding='utf-8'))
    engels_path = os.path.join(REPO, 'roadmap', '01.11.26', 'engels', 'city_schools.json')
    engels = json.load(open(engels_path, encoding='utf-8')) if os.path.exists(engels_path) else []

    targets = []
    for s in final:
        if s.get('link_gosuslugi'):
            targets.append({'school_id': s['id'], 'name': s.get('short_name') or s.get('name_2gis'),
                            'url': s['link_gosuslugi'], 'city': 'Саратов'})
    for s in engels:
        if s.get('site'):
            targets.append({'school_id': s['school_id'], 'name': s['name_short'],
                            'url': s['site'], 'city': 'Энгельс'})

    out = []
    done = 0
    with sync_playwright() as p:
        b = p.chromium.launch(channel='chrome', headless=True)
        ctx = b.new_context(user_agent=UA, locale='ru-RU')
        pg = ctx.new_page()
        for t in targets:
            title = ''
            status = 'ok'
            try:
                resp = pg.goto(t['url'], timeout=30000, wait_until='domcontentloaded')
                code = resp.status if resp else 0
                pg.wait_for_timeout(1500)
                title = (pg.title() or '')[:200]
                # название ОО: h1/og:site_name — <title> у госуслуг-сайтов общий
                org = ''
                try:
                    org = pg.evaluate(
                        """() => {
                          const h = document.querySelector('h1');
                          const og = document.querySelector('meta[property=\"og:site_name\"]');
                          const meta = document.querySelector('meta[name=\"title\"]');
                          return (h && h.innerText.trim()) || (og && og.content) || (meta && meta.content) || '';
                        }"""
                    ) or ''
                except Exception:
                    org = ''
                haystack = f'{org} {title}'
                if code >= 400:
                    status = f'http_{code}'
                else:
                    tn = tokens(haystack) - STOP
                    nn = tokens(t['name']) - STOP
                    common = tn & nn
                    if not common:
                        status = 'mismatch'
                    else:
                        title = haystack.strip()[:200]
            except Exception as e:
                status = 'error: ' + str(e)[:60]
            out.append({'school_id': t['school_id'], 'city': t['city'], 'name': t['name'],
                        'url': t['url'], 'page_title': title, 'status': status})
            done += 1
            if status != 'ok':
                print(f"{done}/{len(targets)} {status}: {t['name'][:36]} | {title[:70]}", flush=True)
            json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            time.sleep(0.3)
        b.close()

    bad = [x for x in out if x['status'] != 'ok']
    print(f'Проверено {len(out)}, расхождений/ошибок: {len(bad)}')
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
