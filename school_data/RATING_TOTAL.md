# Расчёт рейтингов (`prepare_final_data.py`)

## Итоговый рейтинг `rating_total`

**Простая сумма** всех заполненных полей из списка (без весов, может быть **> 100**):

- `rating_2gis`
- `rating_yandex`
- `rating_ege`
- `rating_olympiads`
- `rating_university_admission`
- `rating_teachers`, `rating_mto`, `rating_psychological_climate`
- `rating_sports_infrastructure`

Пустое поле (`null`) **не входит** в сумму (не штраф).

---

## 2ГИС / Яндекс

- В JSON: **0–5**, 1 знак после запятой (как на площадке).
- В итог складывается как есть.

---

## ЕГЭ

| Поле | Смысл |
|------|--------|
| `ege_average_score` | **Исходный** средний балл из ячейки (0 если данных нет), 2 знака |
| `ege_year` | Год данных (целое) |
| `rating_ege` | Балл с устареванием: **−10% за каждый год** от 2025; **≥10 лет** → **0** |

Пример: 65,12 в 2023 → за 2 года: `65.12 × 0.9² ≈ 52.75` → `rating_ege`.

---

## Поступление в ВУЗ

| Поле | Смысл |
|------|--------|
| `university_admission_percent` | **Исходный** % из источника (не уменьшается) |
| `university_admission_year` | Год данных (целое) |
| `rating_university_admission` | Рейтинг с устареванием (−10%/год от 2025, ≥10 лет → 0) |

---

## Олимпиады

Сырьё: `победители / годы / вместимость`.

**`rating_olympiads`** — шкала **0–100** относительно других школ (лидер ≈ 100, с обрезкой по 95-му перцентилю).

`olympiad_winners_count` и `olympiad_years_span` — без изменений.

---

## Отзывы (NLP)

`rating_teachers`, `rating_mto`, `rating_psychological_climate` — индекс тональности **0..1**.

---

## Пересборка

```powershell
python school_data/prepare_final_data.py
```
