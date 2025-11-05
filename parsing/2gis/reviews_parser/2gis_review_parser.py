#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер карточек школ 2ГИС на Selenium.
Читает ссылки из файла со списком школ и сохраняет данные отзывов по шаблону:

schools: [{ id, name, full_name, adres, rating_2gis, url }]
reviews: [{ school_id, date, text, weightы }]

Также создаёт для каждой школы отдельный файл в каталоге output:
<id>_2gis_review.json
"""

import json
import os
import time
from typing import Dict, Any, List

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains


# Пути относительно текущего файла
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def setup_driver() -> webdriver.Chrome:
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


def wait_text_or_empty(driver: webdriver.Chrome, by: By, locator: str, timeout: int = 10) -> str:
    try:
        el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, locator)))
        text = el.text.strip()
        return text
    except TimeoutException:
        return ""


def parse_card(driver: webdriver.Chrome, url: str) -> Dict[str, Any]:
    driver.get(url)

    # Небольшая пауза, чтобы прогрузились динамические блоки
    time.sleep(1.0)

    name = wait_text_or_empty(driver, By.CLASS_NAME, "_1x89xo5")
    full_name = wait_text_or_empty(driver, By.CLASS_NAME, "_bgn3t31")

    adres_part1 = wait_text_or_empty(driver, By.CLASS_NAME, "_1p8iqzw")
    adres_part2 = wait_text_or_empty(driver, By.CLASS_NAME, "_2lcm958")
    adres = (adres_part1 + ". " if adres_part1 else "") + adres_part2

    rating_2gis = wait_text_or_empty(driver, By.CLASS_NAME, "_y10azs")

    return {
        "name": name,
        "full_name": full_name,
        "adres": adres,
        "rating_2gis": rating_2gis,
        "url": url,
    }


def parse_reviews(driver: webdriver.Chrome, review_url: str, school_id: str) -> list:
    """Парсит отзывы, теперь с физической прокруткой мыши!"""
    driver.get(review_url)
    # Сохраняем HTML страницы для дебага
    try:
        dom_path = os.path.join(OUTPUT_DIR, f"{school_id}_2gis_reviews_dom.html")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(dom_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception as e:
        print(f"[warn] Не удалось сохранить DOM для id={school_id}: {e}")
    # Физическая прокрутка мыши
    try:
        # Размер окна
        width = driver.execute_script("return window.innerWidth")
        height = driver.execute_script("return window.innerHeight")
        x = int(width * 0.375)
        y = int(height * 0.5)
        actions = ActionChains(driver)
        actions.move_by_offset(x, y).perform()
        time.sleep(0.2)
        # Несколько раз крутим колесо вниз (обычно 100-300 на скролл)
        for _ in range(4):
            driver.execute_script('window.scrollBy(0, 300);')
            actions = ActionChains(driver)
            actions.wheel(0, 350).perform()  # Вниз (в пикселях)
            time.sleep(0.7)
        # Вернуть мышь в начало (во избежание ошибок)
        actions.move_by_offset(-x, -y).perform()
    except Exception as e:
        print(f"[warn] Не удалось выполнить физическую прокрутку: {e}")
    # Ищем все длинные тексты
    review_elems = driver.find_elements(By.CLASS_NAME, '_1wlx08h')
    # Если длинных 0 — ищем короткие
    if not review_elems:
        review_elems = driver.find_elements(By.CLASS_NAME, '_1msln3t')
    reviews = []
    for elem in review_elems:
        # Сам текст
        text = elem.text.strip()
        # Пытаемся найти дату — ищем ближайший вверх _a5f6uz или _1k5soqfl, внутри ищем дату
        date = ''
        try:
            par = elem
            for _ in range(3):
                par = par.find_element(By.XPATH, '..')
                try:
                    date = par.find_element(By.CLASS_NAME, '_a5f6uz').text.strip()
                    break
                except Exception:
                    continue
        except Exception:
            date = ''
        # Пытаемся найти реакцию рядом вверх
        weighty = None
        try:
            par = elem
            for _ in range(4):
                par = par.find_element(By.XPATH, '..')
                reacts = par.find_elements(By.CLASS_NAME, '_e296pg')
                if reacts:
                    # В первом таком ищем _qdh7m6f
                    if reacts[0].find_elements(By.CLASS_NAME, '_qdh7m6f'):
                        weighty = True
                    break
        except Exception:
            weighty = None
        if text or date:
            reviews.append({
                'school_id': school_id,
                'date': date,
                'text': text,
                'weightы': weighty
            })
    if not reviews:
        print(f'❗ Отзывов/элементов с _1wlx08h или _1msln3t не найдено для школы {school_id}!')
    return reviews


def _load_json_allowing_line_comments(path: str) -> Dict[str, Any]:
    """
    Поддержка // комментариев вне строк JSON.
    Реализовано посимвольным разбором, чтобы не ломать URL вида https://...
    """
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    result_chars: List[str] = []
    in_string = False
    escape = False
    i = 0
    length = len(src)
    while i < length:
        ch = src[i]
        if in_string:
            result_chars.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        # вне строки
        if ch == '"':
            in_string = True
            result_chars.append(ch)
            i += 1
            continue

        # однострочный комментарий // ... до конца строки
        if ch == '/' and i + 1 < length and src[i + 1] == '/':
            # пропускаем до конца строки
            while i < length and src[i] not in ['\n', '\r']:
                i += 1
            # перевод строки сохраняем как есть
            continue

        result_chars.append(ch)
        i += 1

    cleaned = ''.join(result_chars)
    return json.loads(cleaned)


def load_input_links(input_file: str) -> List[Dict[str, str]]:
    """Загружает список школ из входного JSON файла"""
    data = _load_json_allowing_line_comments(input_file)
    # Поддерживаем разные форматы входного файла
    if "school_name" in data:
        return data.get("school_name", [])
    elif "data" in data:
        return data.get("data", [])
    else:
        return data if isinstance(data, list) else []


def ensure_output_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_aggregate(schools: list, reviews: list) -> None:
    """Сохраняет агрегированный файл со всеми школами и отзывами"""
    ensure_output_dir()
    aggregate_file = os.path.join(OUTPUT_DIR, "schools_2gis.json")
    payload = {
        "resource": "2gis",
        "schools": schools,
        "reviews": reviews,
    }
    with open(aggregate_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def save_school_file(school: dict, reviews: list) -> None:
    """Сохраняет отдельный файл для каждой школы"""
    ensure_output_dir()
    school_id = school["id"]
    filename = os.path.join(OUTPUT_DIR, f"{school_id}_2gis_review.json")
    payload = {
        "resource": "2gis",
        "schools": [
            {
                "id": school["id"],
                "name": school.get("name", ""),
                "full_name": school.get("full_name", ""),
                "adres": school.get("adres", ""),
                "rating_2gis": school.get("rating_2gis", ""),
                "url": school.get("url", ""),
            }
        ],
        "reviews": reviews,
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main(input_file: str = None) -> None:
    """
    Основная функция парсинга отзывов
    
    Args:
        input_file: Путь к JSON файлу со списком школ (должен содержать поля 'link' и 'review_link')
                   Если не указан, ищет файл в текущей директории или родительской
    """
    # Ищем входной файл
    if input_file is None:
        # Ищем в разных местах
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "2gis_all_schools.json"),
            os.path.join(os.path.dirname(__file__), "input.json"),
        ]
        input_file = None
        for path in possible_paths:
            if os.path.exists(path):
                input_file = path
                break
        
        if input_file is None:
            print("Ошибка: не найден входной файл со списком школ")
            print("Укажите путь к файлу с полями 'link' и 'review_link' для каждой школы")
            return
    
    ensure_output_dir()
    links = load_input_links(input_file)
    if not links:
        print(f"Файл {input_file} пуст или не содержит данных о школах")
        return

    driver = setup_driver()
    collected = []
    all_reviews = []

    try:
        for idx, item in enumerate(links, start=1):
            url = item.get("link", "").strip() or item.get("url", "").strip()
            review_url = item.get("review_link", "").strip()
            if not url:
                continue

            card = parse_card(driver, url)
            school_row = {
                "id": str(idx),
                **card,
            }
            collected.append(school_row)

            # Парсинг отзывов
            reviews = []
            if review_url:
                reviews = parse_reviews(driver, review_url, str(idx))
                all_reviews.extend(reviews)
            save_school_file(school_row, reviews)
            time.sleep(0.5)

        # Общий агрегированный файл
        save_aggregate(collected, all_reviews)
        print(f"Готово. Сохранено школ: {len(collected)}")

    finally:
        driver.quit()


if __name__ == "__main__":
    import sys
    input_file = sys.argv[1] if len(sys.argv) > 1 else None
    main(input_file)




