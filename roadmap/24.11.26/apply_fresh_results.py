#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновление данных ЕГЭ/ВУЗ из свежей выгрузки sg_main в extract-файл, который читает
prepare_final_data.py.

Осторожные правила (по методике аудита 24.11.2026):
  1) «Средний балл …»           -> обновляем балл и год;
  2) «Высший/максимальный/сто…»  -> это НЕ средний: значение ЕГЭ очищаем (было ошибкой);
  3) в новой выгрузке ничего нет  -> старые данные НЕ трогаем (нет подтверждения ошибки:
     прогон мог не отдать блок результатов, это не значит «данных нет»).

Запуск из корня репозитория:
  python roadmap/24.11.26/apply_fresh_results.py
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXTRACT = REPO / "school_data" / "sd_2_stage_gosuslugi_infrastucture_output_extract.json"
FRESH = REPO / "roadmap" / "24.11.26" / "sg_all_saratov_output.json"

NOT_AVERAGE = ("высший балл", "стобалльн", "максимальн", "наивысш", "лучший результат")
AVERAGE = ("средний балл", "средний результат")


def classify(raw):
    """-> ('SET'|'DROP'|'KEEP', (score, year) | None)"""
    text = str(raw or "").strip()
    if not text:
        return "KEEP", None
    low = text.lower()
    if any(m in low for m in NOT_AVERAGE):
        return "DROP", None
    if not any(m in low for m in AVERAGE):
        return "KEEP", None
    m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*-", text)
    if not m:
        return "KEEP", None
    years = re.findall(r"(20\d{2})", text)
    year = int(years[-1]) if years else None
    return "SET", (round(float(m.group(1).replace(",", ".")), 2), year)


def main() -> None:
    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    fresh_raw = json.loads(FRESH.read_text(encoding="utf-8"))
    fresh = {int(x["id"]): x for x in fresh_raw if x.get("id") is not None}

    stats = {"set": 0, "drop": 0, "keep": 0, "no_fresh": 0, "vuz_set": 0}
    for rec in extract:
        sid = rec.get("id")
        if sid is None:
            continue
        f = fresh.get(int(sid))
        if not f:
            stats["no_fresh"] += 1
            continue
        new_ege = f.get("EGE_2026") or f.get("EGE")
        action, val = classify(new_ege)
        if action == "SET":
            rec["EGE"] = new_ege
            rec["EGE_2026"] = new_ege
            stats["set"] += 1
        elif action == "DROP":
            rec["EGE"] = None
            rec["EGE_2026"] = None
            stats["drop"] += 1
        else:
            stats["keep"] += 1
        new_vuz = f.get("VUZ_2026") or f.get("VUZ")
        if new_vuz and str(new_vuz).strip():
            rec["VUZ"] = new_vuz
            rec["VUZ_2026"] = new_vuz
            stats["vuz_set"] += 1

    EXTRACT.write_text(json.dumps(extract, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Обновлено записей:", stats)


if __name__ == "__main__":
    main()
