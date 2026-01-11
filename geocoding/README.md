# Геокодирование (Geocoding)

Модуль для геокодирования адресов школ (преобразование адресов в координаты).

## Структура

- `gc_data/` - папка с данными
  - `gc_input/` - входные данные (JSON файлы с адресами)
  - `gc_output/` - выходные данные (JSON файлы с координатами)
- `gc_src/` - папка с исходным кодом
  - `gc_main.py` - основной скрипт геокодирования
  - `gc_merge_school.py` - объединение данных о школах

## Функционал

Модуль выполняет геокодирование адресов школ из разных источников (2ГИС, Яндекс.Карты) и объединяет результаты.

## Использование

```bash
python geocoding/gc_src/gc_main.py
python geocoding/gc_src/gc_merge_school.py
```

Входные файлы:
- `gc_data/gc_input/gc_2gis_input_data.json` - данные из 2ГИС
- `gc_data/gc_input/gc_ym_input_data.json` - данные из Яндекс.Карт

Выходные файлы:
- `gc_data/gc_output/gc_2gis_output_data.json` - геокодированные данные 2ГИС
- `gc_data/gc_output/gc_ym_output_data.json` - геокодированные данные Яндекс.Карт
- `gc_data/gc_output/gc_merge_data.json` - объединенные данные

