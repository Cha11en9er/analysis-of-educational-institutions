# Векторизация и объединение (Vectorization and Merging)

Модуль для объединения данных о школах из разных источников (2ГИС и Яндекс.Карты) с использованием векторного поиска.

## Структура

- `vam_data/` - папка с данными
  - `vam_data_input/` - входные данные (JSON файлы из 2ГИС и Яндекс.Карт)
  - `vam_data_output/` - выходные данные (объединенные данные)
- `vam_src/` - папка с исходным кодом
  - `vectorization_and_merging.py` - основной скрипт объединения
  - `vectorization_prepare_data.py` - подготовка данных для векторизации
  - `vectorization_and_merging_test.py` - тестовый скрипт

## Алгоритм

1. **Векторизация**: Преобразование названий и адресов школ в векторы с помощью модели `sentence-transformers/all-mpnet-base-v2`
2. **Поиск совпадений**: Вычисление косинусного сходства между векторами школ из разных источников
3. **Объединение**: Создание объединенных записей для школ с высоким сходством (>0.78)

## Зависимости

- `sentence-transformers` - для векторизации текста
- `scikit-learn` - для вычисления косинусного сходства
- `numpy` - для работы с массивами

## Использование

```bash
# Подготовка данных
python parsing/vectorization_and_merging/vam_src/vectorization_prepare_data.py

# Объединение данных
python parsing/vectorization_and_merging/vam_src/vectorization_and_merging.py
```

Входные файлы:
- `vam_data/vam_data_input/vam_2gis_input_data.json` - данные из 2ГИС
- `vam_data/vam_data_input/vam_ym_input_data.json` - данные из Яндекс.Карт

Выходной файл:
- `vam_data/vam_data_output/gold_vam_output_data.json` - объединенные данные

