#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Разметка отзывов школ Энгельса по темам (те же правила, что для Саратова).

Идентификаторы отзывов совпадают с db_load_engels_reviews.py:
    2ГИС:  2_000_000_000 + (code_oo - 200_000) * 10_000 + idx
    Яндекс: 3_000_000_000 + (code_oo - 200_000) * 10_000 + idx

Выход: roadmap/22.11.26/reviews_analyzed/school_<100000+code>.json
(формат тот же, что читает db_load_review_topics.py: [{review_id, topics, overall}]).
Школы берём из roadmap/01.11.26/engels/city_schools.json — отзывы прочих
организаций (садики, центры) не размечаем.

Запуск из корня репозитория:
  python roadmap/25.11.26/analyze_engels_reviews.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "db" / "db_src" / "db_insert"))
from analyze_reviews import analyze  # noqa: E402

EN_DIR = REPO / "roadmap" / "08.11.26" / "engels"
SCHOOLS = REPO / "roadmap" / "01.11.26" / "engels" / "city_schools.json"
OUT_DIR = REPO / "roadmap" / "22.11.26" / "reviews_analyzed"

BASE_2GIS = 2_000_000_000
BASE_YM = 3_000_000_000


def review_id(base: int, code_oo: int, idx: int) -> int:
    return base + (code_oo - 200_000) * 10_000 + idx


def main() -> None:
    known_codes = {int(s["code_oo"]) for s in json.loads(SCHOOLS.read_text(encoding="utf-8"))}
    gis = json.loads((EN_DIR / "2gis_reviews_engels.json").read_text(encoding="utf-8"))
    ym = json.loads((EN_DIR / "ym_reviews_engels.json").read_text(encoding="utf-8"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    files = 0
    for source, base in ((gis, BASE_2GIS), (ym, BASE_YM)):
        for code_str, rec in source.items():
            code = int(code_str)
            if code not in known_codes:
                continue
            sid = 100000 + code
            raw = []
            for idx, r in enumerate(rec.get("reviews", [])):
                if not r.get("text"):
                    continue
                raw.append({"review_id": review_id(base, code, idx), "text": r["text"],
                            "rating": r.get("rating")})
            if not raw:
                continue
            result = [analyze(r) for r in raw]
            path = OUT_DIR / f"school_{sid}.json"
            if path.exists():
                # школа уже размечена: дописываем только новые источники (по review_id)
                prev = {x["review_id"]: x for x in json.loads(path.read_text(encoding="utf-8"))}
                prev.update({x["review_id"]: x for x in result})
                result = list(prev.values())
            path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
            total += len(raw)
            files += 1

    with_topics = 0
    for f in sorted(OUT_DIR.glob("school_1*.json")):
        for item in json.loads(f.read_text(encoding="utf-8")):
            if item.get("topics"):
                with_topics += 1
    print(f"Школ размечено: {files}, отзывов: {total}; в файлах Энгельса с темами: {with_topics}")


if __name__ == "__main__":
    main()
