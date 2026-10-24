# Статус полей `final_school_data.json`

Актуально после переработки формулы рейтинга (`prepare_final_data.py`).

## Итоговый рейтинг

См. `RATING_TOTAL.md` и `.cursor/rules/rating-formula.mdc`.

В сумму входят: ЕГЭ, ВУЗ/10, среднее карт, профили, олимпиады/вместимость×10, спорт (бассейн/ФОК/площадка), штраф −10 за вторую смену.

Не входят: отзывы, год постройки/реконструкции, стадион.

## Ключевые поля рейтинга

| Ключ | Смысл |
|---|---|
| `rating_total` | сумма составляющих |
| `rating_ege` | средний балл ЕГЭ как есть |
| `rating_university_admission` | `% / 10` |
| `rating_maps` | среднее 2ГИС и Яндекс |
| `rating_profiles` | число кластеров (0–4) |
| `rating_olympiads` | winners / capacity × 10 |
| `rating_sports_infrastructure` | 0–3 |
| `has_second_shift` | пока `null` у всех |

## Профили

`profile_phys_math`, `profile_chem_bio`, `profile_soc_econ`, `profile_physical`.

## Пересборка

```powershell
python school_data/prepare_final_data.py
```

Матрица: `school_data/rating_matrix.csv`.
