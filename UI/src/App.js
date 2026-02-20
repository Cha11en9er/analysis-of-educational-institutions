import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import MapView from './components/MapView';
import SidePanel from './components/SidePanel';
import Toast from './components/Toast';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const defaultFilterState = {
  yearMin: null,
  yearMax: null,
  ratingMin: null,
  ratingMax: null,
  sports: null,
};

function buildParams(search, filterState, filtersApplied) {
  const params = {};
  if (search && search.trim()) params.search = search.trim();
  if (!filtersApplied) return params;
  const f = filterState;
  if (f.yearMin != null && f.yearMin !== '') params.year_min = Number(f.yearMin);
  if (f.yearMax != null && f.yearMax !== '') params.year_max = Number(f.yearMax);
  if (f.ratingMin != null && f.ratingMin !== '') params.rating_min = Number(f.ratingMin);
  if (f.ratingMax != null && f.ratingMax !== '') params.rating_max = Number(f.ratingMax);
  if (f.sports) {
    if (f.sports.has_pool) params.has_pool = true;
    if (f.sports.has_stadium) params.has_stadium = true;
    if (f.sports.has_sports_ground) params.has_sports_ground = true;
    if (f.sports.has_sports_complex) params.has_sports_complex = true;
  }
  return params;
}

function validateFilters(filterState, setToast) {
  const f = filterState;
  const yMin = f.yearMin != null && f.yearMin !== '' ? Number(f.yearMin) : null;
  const yMax = f.yearMax != null && f.yearMax !== '' ? Number(f.yearMax) : null;
  if (yMin != null && yMax != null && yMin > yMax) {
    setToast({ message: 'Год постройки: начальное значение не может быть больше конечного', type: 'error' });
    return false;
  }
  const rMin = f.ratingMin != null && f.ratingMin !== '' ? Number(f.ratingMin) : null;
  const rMax = f.ratingMax != null && f.ratingMax !== '' ? Number(f.ratingMax) : null;
  if (rMin != null && rMax != null && rMin > rMax) {
    setToast({ message: 'Рейтинг: минимальное значение не может быть больше максимального', type: 'error' });
    return false;
  }
  if (rMin != null && (rMin < 1 || rMin > 5)) {
    setToast({ message: 'Рейтинг должен быть от 1 до 5', type: 'error' });
    return false;
  }
  if (rMax != null && (rMax < 1 || rMax > 5)) {
    setToast({ message: 'Рейтинг должен быть от 1 до 5', type: 'error' });
    return false;
  }
  return true;
}

function App() {
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchSubmitted, setSearchSubmitted] = useState('');
  const [filterState, setFilterState] = useState(defaultFilterState);
  const [filtersApplied, setFiltersApplied] = useState(false);
  const [toast, setToast] = useState(null);

  const fetchSchools = useCallback(async (params = {}) => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API_URL}/api/schools/map`, { params });
      setSchools(data.schools || []);
      return data.count ?? (data.schools || []).length;
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Ошибка загрузки данных';
      setToast({ message: `Ошибка при использовании фильтра: ${msg}`, type: 'error' });
      setSchools([]);
      return 0;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSchools();
  }, [fetchSchools]);

  const handleSearchSubmit = useCallback(() => {
    setSearchSubmitted(searchQuery);
    const params = buildParams(searchQuery, filterState, filtersApplied);
    fetchSchools(params).then((count) => {
      setToast({ message: `Найдено школ: ${count} после использования фильтра`, type: 'info' });
    });
  }, [searchQuery, filterState, filtersApplied, fetchSchools]);

  const handleApply = useCallback(() => {
    if (!validateFilters(filterState, setToast)) return;
    setFiltersApplied(true);
    const params = buildParams(searchSubmitted || searchQuery, filterState, true);
    fetchSchools(params).then((count) => {
      setToast({ message: `Найдено школ: ${count} после использования фильтра`, type: 'info' });
    });
  }, [filterState, searchSubmitted, searchQuery, fetchSchools]);

  const handleReset = useCallback(() => {
    setFilterState(defaultFilterState);
    setFiltersApplied(false);
    setSearchQuery('');
    setSearchSubmitted('');
    fetchSchools().then((count) => {
      setToast({ message: `Найдено школ: ${count} после использования фильтра`, type: 'info' });
    });
  }, [fetchSchools]);

  return (
    <div className="app">
      <SidePanel
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSearchSubmit={handleSearchSubmit}
        filterState={filterState}
        onFilterChange={setFilterState}
        onApply={handleApply}
        onReset={handleReset}
        filtersApplied={filtersApplied}
        loading={loading}
      />
      <main className="map-area">
        <MapView schools={schools} />
      </main>
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}

export default App;
