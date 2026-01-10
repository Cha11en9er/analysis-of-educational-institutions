# Парсинг Яндекс.Карт (Yandex Maps Parsing)

Модуль для парсинга данных о школах и отзывах из Яндекс.Карт.

## Структура

- `ym_data/` - папка с данными
  - `ym_input/` - входные данные (HTML файлы, JSON со списком школ)
  - `ym_output/` - выходные данные (распарсенные данные о школах и отзывах)
- `ym_src/` - папка с исходным кодом
  - `ym_school_parser/` - парсеры школ (1-й и 2-й этапы)
  - `ym_review_parser/` - парсеры отзывов

## Этапы парсинга

### 1-й этап (ym_1_stage_school_parser.py)
Парсит список всех школ из поиска Яндекс.Карт:
- Название школы
- URL страницы школы
- Координаты

Результат сохраняется в `ym_data/ym_output/ym_school_output.json`

### 2-й этап (ym_2_stage_school_parser/)
Парсит детальную информацию о каждой школе:
- Полное название
- Адрес
- Рейтинг
- Количество отзывов
- Дополнительная информация

Результат сохраняется в `ym_data/ym_output/ym_full_school_data.json`

### Парсинг отзывов (ym_review_parser.py)
Парсит отзывы о школах:
- Дата отзыва
- Текст отзыва
- Рейтинг (звезды)
- Количество лайков/дизлайков

Результат сохраняется в `ym_data/ym_output/ym_review_output.json`

## Зависимости

- `selenium` - для автоматизации браузера
- `beautifulsoup4` - для парсинга HTML
- `pyautogui` - для обработки капчи (опционально)

## Использование

```bash
# 1-й этап: парсинг списка школ
python parsing/yandex_maps/ym_src/ym_school_parser/ym_1_stage_school_paser/ym_school_parser.py

# 2-й этап: парсинг детальной информации
python parsing/yandex_maps/ym_src/ym_school_parser/ym_2_stage_school_parser/ym_find_all_info.py

# Парсинг отзывов
python parsing/yandex_maps/ym_src/ym_review_parser/ym_review_parser.py
```

