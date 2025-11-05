# Анализ образовательных учреждений Саратова

Проект для парсинга, хранения и анализа данных об образовательных учреждениях города Саратова из различных источников.

## Структура проекта

```
analysis-of-educational-institutions/
├── parsing/                          # Модуль парсинга данных
│   ├── 2gis/                         # Источник: 2GIS
│   │   ├── schools_parser/           # Парсер списка всех школ
│   │   │   ├── main.py              # Основной скрипт парсинга
│   │   │   └── output/               # Выходные JSON файлы
│   │   │       └── example_output.json
│   │   └── reviews_parser/          # Парсер отзывов для каждой школы
│   │       ├── main.py              # Основной скрипт парсинга отзывов
│   │       └── output/               # Выходные JSON файлы с отзывами
│   │           └── example_output.json
│   ├── uchi_ru/                      # Источник: uchi.ru
│   │   └── schools_parser/           # Парсер списка школ
│   │       ├── main.py              # Парсер на requests/BeautifulSoup
│   │       ├── selenium_main.py     # Парсер на Selenium (для обхода защиты)
│   │       └── output/              # Выходные JSON файлы
│   │           └── example_output.json
│   └── yandex_maps/                  # Источник: Яндекс Карты (будущий)
│
├── data_to_postgres/                 # Модуль переноса данных в PostgreSQL
│   └── README.md                     # Описание модуля
│
├── sentiment_analysis/                # Модуль анализа тональности отзывов
│   └── README.md                     # Описание модуля
│
├── requirements.txt                  # Зависимости проекта
└── README.md                         # Этот файл

```

## Описание модулей

### 1. Парсинг (parsing/)

Парсинг данных из различных источников о школах города Саратова.

#### 2GIS
- **schools_parser** - Парсит список всех школ города Саратова с их основными данными (название, URL, адрес)
- **reviews_parser** - Парсит отзывы для каждой найденной школы (текст, дата, важность)

#### uchi.ru
- **schools_parser** - Парсит список школ с сайта uchi.ru
  - `main.py` - Базовая версия на requests
  - `selenium_main.py` - Версия на Selenium для обхода защиты от ботов

#### Яндекс Карты
- Папка зарезервирована для будущего парсера

### 2. Перенос в PostgreSQL (data_to_postgres/)

Модуль для переноса спарсенных данных из JSON файлов в базу данных PostgreSQL.

**Статус:** В разработке

### 3. Анализ тональности (sentiment_analysis/)

Модуль для анализа смысла и тональности отзывов с помощью нейронных сетей.

**Статус:** В разработке

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## Использование

### Парсинг школ из 2GIS

```bash
cd parsing/2gis/schools_parser
python main.py
```

Результаты сохраняются в `parsing/2gis/schools_parser/output/`

### Парсинг отзывов из 2GIS

```bash
cd parsing/2gis/reviews_parser
python main.py [путь_к_файлу_со_школами.json]
```

Результаты сохраняются в `parsing/2gis/reviews_parser/output/`

### Парсинг школ из uchi.ru

```bash
cd parsing/uchi_ru/schools_parser
python main.py          # Базовая версия
# или
python selenium_main.py # Версия с Selenium
```

Результаты сохраняются в `parsing/uchi_ru/schools_parser/output/`

## Формат данных

### Выходной формат для парсера школ (2GIS)

```json
{
  "source": "2GIS",
  "topic": "Школы Саратова",
  "description": "Сырые данные со всех страниц",
  "total_elements": 208,
  "total_pages": 18,
  "data": [
    {
      "name": "Название школы",
      "url": "https://2gis.ru/..."
    }
  ]
}
```

### Выходной формат для парсера отзывов (2GIS)

```json
{
  "resource": "2gis",
  "schools": [
    {
      "id": "1",
      "name": "Название школы",
      "full_name": "Полное название",
      "adres": "Адрес",
      "rating_2gis": "4.5",
      "url": "https://2gis.ru/..."
    }
  ],
  "reviews": [
    {
      "school_id": "1",
      "date": "15.01.2024",
      "text": "Текст отзыва",
      "weightы": true
    }
  ]
}
```

## Требования

- Python 3.7+
- Selenium (для парсеров с Selenium)
- ChromeDriver (для Selenium)
- requests, beautifulsoup4 (для базовых парсеров)

## Лицензия

Проект для образовательных целей.
