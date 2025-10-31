#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой парсер для сохранения HTML страниц uchi.ru
"""

import requests
import time
from urllib.parse import urlencode

def save_page_html(page_num, filename=None):
    """Сохраняет HTML страницы в файл"""
    
    # Параметры запроса
    params = {
        'page': page_num,
        'region': 'Саратовская область',
        'city': 'Саратов',
        'name': ''
    }
    
    url = f"https://uchi.ru/schools?{urlencode(params)}"
    
    # Заголовки для имитации браузера
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }
    
    try:
        print(f"Загружаю страницу {page_num}...")
        print(f"URL: {url}")
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Определяем имя файла
        if filename is None:
            filename = f"page_{page_num}.html"
        
        # Сохраняем HTML
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        print(f"Страница {page_num} сохранена в файл: {filename}")
        print(f"Размер файла: {len(response.text)} символов")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при загрузке страницы {page_num}: {e}")
        return False
    except Exception as e:
        print(f"Неожиданная ошибка на странице {page_num}: {e}")
        return False

def main():
    """Основная функция"""
    print("Простой парсер uchi.ru")
    print("=" * 30)
    
    # Сохраняем первую страницу
    success = save_page_html(1, "uchi_page_1.html")
    
    if success:
        print("\nПроверьте файл uchi_page_1.html")
        print("Откройте его в браузере для анализа структуры")
    else:
        print("\nНе удалось загрузить страницу")
        print("Возможно, сайт блокирует запросы")

if __name__ == "__main__":
    main()
