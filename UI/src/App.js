import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import axios from 'axios';
import './App.css';
import MapView from './components/MapView';
import SidePanel from './components/SidePanel';
import SchoolBottomCard from './components/SchoolBottomCard';
import SchoolAnalysisPage from './components/SchoolAnalysisPage';
import AnalyticsView, { AnalyticsChart } from './components/AnalyticsView';
import Toast from './components/Toast';
import PreferenceModal from './components/PreferenceModal';

// Пустая строка = тот же origin (nginx проксирует /api → uvicorn).
// На проде без .env — тот же origin; локальная разработка (localhost/127.0.0.1) — :8000.
function resolveApiUrl() {
  const fromEnv = process.env.REACT_APP_API_URL;
  if (fromEnv !== undefined) return fromEnv;
  if (typeof window !== 'undefined' &&
      /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)) {
    return 'http://localhost:8000';
  }
  return '';
}
const API_URL = resolveApiUrl();

const LS_PREFS = 'schoolMapPreferences';
const LS_MODAL_DISMISSED = 'schoolPreferencesModalDismissed';

const defaultFilterState = {
  yearMin: null,
  yearMax: null,
  ratingMin: null,
  ratingMax: null,
  sports: null,
};

const defaultPreferenceState = {
  olympiads: false,
  bullying: false,
  staff: false,
  building: false,
  exam: false,
  location: false,
  userLat: null,
  userLon: null,
};

function loadStoredPreferences() {
  try {
    const raw = localStorage.getItem(LS_PREFS);
    if (!raw) return { ...defaultPreferenceState, active: false };
    const o = JSON.parse(raw);
    return {
      ...defaultPreferenceState,
      olympiads: !!o.olympiads,
      bullying: !!o.bullying,
      staff: !!o.staff,
      building: !!o.building,
      exam: !!o.exam,
      location: !!o.location,
      userLat: o.userLat != null ? Number(o.userLat) : null,
      userLon: o.userLon != null ? Number(o.userLon) : null,
      active: !!o.active,
    };
  } catch {
    return { ...defaultPreferenceState, active: false };
  }
}

function persistPreferences(prefs, active) {
  const payload = {
    olympiads: prefs.olympiads,
    bullying: prefs.bullying,
    staff: prefs.staff,
    building: prefs.building,
    exam: prefs.exam,
    location: prefs.location,
    userLat: prefs.userLat,
    userLon: prefs.userLon,
    active,
  };
  localStorage.setItem(LS_PREFS, JSON.stringify(payload));
}

function mergePreferenceParams(params, preferenceState, preferencesActive) {
  if (!preferencesActive) return params;
  const p = { ...params };
  if (preferenceState.olympiads) p.pref_olympiads = true;
  if (preferenceState.bullying) p.pref_bullying = true;
  if (preferenceState.staff) p.pref_staff = true;
  if (preferenceState.building) p.pref_building = true;
  if (preferenceState.exam) p.pref_exam = true;
  if (preferenceState.location) {
    p.pref_location = true;
    if (preferenceState.userLat != null && preferenceState.userLon != null) {
      p.user_lat = preferenceState.userLat;
      p.user_lon = preferenceState.userLon;
    }
  }
  return p;
}

function buildParams(search, filterState, filtersApplied, preferenceState, preferencesActive) {
  const params = {};
  if (search && search.trim()) params.search = search.trim();
  if (!filtersApplied) {
    return mergePreferenceParams(params, preferenceState, preferencesActive);
  }
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
  return mergePreferenceParams(params, preferenceState, preferencesActive);
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
  const initPrefs = loadStoredPreferences();
  const { active: initPrefsActive, ...initPreferenceState } = initPrefs;

  const [schools, setSchools] = useState([]);
  const [totalCount, setTotalCount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchSubmitted, setSearchSubmitted] = useState('');
  const [filterState, setFilterState] = useState(defaultFilterState);
  const [filtersApplied, setFiltersApplied] = useState(false);
  const [preferenceState, setPreferenceState] = useState(initPreferenceState);
  const [preferencesActive, setPreferencesActive] = useState(initPrefsActive);
  const [showPreferenceModal, setShowPreferenceModal] = useState(
    () => localStorage.getItem(LS_MODAL_DISMISSED) !== '1'
  );
  const [toast, setToast] = useState(null);
  const mapFetchOnce = useRef(false);

  const [selectedSchoolId, setSelectedSchoolId] = useState(null);
  const [schoolDetail, setSchoolDetail] = useState(null);
  const [schoolDetailLoading, setSchoolDetailLoading] = useState(false);
  const [sortBy, setSortBy] = useState('rating_total');
  const [showAnalysisPage, setShowAnalysisPage] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [institutionToast, setInstitutionToast] = useState(null);
  // Разграничение заведений: группа для селектора + город + общие/частные внутри школ
  const [selectedGroup, setSelectedGroup] = useState('schools'); // schools|preschool|vuz|other
  const [selectedCity, setSelectedCity] = useState('Саратов'); // Саратов|Энгельс
  const [schoolOwnership, setSchoolOwnership] = useState('all'); // all|public|private
  const [institutionsByGroup, setInstitutionsByGroup] = useState({}); // group -> list
  const [analyticsReviews, setAnalyticsReviews] = useState([]);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsAppliedTopics, setAnalyticsAppliedTopics] = useState([]);
  const [analyticsInterval, setAnalyticsInterval] = useState('month');

  const fetchSchools = useCallback(
    async (params = {}) => {
      setLoading(true);
      try {
        const p = { ...params };
        if (schoolOwnership !== 'all') p.ownership = schoolOwnership;
        p.city = selectedCity;
        const { data } = await axios.get(`${API_URL}/api/schools/map`, { params: p });
        setSchools(data.schools || []);
        const count = data.count ?? (data.schools || []).length;
        setTotalCount(count);
        return count;
      } catch (err) {
        const msg = err.response?.data?.detail || err.message || 'Ошибка загрузки данных';
        setToast({ message: `Ошибка при использовании фильтра: ${msg}`, type: 'error' });
        setSchools([]);
        setTotalCount(0);
        return 0;
      } finally {
        setLoading(false);
      }
    },
    [schoolOwnership, selectedCity]
  );

  // смена общие/частные или города — перезагрузка школ с текущими фильтрами
  useEffect(() => {
    if (mapFetchOnce.current !== true) return;
    const p = buildParams(searchSubmitted || searchQuery, filterState, filtersApplied, preferenceState, preferencesActive);
    fetchSchools(p);
    setSelectedSchoolId(null);
    setSchoolDetail(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schoolOwnership, selectedCity]);

  useEffect(() => {
    if (mapFetchOnce.current) return;
    mapFetchOnce.current = true;
    const s = loadStoredPreferences();
    const { active, ...rest } = s;
    const p = buildParams('', defaultFilterState, false, rest, active);
    p.city = selectedCity;
    fetchSchools(p);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchSchools]);

  // Клик по учреждению — карточка-минимум (имя/адрес/сайт)
  useEffect(() => {
    window.__uchgradInstitutionClick = (it) => {
      setInstitutionToast(it);
    };
    return () => {
      delete window.__uchgradInstitutionClick;
    };
  }, []);

  // Загрузка учреждений по выбранной группе и городу (для не-школьных групп)
  useEffect(() => {
    if (selectedGroup === 'schools') return undefined;
    let cancelled = false;
    axios
      .get(`${API_URL}/api/institutions`, {
        params: { group: selectedGroup, city: selectedCity },
      })
      .then(({ data }) => {
        if (!cancelled) {
          setInstitutionsByGroup((prev) => ({
            ...prev,
            [`${selectedCity}_${selectedGroup}`]: data.institutions || [],
          }));
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedGroup, selectedCity]);

  const groupInstitutions = institutionsByGroup[`${selectedCity}_${selectedGroup}`] || [];

  const handleSchoolClick = useCallback(
    async (school) => {
      setShowAnalysisPage(false);
      setSelectedSchoolId(school.school_id);
      setSchoolDetailLoading(true);
      setSchoolDetail(null);
      try {
        const [{ data: detail }, { data: catchment }] = await Promise.all([
          axios.get(`${API_URL}/api/schools/${school.school_id}`),
          axios
            .get(`${API_URL}/api/schools/${school.school_id}/catchment`)
            .catch(() => ({ data: null })),
        ]);
        setSchoolDetail({ ...detail, catchment: catchment?.points || [] });
      } catch (err) {
        const msg = err.response?.data?.detail || err.message || 'Ошибка загрузки';
        setToast({ message: msg, type: 'error' });
        setSelectedSchoolId(null);
      } finally {
        setSchoolDetailLoading(false);
      }
    },
    []
  );

  // Ранг школы по итоговому рейтингу в текущей выборке
  const rankedIds = useMemo(() => {
    const val = (s) => (typeof s.rating_total === 'number' && Number.isFinite(s.rating_total) ? s.rating_total : null);
    return [...schools]
      .sort((a, b) => {
        const va = val(a);
        const vb = val(b);
        if (va == null) return 1;
        if (vb == null) return -1;
        return vb - va;
      })
      .map((s) => s.school_id);
  }, [schools]);
  const rankOf = useCallback(
    (id) => {
      const i = rankedIds.indexOf(id);
      return i === -1 ? null : i + 1;
    },
    [rankedIds]
  );

  // Максимумы по выборке — для относительного масштаба полосок компонентов
  const maxima = useMemo(() => ({
    olympiads: Math.max(0, ...schools.map((s) => s.olympiad_winners_count || 0)),
  }), [schools]);

  const handleOpenAnalysisPage = useCallback(() => setShowAnalysisPage(true), []);

  const handleCloseBottomCard = useCallback(() => {
    setSelectedSchoolId(null);
    setSchoolDetail(null);
  }, []);

  const handleStatistics = useCallback(() => {
    if (!selectedSchoolId) return;
    setShowAnalytics(true);
    setAnalyticsAppliedTopics([]);
  }, [selectedSchoolId]);

  useEffect(() => {
    if (!showAnalytics || !selectedSchoolId) return;
    setAnalyticsLoading(true);
    axios
      .get(`${API_URL}/api/schools/${selectedSchoolId}/reviews/topics`)
      .then(({ data }) => setAnalyticsReviews(data.reviews || []))
      .catch(() => setAnalyticsReviews([]))
      .finally(() => setAnalyticsLoading(false));
  }, [showAnalytics, selectedSchoolId]);

  const handleBackFromAnalytics = useCallback(() => {
    setShowAnalytics(false);
    setAnalyticsReviews([]);
    setAnalyticsAppliedTopics([]);
  }, []);

  const handleBackFromAnalysisPage = useCallback(() => {
    setShowAnalysisPage(false);
  }, []);

  const handleSearchSubmit = useCallback(() => {
    setSearchSubmitted(searchQuery);
    const params = buildParams(searchQuery, filterState, filtersApplied, preferenceState, preferencesActive);
    fetchSchools(params).then((count) => {
      setToast({ message: `Найдено школ: ${count} после использования фильтра`, type: 'info' });
    });
  }, [searchQuery, filterState, filtersApplied, preferenceState, preferencesActive, fetchSchools]);

  const handleApply = useCallback(() => {
    if (!validateFilters(filterState, setToast)) return;
    setFiltersApplied(true);
    const params = buildParams(searchSubmitted || searchQuery, filterState, true, preferenceState, preferencesActive);
    fetchSchools(params).then((count) => {
      setToast({ message: `Найдено школ: ${count} после использования фильтра`, type: 'info' });
    });
  }, [filterState, searchSubmitted, searchQuery, preferenceState, preferencesActive, fetchSchools]);

  const handleReset = useCallback(() => {
    setFilterState(defaultFilterState);
    setFiltersApplied(false);
    setSearchQuery('');
    setSearchSubmitted('');
    const params = buildParams('', defaultFilterState, false, preferenceState, preferencesActive);
    fetchSchools(params).then((count) => {
      setToast({ message: `Найдено школ: ${count} после использования фильтра`, type: 'info' });
    });
  }, [fetchSchools, preferenceState, preferencesActive]);

  const handlePreferenceBackdropClose = useCallback(() => {
    localStorage.setItem(LS_MODAL_DISMISSED, '1');
    setShowPreferenceModal(false);
  }, []);

  const handlePreferenceSkipNoPrefs = useCallback(() => {
    localStorage.setItem(LS_MODAL_DISMISSED, '1');
    setShowPreferenceModal(false);
    setPreferencesActive(false);
    persistPreferences(preferenceState, false);
    const params = buildParams(searchSubmitted || searchQuery, filterState, filtersApplied, preferenceState, false);
    fetchSchools(params).then((count) => {
      setToast({ message: `Подбор отключён. Найдено школ: ${count}`, type: 'info' });
    });
  }, [searchSubmitted, searchQuery, filterState, filtersApplied, preferenceState, fetchSchools]);

  const handlePreferenceApply = useCallback(
    (form) => {
      const next = {
        olympiads: form.olympiads,
        bullying: form.bullying,
        staff: form.staff,
        building: form.building,
        exam: form.exam,
        location: form.location,
        userLat: form.userLat,
        userLon: form.userLon,
      };
      setPreferenceState(next);
      setPreferencesActive(true);
      persistPreferences(next, true);
      localStorage.setItem(LS_MODAL_DISMISSED, '1');
      setShowPreferenceModal(false);
      const params = buildParams(searchSubmitted || searchQuery, filterState, filtersApplied, next, true);
      fetchSchools(params).then((count) => {
        setToast({ message: `Подбор применён. Найдено школ: ${count}`, type: 'info' });
      });
    },
    [searchSubmitted, searchQuery, filterState, filtersApplied, fetchSchools]
  );

  const handleOpenPreferenceModal = useCallback(() => {
    setShowPreferenceModal(true);
  }, []);

  const showSchoolDetail = selectedSchoolId != null && !showAnalytics;

  if (showAnalysisPage && schoolDetail) {
    return (
      <div className="app app-analysis-page">
        <SchoolAnalysisPage
          school={schoolDetail}
          rank={rankOf(schoolDetail.school_id)}
          total={rankedIds.length}
          onBack={handleBackFromAnalysisPage}
          onShowDynamics={handleStatistics}
        />
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

  return (
    <div className="app">
      {showAnalytics ? (
        <AnalyticsView
          school={schoolDetail}
          onBack={handleBackFromAnalytics}
          reviews={analyticsReviews}
          loading={analyticsLoading}
          appliedTopics={analyticsAppliedTopics}
          onApplyTopics={setAnalyticsAppliedTopics}
          interval={analyticsInterval}
          onIntervalChange={setAnalyticsInterval}
        />
      ) : (
        <SidePanel
          schools={schools}
          totalCount={totalCount}
          selectedSchoolId={selectedSchoolId}
          onSelectSchool={handleSchoolClick}
          sortBy={sortBy}
          onSortChange={setSortBy}
          selectedGroup={selectedGroup}
          onGroupChange={setSelectedGroup}
          selectedCity={selectedCity}
          onCityChange={setSelectedCity}
          schoolOwnership={schoolOwnership}
          onOwnershipChange={setSchoolOwnership}
          groupInstitutions={groupInstitutions}
          onSelectInstitution={setInstitutionToast}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onSearchSubmit={handleSearchSubmit}
          filterState={filterState}
          onFilterChange={setFilterState}
          onApply={handleApply}
          onReset={handleReset}
          filtersApplied={filtersApplied}
          loading={loading}
          preferencesActive={preferencesActive}
          onOpenPreferences={handleOpenPreferenceModal}
        />
      )}
      <main className="map-area">
        {showAnalytics ? (
          <AnalyticsChart
            reviews={analyticsReviews}
            appliedTopics={analyticsAppliedTopics}
            interval={analyticsInterval}
            loading={analyticsLoading}
          />
        ) : (
          <>
            {schoolDetailLoading && (
              <div className="map-loading-overlay">
                <span>Загрузка…</span>
              </div>
            )}
            <MapView
              schools={schools}
              selectedSchool={selectedGroup === 'schools' ? schoolDetail : null}
              onSchoolClick={handleSchoolClick}
              preferencesActive={preferencesActive}
              institutionsGroup={
                selectedGroup === 'schools'
                  ? null
                  : { group: selectedGroup, items: groupInstitutions }
              }
            />
            {showSchoolDetail && selectedGroup === 'schools' && schoolDetail && (
              <SchoolBottomCard
                school={schoolDetail}
                rank={rankOf(schoolDetail.school_id)}
                total={rankedIds.length}
                maxima={maxima}
                onClose={handleCloseBottomCard}
                onOpenDetails={handleOpenAnalysisPage}
              />
            )}
          </>
        )}
      </main>
      {!showAnalytics && !showSchoolDetail && (
        <PreferenceModal
          open={showPreferenceModal}
          onBackdropClose={handlePreferenceBackdropClose}
          onSkipWithoutPrefs={handlePreferenceSkipNoPrefs}
          onApply={handlePreferenceApply}
          initialForm={preferenceState}
          loading={loading}
          onToast={setToast}
        />
      )}
      {institutionToast && (
        <div className="institution-card" role="status">
          <button
            type="button"
            className="bottom-card-close"
            onClick={() => setInstitutionToast(null)}
            aria-label="Закрыть"
          >
            ✕
          </button>
          <div className="inst-name">{institutionToast.name}</div>
          <div className="inst-address">{institutionToast.address || 'Адрес не указан'}</div>
          <div className="inst-links">
            {institutionToast.phone && <span className="inst-item">{institutionToast.phone}</span>}
            {institutionToast.site && (
              <a href={institutionToast.site} target="_blank" rel="noopener noreferrer">
                Сайт учреждения
              </a>
            )}
          </div>
        </div>
      )}
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
