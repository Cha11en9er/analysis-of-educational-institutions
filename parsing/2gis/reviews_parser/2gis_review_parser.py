#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер отзывов школ 2ГИС на Selenium.
Читает ссылки из файла со списком школ и сохраняет все отзывы в один файл:

reviews: [{ school_id, date, text, likes_count }]

Сохраняет все отзывы в файл: 2gis_reviews_data/2gis_scools_reviews.json
"""

import json
import os
import re
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
REVIEWS_DATA_DIR = os.path.join(os.path.dirname(__file__), "2gis_reviews_data")
REVIEWS_OUTPUT_FILE = os.path.join(REVIEWS_DATA_DIR, "2gis_scools_reviews.json")
DEBUG_HTML_DIR = os.path.join(os.path.dirname(__file__), "debug_html")


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




def extract_reviews_from_json(html: str) -> List[Dict[str, Any]]:
    """Извлекает отзывы из JSON данных в HTML"""
    reviews_data = []
    processed_texts = set()  # Для избежания дубликатов
    
    # Сначала пытаемся найти JSON в script тегах
    script_pattern = r'<script[^>]*type\s*=\s*["\']application/json["\'][^>]*>(.*?)</script>'
    script_matches = re.finditer(script_pattern, html, re.DOTALL | re.IGNORECASE)
    
    for script_match in script_matches:
        script_content = script_match.group(1)
        try:
            # Пытаемся распарсить JSON
            data = json.loads(script_content)
            # Рекурсивно ищем отзывы в JSON структуре
            reviews = _find_reviews_in_json(data)
            for review in reviews:
                text = review.get('text', '')
                if text and text not in processed_texts:
                    processed_texts.add(text)
                    reviews_data.append(review)
        except:
            pass
    
    # Если не нашли в script тегах, ищем JSON объекты напрямую в HTML
    # Ищем все места, где есть "text" и "likes_count" в пределах разумного расстояния
    if not reviews_data:
        # Ищем паттерн для текста отзыва
        text_pattern = r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"'
        
        for text_match in re.finditer(text_pattern, html):
            text_pos = text_match.start()
            text = text_match.group(1)
            # Декодируем escape-последовательности
            text = text.replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r').replace('\\\\', '\\')
            
            # Пропускаем пустые тексты и дубликаты
            if not text or text in processed_texts:
                continue
            
            # Ищем likes_count в окрестности (в пределах 1500 символов)
            context_start = max(0, text_pos - 500)
            context_end = min(len(html), text_pos + 1500)
            context = html[context_start:context_end]
            
            likes_match = re.search(r'"likes_count"\s*:\s*(\d+)', context)
            if not likes_match:
                continue
            
            likes_count = int(likes_match.group(1))
            
            # Ищем дату в разных форматах (расширяем контекст для поиска даты)
            date = ''
            date_context_start = max(0, text_pos - 1000)
            date_context_end = min(len(html), text_pos + 2000)
            date_context = html[date_context_start:date_context_end]
            
            date_patterns = [
                r'"date"\s*:\s*"((?:[^"\\]|\\.)*)"',
                r'"created_at"\s*:\s*"((?:[^"\\]|\\.)*)"',
                r'"published_at"\s*:\s*"((?:[^"\\]|\\.)*)"',
            ]
            for date_pattern in date_patterns:
                date_match = re.search(date_pattern, date_context)
                if date_match:
                    date = date_match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r')
                    break
            
            processed_texts.add(text)
            reviews_data.append({
                'text': text,
                'likes_count': likes_count,
                'date': date
            })
    
    return reviews_data


def _find_reviews_in_json(data: Any, path: str = '') -> List[Dict[str, Any]]:
    """Рекурсивно ищет отзывы в JSON структуре"""
    reviews = []
    
    if isinstance(data, dict):
        # Проверяем, является ли это объектом отзыва
        if 'text' in data and 'likes_count' in data:
            review = {
                'text': data.get('text', ''),
                'likes_count': int(data.get('likes_count', 0)),
                'date': data.get('date', data.get('created_at', data.get('published_at', '')))
            }
            reviews.append(review)
        else:
            # Рекурсивно ищем в значениях словаря
            for key, value in data.items():
                reviews.extend(_find_reviews_in_json(value, f"{path}.{key}"))
    elif isinstance(data, list):
        # Рекурсивно ищем в элементах списка
        for idx, item in enumerate(data):
            reviews.extend(_find_reviews_in_json(item, f"{path}[{idx}]"))
    
    return reviews


def parse_reviews(driver: webdriver.Chrome, review_url: str, school_id: str) -> list:
    """Парсит отзывы из JSON данных в HTML и даты из DOM"""
    try:
        driver.get(review_url)
    except Exception as e:
        print(f"[error] Не удалось загрузить страницу для школы {school_id}: {e}")
        return []
    
    # Ждём загрузки элементов отзывов (может не быть, если отзывов нет)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, '_a5f6uz'))
        )
    except TimeoutException:
        # Проверяем, есть ли вообще отзывы на странице
        try:
            # Ищем любые признаки отзывов
            has_reviews = driver.find_elements(By.CLASS_NAME, '_1wlx08h') or \
                         driver.find_elements(By.CLASS_NAME, '_1msln3t') or \
                         driver.find_elements(By.CLASS_NAME, '_a5f6uz')
            if not has_reviews:
                print(f"[info] У школы {school_id} нет отзывов")
                return []
        except:
            pass
        print(f"[warn] Таймаут ожидания загрузки отзывов для школы {school_id}")
    
    time.sleep(2.0)  # Дополнительная пауза для загрузки данных
    
    # Прокрутка для загрузки всех отзывов
    try:
        for i in range(6):  # Увеличиваем количество прокруток
            driver.execute_script('window.scrollBy(0, 500);')
            time.sleep(1.0)  # Увеличиваем паузу
    except Exception as e:
        print(f"[warn] Не удалось выполнить прокрутку: {e}")
    
    time.sleep(2.0)  # Пауза после прокрутки для загрузки данных
    
    # Получаем HTML контент
    try:
        html_content = driver.page_source
    except Exception as e:
        print(f"[error] Не удалось получить HTML для школы {school_id}: {e}")
        return []
    
    # Сохраняем HTML для отладки
    try:
        os.makedirs(DEBUG_HTML_DIR, exist_ok=True)
        html_file = os.path.join(DEBUG_HTML_DIR, f"{school_id}_reviews.html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(f"<!-- URL: {review_url} -->\n")
            f.write(f"<!-- School ID: {school_id} -->\n")
            f.write(html_content)
        print(f"[debug] Сохранён HTML: {school_id}_reviews.html")
    except Exception as e:
        print(f"[warn] Не удалось сохранить HTML: {e}")
    
    # Сначала пытаемся извлечь отзывы из JSON данных в HTML
    try:
        json_reviews = extract_reviews_from_json(html_content)
        print(f"[debug] Извлечено отзывов из JSON: {len(json_reviews)}")
    except Exception as e:
        print(f"[error] Ошибка при извлечении отзывов из JSON для школы {school_id}: {e}")
        json_reviews = []
    
    # Если нашли отзывы в JSON, используем их, но даты извлекаем из DOM
    if json_reviews:
        try:
            # Извлекаем все тексты отзывов из DOM для сопоставления с датами
            text_elements_long = driver.find_elements(By.CLASS_NAME, '_1wlx08h')
            text_elements_short = driver.find_elements(By.CLASS_NAME, '_1msln3t')
            dom_texts = []
            
            # Сопоставляем тексты и даты из DOM
            for text_elem in text_elements_long + text_elements_short:
                try:
                    text = text_elem.text.strip()
                    if not text:
                        continue
                    
                    # Ищем дату для этого текста - ищем ближайший элемент _a5f6uz в родительских элементах
                    date = ''
                    try:
                        par = text_elem
                        for _ in range(10):  # Ищем в родительских элементах
                            par = par.find_element(By.XPATH, '..')
                            try:
                                date_elem = par.find_element(By.CLASS_NAME, '_a5f6uz')
                                date = date_elem.text.strip()
                                if date:
                                    break
                            except:
                                continue
                    except:
                        pass
                    
                    if text and text not in [t['text'] for t in dom_texts]:
                        dom_texts.append({'text': text, 'date': date})
                except Exception as e:
                    print(f"[warn] Ошибка при обработке элемента текста: {e}")
                    continue
            
            print(f"[debug] Найдено текстов в DOM: {len(dom_texts)}")
            
            # Сопоставляем JSON отзывы с датами из DOM
            reviews = []
            for review_data in json_reviews:
                try:
                    text = review_data.get('text', '')
                    date = review_data.get('date', '')
                    
                    # Если дата не найдена в JSON, ищем её в DOM по тексту
                    if not date:
                        # Ищем точное совпадение текста
                        for dom_item in dom_texts:
                            if dom_item['text'] == text or text.startswith(dom_item['text'][:50]) or dom_item['text'].startswith(text[:50]):
                                date = dom_item['date']
                                break
                        
                        # Если не нашли точное совпадение, ищем частичное
                        if not date:
                            for dom_item in dom_texts:
                                # Сравниваем первые 100 символов
                                text_start = text[:100] if len(text) > 100 else text
                                dom_text_start = dom_item['text'][:100] if len(dom_item['text']) > 100 else dom_item['text']
                                if text_start == dom_text_start or (len(text_start) > 50 and text_start in dom_text_start) or (len(dom_text_start) > 50 and dom_text_start in text_start):
                                    date = dom_item['date']
                                    break
                    
                    reviews.append({
                        'school_id': school_id,
                        'date': date,
                        'text': text,
                        'likes_count': review_data.get('likes_count', 0)
                    })
                except Exception as e:
                    print(f"[warn] Ошибка при обработке отзыва: {e}")
                    continue
            
            print(f"[debug] Обработано отзывов из JSON с датами из DOM: {len(reviews)}")
            return reviews
        except Exception as e:
            print(f"[error] Ошибка при извлечении дат из DOM для школы {school_id}: {e}")
            # Возвращаем отзывы без дат, если не удалось извлечь даты
            reviews = []
            for review_data in json_reviews:
                reviews.append({
                    'school_id': school_id,
                    'date': review_data.get('date', ''),
                    'text': review_data.get('text', ''),
                    'likes_count': review_data.get('likes_count', 0)
                })
            return reviews
    
    # Если не нашли в JSON, используем старый метод парсинга DOM
    print("[debug] JSON отзывы не найдены, используем парсинг DOM")
    
    try:
        # Ищем контейнеры отзывов - ищем элементы с классом, который содержит отзывы
        # Пробуем найти все контейнеры отзывов
        review_containers = driver.find_elements(By.CSS_SELECTOR, '[class*="_172gbf8"], [class*="_1k5soqfl"]')
        if not review_containers:
            # Альтернативный способ - ищем по структуре
            try:
                review_containers = driver.find_elements(By.XPATH, "//div[contains(@class, '_') and .//div[contains(@class, '_a5f6uz')]]")
            except:
                review_containers = []
        
        print(f"[debug] Найдено контейнеров отзывов: {len(review_containers)}")
        
        if not review_containers:
            print(f"[info] У школы {school_id} нет отзывов (контейнеры не найдены)")
            return []
        
        reviews = []
        processed_texts = set()  # Для избежания дубликатов
        
        # Для каждого контейнера извлекаем данные отзыва
        for idx, container in enumerate(review_containers):
            try:
                # Ищем текст отзыва
                text_elem = None
                try:
                    text_elem = container.find_element(By.CLASS_NAME, '_1wlx08h')
                except:
                    try:
                        text_elem = container.find_element(By.CLASS_NAME, '_1msln3t')
                    except:
                        pass
                
                if not text_elem:
                    continue
                
                text = text_elem.text.strip()
                if not text or text in processed_texts:
                    continue
                
                processed_texts.add(text)
                
                # Ищем дату
                date = ''
                try:
                    date_elem = container.find_element(By.CLASS_NAME, '_a5f6uz')
                    date = date_elem.text.strip()
                except:
                    pass
                
                # Извлекаем likes_count из JSON в HTML
                likes_count = 0
                try:
                    # Ищем JSON данные для этого отзыва в HTML
                    # Ищем текст отзыва в HTML и рядом с ним ищем likes_count
                    text_escaped = re.escape(text[:100])  # Первые 100 символов для поиска
                    pattern = rf'{text_escaped}.*?"likes_count"\s*:\s*(\d+)'
                    match = re.search(pattern, html_content, re.DOTALL)
                    if match:
                        likes_count = int(match.group(1))
                except Exception as e:
                    print(f"[debug] Не удалось извлечь likes_count для отзыва {idx}: {e}")
                
                reviews.append({
                    'school_id': school_id,
                    'date': date,
                    'text': text,
                    'likes_count': likes_count
                })
                
                print(f"[debug] Обработан отзыв {idx}: текст (длина: {len(text)}), дата: {date}, likes_count: {likes_count}")
                
            except Exception as e:
                print(f"[debug] Ошибка при обработке контейнера {idx}: {e}")
                continue
        
        print(f"[debug] Обработано контейнеров: {len(review_containers)}, найдено уникальных отзывов: {len(reviews)}")
        return reviews
    except Exception as e:
        print(f"[error] Ошибка при парсинге DOM для школы {school_id}: {e}")
        return []


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
    if "data" in data:
        return data.get("data", [])
    elif "school_name" in data:
        return data.get("school_name", [])
    else:
        return data if isinstance(data, list) else []


def save_all_reviews(reviews: list) -> None:
    """Сохраняет все отзывы в один файл"""
    os.makedirs(REVIEWS_DATA_DIR, exist_ok=True)
    
    # Загружаем существующие отзывы, если файл есть
    existing_reviews = []
    if os.path.exists(REVIEWS_OUTPUT_FILE):
        try:
            with open(REVIEWS_OUTPUT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_reviews = data.get("reviews", [])
        except Exception:
            existing_reviews = []
    
    # Объединяем старые и новые отзывы
    all_reviews = existing_reviews + reviews
    
    # Сохраняем все отзывы
    payload = {
        "resource": "2gis",
        "reviews": all_reviews,
    }
    with open(REVIEWS_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main(input_file: str = None) -> None:
    """
    Основная функция парсинга отзывов
    
    Args:
        input_file: Путь к JSON файлу со списком школ (должен содержать поля 'feedback_link')
                   Если не указан, ищет файл в текущей директории
    """
    # Ищем входной файл
    if input_file is None:
        # Ищем в разных местах
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "2gis_reviews_data", "2gis_schools_with_info.json"),
            os.path.join(os.path.dirname(__file__), "input.json"),
        ]
        input_file = None
        for path in possible_paths:
            if os.path.exists(path):
                input_file = path
                break
        
        if input_file is None:
            print("Ошибка: не найден входной файл со списком школ")
            print("Укажите путь к файлу с полем 'feedback_link' для каждой школы")
            return
    
    schools_data = load_input_links(input_file)
    if not schools_data:
        print(f"Файл {input_file} пуст или не содержит данных о школах")
        return

    driver = setup_driver()
    all_reviews = []

    try:
        for item in schools_data:
            school_id = item.get("id", "").strip()
            feedback_link = item.get("feedback_link", "").strip()
            
            if not school_id:
                print(f"Пропущена запись без id: {item.get('name', 'неизвестно')}")
                continue

            # Парсинг отзывов
            if feedback_link:
                print(f"Парсинг отзывов для школы {school_id}: {item.get('name', 'неизвестно')}")
                reviews = parse_reviews(driver, feedback_link, school_id)
                all_reviews.extend(reviews)
                print(f"  Найдено отзывов: {len(reviews)}")
            else:
                print(f"Пропущена школа {school_id}: нет feedback_link")
            
            time.sleep(0.5)

        # Сохраняем все отзывы в один файл
        save_all_reviews(all_reviews)
        print(f"Готово. Всего отзывов: {len(all_reviews)}")

    finally:
        driver.quit()


if __name__ == "__main__":
    import sys
    input_file = sys.argv[1] if len(sys.argv) > 1 else None
    main(input_file)




