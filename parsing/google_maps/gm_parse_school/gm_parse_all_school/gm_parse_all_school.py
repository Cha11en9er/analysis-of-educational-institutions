#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер школ Google Maps на Selenium.
Получает HTML код страницы с обходом детекта парсеров.
"""

import os
import sys
import time
from typing import Optional

import pyautogui
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Настройка pyautogui
pyautogui.PAUSE = 0.1  # Небольшая пауза между действиями
pyautogui.FAILSAFE = True  # Безопасность: перемещение мыши в угол экрана прервёт выполнение

# Попытка импортировать keyboard для перехвата клавиш
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("[warn] Библиотека 'keyboard' не установлена. Используется альтернативный метод.")
    print("[warn] Для лучшей работы установите: pip install keyboard")


def setup_driver(headless: bool = False, user_data_dir: Optional[str] = None) -> webdriver.Chrome:
    """
    Настройка Chrome драйвера с обходом детекта парсеров и улучшенным отпечатком браузера
    
    Args:
        headless: Запускать браузер в фоновом режиме
        user_data_dir: Путь к директории профиля пользователя Chrome (опционально)
    
    Returns:
        Настроенный Chrome WebDriver
    """
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless")
    
    # Базовые опции для стабильности
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Обход детекта автоматизации
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Использование реального профиля пользователя (если указан)
    if user_data_dir:
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        chrome_options.add_argument("--profile-directory=Default")
    
    # Изменённый User-Agent для другого отпечатка (Chrome 130)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )
    
    # Реалистичные метаданные профиля с изменёнными значениями
    prefs = {
        # Базовые настройки
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.geolocation": 1,  # Разрешаем геолокацию для реалистичности
        "profile.default_content_setting_values.media_stream": 2,
        
        # Реалистичные настройки для обхода детекта
        "profile.managed_default_content_settings.images": 1,  # Включаем изображения для реалистичности
        "profile.content_settings.exceptions.plugins": {},
        "profile.content_settings.plugin_whitelist.adobe-flash-player": 1,
        
        # Языковые настройки
        "intl.accept_languages": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        
        # Часовой пояс (Москва)
        "profile.default_content_setting_values.timezone": "Europe/Moscow",
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Дополнительные опции для обхода детекта
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions-file-access-check")
    chrome_options.add_argument("--disable-extensions-http-throttling")
    
    # Реалистичное разрешение экрана (изменено для другого отпечатка)
    chrome_options.add_argument("--window-size=1366,768")
    chrome_options.add_argument("--start-maximized")
    
    # Дополнительные опции для реалистичности
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    
    # Дополнительные опции для обхода детекта Google
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-default-apps")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Устанавливаем реалистичные размеры окна
    driver.set_window_size(1366, 768)
    
    # Улучшенная маскировка через JavaScript с другим отпечатком
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            // Удаляем webdriver флаг
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Переопределяем plugins для реалистичности
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                    ];
                    return plugins;
                }
            });
            
            // Реалистичные языки
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en']
            });
            
            // Реалистичная платформа
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
            
            // Изменённый hardwareConcurrency для другого отпечатка
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 4
            });
            
            // Изменённая память для другого отпечатка
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 4
            });
            
            // Переопределяем permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Скрываем chrome объекта
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Переопределяем toString для функций
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'NVIDIA Corporation';
                }
                if (parameter === 37446) {
                    return 'NVIDIA GeForce GTX 1050/PCIe/SSE2';
                }
                return getParameter(parameter);
            };
            
            // Маскируем автоматизацию
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
            
            // Переопределяем connection для реалистичности
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                })
            });
            
            // Переопределяем getBattery для реалистичности
            if (navigator.getBattery) {
                navigator.getBattery = function() {
                    return Promise.resolve({
                        charging: true,
                        chargingTime: 0,
                        dischargingTime: Infinity,
                        level: 1
                    });
                };
            }
        """
    })
    
    # Дополнительная маскировка через CDP с изменёнными параметрами
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "acceptLanguage": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "platform": "Win32"
    })
    
    # Устанавливаем реалистичные параметры экрана через CDP
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": 1366,
        "height": 768,
        "deviceScaleFactor": 1,
        "mobile": False
    })
    
    return driver


def wait_for_key_press(key: str = 'p', message: str = None) -> None:
    """
    Ожидает нажатия указанной клавиши перед продолжением выполнения.
    
    Args:
        key: Клавиша для ожидания (по умолчанию 'p')
        message: Сообщение для вывода (опционально)
    
    Returns:
        None
    """
    if message:
        print(f"\n{message}")
    else:
        print(f"\n[info] Ожидание нажатия клавиши '{key.upper()}' для продолжения...")
        print(f"[info] Пройдите капчу и нажмите '{key.upper()}' когда будете готовы")
    
    if KEYBOARD_AVAILABLE:
        # Используем библиотеку keyboard для перехвата клавиш
        print(f"[info] Нажмите '{key.upper()}' в любом месте...")
        keyboard.wait(key)
        print(f"[info] Клавиша '{key.upper()}' нажата, продолжаем...")
    else:
        # Альтернативный метод через input (работает только в консоли)
        if sys.platform == 'win32':
            try:
                import msvcrt
                print(f"[info] Нажмите '{key.upper()}' в консоли...")
                while True:
                    if msvcrt.kbhit():
                        char = msvcrt.getch().decode('utf-8').lower()
                        if char == key.lower():
                            print(f"[info] Клавиша '{key.upper()}' нажата, продолжаем...")
                            break
            except Exception:
                # Если msvcrt не работает, используем input
                input(f"[info] Нажмите Enter после прохождения капчи (альтернативный метод)...")
        else:
            # Для Linux/Mac используем input
            input(f"[info] Нажмите Enter после прохождения капчи (альтернативный метод)...")


def scroll_to_bottom_google_maps(driver: webdriver.Chrome) -> None:
    """
    Прокручивает страницу Google Maps до конца для загрузки всех школ.
    Улучшенная версия с подсчётом элементов и более реалистичной прокруткой.
    
    Args:
        driver: WebDriver экземпляр
    
    Returns:
        None
    """
    print("[info] Начало прокрутки страницы Google Maps...")
    
    # Ждём появления результатов поиска
    print("[info] Ожидание появления результатов поиска...")
    time.sleep(3.0)
    
    # Пробуем найти контейнер со списком результатов
    # Google Maps использует различные контейнеры для результатов поиска
    scroll_containers = [
        "div[role='feed']",  # Основной контейнер результатов поиска
        "div[aria-label*='Результаты']",  # Контейнер с результатами
        "div.m6QErb",  # Класс контейнера результатов
        "div[jsaction*='scroll']",  # Элементы с прокруткой
        "div[aria-label*='Results']",  # Английская версия
    ]
    
    scroll_element = None
    for selector in scroll_containers:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                scroll_element = elements[0]
                print(f"[info] Найден контейнер для прокрутки: {selector}")
                break
        except Exception:
            continue
    
    if not scroll_element:
        print("[warn] Не найден контейнер для прокрутки, используем прокрутку всей страницы")
        scroll_element = None
    
    # Подсчитываем элементы до начала прокрутки
    last_count = 0
    no_change_counter = 0
    max_attempts = 150  # Увеличиваем количество попыток
    attempts = 0
    
    print("[info] Начало прокрутки с подсчётом элементов...")
    
    while attempts < max_attempts:
        try:
            # Подсчитываем количество элементов результатов
            try:
                # Пробуем найти элементы результатов Google Maps
                result_selectors = [
                    "div[role='article']",  # Основной селектор для результатов
                    "div[data-value='Directions']",  # Элементы с кнопкой "Маршрут"
                    "a[data-value='Directions']",  # Альтернативный селектор
                ]
                
                current_count = 0
                for selector in result_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if len(elements) > current_count:
                            current_count = len(elements)
                    except:
                        continue
                
                # Если не нашли через селекторы, пробуем через JavaScript
                if current_count == 0:
                    current_count = driver.execute_script(
                        """
                        const articles = document.querySelectorAll("div[role='article']");
                        return articles ? articles.length : 0;
                        """
                    )
                
            except Exception as e:
                current_count = last_count
                print(f"[warn] Ошибка при подсчёте элементов: {e}")
            
            # Проверяем, изменилось ли количество элементов
            if current_count == last_count:
                no_change_counter += 1
                if no_change_counter >= 10:  # Если 10 раз подряд не изменилось
                    print(f"[info] Количество элементов не изменилось 10 раз подряд. Загружено: {current_count} элементов")
                    print(f"[info] Останавливаем прокрутку после {attempts} попыток")
                    break
            else:
                no_change_counter = 0
                if current_count > last_count:
                    print(f"[info] Найдено элементов: {current_count} (было: {last_count}, попытка {attempts + 1})")
            
            last_count = current_count
            
            # Прокручиваем
            if scroll_element:
                # Прокручиваем найденный контейнер небольшими шагами
                scroll_now, scroll_height = driver.execute_script(
                    """
                    const scroll_element = arguments[0];
                    if (!scroll_element) {
                        return [0, 0];
                    }
                    // Прокручиваем небольшими шагами для реалистичности
                    scroll_element.scrollBy({
                        top: 500,
                        behavior: 'smooth'
                    });
                    return [scroll_element.scrollTop, scroll_element.scrollHeight];
                    """,
                    scroll_element
                )
            else:
                # Прокручиваем всю страницу небольшими шагами
                scroll_now, scroll_height = driver.execute_script(
                    """
                    window.scrollBy({
                        top: 500,
                        behavior: 'smooth'
                    });
                    return [window.pageYOffset || document.documentElement.scrollTop, 
                            document.documentElement.scrollHeight];
                    """
                )
            
            attempts += 1
            
            # Выводим прогресс каждые 20 попыток
            if attempts % 20 == 0:
                print(f"[info] Прогресс прокрутки: попытка {attempts}/{max_attempts}, элементов: {current_count}, позиция: {scroll_now}/{scroll_height}")
            
            # Увеличиваем задержку для более реалистичной прокрутки
            time.sleep(0.5)  # Увеличена пауза между прокрутками
            
            # Проверяем, достигли ли мы конца
            if scroll_now >= scroll_height - 100:  # Небольшой запас
                print(f"[info] Достигнут конец контейнера (попытка {attempts})")
                # Делаем ещё несколько попыток на случай подгрузки
                if no_change_counter >= 5:
                    break
            
        except Exception as e:
            print(f"[warn] Ошибка при прокрутке: {e}")
            # Продолжаем попытки
            attempts += 1
            time.sleep(0.5)
    
    print(f"[info] Прокрутка завершена после {attempts} попыток")
    print(f"[info] Итого загружено элементов: {last_count}")
    print(f"[info] Ожидание загрузки всех данных после прокрутки...")
    time.sleep(5.0)  # Увеличена пауза после прокрутки для загрузки динамического контента


def get_page_html(url: str, wait_timeout: int = 10, scroll: bool = False, 
                  user_data_dir: Optional[str] = None) -> Optional[str]:
    """
    Получает HTML код страницы Google Maps
    
    Args:
        url: URL страницы для парсинга
        wait_timeout: Таймаут ожидания загрузки элементов (секунды)
        scroll: Прокручивать страницу для загрузки динамического контента
        user_data_dir: Путь к директории профиля пользователя Chrome (опционально)
                      Пример для Windows: r"C:\\Users\\YourName\\AppData\\Local\\Google\\Chrome\\User Data"
                      или используйте прямые слеши: "C:/Users/YourName/AppData/Local/Google/Chrome/User Data"
    
    Returns:
        HTML код страницы или None в случае ошибки
    """
    driver = None
    try:
        driver = setup_driver(headless=False, user_data_dir=user_data_dir)
        driver.get(url)
        
        # Ждём загрузки основного контента
        try:
            WebDriverWait(driver, wait_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            print(f"[warn] Таймаут ожидания загрузки страницы: {url}")
        
        print("[info] Ожидание полной загрузки страницы...")
        time.sleep(5.0)  # Увеличена пауза для загрузки динамического контента
        
        # Ждём появления результатов поиска
        print("[info] Ожидание появления результатов поиска...")
        try:
            # Пробуем дождаться появления контейнера с результатами
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed'], div[role='article']"))
            )
            print("[info] Результаты поиска обнаружены")
        except TimeoutException:
            print("[warn] Таймаут ожидания результатов поиска, продолжаем...")
        
        time.sleep(3.0)  # Дополнительная пауза
        
        # Ручная прокрутка пользователем (если нужно)
        if scroll:
            # Ожидаем нажатия клавиши 'P' перед началом ручной прокрутки
            wait_for_key_press('p', 
                "[info] ========================================\n"
                "[info] Страница загружена. Пройдите капчу.\n"
                "[info] После прохождения капчи нажмите 'P' для начала ручной прокрутки.\n"
                "[info] ========================================")
            
            # Пользователь сам прокручивает страницу
            print("[info] Прокрутите страницу вниз вручную для загрузки всех данных.")
            print("[info] Когда закончите прокрутку, нажмите 'P' для сохранения HTML.")
            
            # Ждём нажатия 'P' после завершения прокрутки
            wait_for_key_press('p',
                "[info] ========================================\n"
                "[info] Нажмите 'P' когда закончите прокрутку.\n"
                "[info] HTML будет сохранён.\n"
                "[info] ========================================")
        
        # Получаем HTML
        html = driver.page_source
        return html
        
    except Exception as e:
        print(f"[error] Ошибка при получении HTML: {e}")
        return None
        
    finally:
        if driver:
            driver.quit()


def save_html_to_file(html: str, filepath: str) -> bool:
    """
    Сохраняет HTML в файл
    
    Args:
        html: HTML код для сохранения
        filepath: Путь к файлу для сохранения
    
    Returns:
        True если успешно, False в случае ошибки
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[info] HTML сохранён: {filepath}")
        return True
    except Exception as e:
        print(f"[error] Не удалось сохранить HTML: {e}")
        return False


def main():
    """Пример использования"""
    # URL из комментария в файле
    url = "https://www.google.com/maps/search/%D1%88%D0%BA%D0%BE%D0%BB%D1%8B+%D1%81%D0%B0%D1%80%D0%B0%D1%82%D0%BE%D0%B2%D0%B0/@51.5642244,45.8778875,12z?entry=ttu&g_ep=EgoyMDI1MTExNy4wIKXMDSoASAFQAw%3D%3D"
    
    # Опционально: используйте реальный профиль Chrome для лучшего обхода детекта
    # Раскомментируйте и укажите путь к вашему профилю Chrome:
    # user_data_dir = r"C:\Users\YourName\AppData\Local\Google\Chrome\User Data"
    # ВАЖНО: Закройте все окна Chrome перед запуском парсера!
    user_data_dir = None
    
    print(f"[info] Получение HTML для: {url}")
    html = get_page_html(url, wait_timeout=15, scroll=True, user_data_dir=user_data_dir)
    
    if html:
        # Сохраняем в файл для анализа
        # Путь: parsing/google_maps/gm_parse_school/gm_parse_all_school/ -> .. -> .. -> gm_data/gm_debug_html/
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, "..", "..", "gm_data", "gm_debug_html")
        output_dir = os.path.abspath(os.path.normpath(output_dir))  # Нормализуем путь
        output_file = os.path.join(output_dir, "gm_debug_html.html")
        
        # Выводим информацию о пути для проверки
        print(f"[info] Путь к директории gm_debug_html: {output_dir}")
        print(f"[info] Полный путь к файлу: {output_file}")
        
        save_html_to_file(html, output_file)
        print(f"[info] Размер HTML: {len(html)} символов")
    else:
        print("[error] Не удалось получить HTML")


if __name__ == "__main__":
    main()
