#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер uchi.ru с использованием Selenium для обхода защиты
Требует установки: pip install selenium
И скачивания ChromeDriver
"""

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

import time
import json
import os
from urllib.parse import urlencode

# Путь к папке output относительно текущего файла
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


class UchiRuSeleniumParser:
    def __init__(self):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium не установлен. Установите: pip install selenium")
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Настройка Chrome WebDriver"""
        chrome_options = Options()
        
        # Опции для обхода детекции ботов
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Отключаем изображения для ускорения
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("✅ Chrome WebDriver инициализирован")
        except Exception as e:
            print(f"❌ Ошибка инициализации WebDriver: {e}")
            print("Убедитесь, что ChromeDriver установлен и находится в PATH")
            raise
    
    def get_page_data(self, page_num):
        """Получает данные с одной страницы"""
        params = {
            'page': page_num,
            'region': 'Саратовская область',
            'city': 'Саратов',
            'name': ''
        }
        
        url = f"https://uchi.ru/schools?{urlencode(params)}"
        
        try:
            print(f"Загружаю страницу {page_num}: {url}")
            self.driver.get(url)
            
            # Ждем загрузки страницы
            wait = WebDriverWait(self.driver, 20)
            
            # Проверяем, не появилась ли защита от ботов
            try:
                # Ждем появления элементов с названиями школ
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "RatingItem_name__FBvkh")))
                print(f"✅ Страница {page_num} загружена успешно")
                
                # Извлекаем названия школ
                school_elements = self.driver.find_elements(By.CLASS_NAME, "RatingItem_name__FBvkh")
                school_names = [elem.text.strip() for elem in school_elements if elem.text.strip()]
                
                print(f"Найдено школ на странице {page_num}: {len(school_names)}")
                for name in school_names:
                    print(f"  - {name}")
                
                return school_names
                
            except TimeoutException:
                # Проверяем, не появилась ли защита
                if "servicepipe.ru" in self.driver.page_source or "id_spinner" in self.driver.page_source:
                    print(f"❌ Страница {page_num} заблокирована защитой от ботов")
                    return []
                else:
                    print(f"❌ Таймаут загрузки страницы {page_num}")
                    return []
            
        except Exception as e:
            print(f"❌ Ошибка при загрузке страницы {page_num}: {e}")
            return []
    
    def parse_all_pages(self, start_page=1, end_page=15):
        """Парсит все страницы"""
        all_schools = set()
        
        print(f"Начинаю парсинг страниц с {start_page} по {end_page}")
        print("=" * 50)
        
        for page in range(start_page, end_page + 1):
            schools = self.get_page_data(page)
            all_schools.update(schools)
            
            # Пауза между страницами
            time.sleep(2)
        
        print(f"\nПарсинг завершен. Всего найдено уникальных школ: {len(all_schools)}")
        return all_schools
    
    def save_to_json(self, schools, filename=None):
        """Сохраняет результаты в JSON файл"""
        if filename is None:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            filename = os.path.join(OUTPUT_DIR, "schools_uchi_ru_selenium.json")
        
        try:
            schools_list = sorted(list(schools))
            data = {
                "source": "uchi.ru",
                "topic": "Школы Саратова",
                "description": "Данные школ с сайта uchi.ru (Selenium)",
                "total_schools": len(schools_list),
                "data": [{"name": name} for name in schools_list]
            }
            
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else OUTPUT_DIR, exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Данные сохранены в файл: {filename}")
            
        except Exception as e:
            print(f"❌ Ошибка при сохранении файла: {e}")
    
    def save_to_txt(self, schools, filename=None):
        """Сохраняет результаты в txt файл"""
        if filename is None:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            filename = os.path.join(OUTPUT_DIR, "schools_data_selenium.txt")
        
        try:
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else OUTPUT_DIR, exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Данные школ с сайта uchi.ru (Selenium)\n")
                f.write("=" * 50 + "\n\n")
                
                for i, school_name in enumerate(sorted(schools), 1):
                    f.write(f"{i}. {school_name}\n")
                
                f.write(f"\nВсего найдено школ: {len(schools)}")
            
            print(f"✅ Данные сохранены в файл: {filename}")
            
        except Exception as e:
            print(f"❌ Ошибка при сохранении файла: {e}")
    
    def close(self):
        """Закрывает браузер"""
        if self.driver:
            self.driver.quit()
            print("Браузер закрыт")

def main():
    """Основная функция"""
    if not SELENIUM_AVAILABLE:
        print("❌ Selenium не установлен!")
        print("Установите: pip install selenium")
        print("И скачайте ChromeDriver с https://chromedriver.chromium.org/")
        return
    
    parser = None
    try:
        print("Парсер uchi.ru с Selenium")
        print("=" * 30)
        
        parser = UchiRuSeleniumParser()
        schools = parser.parse_all_pages(1, 15)
        parser.save_to_json(schools)
        parser.save_to_txt(schools)
        
        print("\n✅ Парсинг завершен успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        if parser:
            parser.close()

if __name__ == "__main__":
    main()





