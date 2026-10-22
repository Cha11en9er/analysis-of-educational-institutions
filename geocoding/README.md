# Геокодирование (Geocoding)

## Данные (`gc_data/`)

| Файл | Назначение |
|------|------------|
| `gc_input/addresses.json` | Прикреплённые адреса совпавших школ (вход) |
| `gc_output/geocoded.json` | Школы + улицы + координаты (выход) |
| `gc_output/_cache.json` | Кэш API (для продолжения прогона) |

## Команды

```bash
# 1. Собрать addresses.json из CSV + final_school_data
python geocoding/scripts/build_gc_matched_input.py

# 2. Геокодировать (пишет _cache.json и geocoded.json)
python geocoding/scripts/geocode_gc_ans_matched.py

# Только пересобрать geocoded.json из кэша
python geocoding/scripts/build_geocoded.py
```

## Формат `geocoded.json`

```json
[
  {
    "id": 10,
    "label": "Гимназия №2",
    "district": "Волжский",
    "streets": [
      { "name": "им. Лермонтова М.Ю.", "points": [[51.525533, 46.045432], [51.52583, 46.048028]] }
    ]
  }
]
```

До **8 точек** на улицу (равномерная выборка из списка домов).

## Legacy

Старые скрипты `gc_src/gc_main.py`, `gc_merge_school.py` — отдельный пайплайн по зданиям школ из 2ГИС/Яндекс.
