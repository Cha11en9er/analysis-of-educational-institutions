import React, { useMemo } from 'react';
import logo from '../logo.svg';
import { StarRating, avgReviewRating } from './SchoolBottomCard';

const SPORTS_LABELS = {
  has_stadium: 'Футбольное поле',
  has_pool: 'Бассейн',
  has_sports_ground: 'Спорт площадка',
  has_sports_complex: 'Спорткомплекс',
};

const PREFS_LABELS = {
  olympiads: 'олимпиады',
  bullying: 'климат',
  staff: 'учителя',
  building: 'ремонт',
  exam: 'ЕГЭ',
  location: 'близость',
};

const SORT_OPTIONS = [
  { key: 'rating_total', label: 'По итоговому рейтингу' },
  { key: 'ege_average_score', label: 'По баллу ЕГЭ' },
  { key: 'rating_yandex', label: 'По рейтингу Яндекса' },
  { key: 'year_built', label: 'По году постройки (новые)' },
];

function sortSchools(schools, sortKey, preferencesActive) {
  // RANK-01 (аудит 25.11): при активном подборе список сортируется по
  // preference_score — как обещает подбор, а не по общему рейтингу
  if (preferencesActive) {
    return [...schools].sort((a, b) => {
      const va = typeof a.preference_score === 'number' && Number.isFinite(a.preference_score) ? a.preference_score : null;
      const vb = typeof b.preference_score === 'number' && Number.isFinite(b.preference_score) ? b.preference_score : null;
      if (va == null && vb == null) return (a.school_id || 0) - (b.school_id || 0);
      if (va == null) return 1;
      if (vb == null) return -1;
      return vb - va;
    });
  }
  const val = (s) => {
    const v = s[sortKey];
    return typeof v === 'number' && Number.isFinite(v) ? v : null;
  };
  return [...schools].sort((a, b) => {
    const va = val(a);
    const vb = val(b);
    if (va == null && vb == null) return (a.school_id || 0) - (b.school_id || 0);
    if (va == null) return 1; // школы без данных идут вниз списка
    if (vb == null) return -1;
    return vb - va;
  });
}

/**
 * Короткие подписи активных фильтров для чипов в сайдбаре.
 */
export function activeFilterChips(filterState, preferenceState, preferencesActive) {
  const chips = [];
  if (preferencesActive && preferenceState) {
    const picked = Object.entries(PREFS_LABELS)
      .filter(([key]) => preferenceState[key])
      .map(([, label]) => label);
    if (picked.length) chips.push({ kind: 'prefs', label: `Подбор: ${picked.join(', ')}` });
  }
  const f = filterState || {};
  if (f.ratingMin != null && f.ratingMin !== '' && f.ratingMax != null && f.ratingMax !== '') {
    chips.push({ kind: 'rating', label: `Рейтинг ${f.ratingMin}–${f.ratingMax}` });
  } else if (f.ratingMin != null && f.ratingMin !== '') {
    chips.push({ kind: 'rating', label: `Рейтинг от ${f.ratingMin}` });
  } else if (f.ratingMax != null && f.ratingMax !== '') {
    chips.push({ kind: 'rating', label: `Рейтинг до ${f.ratingMax}` });
  }
  if (f.yearMin != null && f.yearMin !== '') chips.push({ kind: 'yearMin', label: `Год от ${f.yearMin}` });
  if (f.yearMax != null && f.yearMax !== '') chips.push({ kind: 'yearMax', label: `Год до ${f.yearMax}` });
  Object.entries(f.sports || {}).forEach(([key, on]) => {
    if (on) chips.push({ kind: `sport:${key}`, label: SPORTS_LABELS[key] || key });
  });
  return chips;
}

export default function SidePanel({
  schools,
  totalCount,
  selectedSchoolId,
  onSelectSchool,
  sortBy,
  onSortChange,
  selectedGroup,
  onGroupChange,
  selectedCity,
  onCityChange,
  schoolOwnership,
  onOwnershipChange,
  groupInstitutions,
  onSelectInstitution,
  searchQuery,
  onSearchChange,
  onSearchSubmit,
  onSearchClear,
  filterState,
  preferenceState,
  preferencesActive,
  onOpenFilters,
  onRemoveChip,
  loading,
  instLoading,
  instError,
  onInstRetry,
  instQuery,
  onInstQueryChange,
  selectedInstitutionId,
  onResetAll,
}) {
  const instSource = groupInstitutions.filter((i) => i.location?.coordinates);
  const visibleInstitutions = useMemo(() => {
    const q = (instQuery || '').trim().toLowerCase().replace(/ё/g, 'е');
    if (!q) return instSource;
    return instSource.filter((it) => {
      const hay = `${it.name || ''} ${it.name_full || ''} ${it.address || ''}`
        .toLowerCase()
        .replace(/ё/g, 'е');
      return hay.includes(q);
    });
  }, [instSource, instQuery]);
  const rankedSchools = useMemo(
    () => sortSchools(schools || [], sortBy || 'rating_total', preferencesActive),
    [schools, sortBy, preferencesActive]
  );
  const chips = useMemo(
    () => activeFilterChips(filterState, preferenceState, preferencesActive),
    [filterState, preferenceState, preferencesActive]
  );

  return (
    <aside className="side-panel">
      <div className="brand-row">
        <img src={logo} alt="УчГрад" className="brand-logo" />
        <div>
          <h1 className="panel-title">УчГрад</h1>
          <p className="panel-subtitle">Рейтинги и подбор учебных заведений</p>
        </div>
      </div>

      <section className="group-selector-section">
        <label className="label">Заведения</label>
        <div className="group-selector">
          {[
            ['schools', 'Школы'],
            ['preschool', 'Детские сады'],
            ['vuz', 'Вузы'],
            ['other', 'Иные'],
          ].map(([g, label]) => (
            <button
              type="button"
              key={g}
              className={`group-btn ${selectedGroup === g ? 'on' : ''}`}
              onClick={() => onGroupChange(g)}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="label" style={{ marginTop: '0.6rem' }}>Город</label>
        <div className="group-selector">
          {['Саратов', 'Энгельс'].map((c) => (
            <button
              type="button"
              key={c}
              className={`group-btn city ${selectedCity === c ? 'on' : ''}`}
              onClick={() => onCityChange(c)}
            >
              {c}
            </button>
          ))}
        </div>
        {selectedGroup === 'schools' && (
          <div className="ownership-selector">
            {[
              ['all', 'Все'],
              ['public', 'Общие'],
              ['private', 'Частные'],
            ].map(([o, label]) => (
              <button
                type="button"
                key={o}
                className={`group-btn ownership ${schoolOwnership === o ? 'on' : ''}`}
                onClick={() => onOwnershipChange(o)}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </section>

      {selectedGroup === 'schools' ? (
        <>
          <section className="search-section">
            <div className="search-row">
              <input
                type="text"
                className="search-input"
                placeholder="Поиск школы..."
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && onSearchSubmit()}
              />
              {searchQuery ? (
                <button
                  type="button"
                  className="search-btn"
                  onClick={onSearchClear}
                  aria-label="Очистить поиск"
                  title="Очистить поиск"
                >
                  <span className="search-icon">✕</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="search-btn"
                  onClick={onSearchSubmit}
                  aria-label="Найти"
                  title="Найти"
                >
                  <span className="search-icon">🔍</span>
                </button>
              )}
            </div>
          </section>

          <div className="filters-row">
            <button type="button" className="btn-filters" onClick={onOpenFilters}>
              Фильтры и подбор
              {chips.length > 0 && <span className="filters-count">{chips.length}</span>}
            </button>
          </div>

          {chips.length > 0 && (
            <div className="active-chips">
              {chips.map((c) => (
                <button
                  type="button"
                  key={c.kind}
                  className="active-chip"
                  onClick={() => onRemoveChip(c.kind)}
                  title="Убрать фильтр"
                >
                  {c.label}
                  <span className="chip-x">✕</span>
                </button>
              ))}
            </div>
          )}

          <section className="school-list-section">
            <div className="school-list-header">
              <span className="school-count">
                Найдено школ: <strong>{totalCount != null ? totalCount : rankedSchools.length}</strong>
              </span>
              <select
                className="sort-select"
                value={sortBy || 'rating_total'}
                onChange={(e) => onSortChange(e.target.value)}
                aria-label="Сортировка списка"
              >
                {SORT_OPTIONS.map(({ key, label }) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>
            <div className="school-list">
              {loading && rankedSchools.length === 0 && <div className="school-list-empty">Загрузка…</div>}
              {!loading && rankedSchools.length === 0 && (
                <div className="school-list-empty">
                  Ничего не найдено. Измените фильтры
                  <div style={{ marginTop: '0.5rem' }}>
                    <button type="button" className="chip" onClick={onResetAll}>
                      Сбросить фильтры и поиск
                    </button>
                  </div>
                </div>
              )}
              {rankedSchools.map((s, idx) => (
                <button
                  type="button"
                  key={s.school_id}
                  className={`school-row ${selectedSchoolId === s.school_id ? 'active' : ''}`}
                  onClick={() => onSelectSchool(s)}
                >
                  <span className="school-rank">
                    {(!preferencesActive && (sortBy || 'rating_total') === 'rating_total')
                      ? `#${idx + 1}`
                      : `${idx + 1}.`}
                  </span>
                  <span className="school-row-body">
                    <span className="school-row-name">{s.name_ym || s.name_2gis || `Школа ${s.school_id}`}</span>
                    <span className="school-row-meta">
                      {preferencesActive && typeof s.preference_score === 'number' ? (
                        <span className="pts">совпадение {Math.round(s.preference_score)}%</span>
                      ) : (
                        s.rating_total != null && (
                          <span className="pts">{Number(s.rating_total).toFixed(1)} балла</span>
                        )
                      )}
                      {s.ege_average_score != null && s.ege_average_score > 0 && (
                        <span className="ege"> ЕГЭ {Math.round(s.ege_average_score)}</span>
                      )}
                    </span>
                  </span>
                  <StarRating value={avgReviewRating(s)} size={12} />
                </button>
              ))}
            </div>
          </section>
        </>
      ) : (
        <section className="school-list-section">
          <div className="search-section">
            <div className="search-row">
              <input
                type="text"
                className="search-input"
                placeholder="Поиск по названию или адресу..."
                value={instQuery}
                onChange={(e) => onInstQueryChange(e.target.value)}
              />
              {instQuery && (
                <button
                  type="button"
                  className="search-btn"
                  onClick={() => onInstQueryChange('')}
                  aria-label="Очистить поиск"
                  title="Очистить поиск"
                >
                  <span className="search-icon">✕</span>
                </button>
              )}
            </div>
          </div>
          <div className="school-list-header">
            <span className="school-count">
              Найдено: <strong>{visibleInstitutions.length}</strong>
            </span>
          </div>
          <div className="school-list">
            {instLoading && <div className="school-list-empty">Загрузка…</div>}
            {!instLoading && instError && (
              <div className="school-list-empty">
                Не удалось загрузить учреждения: {instError}
                <div style={{ marginTop: '0.5rem' }}>
                  <button type="button" className="chip" onClick={onInstRetry}>Повторить</button>
                </div>
              </div>
            )}
            {!instLoading && !instError && visibleInstitutions.map((it) => (
              <button
                type="button"
                key={it.institution_id}
                className={`school-row ${selectedInstitutionId === it.institution_id ? 'active' : ''}`}
                onClick={() => onSelectInstitution(it)}
              >
                <span className="school-row-body">
                  <span className="school-row-name">{it.name}</span>
                  <span className="school-row-meta">{it.address || ''}</span>
                </span>
              </button>
            ))}
            {!instLoading && !instError && visibleInstitutions.length === 0 && (
              <div className="school-list-empty">
                {instQuery ? 'Ничего не найдено по запросу' : 'Нет данных для этой группы и города'}
              </div>
            )}
          </div>
        </section>
      )}
    </aside>
  );
}
