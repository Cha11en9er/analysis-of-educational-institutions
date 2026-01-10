# Ссылка на страницу с школами в Саратове (2GIS)
# 1 - https://2gis.ru/saratov/search/Школы%20саратова?m=46.031248%2C51.544996%2F10.86
# 2 - https://2gis.ru/saratov/search/Школы%20саратова/page/2?m=46.031248%2C51.544996%2F10.86
# 18 - https://2gis.ru/saratov/search/Школы%20саратова/page/18?m=46.031248%2C51.544996%2F10.86

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# файл для парсинга всех школ в Саратове

"""
Парсер 2GIS для школ Саратова с использованием Selenium
Извлекает: название школы, URL страницы
Требует установки: pip install selenium
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
from urllib.parse import urljoin, urlparse

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[WARN] pyautogui не установлен. Установите: pip install pyautogui")

# Путь к папке output относительно текущего файла
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TGIS_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
DATA_DIR = os.path.join(TGIS_ROOT, "2gis_data")
OUTPUT_DIR = os.path.join(DATA_DIR, "tgis_output")


class TwoGisSchoolParser:
    def __init__(self):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium не установлен. Установите: pip install selenium")
        
        self.driver = None
        self.base_url = "https://2gis.ru"
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
            print("[OK] Chrome WebDriver инициализирован")
        except Exception as e:
            print(f"[ERROR] Ошибка инициализации WebDriver: {e}")
            print("Убедитесь, что ChromeDriver установлен и находится в PATH")
            raise
    
    def scroll_to_load_all(self):
        """Прокручивает страницу для загрузки всех элементов используя колесо мыши"""
        print("Прокручиваю страницу для загрузки всех школ (колесо мыши)...")
        
        if not PYAUTOGUI_AVAILABLE:
            print("[ERROR] pyautogui не доступен! Используем JavaScript скроллинг")
            return
        
        last_count = 0
        no_change_counter = 0
        
        # Получаем координаты окна браузера
        window_pos = self.driver.get_window_position()
        window_size = self.driver.get_window_size()
        
        # Центр окна браузера (где будет прокрутка)
        center_x = window_pos['x'] + window_size['width'] // 2
        center_y = window_pos['y'] + window_size['height'] // 2 + 100  # Чуть выше центра для прокрутки результатов
        
        print(f"Навожу мышь на координаты: ({center_x}, {center_y})")
        
        # Перемещаем мышь на центр окна браузера
        pyautogui.moveTo(center_x, center_y, duration=0.5)
        time.sleep(0.5)
        
        for i in range(150):  # Максимум 150 прокруток
            # Получаем текущее количество элементов
            containers = self.driver.find_elements(By.CSS_SELECTOR, "div._zjunba")
            current_count = len(containers)
            
            # Если количество не изменилось после нескольких прокруток - останавливаемся
            if current_count == last_count:
                no_change_counter += 1
                if no_change_counter >= 8:  # Увеличиваем до 8
                    print(f"Количество школ не изменилось 8 раз подряд. Загружено: {current_count}")
                    break
            else:
                no_change_counter = 0
                print(f"Найдено школ: {current_count} (прокрутка {i+1})")
            
            last_count = current_count
            
            # Прокручиваем колесом мыши вниз на 5 кликов
            pyautogui.scroll(-5)
            time.sleep(0.2)  # Небольшая пауза для загрузки
            
            # Каждые 30 прокруток делаем более агрессивную прокрутку
            if (i + 1) % 30 == 0:
                # Прокручиваем в самый низ
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                # Возвращаемся немного назад и прокручиваем
                pyautogui.scroll(3)
                time.sleep(0.3)
        
        # Финальная прокрутка в самый низ для загрузки всех элементов
        print("Финальная прокрутка...")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Возвращаемся в начало
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        # Последний раз получаем количество
        final_containers = self.driver.find_elements(By.CSS_SELECTOR, "div._zjunba")
        print(f"Финальное количество найденных школ: {len(final_containers)}")
    
    def get_schools_from_page(self):
        """Извлекает ВСЕ данные со страницы без фильтрации"""
        schools = []
        
        try:
            # Найдем все контейнеры с классом _zjunba (это контейнеры элементов)
            containers = self.driver.find_elements(By.CSS_SELECTOR, "div._zjunba")
            
            print(f"Найдено контейнеров: {len(containers)}")
            
            for idx, container in enumerate(containers):
                try:
                    # Получаем весь текст контейнера
                    all_text = container.text.strip()
                    
                    # Пробуем найти ссылку
                    href = None
                    full_url = None
                    
                    try:
                        link = container.find_element(By.CSS_SELECTOR, "a._1rehek")
                        href = link.get_attribute("href")
                        if href:
                            # Если URL относительный, делаем его абсолютным
                            if href.startswith("/"):
                                full_url = urljoin(self.base_url, href)
                            else:
                                full_url = href
                    except NoSuchElementException:
                        pass
                    
                    # Извлекаем название
                    school_name = all_text.split('\n')[0][:100] if all_text else f"Элемент {idx+1}"
                    
                    # Добавляем в список ВСЕ элементы (без поля text)
                    schools.append({
                        "name": school_name,
                        "url": full_url if full_url else ""
                    })
                    
                except Exception as e:
                    # Добавляем пустой элемент с ошибкой
                    schools.append({
                        "name": f"Error {idx+1}",
                        "url": ""
                    })
            
            print(f"Извлечено элементов: {len(schools)}")
            
        except Exception as e:
            print(f"[ERROR] Ошибка при извлечении данных: {e}")
            import traceback
            traceback.print_exc()
        
        return schools
    
    def parse_page(self, url, expected_page_num=None):
        """Парсит одну страницу"""
        try:
            print(f"\nЗагружаю страницу: {url}")
            self.driver.get(url)
            
            # Ждем загрузки страницы
            wait = WebDriverWait(self.driver, 20)
            
            try:
                # Ждем появления хотя бы одного элемента со школой
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a._1rehek")))
                
                # Получаем текущий URL после загрузки и проверяем
                time.sleep(1)  # Небольшая пауза для завершения редиректов
                current_url = self.driver.current_url
                print(f"[OK] Страница загружена успешно")
                print(f"[DEBUG] Запрошенный URL: {url}")
                print(f"[DEBUG] Текущий URL: {current_url}")
                
                # Проверяем, что мы на правильной странице
                if expected_page_num is not None and expected_page_num > 1:
                    if f"/page/{expected_page_num}" not in current_url:
                        print(f"[WARN] Возможно редирект! Ожидалась страница {expected_page_num}, но URL: {current_url}")
                
                time.sleep(2)  # Дополнительная пауза для полной загрузки
                
                # Прокручиваем страницу для загрузки всех элементов
                self.scroll_to_load_all()
                
                # Извлекаем данные школ
                schools = self.get_schools_from_page()
                
                print(f"Найдено школ: {len(schools)}")
                
                return schools
                
            except TimeoutException:
                print(f"[ERROR] Таймаут загрузки страницы")
                return []
            
        except Exception as e:
            print(f"[ERROR] Ошибка при загрузке страницы: {e}")
            return []
    
    def click_next_page(self):
        """Нажимает кнопку 'Следующая страница'"""
        try:
            print(f"[DEBUG] Прокручиваем страницу до конца для поиска кнопки пагинации...")
            
            # Прокручиваем страницу в самый низ, чтобы увидеть кнопку пагинации
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Прокручиваем еще раз для уверенности
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Ищем кнопку по классу _n5hmn94 - берем ПОСЛЕДНЮЮ (это кнопка "вперед")
            try:
                all_buttons = self.driver.find_elements(By.CSS_SELECTOR, "div._n5hmn94")
                print(f"[DEBUG] Найдено кнопок пагинации: {len(all_buttons)}")
                
                if len(all_buttons) < 2:
                    print(f"[ERROR] Нужно минимум 2 кнопки, найдено: {len(all_buttons)}")
                    return False
                
                # Берем ПОСЛЕДНЮЮ кнопку (это кнопка "вперед")
                next_button = all_buttons[-1]
                print(f"[OK] Найдена кнопка следующей страницы (последняя кнопка из {len(all_buttons)})!")
                
                # Прокручиваем к кнопке чтобы убедиться что она видна
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(0.5)
                
                # Пробуем кликнуть
                try:
                    next_button.click()
                except:
                    # Если не получается, используем JavaScript
                    self.driver.execute_script("arguments[0].click();", next_button)
                
                time.sleep(2)  # Ждем загрузки следующей страницы
                return True
                
            except NoSuchElementException:
                print(f"[ERROR] Кнопка с классом '_n5hmn94' не найдена")
                return False
            
        except Exception as e:
            print(f"[ERROR] Ошибка при нажатии на кнопку: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def generate_page_url(self, page_num):
        """Генерирует URL для страницы"""
        base_url = "https://2gis.ru/saratov/search/Школы%20саратова"
        
        if page_num == 1:
            # Первая страница без /page/
            return base_url
        else:
            # Остальные страницы с /page/N
            return f"{base_url}/page/{page_num}"
    
    def save_page_to_json(self, schools, page_num, output_dir=None):
        """Сохраняет результаты одной страницы в отдельный JSON файл"""
        if output_dir is None:
            output_dir = OUTPUT_DIR
        
        try:
            # Создаем директорию, если её нет
            os.makedirs(output_dir, exist_ok=True)
            
            # Имя файла
            filename = os.path.join(output_dir, f"page_{page_num}.json")
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "source": "2GIS",
                    "topic": "Школы Саратова",
                    "description": "Сырые данные со страницы (без фильтрации)",
                    "page": page_num,
                    "data": schools
                }, f, ensure_ascii=False, indent=2)
            
            print(f"[OK] Страница {page_num} сохранена: {filename}")
            
        except Exception as e:
            print(f"[ERROR] Ошибка при сохранении файла: {e}")
    
    def save_to_json(self, schools, filename=None):
        """Сохраняет результаты в JSON файл"""
        if filename is None:
            filename = os.path.join(OUTPUT_DIR, "all_schools.json")
        
        try:
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else OUTPUT_DIR, exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "source": "2GIS",
                    "topic": "Школы Саратова",
                    "description": "Сырые данные со всех страниц (без фильтрации)",
                    "total_pages": 18,
                    "data": schools
                }, f, ensure_ascii=False, indent=2)
            
            print(f"[OK] Данные сохранены в файл: {filename}")
            print(f"[OK] Всего элементов: {len(schools)}")
            
        except Exception as e:
            print(f"[ERROR] Ошибка при сохранении файла: {e}")
    
    def close(self):
        """Закрывает браузер"""
        if self.driver:
            self.driver.quit()
            print("Браузер закрыт")

def main():
    """Основная функция"""
    if not SELENIUM_AVAILABLE:
        print("[ERROR] Selenium не установлен!")
        print("Установите: pip install selenium")
        print("И скачайте ChromeDriver с https://chromedriver.chromium.org/")
        return
    
    parser = None
    try:
        print("Парсер 2GIS - Школы Саратова")
        print("=" * 40)
        
        parser = TwoGisSchoolParser()
        all_schools = []
        
        # Проходим по всем страницам от 1 до 18
        total_pages = 18
        for page in range(1, total_pages + 1):
            print(f"\n{'='*60}")
            print(f"Обработка страницы {page}/{total_pages}")
            print(f"{'='*60}")
            
            try:
                if page == 1:
                    # Первая страница - загружаем напрямую
                    url = parser.generate_page_url(page)
                    print(f"[DEBUG] Загрузка первой страницы: {url}")
                    schools = parser.parse_page(url, expected_page_num=1)
                elif page <= 5:
                    # Страницы 2-5 - загружаем напрямую по URL
                    url = parser.generate_page_url(page)
                    print(f"[DEBUG] Загрузка страницы {page}: {url}")
                    schools = parser.parse_page(url, expected_page_num=page)
                else:
                    # Страницы >5 - нажимаем кнопку "Следующая"
                    print(f"[DEBUG] Нажимаем кнопку 'Следующая страница' для перехода к странице {page}")
                    success = parser.click_next_page()
                    
                    if success:
                        # После нажатия ждем загрузки и парсим
                        time.sleep(2)
                        
                        # Прокручиваем страницу
                        parser.scroll_to_load_all()
                        
                        # Извлекаем данные
                        schools = parser.get_schools_from_page()
                        
                        print(f"[OK] Страница {page} загружена через кнопку")
                    else:
                        print(f"[ERROR] Не удалось перейти на страницу {page}")
                        schools = []
                
                # Сохраняем страницу сразу в отдельный файл
                parser.save_page_to_json(schools, page)
                
                # Добавляем во все данные (без поля page)
                all_schools.extend(schools)
                
                print(f"Страница {page}: извлечено {len(schools)} элементов")
                
                # Пауза между страницами
                time.sleep(1)
                
            except Exception as e:
                print(f"[ERROR] Ошибка при обработке страницы {page}: {e}")
                continue
        
        # Сохраняем итоговый файл со всеми данными
        parser.save_to_json(all_schools)
        
        print(f"\n[OK] Парсинг завершен! Всего элементов: {len(all_schools)}")
        print(f"[OK] Файлы сохранены в папку: {OUTPUT_DIR}")
        
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if parser:
            parser.close()

if __name__ == "__main__":
    main()

