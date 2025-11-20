#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер HTML файла с Яндекс.Картами для извлечения данных о школах.
Извлекает названия, URL, ID и ссылки на отзывы из HTML файла.
"""

import json
import os
import re
from typing import List, Dict, Any

from bs4 import BeautifulSoup


def extract_yandex_id(url: str) -> str:
    """
    Извлекает Yandex ID из URL.
    
    Args:
        url: URL вида /maps/org/secondary_school_77/1028265778/
    
    Returns:
        Yandex ID (например, "1028265778")
    """
    # Ищем последний числовой сегмент в URL
    match = re.search(r'/(\d+)/?$', url)
    if match:
        return match.group(1)
    return ""


def parse_schools_from_html(html_file: str) -> List[Dict[str, Any]]:
    """
    Парсит HTML файл и извлекает данные о школах.
    
    Args:
        html_file: Путь к HTML файлу
    
    Returns:
        Список словарей с данными о школах
    """
    schools = []
    
    try:
        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read()
    except Exception as e:
        print(f"[error] Не удалось прочитать файл {html_file}: {e}")
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Ищем все ссылки с href, содержащим /maps/org/
    # Ищем все ссылки с паттерном /maps/org/.../число/
    # Используем более широкий поиск, чтобы найти все возможные варианты
    all_links = soup.find_all('a', href=re.compile(r'/maps/org/[^/"]+/\d+'))
    
    print(f"[info] Найдено ссылок с /maps/org/: {len(all_links)}")
    
    processed_urls = set()  # Для избежания дубликатов
    processed_yandex_ids = set()  # Для избежания дубликатов по ID
    
    for link in all_links:
        try:
            href = link.get('href', '')
            if not href:
                continue
            
            # Исключаем ссылки на галерею, отзывы и другие разделы
            # Нужны только основные страницы организаций
            if '/gallery/' in href or '/reviews/' in href or '/feedback/' in href:
                continue
            
            # Проверяем, что это основная страница организации (заканчивается на /число/ или /число)
            # Исключаем ссылки вида /maps/org/.../число/gallery/ или /maps/org/.../число/reviews/
            if not re.match(r'/maps/org/[^/]+/\d+/?$', href.split('?')[0]):  # Убираем query параметры
                continue
            
            # Нормализуем href (убираем query параметры и добавляем / в конец если нужно)
            href_clean = href.split('?')[0].split('#')[0]
            if not href_clean.endswith('/'):
                href_clean += '/'
            
            # Пропускаем дубликаты по нормализованному URL
            if href_clean in processed_urls:
                continue
            
            # Извлекаем название из aria-label или текста ссылки
            name = link.get('aria-label', '') or link.get_text(strip=True)
            if not name:
                continue
            
            # Фильтруем некорректные названия
            name_lower = name.lower().strip()
            # Исключаем служебные элементы
            if (name_lower == 'фото' or 
                name_lower.startswith('рейтинг') or 
                name_lower.startswith('rating') or
                len(name) < 3 or  # Слишком короткие названия
                name.isdigit()):  # Только цифры
                continue
            
            # Извлекаем Yandex ID
            yandex_id = extract_yandex_id(href_clean)
            if not yandex_id:
                continue
            
            # Пропускаем дубликаты по ID
            if yandex_id in processed_yandex_ids:
                continue
            
            processed_urls.add(href_clean)
            processed_yandex_ids.add(yandex_id)
            
            # Формируем полный URL
            if href_clean.startswith('/'):
                full_url = f"https://yandex.com{href_clean}"
            else:
                full_url = f"https://yandex.com/{href_clean}"
            
            # Формируем ссылку на отзывы
            feedback_link = f"{full_url}reviews/"
            
            school_data = {
                "id": str(len(schools) + 1),  # Используем текущий размер списка + 1
                "name": name,
                "url": full_url,
                "feedback_link": feedback_link,
                "yandex_id": yandex_id
            }
            
            schools.append(school_data)
            
        except Exception as e:
            print(f"[warn] Ошибка при обработке ссылки: {e}")
            continue
    
    return schools


def save_schools_to_json(schools: List[Dict[str, Any]], output_file: str) -> None:
    """
    Сохраняет данные о школах в JSON файл.
    
    Args:
        schools: Список словарей с данными о школах
        output_file: Путь к выходному JSON файлу
    """
    output_data = {
        "source": "yandex_maps",
        "topic": "Школы Саратова",
        "data": schools
    }
    
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)
        print(f"[info] Данные сохранены в {output_file}")
        print(f"[info] Всего школ: {len(schools)}")
    except Exception as e:
        print(f"[error] Не удалось сохранить данные: {e}")


def main():
    """Основная функция"""
    # Определяем пути к файлам
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "..", "data")
    data_dir = os.path.abspath(os.path.normpath(data_dir))
    
    html_file = os.path.join(data_dir, "yandex_maps_schools.html")
    output_file = os.path.join(data_dir, "yandex_schools_output.json")
    
    print(f"[info] Чтение HTML файла: {html_file}")
    
    if not os.path.exists(html_file):
        print(f"[error] Файл не найден: {html_file}")
        return
    
    # Парсим HTML
    schools = parse_schools_from_html(html_file)
    
    if not schools:
        print("[warn] Не найдено школ в HTML файле")
        return
    
    # Сохраняем результаты
    save_schools_to_json(schools, output_file)
    
    # Выводим примеры
    if schools:
        print(f"\n[info] Примеры найденных школ:")
        for school in schools[:3]:
            print(f"  - {school['name']} (ID: {school['yandex_id']})")


if __name__ == "__main__":
    main()

