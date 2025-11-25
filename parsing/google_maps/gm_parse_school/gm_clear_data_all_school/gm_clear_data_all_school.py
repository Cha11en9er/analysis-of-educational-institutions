#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер школ из HTML файла Google Maps.
Извлекает данные школ из gm_debug_html.html и сохраняет в gm_data_all_schools.json
"""

import os
import json
from typing import List, Dict, Any
from bs4 import BeautifulSoup


# Пути относительно текущего файла
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # gm_clear_data_all_school
GM_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))  # google_maps
DATA_DIR = os.path.join(GM_ROOT, "gm_data")
HTML_FILE = os.path.join(DATA_DIR, "gm_debug_html", "gm_debug_html.html")
JSON_FILE = os.path.join(DATA_DIR, "gm_data_all_schools", "gm_data_all_schools.json")


def parse_schools_from_html(html_file: str) -> List[Dict[str, Any]]:
    """
    Парсит школы из HTML файла Google Maps
    
    Args:
        html_file: Путь к HTML файлу
    
    Returns:
        Список словарей с данными школ
    """
    schools = []
    
    try:
        print(f"[info] Чтение HTML файла: {html_file}")
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        print(f"[info] Размер HTML: {len(html_content)} символов")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Ищем все элементы с role="article" и классами Nv2PK Q2HXcd THOPZb
        # Это элементы, содержащие информацию о школах
        school_elements = []
        
        # Вариант 1: поиск по всем классам (точный)
        school_elements = soup.find_all('div', {
            'role': 'article',
            'class': lambda x: x and isinstance(x, list) and 'Nv2PK' in x and 'Q2HXcd' in x and 'THOPZb' in x
        })
        
        print(f"[debug] Вариант 1 (точный поиск): найдено {len(school_elements)} элементов")
        
        # Вариант 2: поиск по строке классов
        if len(school_elements) == 0:
            school_elements = soup.find_all('div', {
                'role': 'article',
                'class': lambda x: x and isinstance(x, str) and 'Nv2PK' in x and 'Q2HXcd' in x and 'THOPZb' in x
            })
            print(f"[debug] Вариант 2 (поиск по строке): найдено {len(school_elements)} элементов")
        
        # Вариант 3: поиск только по role="article" и фильтрация по классам
        if len(school_elements) == 0:
            all_articles = soup.find_all('div', {'role': 'article'})
            print(f"[debug] Всего элементов с role='article': {len(all_articles)}")
            
            # Фильтруем по классам вручную
            for elem in all_articles:
                classes = elem.get('class', [])
                if isinstance(classes, list):
                    class_str = ' '.join(classes)
                else:
                    class_str = str(classes)
                # Проверяем наличие всех трёх классов
                if 'Nv2PK' in class_str and 'Q2HXcd' in class_str and 'THOPZb' in class_str:
                    school_elements.append(elem)
            print(f"[debug] Вариант 3 (фильтрация): найдено {len(school_elements)} элементов")
        
        # Вариант 4: поиск только по классу Nv2PK (если другие варианты не сработали)
        if len(school_elements) == 0:
            school_elements = soup.find_all('div', class_=lambda x: x and 'Nv2PK' in (x if isinstance(x, list) else [x]))
            print(f"[debug] Вариант 4 (только Nv2PK): найдено {len(school_elements)} элементов")
        
        print(f"[info] Итого найдено элементов школ: {len(school_elements)}")
        
        if len(school_elements) == 0:
            print("[warn] Школы не найдены. Проверьте HTML файл.")
            return schools
        
        # Парсим каждый элемент
        for idx, element in enumerate(school_elements, start=1):
            try:
                # Способ 1: Название из aria-label
                name = element.get('aria-label', '').strip()
                
                # Способ 2: Если aria-label пустое, ищем в div с классом qBF1Pd fontHeadlineSmall
                if not name:
                    name_elem = element.find('div', class_=lambda x: x and 'qBF1Pd' in (x if isinstance(x, list) else [x]) and 'fontHeadlineSmall' in (x if isinstance(x, list) else [x]))
                    if name_elem:
                        name = name_elem.text.strip()
                
                # Способ 3: Если не нашли, ищем в span с классом HTCGSb
                if not name:
                    name_elem = element.find('span', class_='HTCGSb')
                    if name_elem:
                        name = name_elem.text.strip()
                
                # Ищем ссылку в теге <a class="hfpxzc">
                link_elem = element.find('a', class_='hfpxzc')
                url = ""
                
                if link_elem:
                    url = link_elem.get('href', '').strip()
                    # Если URL содержит &amp;, заменяем на &
                    url = url.replace('&amp;', '&')
                
                # Если URL относительный, делаем его абсолютным
                if url and url.startswith('/'):
                    url = f"https://www.google.com{url}"
                
                # Добавляем школу только если есть название
                if name:
                    school_data = {
                        "id": str(idx),
                        "name": name,
                        "url": url
                    }
                    schools.append(school_data)
                    print(f"  [{idx}] {name}")
                else:
                    print(f"  [warn] Элемент {idx} не содержит названия, пропускаем")
                    # Выводим отладочную информацию
                    print(f"    [debug] aria-label: {element.get('aria-label', 'нет')}")
                    print(f"    [debug] Классы: {element.get('class', [])}")
                    
            except Exception as e:
                print(f"  [warn] Ошибка при парсинге элемента {idx}: {e}")
                import traceback
                print(f"  [debug] Трассировка: {traceback.format_exc()}")
                continue
        
        return schools
        
    except FileNotFoundError:
        print(f"[error] Файл не найден: {html_file}")
        return []
    except Exception as e:
        print(f"[error] Ошибка при чтении HTML файла: {e}")
        import traceback
        print(f"[debug] Трассировка: {traceback.format_exc()}")
        return []


def save_schools_to_json(schools: List[Dict[str, Any]], output_file: str) -> bool:
    """
    Сохраняет список школ в JSON файл
    
    Args:
        schools: Список словарей с данными школ
        output_file: Путь к файлу для сохранения
    
    Returns:
        True если успешно, False в случае ошибки
    """
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        result = {
            "source": "google_maps",
            "topic": "Школы Саратова",
            "description": "Данные школ получены через парсинг Google Maps",
            "total_schools": len(schools),
            "data": schools
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"[info] Данные сохранены в JSON: {output_file}")
        print(f"[info] Всего школ: {len(schools)}")
        return True
    except Exception as e:
        print(f"[error] Ошибка при сохранении JSON: {e}")
        import traceback
        print(f"[debug] Трассировка: {traceback.format_exc()}")
        return False


def main():
    """Основная функция"""
    print("[info] Начало парсинга школ из HTML файла...")
    print(f"[info] Входной файл: {HTML_FILE}")
    print(f"[info] Выходной файл: {JSON_FILE}")
    
    # Проверяем существование HTML файла
    if not os.path.exists(HTML_FILE):
        print(f"[error] HTML файл не найден: {HTML_FILE}")
        return
    
    # Парсим школы из HTML
    schools = parse_schools_from_html(HTML_FILE)
    
    if schools:
        # Сохраняем в JSON
        save_schools_to_json(schools, JSON_FILE)
        print(f"\n[ok] Успешно обработано {len(schools)} школ")
    else:
        print("[warn] Школы не найдены в HTML файле")


if __name__ == "__main__":
    main()


