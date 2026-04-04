/**
 * Тестовая фича: геоданные привязанных адресов для школы №6 (Саратов).
 * В БД название может быть «МОУ «СОШ № 6»» или «МОУ Средняя общеобразовательная школа №6» и т.п.
 * (?!\\d) после шестёрки — чтобы не спутать с №60, №66, №69…
 */
function matchesGeocodeTestName(n) {
  if (!n) return false;
  // Полное название: …общеобразовательная школа №6 / школа № 6
  if (/школа\s*№\s*6(?!\d)/i.test(n)) return true;
  // Краткое: СОШ №6, СОШ № 6
  if (/сош\s*№\s*6(?!\d)/i.test(n)) return true;
  return false;
}

export function isGeocodeTestSchool(school) {
  if (!school) return false;
  const parts = [school.name_2gis, school.name_ym].filter(Boolean);
  for (const p of parts) {
    if (matchesGeocodeTestName(p.toLowerCase())) return true;
  }
  return false;
}
