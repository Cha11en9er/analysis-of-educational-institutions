# Расчёт рейтингов (`prepare_final_data.py`)

## Итоговый рейтинг `rating_total`

Простая сумма заполненных составляющих (без весов). `null` не входит в сумму.

| Составляющая | Поле | Формула | Пример |
|---|---|---|---|
| ЕГЭ | `rating_ege` | средний балл как есть | 100 → **100** |
| Поступление в ВУЗ | `rating_university_admission` | `% / 10` | 100% → **10** |
| 2ГИС + Яндекс | `rating_maps` | среднее двух рейтингов | (5+3)/2 → **4** |
| Профили | `rating_profiles` | +1 за кластер | соц + мат → **2** |
| Олимпиады | `rating_olympiads` | `победители / вместимость * 10` | 50/200*10 → **2.5** |
| Вторая смена | `has_second_shift` | если `true` → **−10** | пока `null` у всех |
| Спорт | `rating_sports_infrastructure` | +1 за бассейн, ФОК, спортплощадку | макс. **3** |

Пример накопления: 100 + 10 + 4 + 2 + 2.5 − 0 + 3 ≈ **121.5**.

## Профильные кластеры

Только четыре флага (не суммировать сырые предметы):

- `profile_phys_math`
- `profile_soc_econ`
- `profile_chem_bio`
- `profile_physical` (спортивные школы)

## Не входит в рейтинг

- Отзывы: `rating_teachers`, `rating_mto`, `rating_psychological_climate`, `top_tags` — только карточка школы
- `year_built`, `reconstruction_year` — только карточка
- `stadium` — флаг есть, в спорт-рейтинг не входит

## Пересборка

```powershell
python school_data/prepare_final_data.py
```

Матрица: `school_data/rating_matrix.csv`.
