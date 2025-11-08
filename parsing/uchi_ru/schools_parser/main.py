#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер сайта uchi.ru для извлечения данных школ
Извлекает значения класса RatingItem_name__FBvkh с 15 страниц
"""

import requests
from bs4 import BeautifulSoup
import time
import urllib.parse
import os
import json
from typing import List, Set

# Путь к папке output относительно текущего файла
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


class UchiRuParser:
    def __init__(self):
        self.base_url = "https://uchi.ru/schools"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.results = set()  # Используем set для избежания дубликатов
        
    def get_page_data(self, page: int) -> List[str]:
        """Получает данные с одной страницы"""
        params = {
            'page': page,
            'region': 'Саратовская область',
            'city': 'Саратов',
            'name': ''
        }
        
        try:
            print(f"Обрабатываю страницу {page}...")
            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Ищем элементы с классом RatingItem_name__FBvkh
            name_elements = soup.find_all(class_='RatingItem_name__FBvkh')
            
            page_results = []
            for element in name_elements:
                text = element.get_text(strip=True)
                if text:
                    page_results.append(text)
                    print(f"  Найдено: {text}")
            
            return page_results
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при загрузке страницы {page}: {e}")
            return []
        except Exception as e:
            print(f"Неожиданная ошибка на странице {page}: {e}")
            return []
    
    def parse_all_pages(self, start_page: int = 1, end_page: int = 15):
        """Парсит все страницы от start_page до end_page включительно"""
        print(f"Начинаю парсинг страниц с {start_page} по {end_page}")
        
        for page in range(start_page, end_page + 1):
            page_data = self.get_page_data(page)
            self.results.update(page_data)
            
            # Небольшая пауза между запросами
            time.sleep(1)
            
        print(f"\nПарсинг завершен. Найдено уникальных записей: {len(self.results)}")
    
    def save_to_json(self, filename: str = None):
        """Сохраняет результаты в JSON файл"""
        if filename is None:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            filename = os.path.join(OUTPUT_DIR, "schools_uchi_ru.json")
        
        try:
            schools_list = sorted(list(self.results))
            data = {
                "source": "uchi.ru",
                "topic": "Школы Саратова",
                "description": "Данные школ с сайта uchi.ru",
                "total_schools": len(schools_list),
                "data": [{"name": name} for name in schools_list]
            }
            
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else OUTPUT_DIR, exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"Данные сохранены в файл: {filename}")
            
        except Exception as e:
            print(f"Ошибка при сохранении файла: {e}")
    
    def save_to_txt(self, filename: str = None):
        """Сохраняет результаты в txt файл"""
        if filename is None:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            filename = os.path.join(OUTPUT_DIR, "schools_data.txt")
        
        try:
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else OUTPUT_DIR, exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Данные школ с сайта uchi.ru\n")
                f.write("=" * 50 + "\n\n")
                
                for i, school_name in enumerate(sorted(self.results), 1):
                    f.write(f"{i}. {school_name}\n")
                
                f.write(f"\nВсего найдено школ: {len(self.results)}")
            
            print(f"Данные сохранены в файл: {filename}")
            
        except Exception as e:
            print(f"Ошибка при сохранении файла: {e}")
    
    def run(self):
        """Запускает полный процесс парсинга"""
        print("Запуск парсера uchi.ru")
        print("=" * 30)
        
        self.parse_all_pages(1, 15)
        self.save_to_json()
        self.save_to_txt()
        
        print("\nПарсинг завершен успешно!")

def main():
    parser = UchiRuParser()
    parser.run()

if __name__ == "__main__":
    main()





