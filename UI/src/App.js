import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import axios from 'axios';
import './App.css';
import MapView from './components/MapView';
import SidePanel from './components/SidePanel';
import SchoolBottomCard from './components/SchoolBottomCard';
import InstitutionBottomCard from './components/InstitutionBottomCard';
import SchoolAnalysisPage from './components/SchoolAnalysisPage';
import Toast from './components/Toast';
import FiltersModal from './components/FiltersModal';

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

const SITE_TITLE = 'УчГрад: информация об обучающих учреждениях';

// Ключи подбора «что вам важно в школе» (см. FiltersModal)
const PREF_KEYS = ['olympiads', 'bullying', 'staff', 'building', 'exam', 'location'];

function schoolTitle(school) {
  if (!school) return SITE_TITLE;
  const name = school.name_ym || school.name_2gis || `Школа ${school.school_id}`;
  return `${name} — УчГрад`;
}

const axiosApi = axios.create({
  headers: { 'Cache-Control': 'no-cache' },
});

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
  if (rMin != null && (rMin < 0 || rMin > 110)) {
    setToast({ message: 'Итоговый рейтинг школы от 0 до 110 баллов', type: 'error' });
    return false;
  }
  if (rMax != null && (rMax < 0 || rMax > 110)) {
    setToast({ message: 'Итоговый рейтинг школы от 0 до 110 баллов', type: 'error' });
    return false;
  }
  return true;
}

// есть ли в фильтрах хотя бы одно условие
function filtersActive(f) {
  const nums = [f.yearMin, f.yearMax, f.ratingMin, f.ratingMax];
  if (nums.some((v) => v != null && v !== '')) return true;
  return Object.values(f.sports || {}).some(Boolean);
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
  const [showFiltersModal, setShowFiltersModal] = useState(
    () => localStorage.getItem(LS_MODAL_DISMISSED) !== '1'
  );
  const [toast, setToast] = useState(null);
  const mapFetchOnce = useRef(false);

  const [selectedSchoolId, setSelectedSchoolId] = useState(null);
  const [schoolDetail, setSchoolDetail] = useState(null);
  const [schoolDetailLoading, setSchoolDetailLoading] = useState(false);
  const [sortBy, setSortBy] = useState('rating_total');
  const [showAnalysisPage, setShowAnalysisPage] = useState(false);
  const [institutionToast, setInstitutionToast] = useState(null);
  // Разграничение заведений: группа для селектора + город + общие/частные внутри школ
  const [selectedGroup, setSelectedGroup] = useState('schools'); // schools|preschool|vuz|other
  const [selectedCity, setSelectedCity] = useState('Саратов'); // Саратов|Энгельс
  const [schoolOwnership, setSchoolOwnership] = useState('all'); // all|public|private
  const [institutionsByGroup, setInstitutionsByGroup] = useState({}); // group -> list
  const [institutionsLoading, setInstitutionsLoading] = useState(false);
  const [institutionsError, setInstitutionsError] = useState(null);
  const [institutionQuery, setInstitutionQuery] = useState('');
  const [selectedInstitutionId, setSelectedInstitutionId] = useState(null);
  const [institutionsRetryNonce, setInstitutionsRetryNonce] = useState(0);

  const fetchSchools = useCallback(
    async (params = {}) => {
      setLoading(true);
      try {
        const p = { ...params };
        if (schoolOwnership !== 'all') p.ownership = schoolOwnership;
        p.city = selectedCity;
        const { data } = await axiosApi.get(`${API_URL}/api/schools/map`, { params: p });
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
    // прямой заход по ссылке вида /school/{id} или /school/{id}/analysis
    const m = window.location.pathname.match(/^\/school\/(\d+)(\/analysis)?\/?$/);
    if (m) {
      const sid = Number(m[1]);
      setSelectedSchoolId(sid);
      if (m[2]) setShowAnalysisPage(true);
      loadSchoolDetail(sid);
    }
   
    // прямой заход по ссылке вида /institution/{id}
    const im = window.location.pathname.match(/^\/institution\/(\d+)\/?$/);
    if (im) {
      const iid = Number(im[1]);
      setSelectedInstitutionId(iid);
      setInstitutionsLoading(true);
      axios
        .get(`${API_URL}/api/institutions/${iid}`)
        .then(({ data }) => {
          setSelectedGroup(data.group === 'school' ? 'other' : data.group);
          setSelectedCity(data.city || 'Саратов');
          setInstitutionsByGroup((prev) => ({
            ...prev,
            [`${data.city}_${data.group}`]: [
              ...((prev[`${data.city}_${data.group}`] || []).filter(
                (x) => x.institution_id !== iid
              )),
              data,
            ],
          }));
          setInstitutionToast(data);
          setInstitutionsLoading(false);
        })
        .catch(() => setInstitutionsLoading(false));
    } // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchSchools]);

  // Клик по учреждению открывает его карточку и закрывает школьную.
  // UX-11 (аудит 25.11): выбор учреждения кодируется в адресе /institution/{id}.
  const handleInstitutionClick = useCallback((it) => {
    setSelectedSchoolId(null);
    setSchoolDetail(null);
    setShowAnalysisPage(false);
    const path = window.location.pathname;
    if (/^\/institution\/\d+/.test(path)) {
      window.history.replaceState({}, '', `/institution/${it.institution_id}`);
    } else {
      window.history.pushState({}, '', `/institution/${it.institution_id}`);
    }
    setSelectedInstitutionId(it.institution_id);
    setInstitutionToast(it);
  }, []);

  const handleCloseInstitutionCard = useCallback(() => {
    setInstitutionToast(null);
    setSelectedInstitutionId(null);
    if (/^\/institution\/\d+/.test(window.location.pathname)) {
      window.history.replaceState({}, '', '/');
    }
  }, []);

  useEffect(() => {
    window.__uchgradInstitutionClick = handleInstitutionClick;
    return () => {
      delete window.__uchgradInstitutionClick;
    };
  }, [handleInstitutionClick]);

  // Загрузка учреждений по выбранной группе и городу (для не-школьных групп)
  useEffect(() => {
    if (selectedGroup === 'schools') return undefined;
    let cancelled = false;
    setInstitutionsLoading(true);
    setInstitutionsError(null);
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
          setInstitutionsLoading(false);
        }
      })
      .catch((err) => {
        // UX-10: сбой запроса больше не выглядит как пустой каталог
        if (!cancelled) {
          setInstitutionsError(err.response?.data?.detail || err.message || 'ошибка сети');
          setInstitutionsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedGroup, selectedCity, institutionsRetryNonce]);

  const groupInstitutions = institutionsByGroup[`${selectedCity}_${selectedGroup}`] || [];

  const loadSchoolDetail = useCallback(async (sid) => {
    setSchoolDetailLoading(true);
    setSchoolDetail(null);
    try {
      const [{ data: detail }, { data: catchment }] = await Promise.all([
        axiosApi.get(`${API_URL}/api/schools/${sid}`),
        axios
          .get(`${API_URL}/api/schools/${sid}/catchment`)
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSchoolClick = useCallback(
    async (school) => {
      setShowAnalysisPage(false);
      setInstitutionToast(null);
      setSelectedSchoolId(school.school_id);
      const path = window.location.pathname;
      if (/^\/school\/\d+(\/analysis)?\/?$/.test(path)) {
        // уже открыта другая школа: меняем адрес на месте, чтобы «назад» и крестик
        // всегда вели к общему списку, а не к предыдущей школе
        window.history.replaceState({}, '', `/school/${school.school_id}`);
      } else {
        window.history.pushState({}, '', `/school/${school.school_id}`);
      }
      loadSchoolDetail(school.school_id);
    },
    [loadSchoolDetail]
  );

  // Кнопки «назад/вперёд» браузера: путь определяет, что открыто.
  // /school/{id}/analysis — подробный анализ, /school/{id} — карточка на карте, / — карта.
  useEffect(() => {
    const onPopState = () => {
      const path = window.location.pathname;
      const m = path.match(/^\/school\/(\d+)(\/analysis)?\/?$/);
      const im = path.match(/^\/institution\/(\d+)\/?$/);
      if (m) {
        const sid = Number(m[1]);
        setInstitutionToast(null);
        setSelectedInstitutionId(null);
        if (selectedSchoolId !== sid) {
          setSelectedSchoolId(sid);
          loadSchoolDetail(sid);
        }
        setShowAnalysisPage(Boolean(m[2]));
      } else if (im) {
        const iid = Number(im[1]);
        setSelectedSchoolId(null);
        setSchoolDetail(null);
        setShowAnalysisPage(false);
        // прямая ссылка или возврат: открыть карточку учреждения
        setSelectedInstitutionId(iid);
        setInstitutionsLoading(true);
        axios
          .get(`${API_URL}/api/institutions/${iid}`)
          .then(({ data }) => {
            setInstitutionsByGroup((prev) => ({
              ...prev,
              [`${data.city}_${data.group}`]: [
                ...((prev[`${data.city}_${data.group}`] || []).filter(
                  (x) => x.institution_id !== iid
                )),
                data,
              ],
            }));
            setInstitutionToast(data);
            if (selectedGroup === 'schools') setSelectedGroup(data.group === 'school' ? 'other' : data.group);
            if (selectedCity !== data.city) setSelectedCity(data.city);
            setInstitutionsLoading(false);
          })
          .catch(() => setInstitutionsLoading(false));
      } else {
        setShowAnalysisPage(false);
        setSelectedSchoolId(null);
        setSchoolDetail(null);
        setInstitutionToast(null);
        setSelectedInstitutionId(null);
      }
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [selectedSchoolId, selectedGroup, selectedCity, loadSchoolDetail]);

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
      // RANK-06 (аудит 25.11): место в городе считает API (rank по всем школам
      // города) и не меняется от поиска/фильтров
      const sch = schools.find((x) => x.school_id === id);
      if (sch && typeof sch.city_rank === 'number' && sch.city_rank > 0) {
        return sch.city_rank;
      }
      const i = rankedIds.indexOf(id);
      return i === -1 ? null : i + 1;
    },
    [rankedIds, schools]
  );

  // Максимумы по выборке — для относительного масштаба полосок компонентов
  const maxima = useMemo(() => ({
    olympiads: Math.max(0, ...schools.map((s) => s.olympiad_winners_count || 0)),
  }), [schools]);

  const handleOpenAnalysisPage = useCallback(() => {
    setShowAnalysisPage(true);
    const sid = selectedSchoolId;
    if (sid != null && !/^\/school\/\d+\/analysis\/?$/.test(window.location.pathname)) {
      window.history.pushState({}, '', `/school/${sid}/analysis`);
    }
  }, [selectedSchoolId]);

  const handleGroupChange = useCallback((g) => {
    setInstitutionToast(null);
    setSelectedSchoolId(null);
    setSchoolDetail(null);
    setShowAnalysisPage(false);
    if (/^\/school\/\d+/.test(window.location.pathname)) {
      window.history.replaceState({}, '', '/');
    }
    setSelectedGroup(g);
  }, []);

  const handleCityChange = useCallback((c) => {
    setInstitutionToast(null);
    setSelectedSchoolId(null);
    setSchoolDetail(null);
    setShowAnalysisPage(false);
    if (/^\/school\/\d+/.test(window.location.pathname)) {
      window.history.replaceState({}, '', '/');
    }
    setSelectedCity(c);
  }, []);

  const handleCloseBottomCard = useCallback(() => {
    // крестик в превью всегда закрывает карточку к общему списку,
    // а не возвращает к предыдущей школе
    setSelectedSchoolId(null);
    setSchoolDetail(null);
    setShowAnalysisPage(false);
    if (window.location.pathname !== '/') {
      window.history.replaceState({}, '', '/');
    }
  }, []);

  const handleBackFromAnalysisPage = useCallback(() => {
    // переход «назад» возвращает карточку школы на карте (popstate подхватит путь)
    if (/^\/school\/\d+\/analysis\/?$/.test(window.location.pathname)) {
      window.history.back();
    } else {
      setShowAnalysisPage(false);
    }
  }, []);

  const handleSearchSubmit = useCallback(() => {
    setSearchSubmitted(searchQuery);
    const params = buildParams(searchQuery, filterState, filtersApplied, preferenceState, preferencesActive);
    fetchSchools(params).then((count) => {
      setToast({ message: `Найдено школ: ${count} после использования фильтра`, type: 'info' });
    });
  }, [searchQuery, filterState, filtersApplied, preferenceState, preferencesActive, fetchSchools]);

  const handleSearchClear = useCallback(() => {
    setSearchQuery('');
    setSearchSubmitted('');
    const params = buildParams('', filterState, filtersApplied, preferenceState, preferencesActive);
    fetchSchools(params);
  }, [filterState, filtersApplied, preferenceState, preferencesActive, fetchSchools]);

  // Единая модалка: подбор («что вам важно») и фильтры применяются одним действием
  const handleModalApply = useCallback(
    (nextFilters, nextPrefs) => {
      if (!validateFilters(nextFilters, setToast)) return;
      const hasFilters = filtersActive(nextFilters);
      const anyPref = PREF_KEYS.some((k) => nextPrefs[k]);
      setFilterState(nextFilters);
      setFiltersApplied(hasFilters);
      setPreferenceState(nextPrefs);
      setPreferencesActive(anyPref);
      persistPreferences(nextPrefs, anyPref);
      localStorage.setItem(LS_MODAL_DISMISSED, '1');
      setShowFiltersModal(false);
      const params = buildParams(searchSubmitted || searchQuery, nextFilters, hasFilters, nextPrefs, anyPref);
      fetchSchools(params).then((count) => {
        setToast({ message: `Найдено школ: ${count} после использования фильтра`, type: 'info' });
      });
    },
    [searchSubmitted, searchQuery, fetchSchools]
  );

  // Снять один активный фильтр (чип в сайдбаре) и сразу обновить список
  const handleRemoveChip = useCallback(
    (kind) => {
      const nextFilters = {
        ...filterState,
        sports: { ...(filterState.sports || {}) },
      };
      let nextPrefs = preferenceState;
      if (kind === 'prefs') {
        nextPrefs = {
          ...preferenceState,
          olympiads: false,
          bullying: false,
          staff: false,
          building: false,
          exam: false,
          location: false,
        };
      } else if (kind === 'rating') {
        nextFilters.ratingMin = null;
        nextFilters.ratingMax = null;
      } else if (kind === 'yearMin') {
        nextFilters.yearMin = null;
      } else if (kind === 'yearMax') {
        nextFilters.yearMax = null;
      } else if (kind.startsWith('sport:')) {
        const key = kind.slice('sport:'.length);
        nextFilters.sports = { ...(filterState.sports || {}), [key]: false };
      }
      handleModalApply(nextFilters, nextPrefs);
    },
    [filterState, preferenceState, handleModalApply]
  );

  const handleFiltersClose = useCallback(() => {
    localStorage.setItem(LS_MODAL_DISMISSED, '1');
    setShowFiltersModal(false);
  }, []);

  const handleOpenFilters = useCallback(() => {
    setShowFiltersModal(true);
  }, []);

  const showSchoolDetail = selectedSchoolId != null;

  // Название вкладки: имя выбранной школы (иначе — общее)
  useEffect(() => {
    document.title = schoolTitle(schoolDetail);
    return () => {
      document.title = SITE_TITLE;
    };
  }, [schoolDetail]);

  if (showAnalysisPage && schoolDetail) {
    return (
      <div className="app app-analysis-page">
        <SchoolAnalysisPage
          school={schoolDetail}
          rank={rankOf(schoolDetail.school_id)}
          total={schools[0]?.city_total || rankedIds.length}
          maxima={maxima}
          onBack={handleBackFromAnalysisPage}
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

  const cardOpen = !!(schoolDetail || institutionToast);

  return (
    <div className={`app${cardOpen ? ' app-card-open' : ''}`}>
      <SidePanel
        schools={schools}
        totalCount={totalCount}
        selectedSchoolId={selectedSchoolId}
        onSelectSchool={handleSchoolClick}
        sortBy={sortBy}
        onSortChange={setSortBy}
        selectedGroup={selectedGroup}
        onGroupChange={handleGroupChange}
        selectedCity={selectedCity}
        onCityChange={handleCityChange}
        schoolOwnership={schoolOwnership}
        onOwnershipChange={setSchoolOwnership}
        groupInstitutions={groupInstitutions}
        onSelectInstitution={handleInstitutionClick}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSearchSubmit={handleSearchSubmit}
        onSearchClear={handleSearchClear}
        filterState={filterState}
        preferenceState={preferenceState}
        preferencesActive={preferencesActive}
        onOpenFilters={handleOpenFilters}
        onRemoveChip={handleRemoveChip}
        loading={loading}
        instLoading={institutionsLoading}
        instError={institutionsError}
        onInstRetry={() => setInstitutionsRetryNonce((n) => n + 1)}
        instQuery={institutionQuery}
        onInstQueryChange={setInstitutionQuery}
        selectedInstitutionId={selectedInstitutionId}
      />
      <main className="map-area">
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
              total={schools[0]?.city_total || rankedIds.length}
              maxima={maxima}
              onClose={handleCloseBottomCard}
              onOpenDetails={handleOpenAnalysisPage}
            />
          )}
          {selectedGroup !== 'schools' && institutionToast && (
            <InstitutionBottomCard
              institution={institutionToast}
              onClose={handleCloseInstitutionCard}
            />
          )}
        </>
      </main>
      <FiltersModal
        open={showFiltersModal}
        onClose={handleFiltersClose}
        onApply={handleModalApply}
        initialFilters={filterState}
        initialPrefs={preferenceState}
        loading={loading}
        onToast={setToast}
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

export default App;
