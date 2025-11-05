# OpenMetadata: Руководство по применению в проекте анализа образовательных учреждений

## Что такое OpenMetadata?

**OpenMetadata** — это открытая платформа для управления метаданными (data catalog), которая помогает:

1. **Обнаружение данных** — находить и исследовать данные через поиск и фильтрацию
2. **Отслеживание происхождения данных** — визуализация источников и трансформаций данных
3. **Качество данных** — профилирование, мониторинг и проверка качества
4. **Совместная работа** — обсуждения, задачи и уведомления для команды
5. **Управление данными** — политики, стандарты, домены, владельцы, теги

## Зачем это вашему проекту?

Ваш проект парсит данные о школах из 2GIS и сохраняет их в JSON-файлы. OpenMetadata поможет:

- **Документировать источники данных** (2GIS, uchi.ru)
- **Отслеживать трансформации** (сырые данные → обработанные JSON)
- **Описать схему данных** (структура schools, reviews)
- **Мониторить качество** (проверка полноты данных, валидность)
- **Совместная работа** — команда может комментировать и обсуждать данные

## Как применить OpenMetadata к вашему проекту?

### Вариант 1: Использование OpenMetadata API (Рекомендуется)

Создайте скрипт для регистрации ваших данных в OpenMetadata:

#### Установка

```bash
pip install openmetadata-ingestion
```

#### Пример интеграции

Создайте файл `openmetadata_integration.py`:

```python
"""
Интеграция проекта анализа школ с OpenMetadata.
Регистрирует источники данных и их схемы.
"""

from metadata.ingestion.api.source import SourceStatus
from metadata.generated.schema.entity.data.table import Table, Column
from metadata.generated.schema.entity.services.databaseService import DatabaseService
from metadata.generated.schema.api.data.createTable import CreateTableRequest
from metadata.generated.schema.type.entityReference import EntityReference
import json
import os

# Конфигурация OpenMetadata
OPENMETADATA_SERVER = "http://localhost:8585/api"
OPENMETADATA_AUTH = {"provider": "basic", "credentials": {"username": "admin", "password": "admin"}}

def register_data_sources():
    """
    Регистрирует источники данных проекта в OpenMetadata.
    """
    # 1. Регистрация источника 2GIS
    # 2. Регистрация источника uchi.ru
    # 3. Регистрация схем данных (schools, reviews)
    pass

def create_table_schema(table_name: str, columns: list):
    """
    Создает схему таблицы в OpenMetadata.
    """
    # Определение колонок с типами данных
    table_columns = [
        Column(
            name=col["name"],
            dataType=col["type"],
            description=col.get("description", "")
        )
        for col in columns
    ]
    
    return CreateTableRequest(
        name=table_name,
        columns=table_columns,
        description=f"Таблица {table_name} из проекта анализа образовательных учреждений"
    )

def register_schools_schema():
    """Регистрирует схему данных школ"""
    columns = [
        {"name": "id", "type": "STRING", "description": "Уникальный идентификатор школы"},
        {"name": "name", "type": "STRING", "description": "Краткое название школы"},
        {"name": "full_name", "type": "STRING", "description": "Полное название школы"},
        {"name": "adres", "type": "STRING", "description": "Адрес школы"},
        {"name": "rating_2gis", "type": "STRING", "description": "Рейтинг на 2GIS"},
        {"name": "url", "type": "STRING", "description": "URL страницы школы на 2GIS"},
    ]
    return create_table_schema("schools", columns)

def register_reviews_schema():
    """Регистрирует схему данных отзывов"""
    columns = [
        {"name": "school_id", "type": "STRING", "description": "ID школы"},
        {"name": "date", "type": "STRING", "description": "Дата отзыва"},
        {"name": "text", "type": "STRING", "description": "Текст отзыва"},
        {"name": "weightы", "type": "BOOLEAN", "description": "Важность отзыва"},
    ]
    return create_table_schema("reviews", columns)

if __name__ == "__main__":
    print("Регистрация схем данных в OpenMetadata...")
    register_schools_schema()
    register_reviews_schema()
    print("Готово!")
```

### Вариант 2: Использование конфигурационного файла YAML

Создайте `openmetadata_config.yaml`:

```yaml
source:
  type: custom-json
  serviceName: schools-data-pipeline
  serviceConnection:
    config:
      type: JSON
      sourcePath: "nedvijka_from_laptop/school_review"
  sourceConfig:
    config:
      type: DatabaseMetadata
      schemaFilterPattern:
        includes:
          - "schools"
          - "reviews"
      tableFilterPattern:
        includes:
          - ".*"

sink:
  type: metadata-rest
  config:
    host: http://localhost:8585
    auth_provider: basic
    api_version: v1
```

### Вариант 3: Добавление метаданных в JSON-файлы

Добавьте метаданные напрямую в ваши JSON-файлы:

```json
{
  "_metadata": {
    "source": "2gis",
    "parser": "nedvijka_from_laptop/2gis_review_parser/main.py",
    "last_updated": "2024-01-15T10:30:00Z",
    "schema_version": "1.0",
    "data_quality": {
      "completeness": 0.95,
      "validity": 0.98
    }
  },
  "resource": "2gis",
  "schools": [...],
  "reviews": [...]
}
```

## Установка OpenMetadata

### Через Docker (самый простой способ)

```bash
# Клонируйте репозиторий
git clone https://github.com/open-metadata/OpenMetadata.git
cd OpenMetadata

# Запустите через Docker Compose
docker compose up -d
```

После запуска OpenMetadata будет доступен на `http://localhost:8585`

### Через Python пакет

```bash
pip install openmetadata-ingestion[all]
```

## Практические шаги для вашего проекта

1. **Документирование источников данных:**
   - 2GIS API/веб-сайт
   - uchi.ru
   - Парсеры (selenium_parser.py, parser.py, main.py)

2. **Определение схем данных:**
   - Таблица `schools` (id, name, full_name, adres, rating_2gis, url)
   - Таблица `reviews` (school_id, date, text, weightы)

3. **Создание lineage (происхождения данных):**
   ```
   2GIS веб-сайт → Selenium парсер → JSON файлы → Анализ
   ```

4. **Настройка качества данных:**
   - Проверка на пустые значения
   - Валидация формата дат
   - Проверка рейтингов на диапазон значений

## Полезные ссылки

- [Официальная документация OpenMetadata](https://docs.open-metadata.org/)
- [GitHub репозиторий](https://github.com/open-metadata/OpenMetadata)
- [Примеры интеграций](https://docs.open-metadata.org/connectors)

## Заключение

OpenMetadata превратит ваш проект из набора скриптов в полноценную систему управления данными с документацией, отслеживанием происхождения и контролем качества. Это особенно полезно, если вы планируете расширять проект или работать в команде.

