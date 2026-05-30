from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


INPUT_JSON = Path(
    r"c:\repos\analysis-of-educational-institutions\parsing\school_gosuslugi\sg_data\sg_data_output\sd_2_stage_gosuslugi_infrastucture_output.json"
)
OUTPUT_JSON = Path(
    r"c:\repos\analysis-of-educational-institutions\parsing\school_gosuslugi\sg_data\sg_data_output\sd_2_stage_gosuslugi_infrastucture_output_extract.json"
)

FACTOR_KEYS = [
    "academics_ege_2025",
    "academics_vuz_2025",
    "olympiads",
    "reviews",
    "infrastructure",
    "facility_area",
    "facility_modernity",
    "specialization",
]

MISSING_PENALTY_PER_FACTOR = 0.01


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"([0-9]+(?:[.,][0-9]+)?)", str(value))
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def parse_year_labeled_value(raw: Any, year: int) -> float | None:
    if raw is None:
        return None
    text = str(raw)
    if str(year) not in text:
        return None
    return parse_float(text)


def olympiad_entry_score(entry: Any) -> float:
    text = str(entry).lower()
    count = parse_float(text) or 0.0

    if "школьн" in text:
        stage_weight = 0.25
    elif "муницип" in text:
        stage_weight = 0.50
    elif "регион" in text:
        stage_weight = 0.75
    elif "заключитель" in text or "федерал" in text:
        stage_weight = 1.00
    else:
        stage_weight = 0.60

    level_weight = 1.00 if "всероссий" in text else 0.70
    return count * stage_weight * level_weight


def parse_olympiads(entries: Any) -> tuple[float, float]:
    if not isinstance(entries, list):
        return 0.0, 0.0
    raw_count = 0.0
    weighted_count = 0.0
    for entry in entries:
        current = parse_float(entry) or 0.0
        raw_count += current
        weighted_count += olympiad_entry_score(entry)
    return raw_count, weighted_count


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
        else:
            normalized.append(str(item))

    unique: list[str] = []
    for profile in normalized:
        if profile not in unique:
            unique.append(profile)
    return unique or ["без специализации"]


def specialization_score(spec_list: list[str]) -> float:
    if spec_list == ["без специализации"]:
        return 0.0
    distinct_profiles = len(spec_list)
    return min(1.0, 0.6 + 0.2 * min(2, distinct_profiles - 1))


def minmax(values: list[float | None]) -> tuple[float, float]:
    clean = [value for value in values if value is not None]
    if not clean:
        return 0.0, 1.0
    low = min(clean)
    high = max(clean)
    if high == low:
        high = low + 1.0
    return low, high


def norm(value: float | None, low: float, high: float) -> float | None:
    if value is None:
        return None
    return (value - low) / (high - low)


def compute_infrastructure_raw(school: dict[str, Any]) -> int:
    infra_list = school.get("infrastucture")
    infra_count = len(infra_list) if isinstance(infra_list, list) else 0
    sports_flags = [
        school.get("has_sports_complex"),
        school.get("has_pool"),
        school.get("has_stadium"),
        school.get("has_sports_ground"),
    ]
    sports_count = sum(1 for flag in sports_flags if flag == 1)
    return infra_count + sports_count


def compute_effective_year(school: dict[str, Any]) -> int | None:
    reconstruction_year = school.get("reconstruction_year")
    if isinstance(reconstruction_year, int):
        return reconstruction_year
    year_built = school.get("year_built")
    return year_built if isinstance(year_built, int) else None


def build_rating() -> list[dict[str, Any]]:
    with INPUT_JSON.open("r", encoding="utf-8") as file:
        schools: list[dict[str, Any]] = json.load(file)

    prepared: list[dict[str, Any]] = []
    for school in schools:
        ege_2025 = parse_year_labeled_value(school.get("EGE"), 2025)
        vuz_2025 = parse_year_labeled_value(school.get("VUZ"), 2025)
        olymp_raw, olymp_weighted = parse_olympiads(school.get("Olympiads"))
        reviews = [
            value
            for value in [school.get("rating_yandex"), school.get("rating_2gis")]
            if isinstance(value, (int, float))
        ]
        review_avg = (sum(reviews) / len(reviews)) if reviews else None
        infrastructure_raw = compute_infrastructure_raw(school)
        area_sqm = school.get("area_sqm") if isinstance(school.get("area_sqm"), (int, float)) else None
        effective_year = compute_effective_year(school)
        spec = infer_specialization(school.get("specialization"))

        prepared.append(
            {
                "school": school,
                "ege_2025": ege_2025,
                "vuz_2025": vuz_2025,
                "olymp_raw": olymp_raw,
                "olymp_weighted": olymp_weighted,
                "review_avg": review_avg,
                "infrastructure_raw": float(infrastructure_raw),
                "area_sqm": float(area_sqm) if area_sqm is not None else None,
                "effective_year": float(effective_year) if effective_year is not None else None,
                "specialization_extract": spec,
            }
        )

    lo_ege, hi_ege = minmax([item["ege_2025"] for item in prepared])
    lo_vuz, hi_vuz = minmax([item["vuz_2025"] for item in prepared])
    lo_ol, hi_ol = minmax([item["olymp_weighted"] for item in prepared])
    lo_inf, hi_inf = minmax([item["infrastructure_raw"] for item in prepared])
    lo_area, hi_area = minmax([item["area_sqm"] for item in prepared])
    lo_year, hi_year = minmax([item["effective_year"] for item in prepared])

    output: list[dict[str, Any]] = []
    for item in prepared:
        rating_components: dict[str, float | None] = {
            "academics_ege_2025": norm(item["ege_2025"], lo_ege, hi_ege),
            "academics_vuz_2025": norm(item["vuz_2025"], lo_vuz, hi_vuz),
            "olympiads": norm(item["olymp_weighted"], lo_ol, hi_ol),
            "reviews": (item["review_avg"] / 5.0) if item["review_avg"] is not None else None,
            "infrastructure": norm(item["infrastructure_raw"], lo_inf, hi_inf),
            "facility_area": norm(item["area_sqm"], lo_area, hi_area),
            "facility_modernity": norm(item["effective_year"], lo_year, hi_year),
            "specialization": specialization_score(item["specialization_extract"]),
        }

        filled_components = {
            key: (0.5 if value is None else value) for key, value in rating_components.items()
        }
        missing_count = sum(1 for key in FACTOR_KEYS if rating_components[key] is None)
        completeness = 1.0 - (missing_count / len(FACTOR_KEYS))
        base_average = sum(filled_components[key] for key in FACTOR_KEYS) / len(FACTOR_KEYS)
        penalty = missing_count * MISSING_PENALTY_PER_FACTOR
        final_rating_0_1 = max(0.0, base_average - penalty)

        school_result = dict(item["school"])
        school_result["study_type"] = None
        school_result["specialization_extract"] = item["specialization_extract"]
        school_result["ege_avg_score_2025"] = item["ege_2025"]
        school_result["olympiad_winners_count_raw"] = round(item["olymp_raw"], 3)
        school_result["olympiad_winners_weighted"] = round(item["olymp_weighted"], 3)
        school_result["infrastructure_features_count"] = int(item["infrastructure_raw"])
        school_result["facility_effective_year"] = (
            int(item["effective_year"]) if item["effective_year"] is not None else None
        )
        school_result["rating_components"] = {
            key: (None if value is None else round(value, 4))
            for key, value in rating_components.items()
        }
        school_result["rating_completeness"] = round(completeness, 4)
        school_result["rating_missing_factors_count"] = missing_count
        school_result["rating_missing_penalty"] = round(penalty, 4)
        school_result["rating_overall_equal_weights"] = round(final_rating_0_1 * 100, 2)
        school_result["rating_method"] = (
            "equal_average_with_neutral_fill_small_missing_penalty_"
            "and_extended_facility_specialization_factors"
        )
        output.append(school_result)

    output.sort(
        key=lambda school: (
            school.get("rating_overall_equal_weights", 0.0),
            school.get("rating_completeness", 0.0),
        ),
        reverse=True,
    )
    for index, school in enumerate(output, start=1):
        school["rating_rank"] = index

    return output


def main() -> None:
    rated_schools = build_rating()
    with OUTPUT_JSON.open("w", encoding="utf-8") as file:
        json.dump(rated_schools, file, ensure_ascii=False, indent=2)
    print(f"Saved {len(rated_schools)} schools to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
