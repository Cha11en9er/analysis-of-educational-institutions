#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер школ Яндекс.Карт через API.
Использует Search API для поиска школ, затем парсит отзывы с веб-страниц.

Требуется API ключ: https://developer.tech.yandex.ru/services/
"""

import os
import json
import time
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup


class YandexMapsAPI:
    """Класс для работы с API Яндекс.Карт"""
    
    def __init__(self, api_key: str):
        """
        Инициализация API клиента
        
        Args:
            api_key: API ключ Яндекс.Карт (получить на https://developer.tech.yandex.ru/)
        """
        self.api_key = api_key
        self.search_api_url = "https://search-maps.yandex.ru/v1/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def search_schools(
        self,
        text: str = "школа",
        bbox: Optional[str] = None,
        lat: float = 51.551834,
        lon: float = 46.153670,
        radius: int = 50000,
        results: int = 50,
        lang: str = "ru_RU"
    ) -> List[Dict[str, Any]]:
        """
        Поиск школ через Search API Яндекс.Карт
        
        Args:
            text: Текст поискового запроса
            bbox: Границы области поиска в формате "lon1,lat1~lon2,lat2"
            lat: Широта центра поиска
            lon: Долгота центра поиска
            radius: Радиус поиска в метрах
            results: Максимальное количество результатов
            lang: Язык ответа
        
        Returns:
            Список найденных школ
        """
        params = {
            "apikey": self.api_key,
            "text": text,
            "lang": lang,
            "results": results,
            "type": "biz"
        }
        
        # Используем bbox или ll + r
        if bbox:
            params["bbox"] = bbox
        else:
            params["ll"] = f"{lon},{lat}"
            params["r"] = radius
        
        try:
            response = self.session.get(self.search_api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            schools = []
            for feature in data.get("features", []):
                properties = feature.get("properties", {})
                company_meta = properties.get("CompanyMetaData", {})
                
                school = {
                    "id": feature.get("id"),
                    "name": properties.get("name"),
                    "address": company_meta.get("address"),
                    "url": company_meta.get("url"),
                    "phone": company_meta.get("Phones", [{}])[0].get("formatted") if company_meta.get("Phones") else None,
                    "coordinates": feature.get("geometry", {}).get("coordinates"),
                    "rating": company_meta.get("rating"),
                    "reviews_count": company_meta.get("Reviews", {}).get("reviewsCount") if company_meta.get("Reviews") else None,
                }
                schools.append(school)
            
            return schools
            
        except requests.exceptions.RequestException as e:
            print(f"[error] Ошибка API запроса: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"[error] Ошибка парсинга JSON: {e}")
            return []
    
    def get_school_reviews(self, school_url: str) -> List[Dict[str, Any]]:
        """
        Парсит отзывы со страницы школы на Яндекс.Картах
        
        Args:
            school_url: URL страницы школы
        
        Returns:
            Список отзывов
        """
        try:
            response = self.session.get(school_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            reviews = []
            
            # Ищем отзывы (селекторы могут отличаться, нужно проверить актуальную структуру)
            # Это примерные селекторы, их нужно уточнить для актуальной версии сайта
            review_elements = soup.find_all('div', class_=lambda x: x and 'review' in x.lower())
            
            for review_elem in review_elements:
                try:
                    text_elem = review_elem.find('div', class_=lambda x: x and ('text' in x.lower() or 'body' in x.lower()))
                    date_elem = review_elem.find('span', class_=lambda x: x and 'date' in x.lower())
                    rating_elem = review_elem.find('div', class_=lambda x: x and 'rating' in x.lower())
                    
                    review = {
                        "text": text_elem.get_text(strip=True) if text_elem else "",
                        "date": date_elem.get_text(strip=True) if date_elem else "",
                        "rating": rating_elem.get_text(strip=True) if rating_elem else None
                    }
                    
                    if review["text"]:
                        reviews.append(review)
                        
                except Exception as e:
                    print(f"[warn] Ошибка при парсинге отзыва: {e}")
                    continue
            
            return reviews
            
        except requests.exceptions.RequestException as e:
            print(f"[error] Ошибка при получении страницы {school_url}: {e}")
            return []
    
    def search_schools_in_saratov(self, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Поиск всех школ в Саратове
        
        Args:
            max_results: Максимальное количество результатов
        
        Returns:
            Список школ с информацией
        """
        # Координаты Саратова
        saratov_lat = 51.551834
        saratov_lon = 46.153670
        
        all_schools = []
        offset = 0
        page_size = 50
        
        while len(all_schools) < max_results:
            schools = self.search_schools(
                text="школа",
                lat=saratov_lat,
                lon=saratov_lon,
                radius=50000,  # 50 км радиус
                results=page_size
            )
            
            if not schools:
                break
            
            all_schools.extend(schools)
            
            if len(schools) < page_size:
                break
            
            offset += page_size
            time.sleep(0.5)  # Пауза между запросами
        
        return all_schools[:max_results]


def main():
    """Пример использования API"""
    # ВАЖНО: Замените на ваш API ключ
    # Получить можно на https://developer.tech.yandex.ru/services/
    api_key = os.getenv("YANDEX_MAPS_API_KEY", "YOUR_API_KEY_HERE")
    
    if api_key == "YOUR_API_KEY_HERE":
        print("[error] Укажите API ключ Яндекс.Карт!")
        print("Получите ключ на: https://developer.tech.yandex.ru/services/")
        print("И установите переменную окружения YANDEX_MAPS_API_KEY или измените код")
        return
    
    api = YandexMapsAPI(api_key)
    
    # Поиск школ в Саратове
    print("[info] Поиск школ в Саратове...")
    schools = api.search_schools_in_saratov(max_results=50)
    
    print(f"[info] Найдено школ: {len(schools)}")
    
    # Сохраняем результаты
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "yandex_maps_schools.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "resource": "yandex_maps",
            "schools": schools
        }, f, ensure_ascii=False, indent=2)
    
    print(f"[info] Результаты сохранены: {output_file}")
    
    # Пример получения отзывов для первой школы
    if schools and schools[0].get("url"):
        print(f"\n[info] Получение отзывов для: {schools[0]['name']}")
        reviews = api.get_school_reviews(schools[0]["url"])
        print(f"[info] Найдено отзывов: {len(reviews)}")
        if reviews:
            print(f"[info] Пример отзыва: {reviews[0]}")


if __name__ == "__main__":
    main()


