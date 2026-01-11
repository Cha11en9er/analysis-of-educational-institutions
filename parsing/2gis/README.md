# Парсинг 2ГИС (2GIS Parsing)

Модуль для парсинга данных о школах и отзывах из 2ГИС.

## Структура

- `2gis_data/` - папка с данными
  - `tgis_input/` - входные данные (JSON файлы со списком школ)
  - `tgis_output/` - выходные данные (распарсенные данные о школах и отзывах)
- `tgis_src/` - папка с исходным кодом
  - `2gis_school_parser/` - парсеры школ (1-й и 2-й этапы)
  - `2gis_review_parser/` - парсеры отзывов

## Этапы парсинга

### 1-й этап (2gis_1_stage_school_parser.py)
Парсит список всех школ из поиска 2ГИС:
- Название школы
- URL страницы школы

Результат сохраняется в `2gis_data/tgis_output/2gis_all_school.json`

### 2-й этап (2gis_2_stage_school_parser.py)
Парсит детальную информацию о каждой школе:
- Полное название
- Адрес
- Рейтинг

Результат сохраняется в `2gis_data/tgis_output/2gis_all_school_with_info.json`

### Парсинг отзывов (2gis_review_parser.py)
Парсит отзывы о школах:
- Дата отзыва
- Текст отзыва
- Количество лайков

Результат сохраняется в `2gis_data/tgis_output/2gis_school_reviews.json`

## Зависимости

- `selenium` - для автоматизации браузера
- `beautifulsoup4` - для парсинга HTML
- `pyautogui` - для обработки капчи (опционально)

## Использование

```bash
# 1-й этап: парсинг списка школ
python parsing/2gis/tgis_src/2gis_school_parser/2gis_1_stage_school_parser.py

# 2-й этап: парсинг детальной информации
python parsing/2gis/tgis_src/2gis_school_parser/2gis_2_stage_school_parser.py

# Парсинг отзывов
python parsing/2gis/tgis_src/2gis_review_parser/2gis_review_parser.py
```

