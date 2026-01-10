# Адреса рядом со школами (Addresses Near School)

Модуль для анализа адресов, расположенных рядом со школами.

## Структура

- `ans_data/` - папка с данными
  - Выходные файлы (CSV, TXT)
- `ans_src/` - папка с исходным кодом
  - `ans_extract_school.py` - извлечение данных о школах
  - `ans_prepare_data.py` - подготовка данных
  - `ans_to_csv.py` - конвертация в CSV
  - `ans_transfer_data.py` - перенос данных

## Функционал

Модуль обрабатывает данные о школах и определяет адреса, расположенные вблизи образовательных учреждений.

## Использование

```bash
python adreses_nears_school/ans_src/ans_extract_school.py
python adreses_nears_school/ans_src/ans_prepare_data.py
python adreses_nears_school/ans_src/ans_to_csv.py
```

