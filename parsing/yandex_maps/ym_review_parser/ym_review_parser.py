#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер отзывов школ с Яндекс карт.
Читает данные из yandex_reviews_test_data.json и парсит отзывы для каждой организации.
"""

import json
import os
import re
import time
from typing import List, Dict, Any, Optional

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.common import exceptions as selenium_exceptions
    from bs4 import BeautifulSoup
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("[ERROR] Selenium не установлен. Установите: pip install selenium beautifulsoup4")


# Пути относительно текущего файла
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # ym_review_parser
YM_ROOT = os.path.dirname(CURRENT_DIR)  # yandex_maps
DATA_DIR = os.path.normpath(os.path.join(YM_ROOT, "ym_data", "ym_reviews_data"))
DEBUG_HTML_DIR = os.path.join(DATA_DIR, "debug_html")
INPUT_DIR = os.path.join(DATA_DIR, "input")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
INPUT_FILE = os.path.join(INPUT_DIR, "ym_test_review_school.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ym_review_output.json")


class Review:
    """Класс для представления отзыва"""
    
    def __init__(self, rate: int, text: str, date: str = "", likes: int = 0, dislikes: int = 0):
        self.rating = rate
        self.text = text
        self.date = date
        self.likes = likes
        self.dislikes = dislikes
    
    def __str__(self):
        return f'rate: {self.rating}, text: {self.text[:50]}..., date: {self.date}, likes: {self.likes}, dislikes: {self.dislikes}'
    
    def to_dict(self, school_id: str = None) -> Dict[str, Any]:
        """Преобразует отзыв в словарь для сохранения в JSON"""
        result = {}
        # Добавляем school_id первым, если указан
        if school_id is not None:
            result["school_id"] = school_id
        result["date"] = self.date
        result["text"] = self.text
        result["likes_count"] = self.likes
        result["dislikes_count"] = self.dislikes
        # Добавляем рейтинг только если он не равен 0
        if self.rating > 0:
            result["rating"] = self.rating
        return result


class YandexMapsReviewsParser:
    """Парсер отзывов с Яндекс карт"""
    
    def __init__(self):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium не установлен. Установите: pip install selenium beautifulsoup4")
        self.driver = None
    
    def setup_driver(self) -> webdriver.Chrome:
        """Настройка Chrome WebDriver"""
        chrome_options = Options()
        
        # Опции для обхода детекции ботов
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Отключаем изображения для ускорения
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("[OK] Chrome WebDriver инициализирован")
        except Exception as e:
            print(f"[ERROR] Ошибка инициализации WebDriver: {e}")
            print("Убедитесь, что ChromeDriver установлен и находится в PATH")
            raise
    
    def close_driver(self):
        """Закрывает WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    @staticmethod
    def _scroll_to_bottom(driver: webdriver.Chrome) -> None:
        """Прокручивает страницу до конца для загрузки всех отзывов"""
        bool_val = True
        last_scroll = -1
        max_attempts = 50  # Ограничение на количество попыток
        attempts = 0
        
        while bool_val and attempts < max_attempts:
            try:
                scroll_now, scroll_height = driver.execute_script(
                    """const scroll_element = document.getElementsByClassName('scroll__container')[0]; 
                    if (!scroll_element) {
                        return [0, 0];
                    }
                    const speed = 10000;
                    scroll_element.scrollBy({
                        top: 20000,
                        behavior: 'smooth'
                    });
                    return [scroll_element.scrollTop, scroll_element.scrollHeight];
                    """
                )
                
                bool_val = scroll_now < scroll_height
                
                if scroll_now == last_scroll:
                    break
                
                last_scroll = scroll_now
                attempts += 1
                time.sleep(0.1)
            except Exception as e:
                print(f"[WARN] Ошибка при прокрутке: {e}")
                break
    
    @staticmethod
    def _extract_reviews_from_json(html: str) -> List[Dict[str, Any]]:
        """
        Извлекает отзывы из JSON данных в HTML.
        Ищет объекты с полями reviewId, text, rating, updatedTime, reactions.
        
        Returns:
            Список словарей с данными отзывов из JSON
        """
        json_reviews = []
        processed_review_ids = set()
        
        try:
            # Метод 1: Ищем массив "reviews" в JSON
            # Ищем паттерн "reviews":[{...}]
            reviews_array_pattern = r'"reviews"\s*:\s*\['
            array_matches = list(re.finditer(reviews_array_pattern, html, re.IGNORECASE))
            
            for array_match in array_matches:
                try:
                    array_start = array_match.end()  # Позиция после "["
                    # Ищем закрывающую скобку массива
                    bracket_count = 1
                    array_end = array_start
                    
                    for i in range(array_start, min(array_start + 500000, len(html))):
                        if html[i] == '[':
                            bracket_count += 1
                        elif html[i] == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                array_end = i
                                break
                    
                    if array_end <= array_start:
                        continue
                    
                    array_content = html[array_start:array_end]
                    
                    # Ищем отдельные объекты в массиве
                    # Ищем начало каждого объекта (открывающая фигурная скобка)
                    obj_start = 0
                    while obj_start < len(array_content):
                        obj_start = array_content.find('{', obj_start)
                        if obj_start == -1:
                            break
                        
                        # Парсим объект от { до }
                        brace_count = 0
                        obj_end = obj_start
                        in_string = False
                        escape = False
                        
                        for i in range(obj_start, len(array_content)):
                            ch = array_content[i]
                            
                            if escape:
                                escape = False
                                continue
                            
                            if ch == '\\':
                                escape = True
                                continue
                            
                            if ch == '"' and not escape:
                                in_string = not in_string
                                continue
                            
                            if not in_string:
                                if ch == '{':
                                    brace_count += 1
                                elif ch == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        obj_end = i + 1
                                        break
                        
                        if obj_end <= obj_start:
                            obj_start += 1
                            continue
                        
                        # Извлекаем JSON объект
                        obj_str = array_content[obj_start:obj_end]
                        
                        try:
                            review_obj = json.loads(obj_str)
                            if 'text' in review_obj:
                                review_id = review_obj.get('reviewId') or review_obj.get('id') or str(len(json_reviews))
                                if review_id not in processed_review_ids:
                                    json_reviews.append(review_obj)
                                    processed_review_ids.add(review_id)
                        except json.JSONDecodeError:
                            pass
                        
                        obj_start = obj_end
                        
                except Exception as e:
                    continue
            
            # Метод 2: Ищем отдельные объекты с полем "text" (более универсальный подход)
            # Ищем паттерн "text":"..." и извлекаем полный объект
            if len(json_reviews) < 5:  # Если нашли мало отзывов, пробуем альтернативный метод
                # Ищем паттерн начала текста отзыва
                text_pattern = r'"text"\s*:\s*"'
                for match in re.finditer(text_pattern, html):
                    try:
                        # Находим начало объекта (ищем открывающую фигурную скобку перед text)
                        text_start_pos = match.start()
                        # Ищем начало объекта (может быть за 100-500 символов до text)
                        search_start = max(0, text_start_pos - 500)
                        obj_start = html.rfind('{', search_start, text_start_pos)
                        
                        if obj_start == -1:
                            continue
                        
                        # Парсим объект от { до }
                        brace_count = 0
                        obj_end = obj_start
                        in_string = False
                        escape = False
                        
                        for i in range(obj_start, min(obj_start + 10000, len(html))):
                            ch = html[i]
                            
                            if escape:
                                escape = False
                                continue
                            
                            if ch == '\\':
                                escape = True
                                continue
                            
                            if ch == '"' and not escape:
                                in_string = not in_string
                                continue
                            
                            if not in_string:
                                if ch == '{':
                                    brace_count += 1
                                elif ch == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        obj_end = i + 1
                                        break
                        
                        if obj_end <= obj_start:
                            continue
                        
                        obj_str = html[obj_start:obj_end]
                        
                        try:
                            review_obj = json.loads(obj_str)
                            if 'text' in review_obj and isinstance(review_obj.get('text'), str) and len(review_obj.get('text', '')) > 20:
                                review_id = review_obj.get('reviewId') or review_obj.get('id') or f"text_{hash(review_obj.get('text', '')[:50])}"
                                if review_id not in processed_review_ids:
                                    json_reviews.append(review_obj)
                                    processed_review_ids.add(review_id)
                        except json.JSONDecodeError:
                            pass
                            
                    except Exception as e:
                        continue
            
        except Exception as e:
            print(f"[WARN] Ошибка при извлечении отзывов из JSON: {e}")
        
        print(f"[DEBUG] Извлечено отзывов из JSON: {len(json_reviews)}")
        return json_reviews
    
    def _parse_page(self, url: str, org_id: str = None, org_name: str = None) -> tuple[List[Review], Dict[str, Any]]:
        """
        Парсит страницу с отзывами
        
        Returns:
            Кортеж (список отзывов, словарь с отладочной информацией)
        """
        res = []
        debug_info = {
            "url": url,
            "page_title": "",
            "html_saved": False,
            "html_file": "",
            "found_elements": {},
            "possible_selectors": {},
            "raw_html_length": 0
        }
        
        try:
            print(f"[INFO] Загрузка страницы: {url}")
            self.driver.get(url)
            time.sleep(3)  # Увеличиваем время ожидания загрузки страницы
            
            debug_info["page_title"] = self.driver.title
            print(f"[DEBUG] Заголовок страницы: {debug_info['page_title']}")
            
            print("[INFO] Прокрутка страницы для загрузки всех отзывов...")
            self._scroll_to_bottom(self.driver)
            time.sleep(2)  # Дополнительная пауза после прокрутки
            
            # Сохраняем HTML для отладки
            html_content = self.driver.page_source
            debug_info["raw_html_length"] = len(html_content)
            print(f"[DEBUG] Размер HTML: {len(html_content)} символов")
            
            # Сохраняем HTML в файл
            os.makedirs(DEBUG_HTML_DIR, exist_ok=True)
            safe_name = org_id or "unknown"
            html_filename = os.path.join(DEBUG_HTML_DIR, f"{safe_name}_reviews.html")
            try:
                with open(html_filename, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                debug_info["html_saved"] = True
                debug_info["html_file"] = html_filename
                print(f"[DEBUG] HTML сохранен в: {html_filename}")
            except Exception as e:
                print(f"[WARN] Не удалось сохранить HTML: {e}")
            
            # Извлекаем отзывы из JSON в HTML
            print("\n[DEBUG] Извлечение отзывов из JSON в HTML...")
            json_reviews_data = self._extract_reviews_from_json(html_content)
            
            bs = BeautifulSoup(html_content, 'html.parser')
            
            # Пробуем различные селекторы для отзывов
            possible_selectors = {
                "business-review-view__info": bs.find_all('div', class_='business-review-view__info'),
                "business-review-view": bs.find_all('div', class_='business-review-view'),
                "review-item": bs.find_all('div', class_='review-item'),
                "review": bs.find_all('div', class_='review'),
                "review-view": bs.find_all('div', class_='review-view'),
                "business-review": bs.find_all('div', class_='business-review'),
                "all_divs_with_review": [div for div in bs.find_all('div') if 'review' in str(div.get('class', [])).lower()],
            }
            
            debug_info["possible_selectors"] = {
                key: len(value) for key, value in possible_selectors.items()
            }
            
            print("\n[DEBUG] Результаты поиска различных селекторов:")
            for selector_name, elements in possible_selectors.items():
                count = len(elements)
                print(f"  - {selector_name}: найдено {count} элементов")
                if count > 0 and count <= 5:
                    # Показываем первые несколько элементов для анализа
                    print(f"    Примеры классов первых элементов:")
                    for i, elem in enumerate(elements[:3]):
                        classes = elem.get('class', [])
                        print(f"      [{i+1}] class='{' '.join(classes) if classes else 'нет классов'}'")
            
            # Используем основной селектор
            full_reviews_info = possible_selectors["business-review-view__info"]
            
            print(f"\n[INFO] Используем селектор 'business-review-view__info': найдено {len(full_reviews_info)} элементов")
            
            # Если основной селектор не работает, пробуем альтернативные
            if len(full_reviews_info) == 0:
                print("[WARN] Основной селектор не нашел элементов, пробуем альтернативные...")
                for selector_name, elements in possible_selectors.items():
                    if selector_name != "business-review-view__info" and len(elements) > 0:
                        print(f"[INFO] Пробуем использовать селектор: {selector_name} ({len(elements)} элементов)")
                        full_reviews_info = elements
                        break
            
            # Ищем все возможные элементы с текстом отзывов
            text_selectors = {
                "business-review-view__body-text": bs.find_all('span', class_='business-review-view__body-text'),
                "review-text": bs.find_all('span', class_='review-text'),
                "review-body": bs.find_all('div', class_='review-body'),
                "review-content": bs.find_all('div', class_='review-content'),
            }
            
            debug_info["found_elements"]["text_selectors"] = {
                key: len(value) for key, value in text_selectors.items()
            }
            
            print("\n[DEBUG] Поиск текста отзывов:")
            for selector_name, elements in text_selectors.items():
                count = len(elements)
                print(f"  - {selector_name}: найдено {count} элементов")
                if count > 0 and count <= 3:
                    for i, elem in enumerate(elements[:2]):
                        text_preview = elem.text.strip()[:100] if elem.text else "нет текста"
                        print(f"    [{i+1}] Текст (первые 100 символов): {text_preview}")
            
            # Ищем элементы с рейтингом
            rating_selectors = {
                "business-rating-badge-view__stars": bs.find_all('div', class_='business-rating-badge-view__stars'),
                "rating": bs.find_all('div', class_='rating'),
                "review-rating": bs.find_all('div', class_='review-rating'),
            }
            
            debug_info["found_elements"]["rating_selectors"] = {
                key: len(value) for key, value in rating_selectors.items()
            }
            
            print("\n[DEBUG] Поиск рейтингов:")
            for selector_name, elements in rating_selectors.items():
                count = len(elements)
                print(f"  - {selector_name}: найдено {count} элементов")
            
            # Парсим отзывы
            for elem in full_reviews_info:
                try:
                    # Получаем текст отзыва - используем spoiler-view__text-container
                    review_text = None
                    review_text_elem = elem.find('span', class_='spoiler-view__text-container')
                    
                    if review_text_elem:
                        review_text = review_text_elem.text.strip()
                    else:
                        # Если не нашли, пробуем альтернативные селекторы
                        for text_selector in ['business-review-view__body-text', 'review-text', 'review-body', 'review-content']:
                            review_text_elem = elem.find('span', class_=text_selector) or elem.find('div', class_=text_selector)
                            if review_text_elem:
                                review_text = review_text_elem.text.strip()
                                break
                    
                    # Если всё ещё не нашли, пробуем найти любой длинный текст внутри элемента
                    if not review_text:
                        text_elements = elem.find_all(['span', 'div', 'p'])
                        for text_elem in text_elements:
                            text = text_elem.text.strip() if text_elem.text else ""
                            # Игнорируем короткие тексты типа "Знаток города X уровня"
                            if len(text) > 30 and 'знаток города' not in text.lower():
                                review_text = text
                                break
                    
                    if not review_text:
                        print(f"[DEBUG] Не удалось найти текст отзыва в элементе")
                        continue
                    
                    # Получаем рейтинг - пробуем разные селекторы
                    rate = 0
                    rate_info = None
                    
                    for rating_selector in ['business-rating-badge-view__stars', 'rating', 'review-rating']:
                        rate_info = elem.find('div', class_=rating_selector)
                        if rate_info:
                            # Ищем заполненные звезды
                            full_stars = rate_info.find_all('span', 
                                class_='inline-image _loaded icon business-rating-badge-view__star _full _size_m')
                            if full_stars:
                                rate = len(full_stars)
                                break
                            # Пробуем другие варианты классов звезд
                            all_stars = rate_info.find_all(['span', 'div'], class_=lambda x: x and 'star' in ' '.join(x).lower())
                            if all_stars:
                                # Считаем заполненные звезды по другим признакам
                                rate = len([s for s in all_stars if 'full' in str(s.get('class', [])).lower() or '_full' in str(s.get('class', []))])
                                if rate > 0:
                                    break
                    
                    # Если не нашли рейтинг, пробуем найти по атрибутам data-rating или другим
                    if rate == 0:
                        rating_attr = elem.get('data-rating') or elem.find(attrs={'data-rating': True})
                        if rating_attr:
                            if isinstance(rating_attr, str):
                                try:
                                    rate = int(rating_attr)
                                except:
                                    pass
                            else:
                                try:
                                    rate = int(rating_attr.get('data-rating', 0))
                                except:
                                    pass
                    
                    # Получаем дату отзыва
                    review_date = ""
                    date_elem = elem.find('span', class_='business-review-view__date')
                    if date_elem:
                        date_span = date_elem.find('span')
                        if date_span:
                            review_date = date_span.text.strip()
                        else:
                            review_date = date_elem.text.strip()
                    
                    # Получаем лайки и дизлайки
                    likes = 0
                    dislikes = 0
                    
                    # Ищем все элементы с классом business-reactions-view__counter в элементе отзыва
                    counters_in_review = elem.find_all('div', class_='business-reactions-view__counter')
                    
                    if len(counters_in_review) >= 1:
                        try:
                            likes = int(counters_in_review[0].text.strip())
                        except (ValueError, AttributeError):
                            pass
                    if len(counters_in_review) >= 2:
                        try:
                            dislikes = int(counters_in_review[1].text.strip())
                        except (ValueError, AttributeError):
                            pass
                    
                    # Если не нашли в самом элементе, ищем в родительских элементах
                    if likes == 0 and dislikes == 0:
                        parent = elem.parent
                        if parent:
                            parent_counters = parent.find_all('div', class_='business-reactions-view__counter')
                            if len(parent_counters) >= 1:
                                try:
                                    likes = int(parent_counters[0].text.strip())
                                except (ValueError, AttributeError):
                                    pass
                            if len(parent_counters) >= 2:
                                try:
                                    dislikes = int(parent_counters[1].text.strip())
                                except (ValueError, AttributeError):
                                    pass
                    
                    if review_text:  # Добавляем только если есть текст
                        # Сопоставляем с отзывами из JSON и используем более полный текст
                        dom_text_normalized = ' '.join(review_text.split())
                        
                        # Ищем соответствующий отзыв в JSON по началу текста
                        json_text = review_text
                        json_rating = rate
                        json_likes = likes
                        json_dislikes = dislikes
                        
                        for json_review in json_reviews_data:
                            json_review_text = json_review.get('text', '')
                            if not json_review_text:
                                continue
                            
                            json_review_text_normalized = ' '.join(json_review_text.split())
                            
                            # Сравниваем первые 50 символов для сопоставления
                            dom_start = dom_text_normalized[:50] if len(dom_text_normalized) > 50 else dom_text_normalized
                            json_start = json_review_text_normalized[:50] if len(json_review_text_normalized) > 50 else json_review_text_normalized
                            
                            # Если начало совпадает и JSON текст длиннее - используем его
                            if dom_start and json_start and (
                                dom_start == json_start or 
                                (len(dom_start) > 30 and dom_start in json_review_text_normalized) or
                                (len(json_start) > 30 and json_start in dom_text_normalized)
                            ):
                                if len(json_review_text) > len(review_text):
                                    json_text = json_review_text
                                    # Обновляем данные из JSON, если они есть
                                    if 'rating' in json_review:
                                        json_rating = json_review.get('rating', rate)
                                    if 'reactions' in json_review:
                                        reactions = json_review.get('reactions', {})
                                        json_likes = reactions.get('likes', likes)
                                        json_dislikes = reactions.get('dislikes', dislikes)
                                    print(f"[DEBUG] Использован полный текст из JSON (было {len(review_text)} символов, стало {len(json_text)} символов)")
                                break
                        
                        res.append(Review(json_rating, json_text, review_date, json_likes, json_dislikes))
                        print(f"[DEBUG] Найден отзыв: рейтинг={json_rating}, дата={review_date}, лайки={json_likes}, дизлайки={json_dislikes}, текст (первые 50 символов)='{json_text[:50]}...'")
                except Exception as e:
                    print(f"[WARN] Ошибка при парсинге отдельного отзыва: {e}")
                    import traceback
                    print(f"[DEBUG] Трассировка: {traceback.format_exc()}")
                    continue
            
            print(f"\n[INFO] Итого успешно распарсено отзывов: {len(res)}")
                    
        except selenium_exceptions.WebDriverException as e:
            print(f"[ERROR] Проблемы с WebDriver, url {url}.\n{e}")
            debug_info["error"] = str(e)
        except Exception as e:
            print(f"[ERROR] Неожиданная ошибка при парсинге {url}.\n{e}")
            debug_info["error"] = str(e)
            import traceback
            debug_info["traceback"] = traceback.format_exc()
        
        return res, debug_info
    
    def load_organizations_from_json(self, json_path: str) -> List[Dict[str, Any]]:
        """Загружает список организаций из JSON файла"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('data', [])
        except FileNotFoundError:
            print(f"[ERROR] Файл не найден: {json_path}")
            return []
        except json.JSONDecodeError as e:
            print(f"[ERROR] Ошибка парсинга JSON: {e}")
            return []
    
    def parse_all_organizations(self, input_file: Optional[str] = None, 
                               output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Парсит отзывы для всех организаций из JSON файла
        
        Args:
            input_file: Путь к входному JSON файлу (по умолчанию используется INPUT_FILE)
            output_file: Путь к выходному JSON файлу (по умолчанию используется OUTPUT_FILE)
        
        Returns:
            Словарь с результатами парсинга
        """
        if input_file is None:
            # Ищем входной файл в разных местах
            possible_paths = [
                INPUT_FILE,
                os.path.join(INPUT_DIR, "ym_test_review_school.json"),
                os.path.join(INPUT_DIR, "ym_gold_all_school_data.json"),
                os.path.join(DATA_DIR, "ym_test_review_school.json"),
            ]
            input_file = None
            for path in possible_paths:
                if os.path.exists(path):
                    input_file = path
                    break
            
            if input_file is None:
                print("[ERROR] Не найден входной файл со списком организаций")
                print(f"Искали в следующих местах:")
                for path in possible_paths:
                    print(f"  - {path}")
                return {}
        
        if output_file is None:
            output_file = OUTPUT_FILE
        
        organizations = self.load_organizations_from_json(input_file)
        
        if not organizations:
            print("[ERROR] Не найдено организаций для парсинга")
            return {}
        
        print(f"[INFO] Найдено организаций: {len(organizations)}")
        
        # Создаем директорию для выходного файла, если её нет
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Загружаем существующие отзывы, если файл есть
        all_reviews = []
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_reviews = data.get("reviews", [])
            except Exception:
                all_reviews = []
        
        try:
            self.setup_driver()
            
            for org in organizations:
                org_id = org.get('id')
                org_name = org.get('name', 'Неизвестно')
                feedback_link = org.get('feedback_link')
                
                if not feedback_link:
                    print(f"[WARN] Пропущена организация {org_name}: нет ссылки на отзывы")
                    # Добавляем запись с null для организации без ссылки
                    all_reviews.append({
                        "school_id": str(org_id) if org_id else None,
                        "date": None,
                        "text": None,
                        "likes_count": None,
                        "dislikes_count": None,
                        "rating": None
                    })
                    continue
                
                print(f"\n[INFO] Парсинг отзывов для: {org_name} (ID: {org_id})")
                print(f"[INFO] Ссылка: {feedback_link}")
                
                reviews, debug_info = self._parse_page(feedback_link, org_id=str(org_id), org_name=org_name)
                
                # Удаляем старые отзывы для этой школы
                all_reviews = [r for r in all_reviews if r.get('school_id') != str(org_id)]
                
                # Добавляем новые отзывы
                if reviews:
                    for review in reviews:
                        all_reviews.append(review.to_dict(school_id=str(org_id)))
                else:
                    # Если отзывов нет, добавляем запись с null
                    all_reviews.append({
                        "school_id": str(org_id),
                        "date": None,
                        "text": None,
                        "likes_count": None,
                        "dislikes_count": None,
                        "rating": None
                    })
                
                print(f"[OK] Получено отзывов: {len(reviews)}")
                
                # Сохраняем результаты после каждой организации
                results = {
                    "resource": "yandex_maps",
                    "reviews": all_reviews
                }
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                    print(f"[OK] Сохранено отзывов для школы {org_id}")
                except Exception as e:
                    print(f"[WARN] Не удалось сохранить результаты: {e}")
                
                # Небольшая пауза между запросами
                time.sleep(2)
        
        finally:
            self.close_driver()
        
        # Финальное сохранение результатов
        results = {
            "resource": "yandex_maps",
            "reviews": all_reviews
        }
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n[OK] Результаты сохранены в: {output_file}")
            print(f"[OK] Всего отзывов: {len(all_reviews)}")
        except Exception as e:
            print(f"[ERROR] Ошибка при сохранении результатов: {e}")
        
        return results
    
    def get_reviews_by_organisation_id(self, organization_id: str) -> List[Review]:
        """
        Получает отзывы по ID организации
        
        Args:
            organization_id: ID организации в Яндекс картах
        
        Returns:
            Список отзывов
        """
        url = f'https://yandex.ru/maps/org/{organization_id}/reviews/'
        
        try:
            self.setup_driver()
            reviews, _ = self._parse_page(url, org_id=organization_id)
            return reviews
        finally:
            self.close_driver()


def main():
    """Основная функция для запуска парсера"""
    parser = YandexMapsReviewsParser()
    results = parser.parse_all_organizations()
    
    total_reviews = sum(org.get('reviews_count', 0) for org in results.get('organizations', []))
    print(f"\n[OK] Парсинг завершен. Всего получено отзывов: {total_reviews}")


if __name__ == "__main__":
    main()

