#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер для дополнения информации о школах из 2ГИС.
Читает список школ из JSON файла и парсит дополнительную информацию:
- full_name
- adres_part1
- adres_part2
- adres
"""

import json
import os
import time
from typing import Dict, Any, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import re

# Путь к файлу с данными о школах
INPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "2gis_all_school.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "2gis_all_school_with_info.json")


def setup_driver() -> webdriver.Chrome:
    """Настройка Chrome WebDriver для обхода детекции ботов"""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def wait_text_or_null(driver: webdriver.Chrome, by: By, locator: str, timeout: int = 10):
    """Безопасное получение текста элемента или None (null) при таймауте"""
    try:
        el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, locator)))
        text = el.text.strip()
        return text if text else None
    except TimeoutException:
        return None


def wait_text_by_css_or_null(driver: webdriver.Chrome, css_selector: str, timeout: int = 10):
    """Безопасное получение текста элемента по CSS селектору или None (null) при таймауте"""
    try:
        el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, css_selector)))
        text = el.text.strip()
        return text if text else None
    except TimeoutException:
        return None


def extract_address_from_json(html_content: str) -> Optional[str]:
    """Извлекает адрес из JSON данных в HTML странице"""
    try:
        # Ищем паттерн "full_name":"..." в JSON данных
        # Паттерн: "full_name":"адрес"
        pattern = r'"full_name"\s*:\s*"([^"]+)"'
        match = re.search(pattern, html_content)
        if match:
            address = match.group(1)
            return address if address else None
    except Exception as e:
        print(f"  [DEBUG] Ошибка при извлечении адреса из JSON: {e}")
    return None


def parse_school_info(driver: webdriver.Chrome, url: str) -> Dict[str, Any]:
    """
    Парсит дополнительную информацию о школе со страницы 2ГИС
    
    Args:
        driver: WebDriver для работы с браузером
        url: URL страницы школы
        
    Returns:
        Словарь с информацией о школе: full_name, adres_part1, adres_part2, adres
    """
    driver.get(url)
    
    # Небольшая пауза, чтобы прогрузились динамические блоки
    time.sleep(1.0)
    
    # Получаем HTML код страницы для извлечения JSON данных
    html_content = driver.page_source
    
    # Получаем название (если нужно)
    name = wait_text_or_null(driver, By.CLASS_NAME, "_1x89xo5")
    
    # Получаем полное название
    full_name = wait_text_or_null(driver, By.CLASS_NAME, "_bgn3t31")
    
    # Получаем части адреса
    # adres_part1 - div с классом _1p8iqzw
    adres_part1 = wait_text_or_null(driver, By.CLASS_NAME, "_1p8iqzw")
    
    # adres_part2 - извлекаем из JSON данных в HTML (поле "full_name")
    adres_part2 = extract_address_from_json(html_content)
    
    # Формируем полный адрес (если есть хотя бы одна часть)
    if adres_part1 and adres_part2:
        adres = f"{adres_part1}. {adres_part2}"
    elif adres_part1:
        adres = adres_part1
    elif adres_part2:
        adres = adres_part2
    else:
        adres = None
    
    return {
        "name": name,
        "full_name": full_name,
        "adres_part1": adres_part1,
        "adres_part2": adres_part2,
        "adres": adres,
    }


def load_schools(input_file: str) -> list:
    """Загружает список школ из JSON файла"""
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Поддерживаем разные форматы входного файла
    if "data" in data:
        return data["data"]
    elif isinstance(data, list):
        return data
    else:
        return []


def save_schools(schools: list, output_file: str) -> None:
    """Сохраняет обновленные данные о школах в JSON файл"""
    # Создаем директорию, если её нет
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    result = {
        "source": "2GIS",
        "topic": "Школы Саратова",
        "total_elements": len(schools),
        "data": schools
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    
    print(f"[OK] Данные сохранены в: {output_file}")


def main():
    """Основная функция парсера"""
    print("Парсер дополнения информации о школах 2ГИС")
    print("=" * 50)
    
    # Загружаем список школ
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] Файл не найден: {INPUT_FILE}")
        return
    
    schools = load_schools(INPUT_FILE)
    if not schools:
        print(f"[ERROR] Файл {INPUT_FILE} пуст или не содержит данных")
        return
    
    print(f"Загружено школ для обработки: {len(schools)}")
    
    # Инициализируем драйвер
    driver = setup_driver()
    print("[OK] Chrome WebDriver инициализирован")
    
    try:
        # Обрабатываем каждую школу
        for idx, school in enumerate(schools, start=1):
            school_id = school.get("id", str(idx))
            school_name = school.get("name", "Неизвестно")
            url = school.get("url", "")
            
            if not url:
                print(f"[SKIP] Школа {school_id} ({school_name}): нет URL")
                continue
            
            print(f"\n[{idx}/{len(schools)}] Обработка: {school_name}")
            print(f"  URL: {url}")
            
            try:
                # Парсим дополнительную информацию
                school_info = parse_school_info(driver, url)
                
                # Обновляем данные школы
                school.update({
                    "full_name": school_info["full_name"],
                    "adres_part1": school_info["adres_part1"],
                    "adres_part2": school_info["adres_part2"],
                    "adres": school_info["adres"],
                })
                
                print(f"  [OK] Получено:")
                print(f"    - name: {school_info['name'] or 'null'}")
                print(f"    - full_name: {school_info['full_name'] or 'null'}")
                print(f"    - adres_part1: {school_info['adres_part1'] or 'null'}")
                print(f"    - adres_part2: {school_info['adres_part2'] or 'null'}")
                print(f"    - adres: {school_info['adres'] or 'null'}")
                
                # Пауза между запросами
                time.sleep(0.5)
                
            except Exception as e:
                print(f"  [ERROR] Ошибка при парсинге: {e}")
                # Добавляем null значения в случае ошибки
                school.update({
                    "full_name": None,
                    "adres_part1": None,
                    "adres_part2": None,
                    "adres": None,
                })
                continue
        
        # Сохраняем результаты
        save_schools(schools, OUTPUT_FILE)
        
        print(f"\n[OK] Парсинг завершен! Обработано школ: {len(schools)}")
        
    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()
        print("\n[OK] Браузер закрыт")


if __name__ == "__main__":
    main()
