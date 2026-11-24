import { schoolHasAttachedHouseData } from './schoolAttachment';

const RASPBERRY = '#be185d'; // единый цвет всех школ в любом городе

/**
 * Параметры круглого HTML-маркера школы (без Leaflet).
 * Форма одинаковая для школ, садиков, вузов и прочих учреждений:
 * круг с белой обводкой, цвет зависит от типа заведения.
 */
export function getSchoolMarkerStyle(school, { prefsActive, scoreMin, scoreMax, selected, dimmed } = {}) {
  let diameter = 20;
  let opacity = 1;
  if (prefsActive && school.preference_score != null && scoreMin != null && scoreMax != null) {
    const lo = scoreMin;
    const hi = scoreMax;
    const t = hi > lo ? (school.preference_score - lo) / (hi - lo) : 0.5;
    const clamped = Math.max(0, Math.min(1, t));
    diameter = Math.round(12 + clamped * 14);
    opacity = 0.4 + clamped * 0.6;
  }

  if (selected) {
    diameter = 26;
    opacity = 1;
  } else if (dimmed) {
    // выбрана другая школа: остальные приглушаем, чтобы выбранная выделялась
    opacity = 0.22;
  }

  const fill = RASPBERRY;
  const html = `<div class="school-marker-dot-outer" style="width:${diameter}px;height:${diameter}px;opacity:${opacity}"><div class="school-marker-dot-inner" style="background:${fill}"></div></div>`;

  return { diameter, html, fill };
}

export function schoolMarkerTitle(school) {
  const name = school.name_2gis || school.name_ym || `Школа ${school.school_id}`;
  const parts = [name, school.school_address || ''];
  if (schoolHasAttachedHouseData(school)) {
    parts.push('Есть зона прикрепления домов');
  }
  if (school.preference_score != null) {
    parts.push(`Совпадение: ${school.preference_score}%`);
  }
  return parts.filter(Boolean).join('\n');
}
