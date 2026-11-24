#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновление данных ЕГЭ/ВУЗ из свежей выгрузки sg_main в extract-файл, который читает
prepare_final_data.py.

Правила (по методике аудита 24.11.2026 и уточнению владельца):
  1) на странице школы есть «Общий средний балл ЕГЭ …» (в т.ч. «по всем предметам»)
     -> обновляем общий балл и год;
  2) есть только предметные баллы («по русскому языку», «информатика», «по химии»)
     -> общий балл школы не подтверждён: прежнее значение очищаем, предметные баллы
        сохраняем отдельно (в карточке школы они показываются, в рейтинг не идут);
  3) «высший/максимальный/сто…» -> это не средний: значение ЕГЭ очищаем;
  4) в новой выгрузке по ЕГЭ ничего нет -> старые данные НЕ трогаем (прогон мог не
     отдать блок результатов, это не значит «данных нет»).

Разбор строк — в school_data/ege_parser.py (общий модуль с prepare_final_data.py).

Запуск из корня репозитория:
  python roadmap/24.11.26/apply_fresh_results.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "school_data"))
from ege_parser import parse_ege_lines  # noqa: E402

EXTRACT = REPO / "school_data" / "sd_2_stage_gosuslugi_infrastucture_output_extract.json"
FRESH = REPO / "roadmap" / "24.11.26" / "sg_all_saratov_output.json"


def ege_lines_of(fresh_school: dict) -> list[str]:
    """Все строки показателей ЕГЭ из выгрузки sg_main (KPI-блок «Результаты школы»)."""
    raw = fresh_school.get("results_kpi_raw")
    lines = [str(x) for x in raw] if isinstance(raw, list) else []
    lines = [x for x in lines if "егэ" in x.lower()]
    if not lines:
        single = fresh_school.get("EGE_2026") or fresh_school.get("EGE")
        if single:
            lines = [str(single)]
    return lines


def main() -> None:
    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    fresh_raw = json.loads(FRESH.read_text(encoding="utf-8"))
    fresh = {int(x["id"]): x for x in fresh_raw if x.get("id") is not None}
    # перепрогон по исправленным ссылкам (Гимназия №4 и др.) — приоритетнее
    recheck = REPO / "roadmap" / "24.11.26" / "sg_recheck_out.json"
    if recheck.exists():
        for x in json.loads(recheck.read_text(encoding="utf-8")):
            if x.get("id") is not None:
                fresh[int(x["id"])] = x
    # второй свежий забег (42 школы) — самый свежий источник, он перекрывает общий файл
    rest = REPO / "roadmap" / "24.11.26" / "sg_rest_output.json"
    if rest.exists():
        for x in json.loads(rest.read_text(encoding="utf-8")):
            if x.get("id") is not None:
                fresh[int(x["id"])] = x

    stats = {"set": 0, "drop_subjects_only": 0, "drop_max": 0, "keep": 0, "no_fresh": 0, "vuz_set": 0}
    report = []
    for rec in extract:
        sid = rec.get("id")
        if sid is None:
            continue
        f = fresh.get(int(sid))
        if not f:
            stats["no_fresh"] += 1
            continue

        before = rec.get("EGE")
        lines = ege_lines_of(f)
        parsed = parse_ege_lines(lines)
        overall = parsed["overall"]

        if overall is not None:
            # строка-источник общего балла: та, где есть «общий» или предметов нет
            overall_line = None
            for line in parsed["raw_lines"]:
                one = parse_ege_lines([line])
                if one["overall"] is not None:
                    overall_line = line
                    break
            rec["EGE"] = overall_line
            rec["EGE_2026"] = overall_line
            rec["EGE_LINES"] = parsed["raw_lines"]
            stats["set"] += 1
        elif parsed["has_data"]:
            # на странице есть только предметные баллы: общего балла школа не публикует
            rec["EGE"] = None
            rec["EGE_2026"] = None
            rec["EGE_LINES"] = parsed["raw_lines"]
            stats["drop_subjects_only"] += 1
        elif parsed["has_max"]:
            # школа публикует максимумы, а не средние: прежнее значение не подтверждено
            rec["EGE"] = None
            rec["EGE_2026"] = None
            rec["EGE_LINES"] = parsed["raw_lines"]
            stats["drop_max"] += 1
        else:
            # свежих данных по ЕГЭ нет — старое значение не трогаем
            stats["keep"] += 1

        if rec.get("EGE") != before:
            report.append({
                "id": sid,
                "name": rec.get("name") or rec.get("short_name") or rec.get("name_2gis"),
                "before": before,
                "after": rec.get("EGE"),
                "subjects": parsed["subjects"],
            })

        new_vuz = f.get("VUZ_2026") or f.get("VUZ")
        if new_vuz and str(new_vuz).strip():
            rec["VUZ"] = new_vuz
            rec["VUZ_2026"] = new_vuz
            stats["vuz_set"] += 1

    EXTRACT.write_text(json.dumps(extract, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPO / "roadmap" / "24.11.26" / "apply_fresh_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("Обновлено записей:", stats)
    for r in report:
        subs = ", ".join(f"{s['subject']} {s['score']}" for s in r["subjects"]) or "-"
        print(f"  {r['id']:>4} {str(r['name'])[:34]:36} {str(r['before'])[:26]:28} -> {str(r['after'])[:40]:42} | предметы: {subs}")


if __name__ == "__main__":
    main()
