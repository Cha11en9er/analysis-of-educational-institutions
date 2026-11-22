#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сбор фотографий заведений (школы, садики, вузы, спорт/творческие, СПО) — из Яндекс.Карт.

Порядок для каждой организации:
  1) если есть ссылка Яндекс.Карт (школы) — берём её;
     иначе ищем по названию + город через SSR-поиск карт (ym_find.py-подход);
  2) страница организации -> og:image (или первый avatars.mds.yandex.net);
  3) скачивание в UI/public/images/<kind>/<city>/<code_oo>.jpg;
  4) манифест roadmap/22.11.26/photos_manifest.json (файл, источник, размеры).

Запуск из корня репозитория:
  python roadmap/22.11.26/collect_photos.py --limit 20
"""
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.8078.76 Safari/537.36'
OUT_ROOT = os.path.join(REPO, 'UI', 'public', 'images')
MANIFEST = os.path.join(HERE, 'photos_manifest.json')

KIND_DIRS = {
    'general': 'schools', 'preschool': 'kindergartens', 'vuz': 'universities',
    'sport_do': 'sport', 'arts_do': 'arts', 'spo': 'college',
    'internat_cadet': 'boarding', 'other': 'other',
}
CITY_DIRS = {'Саратов': 'saratov', 'Энгельс': 'engels'}
GEO = {'Саратов': '46.031248', 'Энгельс': '46.112284'}
CITY_SLUG = {'Саратов': 'saratov', 'Энгельс': 'engels'}


def load_targets() -> list[dict]:
    """Школы (Саратов из final_school_data.json, Энгельс из city_schools.json)
    + прочие учреждения (институты из выгрузки БД)."""
    targets = []
    final = json.load(open(os.path.join(REPO, 'school_data', 'final_school_data.json'), encoding='utf-8'))
    for s in final:
        if not s.get('link_yandex'):
            continue
        targets.append({
            'code_oo': None, 'kind': 'general', 'city': 'Саратов',
            'name': s.get('short_name') or s.get('name_2gis'),
            'yandex_url': s['link_yandex'], 'school_id': s['id'],
        })
    eng = json.load(open(os.path.join(HERE, '..', '01.11.26', 'engels', 'city_schools.json'), encoding='utf-8'))
    for s in eng:
        if not s.get('link_yandex'):
            continue
        targets.append({
            'code_oo': s['code_oo'], 'kind': 'general', 'city': 'Энгельс',
            'name': s['name_short'], 'yandex_url': s['link_yandex'],
            'school_id': 100000 + s['code_oo'],
        })
    inst = json.load(open(os.path.join(HERE, 'institutions_list.json'), encoding='utf-8'))
    for r in inst:
        if r['kind'] == 'general':
            continue  # школы уже выше
        targets.append({
            'code_oo': r['code_oo'], 'kind': r['kind'], 'city': r['city'],
            'name': r['name'], 'yandex_url': r.get('link_yandex'),
        })
    return targets


def find_org_url(page, name: str, city: str) -> str | None:
    """Поиск организации в Яндекс.Картах: SSR-выдача -> первый org-линк."""
    slug = CITY_SLUG.get(city, 'saratov')
    geo = GEO.get(city, '46.031248')
    q = urllib.parse.quote(name[:70])
    url = f'https://yandex.ru/maps/{geo}/{slug}/search/{q}'
    try:
        page.goto(url, timeout=40000, wait_until='domcontentloaded')
        page.wait_for_timeout(4000)
        html = page.content()
    except Exception:
        return None
    orgs = re.findall(r'org/([a-z0-9_]+)/(\d{9,12})', html)
    for o_slug, o_id in orgs:
        return f'https://yandex.ru/maps/org/{o_slug}/{o_id}/'
    return None


def pick_photo(html: str) -> str | None:
    og = re.search(r'property="og:image" content="([^"]+)"', html)
    if og and 'avatars.mds.yandex.net' in og.group(1):
        return og.group(1)
    avs = sorted(set(re.findall(r'https://avatars\.mds\.yandex\.net/[^\s"\'\\)]+', html)))
    for a in avs:
        if 'get-altay' in a:
            return a
    return avs[0] if avs else None


def download(url: str, path: str):
    url = url.replace('%s', 'L_width')
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read()
    if len(data) < 3000 or data[:2] != b'\xff\xd8':
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--city', default=None)
    ap.add_argument('--kind', default=None)
    args = ap.parse_args()

    targets = load_targets()
    if args.city:
        targets = [t for t in targets if t['city'] == args.city]
    if args.kind:
        targets = [t for t in targets if t['kind'] == args.kind]
    if args.limit:
        targets = targets[:args.limit]
    print(f'Цели: {len(targets)}')

    manifest = json.load(open(MANIFEST, encoding='utf-8')) if os.path.exists(MANIFEST) else {}
    done = 0
    with sync_playwright() as p:
        b = p.chromium.launch(channel='chrome', headless=True)
        ctx = b.new_context(user_agent=UA, locale='ru-RU', viewport={'width': 1400, 'height': 900})
        page = ctx.new_page()
        for t in targets:
            key = f"{t['kind']}|{t['city']}|{t['code_oo']}|{t['name']}"
            if key in manifest:
                done += 1
                continue
            url = t.get('yandex_url')
            if not url:
                url = find_org_url(page, t['name'], t['city'])
                if url:
                    t['yandex_url'] = url
            photo = None
            if url:
                try:
                    page.goto(url.rstrip('/') + '/', timeout=40000, wait_until='domcontentloaded')
                    page.wait_for_timeout(4500)
                    photo = pick_photo(page.content())
                except Exception as e:
                    print('ERR', t['name'], str(e)[:50], flush=True)
            entry = {
                'code_oo': t['code_oo'], 'kind': t['kind'], 'city': t['city'],
                'name': t['name'], 'school_id': t.get('school_id'),
                'org_url': url, 'photo': None, 'source': photo,
            }
            if photo:
                kind_dir = KIND_DIRS.get(t['kind'], 'other')
                city_dir = CITY_DIRS.get(t['city'], 'other')
                fname = f"{t['code_oo'] or t.get('school_id')}.jpg"
                rel = f"{kind_dir}/{city_dir}/{fname}"
                size = download(photo, os.path.join(OUT_ROOT, rel.replace('/', os.sep)))
                entry['photo'] = rel
                entry['width'], entry['height'] = size or (0, 0)
            manifest[key] = entry
            done += 1
            print(f"{done}/{len(targets)} {t['kind']:14} {t['city']:8} {(t['name'] or '')[:38]:40} -> {entry['photo']}", flush=True)
            json.dump(manifest, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            time.sleep(0.7)
        b.close()

    json.dump(manifest, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with_photo = sum(1 for v in manifest.values() if v.get('photo'))
    print(f'Готово: {done}, с фото {with_photo}, без {len(manifest) - with_photo}')


if __name__ == '__main__':
    main()
