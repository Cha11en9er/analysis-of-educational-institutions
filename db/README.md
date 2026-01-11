# База данных (Database)

Модуль для работы с PostgreSQL базой данных: создание схемы, таблиц и вставка данных о школах и отзывах.

## Структура

- `db_data/` - папка с данными
  - `db_input/` - входные данные для тестирования
- `db_src/` - папка с исходным кодом
  - `db_create/` - скрипты создания схемы и таблиц
  - `db_insert/` - скрипты вставки данных
  - `db_truncate/` - скрипты очистки таблиц

## Настройка

Убедитесь, что в `.env` файле в корне проекта указаны параметры подключения к БД:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password
```

## Использование

### Создание схемы и таблиц

```bash
python db/db_src/db_create/create_object.py
```

Создаёт схему `ca` и таблицы:
- `ca.school` - информация о школах
- `ca.review` - отзывы о школах

### Вставка данных о школах

```bash
python db/db_src/db_insert/insert_data_school.py
```

Читает данные из Excel файла `global_data/Здания школ.xlsx` (лист `schools_2_stage`) и вставляет в таблицу `ca.school`.

### Вставка отзывов

```bash
python db/db_src/db_insert/insert_data_review.py
```

Читает данные из JSON файла `recognize_meaning/rm_data/rm_output/rm_output_data.json` и вставляет в таблицу `ca.review`.

### Очистка таблиц

```bash
psql -U your_user -d your_database -f db/db_src/db_truncate/clear_tables.sql
```

Удаляет все данные из таблиц (используйте с осторожностью!).

## Зависимости

- `psycopg2` - драйвер PostgreSQL
- `pandas` - для работы с Excel
- `openpyxl` - для чтения Excel файлов
- `python-dotenv` - для загрузки переменных окружения

