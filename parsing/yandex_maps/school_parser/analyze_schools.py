#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализ HTML файла с Яндекс.Карт - извлечение школ
"""

import re
import os
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

html_file = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "yandex_maps_schools.html"
)

with open(html_file, 'r', encoding='utf-8') as f:
    html = f.read()

# Ищем все aria-label с названиями школ
aria_pattern = r'aria-label="([^"]+)"'
aria_matches = list(re.finditer(aria_pattern, html))

schools = []
seen_titles = set()

for match in aria_matches:
    title = match.group(1)
    title_lower = title.lower()
    
    # Фильтруем только школы
    if not any(word in title_lower for word in ['школ', 'гимнази', 'лице', 'прогимнази']):
        continue
    
    if title in seen_titles:
        continue
    seen_titles.add(title)
    
    # Ищем ссылку на организацию в контексте вокруг aria-label
    # Берем больший контекст (2000 символов до и после)
    match_start = match.start()
    match_end = match.end()
    context_start = max(0, match_start - 500)
    context_end = min(len(html), match_end + 2000)
    context = html[context_start:context_end]
    
    # Ищем data-id для получения ID организации
    data_id_match = re.search(r'data-id="(\d+)"', context)
    
    # Ищем основную ссылку на организацию
    org_link_match = re.search(r'href="(/maps/org/([^/]+)/(\d+)/)"', context)
    # Ищем ссылку на отзывы
    reviews_link_match = re.search(r'href="(/maps/org/([^/]+)/(\d+)/reviews/)"', context)
    
    org_url = None
    reviews_url = None
    seoname = None
    org_id = None
    
    if org_link_match:
        org_url = f"https://yandex.ru{org_link_match.group(1)}"
        seoname = org_link_match.group(2)
        org_id = org_link_match.group(3)
    elif reviews_link_match:
        # Если не нашли основную ссылку, но нашли отзывы, извлекаем данные из них
        reviews_url = f"https://yandex.ru{reviews_link_match.group(1)}"
        seoname = reviews_link_match.group(2)
        org_id = reviews_link_match.group(3)
        org_url = f"https://yandex.ru/maps/org/{seoname}/{org_id}/"
    
    if reviews_link_match and not reviews_url:
        reviews_url = f"https://yandex.ru{reviews_link_match.group(1)}"
    
    schools.append({
        'title': title,
        'url': org_url or '',
        'reviews_url': reviews_url or '',
        'seoname': seoname or '',
        'id': org_id or ''
    })

print(f"Найдено уникальных школ: {len(schools)}\n")
print("=" * 80)
print()

for i, school in enumerate(schools, 1):
    title = school['title']
    title_lower = title.lower()
    
    # Определяем тип
    if 'гимнази' in title_lower:
        school_type = "Гимназия"
    elif 'лице' in title_lower:
        school_type = "Лицей"
    elif 'прогимнази' in title_lower:
        school_type = "Прогимназия"
    else:
        school_type = "Школа"
    
    print(f"{i}. {school_type}: {title}")
    
    if school['url']:
        print(f"   Ссылка: {school['url']}")
    if school['reviews_url']:
        print(f"   Отзывы: {school['reviews_url']}")
    
    print()

print("=" * 80)
print(f"\nИтого найдено: {len(schools)} школ")
print("\n⚠️  ВАЖНО: На сайте Яндекс.Карт используется автоподгрузка (lazy loading),")
print("   поэтому парсер получает только те школы, которые загрузились при открытии страницы.")
print("   Для получения всех школ нужно:")
print("   1. Прокручивать страницу вниз для загрузки новых элементов")
print("   2. Ждать загрузки динамического контента")
print("   3. Возможно, использовать более длительные задержки")

