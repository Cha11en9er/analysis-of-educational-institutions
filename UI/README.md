# Визуализация школ и отзывов

Простое React приложение для визуализации данных о школах и отзывах.

## Установка

```bash
npm install
```

## Запуск

```bash
npm start
```

Приложение откроется на http://localhost:3000

## Настройка API и карты

По умолчанию (локально без `.env`) API: `http://localhost:8000`.

Файл `UI/.env` или `UI/.env.production`:

```
REACT_APP_API_URL=
REACT_APP_YANDEX_MAPS_API_KEY=ваш_ключ_javascript_api
```

Пустой `REACT_APP_API_URL` — запросы на тот же origin (`/api/...`), как на https://uchgrad.ru.

Карта: **Yandex Maps JS API v3** (Leaflet удалён).

## Функционал

- Выбор школы из выпадающего списка
- Выбор топика (ремонт, учителя, еда, администрация, буллинг, инфраструктура, охрана, уборка)
- Фильтрация по датам (от и до)
- Визуализация динамики упоминаний топиков во времени в виде линейной диаграммы

## Структура

- `src/App.js` - основной компонент приложения
- `src/components/Filters.js` - компонент фильтров
- `src/components/Chart.js` - компонент графика

## Прикреплённые дома на карте

Для школ, по которым есть записи в `src/data/geocoded_addresses_by_school.json`, на общей карте маркер **зелёный** (остальные — стандартный синий пин). При открытии карточки школы — оранжевые точки домов и синий полигон (см. `src/utils/buildAddressCoverageGeoJSON.js`).

Пополнение и пересчёт геокода из CSV: `python geocoding/scripts/geocode_ans_stage1_bundle.py` (нужен `YANDEX_API_KEY` в `.env` в корне репозитория). Скрипт дописывает ключи `lyceum62`, `gymnasium1`, `sosh95`, `sosh45` и подмешивает готовый `sosh6` из `geocoded_addresses_sosh6.json`.

