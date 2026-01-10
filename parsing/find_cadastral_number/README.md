# Поиск кадастровых номеров (Find Cadastral Number)

Модуль для поиска кадастровых номеров зданий школ на сайте кадастр.сайт.

## Структура

- `fcn_data/` - папка с данными
  - `fcn_input/` - входные данные (JSON файл с адресами школ)
  - `fcn_output/` - выходные данные (JSON файл с кадастровыми номерами)
- `fcn_src/` - папка с исходным кодом
  - `find_cadastral_number.py` - основной скрипт парсинга

## Функционал

Скрипт автоматически:
1. Открывает сайт кадастр.сайт
2. Вводит адрес школы в поле поиска
3. Извлекает кадастровый номер из результатов
4. Сохраняет результат в JSON файл

## Зависимости

- `selenium` - для автоматизации браузера

## Использование

```bash
python parsing/find_cadastral_number/fcn_src/find_cadastral_number.py
```

Входной файл: `fcn_data/fcn_input/find_cadastral_number_data.json`
Выходной файл: `fcn_data/fcn_output/find_cadastral_number_data_output.json`

