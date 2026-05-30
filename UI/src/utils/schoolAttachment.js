import addressBundle from '../data/geocoded_addresses_by_school.json';

/**
 * Ключ школы в geocoded_addresses_by_school.json (совпадает с geocoding/scripts/geocode_ans_stage1_bundle.py).
 * @param {string} n нормализованное имя (нижний регистр)
 */
/**
 * Не путать обычную СОШ №6 с ГБОУ «Школа … по адаптированным … программам №6» и т.п.
 */
function isAdaptiveOrNonStandardSchool6(n) {
  if (/адаптирован/i.test(n)) return true;
  if (/обучающихся\s+по\s+адаптирован/i.test(n)) return true;
  if (/образовательным\s+программам\s*№\s*6/i.test(n)) return true;
  if (/программам\s*№\s*6/i.test(n) && /школ[аы]\s+для/i.test(n)) return true;
  return false;
}

function matchAttachmentKeyFromName(n) {
  if (!n) return null;
  if (/лицей\s*№\s*62(?!\d)/i.test(n)) return 'lyceum62';
  if (/гимназия\s*№\s*1(?!\d)/i.test(n)) return 'gymnasium1';
  if (/сош\s*№\s*95/i.test(n) || /школа\s*№\s*95/i.test(n) || /школа\s*№95/i.test(n))
    return 'sosh95';
  if (/сош\s*№\s*45(?!\d)/i.test(n) || /школа\s*№\s*45(?!\d)/i.test(n)) return 'sosh45';

  if (isAdaptiveOrNonStandardSchool6(n)) {
    return null;
  }
  if (/сош\s*№\s*6(?!\d)/i.test(n)) return 'sosh6';
  if (/средняя\s+общеобразовательная\s+школ[аы]\s*№\s*6(?!\d)/i.test(n)) return 'sosh6';
  if (/моу\s*«?\s*сош\s*№\s*6(?!\d)/i.test(n)) return 'sosh6';
  if (/общеобразовательная\s+школ[аы]\s*№\s*6(?!\d)/i.test(n)) return 'sosh6';

  return null;
}

/**
 * @param {{ name_2gis?: string, name_ym?: string }} school
 * @returns {string|null}
 */
export function getSchoolAttachmentKey(school) {
  if (!school) return null;
  const parts = [school.name_2gis, school.name_ym].filter(Boolean);
  for (const p of parts) {
    const k = matchAttachmentKeyFromName(p.toLowerCase());
    if (k) return k;
  }
  return null;
}

/**
 * Список адресов (точек) для школы из бандла.
 * @param {string|null} key
 * @returns {Array<{ lat?: number, lon?: number, address?: string }>}
 */
export function getAttachedAddressesForKey(key) {
  if (!key || !addressBundle || typeof addressBundle !== 'object') return [];
  const arr = addressBundle[key];
  return Array.isArray(arr) ? arr : [];
}

/**
 * На карте: есть ненулевой набор геокодированных домов.
 */
export function schoolHasAttachedHouseData(school) {
  const key = getSchoolAttachmentKey(school);
  if (!key) return false;
  return getAttachedAddressesForKey(key).length > 0;
}

/** @deprecated используйте getSchoolAttachmentKey / schoolHasAttachedHouseData */
export function isGeocodeTestSchool(school) {
  return schoolHasAttachedHouseData(school);
}
