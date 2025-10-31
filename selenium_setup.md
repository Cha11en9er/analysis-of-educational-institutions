# Установка Selenium для парсинга uchi.ru

## Проблема
Сайт uchi.ru использует защиту от ботов через servicepipe.ru, которая блокирует обычные HTTP запросы.

## Решение
Использовать Selenium для имитации реального браузера.

## Установка

### 1. Установите Selenium
```bash
pip install selenium
```

### 2. Скачайте ChromeDriver
1. Откройте https://chromedriver.chromium.org/
2. Скачайте версию, соответствующую вашей версии Chrome
3. Распакуйте chromedriver.exe в папку с проектом или добавьте в PATH

### 3. Проверьте версию Chrome
Откройте Chrome → Настройки → О браузере Chrome
Убедитесь, что версия ChromeDriver соответствует версии Chrome

## Использование

```bash
python selenium_parser.py
```

## Альтернативные методы

### Метод 1: Обычные HTTP запросы
```bash
python bypass_parser.py
```

### Метод 2: Простое сохранение HTML
```bash
python simple_parser.py
```

## Примечания
- Selenium требует установки Chrome браузера
- ChromeDriver должен быть совместим с версией Chrome
- Парсинг может занять больше времени из-за загрузки браузера

