import L from 'leaflet';
import { schoolHasAttachedHouseData } from './schoolAttachment';

const BLUE = '#2563eb';
const RASPBERRY = '#be185d';

/**
 * Круглый маркер: синий по умолчанию, малиновый если есть нейро-разбор отзывов;
 * внутри — «дорожки» при наличии прикреплённых адресов.
 * При активном подборе: выше совпадение — крупнее и плотнее по цвету, ниже — мельче и прозрачнее.
 */
export function createSchoolMapIcon(school, { prefsActive, scoreMin, scoreMax } = {}) {
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

  return L.divIcon({
    className: 'school-marker-leaflet',
    html,
    iconSize: [diameter, diameter],
    iconAnchor: [diameter / 2, diameter / 2],
    popupAnchor: [0, -Math.ceil(diameter / 2)],
  });
}

export function tooltipOffsetForMarker(school, { prefsActive, scoreMin, scoreMax } = {}) {
  let diameter = 20;
  if (prefsActive && school.preference_score != null && scoreMin != null && scoreMax != null) {
    const lo = scoreMin;
    const hi = scoreMax;
    const t = hi > lo ? (school.preference_score - lo) / (hi - lo) : 0.5;
    const clamped = Math.max(0, Math.min(1, t));
    diameter = Math.round(12 + clamped * 14);
  }
  return [0, -(Math.ceil(diameter / 2) + 6)];
}
