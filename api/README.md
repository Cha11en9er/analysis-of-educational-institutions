# Schools API

Простое API на FastAPI для работы с данными школ и отзывов из PostgreSQL.

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

**Вариант 1 (через uvicorn напрямую - рекомендуется):**
```bash
uvicorn api.main:app --reload
```

**Вариант 2 (через Python):**
```bash
python api/main.py
```

**Примечание:** FastAPI требует ASGI сервер (uvicorn, hypercorn и т.д.). Uvicorn - самый простой и стандартный вариант для FastAPI.

API будет доступно по адресу: http://localhost:8000

## Эндпоинты

### GET `/`
Корневой эндпоинт - информация об API

### GET `/schools`
Получить список всех школ

**Пример запроса:**
```
GET http://localhost:8000/schools
```

**Ответ:**
```json
{
  "schools": [
    {
      "school_id": 1,
      "school_name": "Школа №1",
      "school_adres": "ул. Ленина, 1"
    }
  ]
}
```

### GET `/schools/{school_id}/reviews`
Получить отзывы по конкретной школе с фильтрацией по датам

**Параметры:**
- `school_id` (обязательный) - ID школы
- `date_start` (опциональный) - начальная дата в формате YYYY-MM-DD
- `date_end` (опциональный) - конечная дата в формате YYYY-MM-DD

**Пример запроса:**
```
GET http://localhost:8000/schools/1/reviews?date_start=2024-01-01&date_end=2024-12-31
```

**Ответ:**
```json
{
  "reviews": [
    {
      "school_id": "1",
      "review_id": 1,
      "review_text": "Отличная школа!",
      "review_date": "2024-05-15",
      "review_topic": "учителя",
      "review_overall": "positive"
    }
  ]
}
```

## Документация API

После запуска доступна автоматическая документация:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Переменные окружения

Убедитесь, что в `.env` файле указаны параметры подключения к БД:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password
```

