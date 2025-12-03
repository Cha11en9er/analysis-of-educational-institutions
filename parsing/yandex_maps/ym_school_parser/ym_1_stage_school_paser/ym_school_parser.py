#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер школ Яндекс.Карт на Selenium.
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
    Настройка Chrome драйвера с обходом детекта парсеров
    
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
    
    # Актуальный реалистичный User-Agent (Chrome 131)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    
    # Реалистичные метаданные профиля
    prefs = {
        # Базовые настройки
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.media_stream": 2,
        
        # Реалистичные настройки для обхода детекта
        "profile.managed_default_content_settings.images": 1,  # Включаем изображения для реалистичности
        "profile.content_settings.exceptions.plugins": {},
        "profile.content_settings.plugin_whitelist.adobe-flash-player": 1,
        
        # Языковые настройки
        "intl.accept_languages": "ru-RU,ru,en-US,en",
        
        # Часовой пояс (Москва)
        "profile.default_content_setting_values.timezone": "Europe/Moscow",
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Дополнительные опции для обхода детекта
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions-file-access-check")
    chrome_options.add_argument("--disable-extensions-http-throttling")
    
    # Реалистичное разрешение экрана
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    
    # Дополнительные опции для реалистичности
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Устанавливаем реалистичные размеры окна
    driver.set_window_size(1920, 1080)
    
    # Скрываем признаки автоматизации через JavaScript
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
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' }
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
            
            // Реалистичный hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });
            
            // Реалистичная память
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
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
                runtime: {}
            };
            
            // Переопределяем toString для функций
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter(parameter);
            };
            
            // Маскируем автоматизацию
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
        """
    })
    
    # Дополнительная маскировка через CDP
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "acceptLanguage": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "platform": "Win32"
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


def scroll_page_with_pyautogui(duration: float = 10.0, scroll_distance: int = 3000, scroll_step: int = 6) -> None:
    """
    Прокручивает страницу вниз с помощью pyautogui.
    Перемещает курсор в правую середину окна и медленно прокручивает вниз.
    
    Args:
        duration: Длительность прокрутки в секундах (по умолчанию 10 секунд)
        scroll_distance: Расстояние прокрутки в пикселях (по умолчанию 3000)
        scroll_step: Размер одного шага прокрутки в пикселях (по умолчанию 3)
                    Больше значение = быстрее прокрутка, но менее плавно
                    Меньше значение = медленнее прокрутка, но более плавно
    
    Returns:
        None
    """
    try:
        # Пауза перед началом прокрутки
        print(f"[info] Пауза 3 секунды перед началом прокрутки...")
        time.sleep(3.0)
        
        # Получаем размеры экрана
        screen_width, screen_height = pyautogui.size()
        
        # Вычисляем координаты правой середины экрана
        # Правая треть экрана, по вертикали - середина
        target_x = int(screen_width * 0.25)  # Правая треть
        target_y = int(screen_height * 0.5)    # Середина по вертикали
        
        print(f"[info] Перемещение курсора в позицию ({target_x}, {target_y})")
        
        # Плавно перемещаем курсор в целевую позицию
        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.3)  # Небольшая пауза после перемещения
        
        # Вычисляем количество шагов прокрутки
        steps = max(1, int(scroll_distance / scroll_step))  # Минимум 1 шаг
        step_duration = duration / steps
        
        print(f"[info] Начало прокрутки: {scroll_distance}px за {duration} секунд")
        print(f"[info] Размер шага: {scroll_step}px, количество шагов: {steps}")
        
        # Медленно прокручиваем вниз
        for i in range(steps):
            pyautogui.scroll(-scroll_step)  # Прокрутка вниз (отрицательное значение)
            time.sleep(step_duration)
            
            # Выводим прогресс каждые 10% прокрутки
            if steps >= 10 and i > 0 and i % (steps // 10) == 0:
                progress = int((i / steps) * 100)
                print(f"[info] Прогресс прокрутки: {progress}%")
        
        print(f"[info] Прокрутка завершена")
        print(f"[info] Ожидание загрузки всех данных после прокрутки...")
        time.sleep(5.0)  # Пауза после прокрутки для загрузки динамического контента
        print(f"[info] Данные должны быть загружены")
        
    except Exception as e:
        print(f"[warn] Ошибка при прокрутке через pyautogui: {e}")
        print(f"[warn] Продолжаем без прокрутки...")


def get_page_html(url: str, wait_timeout: int = 10, scroll: bool = True, 
                  use_pyautogui_scroll: bool = True, user_data_dir: Optional[str] = None) -> Optional[str]:
    """
    Получает HTML код страницы Яндекс.Карт
    
    Args:
        url: URL страницы для парсинга
        wait_timeout: Таймаут ожидания загрузки элементов (секунды)
        scroll: Прокручивать страницу для загрузки динамического контента
        use_pyautogui_scroll: Использовать pyautogui для прокрутки (медленная, реалистичная)
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
        
        time.sleep(2.0)  # Дополнительная пауза для загрузки динамического контента
        
        # Прокрутка для загрузки всех элементов (если нужно)
        if scroll:
            if use_pyautogui_scroll:
                # Ожидаем нажатия клавиши 'P' перед началом прокрутки
                # Это даёт время пройти капчу вручную
                wait_for_key_press('p', 
                    "[info] ========================================\n"
                    "[info] Страница загружена. Пройдите капчу.\n"
                    "[info] После прохождения капчи нажмите 'P' для начала прокрутки.\n"
                    "[info] ========================================")
                
                # Используем pyautogui для медленной, реалистичной прокрутки
                print(f"[info] Использование pyautogui для прокрутки страницы")
                # duration=5.0 - прокрутка в 2 раза быстрее (было 10 секунд, стало 5)
                scroll_page_with_pyautogui(duration=5.0, scroll_distance=3000, scroll_step=6)
                
                # Дополнительное ожидание загрузки всех элементов после прокрутки
                print(f"[info] Дополнительное ожидание загрузки динамического контента...")
                time.sleep(3.0)
                
                # Прокручиваем немного вверх и вниз для триггера загрузки
                try:
                    driver.execute_script('window.scrollBy(0, -100);')
                    time.sleep(1.0)
                    driver.execute_script('window.scrollBy(0, 100);')
                    time.sleep(2.0)
                    print(f"[info] Финальная проверка загрузки контента...")
                except Exception as e:
                    print(f"[warn] Не удалось выполнить финальную прокрутку: {e}")
            else:
                # Старый метод через JavaScript (быстрая прокрутка)
                try:
                    print(f"[info] Использование JavaScript для прокрутки страницы")
                    # Прокручиваем страницу несколько раз
                    for i in range(5):
                        driver.execute_script('window.scrollBy(0, 500);')
                        time.sleep(0.5)
                    
                    # Прокручиваем вверх
                    driver.execute_script('window.scrollTo(0, 0);')
                    time.sleep(1.0)
                except Exception as e:
                    print(f"[warn] Не удалось выполнить прокрутку: {e}")
        
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
    url = "https://yandex.ru/maps/194/saratov/search/%D1%88%D0%BA%D0%BE%D0%BB%D1%8B%20%D1%81%D0%B0%D1%80%D0%B0%D1%82%D0%BE%D0%B2%D0%B0/?ll=46.153670%2C51.551834&sctx=ZAAAAAgCEAAaKAoSCZ8ENufgD0dAESRh304iwElAEhIJj3IwmwDDzj8RNX9Ma9PYtj8iBgABAgMEBSgKOABAildIAWoCcnWdAc3MzD2gAQCoAQC9ASXHyvrCAYgB7MzUg9ICsq6o6gODoaicBJKag5QE98GH7b0G76SN1OYFvoOGypQFuLKMlwSNp%2B6cBPGLwfC1Ari4pODYAsyd4IoE5re57AOs57zBjwOaiNL9A9uxnMK%2FAoLM7owEq%2Bbt8QO3%2FJ3lA%2BT90oTCBdfnxvAD2sXUwQSe4Ovg3QOD25aIBJ2L8p%2F1A4ICG9GI0LrQvtC70Ysg0YHQsNGA0LDRgtC%2B0LLQsIoCUTE4NDEwNjI0MCQxODQxMDYyMzQkMTg0MTA2MjM4JDM3MzEwNzcyNjk3JDE4NDEwNjI1MiQxODQxMDYyNTQkMTg0MTA2MjUwJDE4NDEwNTkyNJICAzE5NJoCDGRlc2t0b3AtbWFwc6oCGDk4MTQzNjkxNDA5LDIxODE0NjkzNDQ1NdoCKAoSCQflfRzNFUdAEbLOgvj5w0lAEhIJAN1CVyJQ9z8RwND1M6tN4T%2FgAgE%3D&sll=46.153670%2C51.551834&sspn=1.457064%2C0.540483&z=10.4"
    
    # Опционально: используйте реальный профиль Chrome для лучшего обхода детекта
    # Раскомментируйте и укажите путь к вашему профилю Chrome:
    # user_data_dir = r"C:\Users\YourName\AppData\Local\Google\Chrome\User Data"
    # ВАЖНО: Закройте все окна Chrome перед запуском парсера!
    user_data_dir = None
    
    print(f"[info] Получение HTML для: {url}")
    html = get_page_html(url, wait_timeout=15, scroll=True, user_data_dir=user_data_dir)
    
    if html:
        # Сохраняем в файл для анализа
        # Путь к ym_1_stage_data: parsing/yandex_maps/ym_data/ym_1_stage_data
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ym_root = os.path.abspath(os.path.join(script_dir, "..", "..", "ym_data"))
        ym_1_stage_dir = os.path.join(ym_root, "ym_1_stage_data")
        output_dir = os.path.join(ym_1_stage_dir, "debug_html")
        output_file = os.path.join(output_dir, "ym_maps_schools.html")
        
        # Выводим информацию о пути для проверки
        print(f"[info] Путь к директории debug_html: {output_dir}")
        print(f"[info] Полный путь к файлу: {output_file}")
        
        save_html_to_file(html, output_file)
        print(f"[info] Размер HTML: {len(html)} символов")
    else:
        print("[error] Не удалось получить HTML")


if __name__ == "__main__":
    main()
