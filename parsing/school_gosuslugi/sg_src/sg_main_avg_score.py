#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Извлечение specialization_extract из infrastructure JSON.

Рейтинг школ считается только в school_data/prepare_final_data.py.
Здесь рейтинг не считается и в выход не пишется.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


INPUT_JSON = Path(
    r"c:\repos\analysis-of-educational-institutions\parsing\school_gosuslugi\sg_data\sg_data_output\sd_2_stage_gosuslugi_infrastucture_output.json"
)
OUTPUT_JSON = Path(
    r"c:\repos\analysis-of-educational-institutions\parsing\school_gosuslugi\sg_data\sg_data_output\sd_2_stage_gosuslugi_infrastucture_output_extract.json"
)

# Поля старого equal-weights рейтинга — вычищаем при пересборке extract
LEGACY_RATING_KEYS = (
    "ege_avg_score_2025",
    "olympiad_winners_count_raw",
    "olympiad_winners_weighted",
    "infrastructure_features_count",
    "facility_effective_year",
    "rating_components",
    "rating_completeness",
    "rating_missing_factors_count",
    "rating_missing_penalty",
    "rating_overall_equal_weights",
    "rating_method",
    "rating_rank",
)


def infer_specialization(raw_list: Any) -> list[str]:
    if not isinstance(raw_list, list) or not raw_list:
        return ["без специализации"]

    normalized: list[str] = []
    for item in raw_list:
        text = str(item).lower()
        if "универсал" in text:
            normalized.append("без специализации")
        elif "физ" in text and "мат" in text:
            normalized.append("физ-мат")
        elif ("хим" in text and "био" in text) or "естествен" in text:
            normalized.append("хим-био")
        elif "гуман" in text:
            normalized.append("гуманитарная")
        elif "социально" in text or "эконом" in text:
            normalized.append("соц-эконом")
        elif "технолог" in text or "инженер" in text or "it" in text:
            normalized.append("технологическая")
        elif "спорт" in text or "физическ" in text:
            normalized.append("физический")
        else:
            normalized.append(str(item))

    unique: list[str] = []
    for profile in normalized:
        if profile not in unique:
            unique.append(profile)
    return unique or ["без специализации"]


def build_extract() -> list[dict[str, Any]]:
    with INPUT_JSON.open("r", encoding="utf-8") as file:
        schools: list[dict[str, Any]] = json.load(file)

    output: list[dict[str, Any]] = []
    for school in schools:
        school_result = {
            key: value
            for key, value in school.items()
            if key not in LEGACY_RATING_KEYS
        }
        school_result["study_type"] = school.get("study_type")
        school_result["specialization_extract"] = infer_specialization(
            school.get("specialization")
        )
        output.append(school_result)

    output.sort(key=lambda s: int(s.get("id") or 0))
    return output


def main() -> None:
    schools = build_extract()
    with OUTPUT_JSON.open("w", encoding="utf-8") as file:
        json.dump(schools, file, ensure_ascii=False, indent=2)
    print(f"Saved {len(schools)} schools to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
