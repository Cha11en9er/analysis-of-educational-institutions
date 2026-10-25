import React, { useState, useCallback, useMemo } from 'react';
import logo from '../logo.svg';

const FILTER_KEYS = {
  year: 'Год постройки',
  rating: 'Рейтинг',
  sports: 'Наличие спорт объектов',
};

const SPORTS_OPTIONS = [
  { key: 'has_stadium', label: 'Футбольное поле' },
  { key: 'has_pool', label: 'Бассейн' },
  { key: 'has_sports_ground', label: 'Спорт площадка' },
  { key: 'has_sports_complex', label: 'Спорткомплекс' },
];

const SORT_OPTIONS = [
  { key: 'rating_total', label: 'По итоговому рейтингу' },
  { key: 'ege_average_score', label: 'По баллу ЕГЭ' },
  { key: 'rating_yandex', label: 'По рейтингу Яндекса' },
  { key: 'year_built', label: 'По году постройки (новые)' },
];

function sortSchools(schools, sortKey) {
  const val = (s) => {
    const v = s[sortKey];
    return typeof v === 'number' && Number.isFinite(v) ? v : null;
  };
  return [...schools].sort((a, b) => {
    const va = val(a);
    const vb = val(b);
    if (va == null && vb == null) return (a.school_id || 0) - (b.school_id || 0);
    if (va == null) return 1; // школы без данных — вниз списка
    if (vb == null) return -1;
    return sortKey === 'year_built' ? vb - va : vb - va;
  });
}

export default function SidePanel({
  schools,
  totalCount,
  selectedSchoolId,
  onSelectSchool,
  sortBy,
  onSortChange,
  searchQuery,
  onSearchChange,
  onSearchSubmit,
  filterState,
  onFilterChange,
  onApply,
  onReset,
  filtersApplied,
  loading,
  preferencesActive,
  onOpenPreferences,
}) {
  const [openFilter, setOpenFilter] = useState(null);

  const rankedSchools = useMemo(() => sortSchools(schools || [], sortBy || 'rating_total'), [schools, sortBy]);

  const toggleFilter = useCallback((key) => {
    setOpenFilter((prev) => (prev === key ? null : key));
  }, []);

  const handleYearMin = (e) => {
    const v = e.target.value.trim();
    onFilterChange({ ...filterState, yearMin: v === '' ? null : v });
  };
  const handleYearMax = (e) => {
    const v = e.target.value.trim();
    onFilterChange({ ...filterState, yearMax: v === '' ? null : v });
  };
  const handleRatingMin = (e) => {
    const v = e.target.value.trim();
    onFilterChange({ ...filterState, ratingMin: v === '' ? null : v });
  };
  const handleRatingMax = (e) => {
    const v = e.target.value.trim();
    onFilterChange({ ...filterState, ratingMax: v === '' ? null : v });
  };
  const handleSportToggle = (key) => {
    const current = filterState.sports || {};
    onFilterChange({
      ...filterState,
      sports: { ...current, [key]: !current[key] },
    });
  };

  return (
    <aside className="side-panel">
      <div className="brand-row">
        <img src={logo} alt="УчГрад" className="brand-logo" />
        <div>
          <h1 className="panel-title">УчГрад</h1>
          <p className="panel-subtitle">Школы · рейтинги, ЕГЭ, отзывы</p>
        </div>
      </div>
      <div className="preference-panel-row">
        <button
          type="button"
          className="btn-preferences"
          onClick={onOpenPreferences}
          disabled={loading}
        >
          Что вам важно в школе?
        </button>
        {preferencesActive && <span className="preference-badge">подбор вкл.</span>}
      </div>

      <section className="search-section">
        <label className="label">Поиск</label>
        <div className="search-row">
          <input
            type="text"
            className="search-input"
            placeholder="Введите запрос..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSearchSubmit()}
          />
          <button
            type="button"
            className="search-btn"
            onClick={onSearchSubmit}
            aria-label="Найти"
          >
            <span className="search-icon">🔍</span>
          </button>
        </div>
      </section>

      <section className="filters-section">
        <div className="filters-header">
          <span className="label">Фильтры</span>
        </div>

        {Object.entries(FILTER_KEYS).map(([key, label]) => (
          <div key={key} className="filter-block">
            <button
              type="button"
              className={`filter-trigger ${openFilter === key ? 'open' : ''}`}
              onClick={() => toggleFilter(key)}
            >
              {label}
              <span className="filter-chevron">{openFilter === key ? '▼' : '▶'}</span>
            </button>
            {openFilter === key && (
              <div className="filter-body">
                {key === 'year' && (
                  <div className="filter-year">
                    <label>От</label>
                    <input
                      type="number"
                      min={1800}
                      max={2100}
                      placeholder="год"
                      value={filterState.yearMin ?? ''}
                      onChange={handleYearMin}
                    />
                    <label>До</label>
                    <input
                      type="number"
                      min={1800}
                      max={2100}
                      placeholder="год"
                      value={filterState.yearMax ?? ''}
                      onChange={handleYearMax}
                    />
                  </div>
                )}
                {key === 'rating' && (
                  <div className="filter-rating">
                    <label>От</label>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      step={0.1}
                      placeholder="1"
                      value={filterState.ratingMin ?? ''}
                      onChange={handleRatingMin}
                    />
                    <label>До</label>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      step={0.1}
                      placeholder="5"
                      value={filterState.ratingMax ?? ''}
                      onChange={handleRatingMax}
                    />
                  </div>
                )}
                {key === 'sports' && (
                  <div className="filter-sports">
                    {SPORTS_OPTIONS.map(({ key: optKey, label: optLabel }) => (
                      <label key={optKey} className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={!!(filterState.sports && filterState.sports[optKey])}
                          onChange={() => handleSportToggle(optKey)}
                        />
                        {optLabel}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        <div className="apply-row">
          <button
            type="button"
            className="btn-apply"
            onClick={onApply}
            disabled={loading}
          >
            {loading ? 'Загрузка…' : 'Применить'}
          </button>
          {filtersApplied && (
            <button type="button" className="btn-reset" onClick={onReset}>
              Сбросить фильтры
            </button>
          )}
        </div>
      </section>

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
            <div className="school-list-empty">Ничего не найдено — измените фильтры</div>
          )}
          {rankedSchools.map((s, idx) => (
            <button
              type="button"
              key={s.school_id}
              className={`school-row ${selectedSchoolId === s.school_id ? 'active' : ''}`}
              onClick={() => onSelectSchool(s)}
            >
              <span className="school-rank">#{idx + 1}</span>
              <span className="school-row-body">
                <span className="school-row-name">{s.name_ym || s.name_2gis || `Школа ${s.school_id}`}</span>
                <span className="school-row-meta">
                  {s.rating_total != null && <span className="pts">{Number(s.rating_total).toFixed(1)} pts</span>}
                  {s.ege_average_score != null && s.ege_average_score > 0 && (
                    <span className="ege">· ЕГЭ {Math.round(s.ege_average_score)}</span>
                  )}
                </span>
              </span>
            </button>
          ))}
        </div>
      </section>
    </aside>
  );
}
