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

import pyautogui
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains


# Пути относительно текущего файла
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TGIS_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
DATA_DIR = os.path.join(TGIS_ROOT, "2gis_data")
OUTPUT_DIR = os.path.join(DATA_DIR, "tgis_output")
REVIEWS_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "2gis_school_reviews.json")
DEBUG_HTML_DIR = os.path.join(OUTPUT_DIR, "debug_html")


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


def scroll_page_with_pyautogui(duration: float = 3.0, scroll_distance: int = 3000, scroll_step: int = 20) -> None:
    """
    Прокручивает страницу вниз с помощью pyautogui.
    Перемещает курсор в правую середину окна и медленно прокручивает вниз.
    
    Args:
        duration: Длительность прокрутки в секундах (по умолчанию 3 секунды)
        scroll_distance: Расстояние прокрутки в пикселях (по умолчанию 3000)
        scroll_step: Размер одного шага прокрутки в пикселях (по умолчанию 20)
                    Больше значение = быстрее прокрутка, но менее плавно
                    Меньше значение = медленнее прокрутка, но более плавно
    
    Returns:
        None
    """
    try:
        # Пауза перед началом прокрутки
        time.sleep(0.5)
        
        # Получаем размеры экрана
        screen_width, screen_height = pyautogui.size()
        
        # Вычисляем координаты правой середины экрана
        # Правая треть экрана, по вертикали - середина
        target_x = int(screen_width * 0.25)  # Правая треть
        target_y = int(screen_height * 0.5)    # Середина по вертикали
        
        # Быстро перемещаем курсор в целевую позицию
        pyautogui.moveTo(target_x, target_y, duration=0.1)
        time.sleep(0.1)  # Небольшая пауза после перемещения
        
        # Вычисляем количество шагов прокрутки
        steps = max(1, int(scroll_distance / scroll_step))  # Минимум 1 шаг
        step_duration = duration / steps if steps > 0 else 0
        
        # Прокручиваем вниз
        for i in range(steps):
            pyautogui.scroll(-scroll_step)  # Прокрутка вниз (отрицательное значение)
            if step_duration > 0:
                time.sleep(step_duration)
        
        time.sleep(1.0)  # Пауза после прокрутки для загрузки динамического контента
        
    except Exception as e:
        pass




def convert_date_to_postgresql_format(date_str: str) -> str:
    """
    Преобразует дату из ISO формата (например, "2019-09-25T00:33:10.681822+07:00")
    в формат для PostgreSQL (YYYY-MM-DD)
    
    Args:
        date_str: Дата в ISO формате с часовым поясом
        
    Returns:
        Дата в формате YYYY-MM-DD для PostgreSQL
    """
    if not date_str:
        return ''
    
    try:
        # Извлекаем только дату (до символа T)
        if 'T' in date_str:
            date_part = date_str.split('T')[0]
            return date_part
        # Если уже в формате YYYY-MM-DD
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        return date_str
    except Exception:
        return date_str


def extract_reviews_from_json(html: str) -> List[Dict[str, Any]]:
    """
    Извлекает отзывы из JSON данных в HTML.
    Ищет структуру: review -> review_id -> data -> {text, rating, date_created}
    """
    reviews_data = []
    processed_review_ids = set()  # Для избежания дубликатов по ID отзыва
    
    # Пытаемся найти JSON в script тегах с type="application/json"
    script_pattern = r'<script[^>]*type\s*=\s*["\']application/json["\'][^>]*>(.*?)</script>'
    script_matches = re.finditer(script_pattern, html, re.DOTALL | re.IGNORECASE)
    
    for script_match in script_matches:
        script_content = script_match.group(1)
        try:
            # Пытаемся распарсить JSON
            data = json.loads(script_content)
            # Ищем объект "review" в JSON
            reviews = _extract_reviews_from_review_object(data)
            for review in reviews:
                review_id = review.get('review_id', '')
                if review_id and review_id not in processed_review_ids:
                    processed_review_ids.add(review_id)
                    reviews_data.append(review)
            if reviews_data:
                print(f"[debug] Найдено отзывов в application/json script: {len(reviews_data)}")
        except json.JSONDecodeError as e:
            continue
        except Exception as e:
            continue
    
    # Также ищем JSON в обычных script тегах (может быть встроен в JavaScript код)
    if not reviews_data:
        # Ищем паттерн вида: "review": {...} в script тегах
        script_pattern_js = r'<script[^>]*>(.*?)</script>'
        script_js_matches = re.finditer(script_pattern_js, html, re.DOTALL | re.IGNORECASE)
        
        for script_match in script_js_matches:
            script_content = script_match.group(1)
            # Ищем объект "review" в содержимом script
            if '"review"' in script_content and '"text"' in script_content:
                # Пытаемся найти JSON объект, содержащий "review"
                # Ищем начало объекта (может быть window.__INITIAL_STATE__ = {...} или просто {...})
                review_obj_pattern = r'["\']review["\']\s*:\s*\{'
                review_obj_matches = list(re.finditer(review_obj_pattern, script_content))
                
                for review_obj_match in review_obj_matches:
                    # Пытаемся извлечь JSON объект, начиная с "review"
                    start_pos = review_obj_match.start()
                    # Ищем начало полного JSON объекта (может быть в переменной)
                    json_start = start_pos
                    # Ищем назад до начала объекта или присваивания
                    while json_start > 0 and json_start > start_pos - 500:
                        if script_content[json_start:json_start+1] in ['{', '=']:
                            if script_content[json_start] == '{':
                                break
                            elif script_content[json_start] == '=':
                                # Ищем следующий { после =
                                json_start += 1
                                while json_start < len(script_content) and script_content[json_start] in [' ', '\n', '\r', '\t']:
                                    json_start += 1
                                if json_start < len(script_content) and script_content[json_start] == '{':
                                    break
                        json_start -= 1
                    
                    if json_start >= 0:
                        # Пытаемся найти конец JSON объекта
                        brace_count = 0
                        in_string = False
                        escape = False
                        i = json_start
                        end_pos = len(script_content)
                        
                        while i < len(script_content):
                            if escape:
                                escape = False
                            elif script_content[i] == '\\':
                                escape = True
                            elif script_content[i] == '"' and not escape:
                                in_string = not in_string
                            elif not in_string:
                                if script_content[i] == '{':
                                    brace_count += 1
                                elif script_content[i] == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end_pos = i + 1
                                        break
                            i += 1
                        
                        # Пытаемся распарсить найденный JSON
                        try:
                            json_str = script_content[json_start:end_pos]
                            # Убираем возможные присваивания в начале (например, window.__INITIAL_STATE__ = )
                            json_str = re.sub(r'^[^=]*=\s*', '', json_str.strip())
                            # Убираем возможные точки с запятой в конце
                            json_str = json_str.rstrip(';')
                            
                            data = json.loads(json_str)
                            reviews = _extract_reviews_from_review_object(data)
                            added_count = 0
                            for review in reviews:
                                review_id = review.get('review_id', '')
                                if review_id and review_id not in processed_review_ids:
                                    processed_review_ids.add(review_id)
                                    reviews_data.append(review)
                                    added_count += 1
                            
                            if added_count > 0:
                                print(f"[debug] Добавлено отзывов из JavaScript script: {added_count}, всего: {len(reviews_data)}")
                            
                            if reviews_data:
                                break  # Если нашли отзывы, прекращаем поиск
                        except Exception:
                            continue
                
                if reviews_data:
                    break  # Если нашли отзывы, прекращаем поиск
    
    # Если не нашли в script тегах, пытаемся найти JSON объект напрямую в HTML
    # Ищем объект "review": {...}
    if not reviews_data:
        # Ищем начало объекта "review"
        review_pattern = r'"review"\s*:\s*\{'
        review_matches = list(re.finditer(review_pattern, html))
        
        if review_matches:
            # Берем первый найденный объект review
            review_match = review_matches[0]
            start_pos = review_match.start()
            
            # Находим полный JSON объект, начиная с "review"
            # Ищем открывающую скобку после "review":
            brace_count = 0
            in_string = False
            escape = False
            i = review_match.end() - 1  # Начинаем с открывающей скобки
            
            # Находим начало объекта (может быть вложенный объект)
            while i > 0 and html[i] != '{':
                i -= 1
            
            if i >= 0 and html[i] == '{':
                # Теперь ищем конец объекта review
                brace_count = 1
                i += 1
                end_pos = i
                
                while i < len(html) and brace_count > 0:
                    if escape:
                        escape = False
                    elif html[i] == '\\':
                        escape = True
                    elif html[i] == '"' and not escape:
                        in_string = not in_string
                    elif not in_string:
                        if html[i] == '{':
                            brace_count += 1
                        elif html[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i + 1
                                break
                    i += 1
                
                # Пытаемся распарсить найденный JSON
                try:
                    # Ищем полный JSON объект, который содержит "review"
                    # Расширяем поиск назад, чтобы найти начало объекта
                    json_start = start_pos
                    while json_start > 0:
                        if html[json_start] == '{':
                            break
                        json_start -= 1
                    
                    # Пытаемся найти полный валидный JSON
                    # Ищем от начала объекта review до конца
                    json_str = html[json_start:end_pos]
                    
                    # Пробуем распарсить как полный объект
                    try:
                        data = json.loads(json_str)
                    except:
                        # Пробуем обернуть в фигурные скобки, если это не полный объект
                        if not json_str.strip().startswith('{'):
                            json_str = '{' + json_str + '}'
                        data = json.loads(json_str)
                    
                    reviews = _extract_reviews_from_review_object(data)
                    added_count = 0
                    for review in reviews:
                        review_id = review.get('review_id', '')
                        if review_id and review_id not in processed_review_ids:
                            processed_review_ids.add(review_id)
                            reviews_data.append(review)
                            added_count += 1
                    if added_count > 0:
                        print(f"[debug] Добавлено отзывов из HTML JSON: {added_count}, всего: {len(reviews_data)}")
                except Exception as e:
                    # Если не удалось распарсить как JSON, пробуем найти через regex
                    pass
    
    # Если всё ещё не нашли, пробуем найти через поиск структуры "review": {...}
    # Это fallback метод для случаев, когда JSON не валидный
    if not reviews_data:
        # Ищем все вхождения "review": { и извлекаем каждый отзыв отдельно
        # Ищем паттерн начала объекта review с review_id
        review_id_pattern = r'"review"\s*:\s*\{[^}]*"(\d+)"\s*:\s*\{'
        review_id_matches = list(re.finditer(review_id_pattern, html, re.DOTALL))
        
        for review_id_match in review_id_matches:
            review_id = review_id_match.group(1)
            if review_id in processed_review_ids:
                continue
            
            # Находим начало объекта data для этого review_id
            match_start = review_id_match.end()
            # Ищем "data": { после review_id
            data_match = re.search(r'"data"\s*:\s*\{', html[match_start:match_start + 500])
            if not data_match:
                continue
            
            data_start = match_start + data_match.end() - 1  # Позиция открывающей скобки data
            
            # Извлекаем текст отзыва с правильной обработкой escape-последовательностей
            # Ищем "text": " и извлекаем до закрывающей кавычки с учетом escape
            text_pattern = r'"text"\s*:\s*"'
            text_match = re.search(text_pattern, html[data_start:data_start + 50000])  # Увеличиваем контекст до 50000
            if not text_match:
                continue
            
            text_start_pos = data_start + text_match.end()
            text_end_pos = text_start_pos
            
            # Вручную парсим строку JSON, учитывая escape-последовательности
            max_search_length = min(text_start_pos + 20000, len(html))  # Увеличиваем лимит до 20000
            i = text_start_pos
            in_string = True
            escape = False
            
            while i < max_search_length:
                if escape:
                    escape = False
                    i += 1
                    continue
                elif html[i] == '\\':
                    escape = True
                    i += 1
                    continue
                elif html[i] == '"':
                    # Проверяем, что после кавычки идет валидный JSON символ
                    if i + 1 < len(html):
                        next_char = html[i + 1]
                        if next_char in [',', '}', ']', ' ', '\n', '\r', '\t', ':']:
                            text_end_pos = i
                            break
                    else:
                        text_end_pos = i
                        break
                i += 1
            
            if text_end_pos == text_start_pos:
                continue  # Не нашли закрывающую кавычку
            
            # Извлекаем текст с escape-последовательностями
            text_with_escapes = html[text_start_pos:text_end_pos]
            
            # Декодируем escape-последовательности через json.loads
            try:
                text = json.loads('"' + text_with_escapes + '"')
            except json.JSONDecodeError:
                # Fallback на ручное декодирование
                text = text_with_escapes.replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t').replace('\\\\', '\\')
            
            # Ищем rating и date_created в окрестности
            search_start = max(0, data_start)
            search_end = min(len(html), text_end_pos + 2000)
            search_context = html[search_start:search_end]
            
            rating_match = re.search(r'"rating"\s*:\s*(\d+)', search_context)
            date_match = re.search(r'"date_created"\s*:\s*"([^"]+)"', search_context)
            likes_match = re.search(r'"likes_count"\s*:\s*(\d+)', search_context)
            
            rating = int(rating_match.group(1)) if rating_match else None
            date_created = date_match.group(1) if date_match else ''
            likes_count = int(likes_match.group(1)) if likes_match else 0
            
            processed_review_ids.add(review_id)
            reviews_data.append({
                'review_id': review_id,
                'text': text,
                'rating': rating,
                'date_created': date_created,
                'date': convert_date_to_postgresql_format(date_created),
                'likes_count': likes_count
            })
            print(f"[debug] Извлечен отзыв через fallback метод {review_id}: текст (длина: {len(text)}), рейтинг: {rating}")
    
    if reviews_data:
        print(f"[debug] Всего извлечено отзывов: {len(reviews_data)}")
    
    return reviews_data


def _extract_reviews_from_review_object(data: Any) -> List[Dict[str, Any]]:
    """
    Извлекает отзывы из JSON структуры вида:
    {
        "review": {
            "review_id": {
                "data": {
                    "text": "...",
                    "rating": 5,
                    "date_created": "...",
                    ...
                },
                "meta": {...}
            }
        }
    }
    """
    reviews = []
    
    if not isinstance(data, dict):
        return reviews
    
    # Ищем объект "review"
    if 'review' in data:
        review_obj = data['review']
        if isinstance(review_obj, dict):
            # Проходим по всем ключам (это review_id) - ВАЖНО: извлекаем ВСЕ отзывы
            total_reviews_found = len(review_obj)
            print(f"[debug] Найдено отзывов в объекте review: {total_reviews_found}")
            
            for review_id, review_data in review_obj.items():
                if isinstance(review_data, dict) and 'data' in review_data:
                    review_data_obj = review_data['data']
                    if isinstance(review_data_obj, dict):
                        # Извлекаем нужные поля
                        text = review_data_obj.get('text', '')
                        rating = review_data_obj.get('rating')
                        date_created = review_data_obj.get('date_created', '')
                        likes_count = review_data_obj.get('likes_count', 0)
                        
                        # Проверяем, что это действительно отзыв (есть текст)
                        if text:
                            review = {
                                'review_id': review_id,
                                'text': text,
                                'rating': rating,
                                'date_created': date_created,
                                'date': convert_date_to_postgresql_format(date_created),
                                'likes_count': int(likes_count) if likes_count is not None else 0
                            }
                            reviews.append(review)
                            print(f"[debug] Извлечен отзыв {review_id}: текст (длина: {len(text)}), рейтинг: {rating}, дата: {date_created}")
                        else:
                            print(f"[debug] Пропущен отзыв {review_id}: нет текста")
                else:
                    print(f"[debug] Пропущен отзыв {review_id}: нет структуры data")
            
            print(f"[debug] Всего извлечено валидных отзывов: {len(reviews)} из {total_reviews_found}")
    
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
                return [{
                    'school_id': school_id,
                    'text': None,
                    'rating': None,
                    'date': None,
                    'date_created': None,
                    'likes_count': None
                }]
        except:
            pass
        print(f"[warn] Таймаут ожидания загрузки отзывов для школы {school_id}")
    
    time.sleep(1.0)  # Дополнительная пауза для загрузки данных
    
    # Физическая прокрутка для загрузки всех отзывов через pyautogui
    try:
        scroll_page_with_pyautogui(duration=2.0, scroll_distance=2000, scroll_step=30)
    except Exception as e:
        # Fallback на обычную прокрутку через JavaScript
        try:
            for i in range(5):
                driver.execute_script('window.scrollBy(0, 500);')
                time.sleep(0.3)
        except Exception as e2:
            pass
    
    time.sleep(1.5)  # Дополнительная пауза после прокрутки для загрузки данных
    
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
    
    # Извлекаем отзывы из JSON данных в HTML
    try:
        json_reviews = extract_reviews_from_json(html_content)
        print(f"[debug] Извлечено отзывов из JSON: {len(json_reviews)}")
    except Exception as e:
        print(f"[error] Ошибка при извлечении отзывов из JSON для школы {school_id}: {e}")
        json_reviews = []
    
    # Если нашли отзывы в JSON, используем их напрямую
    if json_reviews:
        reviews = []
        for review_data in json_reviews:
            try:
                reviews.append({
                    'school_id': school_id,
                    'text': review_data.get('text', ''),
                    'rating': review_data.get('rating'),
                    'date': review_data.get('date', ''),  # Уже в формате YYYY-MM-DD для PostgreSQL
                    'date_created': review_data.get('date_created', ''),  # Оригинальная дата в ISO формате
                    'likes_count': review_data.get('likes_count', 0)
                })
            except Exception as e:
                print(f"[warn] Ошибка при обработке отзыва: {e}")
                continue
        
        print(f"[debug] Обработано отзывов из JSON: {len(reviews)}")
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
            return [{
                'school_id': school_id,
                'text': None,
                'rating': None,
                'date': None,
                'date_created': None,
                'likes_count': None
            }]
        
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
                    # Используем более надежный метод: ищем начало текста в JSON и извлекаем до закрывающей кавычки
                    # Берем первые 30 символов текста для поиска (меньше, чтобы избежать проблем с кавычками и спецсимволами)
                    text_search = text[:30] if len(text) > 30 else text
                    # Экранируем специальные символы для regex
                    text_search_escaped = re.escape(text_search)
                    
                    # Ищем позицию текста (или его начала) в HTML - ищем как в экранированном, так и в неэкранированном виде
                    text_positions = []
                    # Поиск точного совпадения (текст может быть в DOM или в JSON)
                    for match_obj in re.finditer(text_search_escaped, html_content):
                        text_positions.append(match_obj.start())
                    
                    # Для каждой позиции ищем ближайший likes_count в JSON
                    for text_pos in text_positions:
                        # Ищем в окрестности (в пределах 3000 символов)
                        search_start = max(0, text_pos - 1000)
                        search_end = min(len(html_content), text_pos + 3000)
                        search_context = html_content[search_start:search_end]
                        
                        # Ищем "likes_count" в этом контексте
                        likes_match = re.search(r'"likes_count"\s*:\s*(\d+)', search_context)
                        if likes_match:
                            likes_count = int(likes_match.group(1))
                            break
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


def load_existing_reviews() -> list:
    """Загружает существующие отзывы из файла"""
    if os.path.exists(REVIEWS_OUTPUT_FILE):
        try:
            with open(REVIEWS_OUTPUT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("reviews", [])
        except Exception:
            return []
    return []


def save_reviews_for_school(school_id: str, reviews: list) -> None:
    """Сохраняет отзывы для одной школы, удаляя старые отзывы этой школы"""
    os.makedirs(REVIEWS_DATA_DIR, exist_ok=True)
    
    # Загружаем существующие отзывы
    existing_reviews = load_existing_reviews()
    
    # Удаляем старые отзывы для этой школы
    existing_reviews = [r for r in existing_reviews if r.get('school_id') != school_id]
    
    # Добавляем новые отзывы
    all_reviews = existing_reviews + reviews
    
    # Сохраняем все отзывы
    payload = {
        "resource": "2gis",
        "reviews": all_reviews,
    }
    with open(REVIEWS_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def save_all_reviews(reviews: list) -> None:
    """Сохраняет все отзывы в один файл (для обратной совместимости)"""
    os.makedirs(REVIEWS_DATA_DIR, exist_ok=True)
    
    # Загружаем существующие отзывы, если файл есть
    existing_reviews = load_existing_reviews()
    
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
        # Ищем в разных местах (тестовый файл имеет приоритет)
        possible_paths = [
            os.path.join(REVIEWS_DATA_DIR, "input", "2gis_test_review_school.json"),  # Тестовый файл
            os.path.join(REVIEWS_DATA_DIR, "input", "2gis_schools_with_info.json"),  # Основной файл
        ]
        input_file = None
        for path in possible_paths:
            if os.path.exists(path):
                input_file = path
                print(f"[info] Используется входной файл: {path}")
                break
        
        if input_file is None:
            print("Ошибка: не найден входной файл со списком школ")
            print(f"Ожидаемые пути:")
            for path in possible_paths:
                print(f"  - {path}")
            print("Укажите путь к файлу с полем 'feedback_link' для каждой школы")
            return
    
    schools_data = load_input_links(input_file)
    if not schools_data:
        print(f"Файл {input_file} пуст или не содержит данных о школах")
        return

    # Выводим информацию о путях
    print(f"[info] Входной файл: {input_file}")
    print(f"[info] Выходной файл: {REVIEWS_OUTPUT_FILE}")
    print(f"[info] Директория для debug HTML: {DEBUG_HTML_DIR}")
    print(f"[info] Найдено школ для обработки: {len(schools_data)}")
    print()

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
                
                # Сохраняем отзывы для этой школы сразу после обработки
                save_reviews_for_school(school_id, reviews)
                print(f"  Сохранено отзывов для школы {school_id}")
            else:
                print(f"Пропущена школа {school_id}: нет feedback_link")
            
            time.sleep(0.5)

        print(f"Готово. Всего отзывов обработано: {len(all_reviews)}")

    finally:
        driver.quit()


if __name__ == "__main__":
    import sys
    input_file = sys.argv[1] if len(sys.argv) > 1 else None
    main(input_file)



