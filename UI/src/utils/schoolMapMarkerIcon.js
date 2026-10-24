import { schoolHasAttachedHouseData } from './schoolAttachment';

const BLUE = '#2563eb';
const RASPBERRY = '#be185d';

/**
 * Параметры круглого HTML-маркера школы (без Leaflet).
 */
export function getSchoolMarkerStyle(school, { prefsActive, scoreMin, scoreMax } = {}) {
  const hasRa = school.has_review_analysis === true;
  const attached = schoolHasAttachedHouseData(school);

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

  const fill = hasRa ? RASPBERRY : BLUE;
  const roadsSvg = attached
    ? `<svg class="school-marker-roads" viewBox="0 0 14 14" width="68%" height="68%" aria-hidden="true" style="pointer-events:none"><path d="M1 7h12M2 3.5h8M4 10.5h8" fill="none" stroke="rgba(255,255,255,0.9)" stroke-width="1.35" stroke-linecap="round"/></svg>`
    : '';

  const html = `<div class="school-marker-dot-outer" style="width:${diameter}px;height:${diameter}px;opacity:${opacity}"><div class="school-marker-dot-inner" style="background:${fill}">${roadsSvg}</div></div>`;

  return { diameter, html, fill };
}

export function schoolMarkerTitle(school) {
  const name = school.name_2gis || school.name_ym || `Школа ${school.school_id}`;
  const parts = [name, school.school_address || ''];
  if (school.preference_score != null) {
    parts.push(`Совпадение: ${school.preference_score}%`);
  }
  return parts.filter(Boolean).join('\n');
}
