import React, { useEffect, useMemo, useRef, useState } from 'react';
import { featureBoundsLatLng } from '../utils/buildAddressCoverageGeoJSON';
import {
  getAttachedAddressesForKey,
  getSchoolAttachmentKey,
} from '../utils/schoolAttachment';
import { getSchoolMarkerStyle, schoolMarkerTitle } from '../utils/schoolMapMarkerIcon';
import { getYandexMapsApiKey, loadYmaps3 } from '../utils/loadYmaps3';

/** Яндекс: [lon, lat] */
const SARATOV_CENTER = [46.0, 51.532];
const DEFAULT_ZOOM = 12;

function lonLatOfSchool(school) {
  const c = school?.location?.coordinates;
  if (!c || c.length !== 2) return null;
  return [c[0], c[1]];
}

function boundsFromLonLats(points) {
  if (!points.length) return null;
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  for (const [lon, lat] of points) {
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
  }
  if (!Number.isFinite(minLon)) return null;
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}

export default function MapView({
  schools,
  selectedSchool,
  onSchoolClick,
  preferencesActive,
  institutionsGroup,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layersRef = useRef({ markers: [], features: [], houses: [], institutions: [] });
  const viewRef = useRef({ center: SARATOV_CENTER, zoom: DEFAULT_ZOOM });
  const onSchoolClickRef = useRef(onSchoolClick);
  const [mapError, setMapError] = useState(null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    onSchoolClickRef.current = onSchoolClick;
  }, [onSchoolClick]);

  const validSchools = useMemo(
    () =>
      (schools || []).filter(
        (s) => s.location?.coordinates && s.location.coordinates.length === 2
      ),
    [schools]
  );

  const markerScale = useMemo(() => {
    const active = Boolean(preferencesActive);
    if (!active || !validSchools.length) {
      return { prefsActive: false, scoreMin: null, scoreMax: null };
    }
    const scores = validSchools.map((s) => s.preference_score).filter((x) => x != null);
    if (scores.length === 0) {
      return { prefsActive: false, scoreMin: null, scoreMax: null };
    }
    return {
      prefsActive: true,
      scoreMin: Math.min(...scores),
      scoreMax: Math.max(...scores),
    };
  }, [validSchools, preferencesActive]);

  const attachmentKey = selectedSchool ? getSchoolAttachmentKey(selectedSchool) : null;
  // Приоритет: catchment из API (school_id) → фоллбек на локальный файл (пилот)
  const catchmentPoints = selectedSchool?.catchment;
  const addressesForSelected = useMemo(
    () =>
      catchmentPoints && catchmentPoints.length > 0
        ? catchmentPoints.map((p) => ({ lat: p.lat, lon: p.lon, address: p.address }))
        : attachmentKey
          ? getAttachedAddressesForKey(attachmentKey)
          : [],
    [catchmentPoints, attachmentKey]
  );

  const showAttachedLayer = Boolean(selectedSchool && addressesForSelected.length > 0);

  // Инициализация карты
  useEffect(() => {
    let cancelled = false;
    const el = containerRef.current;
    if (!el) return undefined;

    (async () => {
      try {
        const ymaps3 = await loadYmaps3(getYandexMapsApiKey());
        if (cancelled || !containerRef.current) return;

        const { YMap, YMapDefaultSchemeLayer, YMapDefaultFeaturesLayer } = ymaps3;

        const map = new YMap(containerRef.current, {
          location: { center: SARATOV_CENTER, zoom: DEFAULT_ZOOM },
          showScaleInCopyrights: true,
        });
        map.addChild(new YMapDefaultSchemeLayer({ theme: 'light' }));
        map.addChild(new YMapDefaultFeaturesLayer());

        mapRef.current = map;
        setMapReady(true);
        setMapError(null);
      } catch (err) {
        if (!cancelled) {
          setMapError(err.message || 'Ошибка загрузки Яндекс.Карт');
        }
      }
    })();

    return () => {
      cancelled = true;
      const map = mapRef.current;
      mapRef.current = null;
      setMapReady(false);
      if (map) {
        try {
          map.destroy();
        } catch {
          /* ignore */
        }
      }
    };
  }, []);

  // Маркеры школ + полигон домов + fit
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !window.ymaps3) return;

    const { YMapMarker, YMapFeature } = window.ymaps3;
    const layers = layersRef.current;

    const clearLayer = (list) => {
      list.forEach((child) => {
        try {
          map.removeChild(child);
        } catch {
          /* ignore */
        }
      });
      list.length = 0;
    };

    clearLayer(layers.markers);
    clearLayer(layers.features);
    clearLayer(layers.houses);
    clearLayer(layers.institutions);

    // Школы рисуем только в группе «schools»
    if (institutionsGroup?.group === 'schools' || !institutionsGroup) {
      validSchools.forEach((school) => {
        const coords = lonLatOfSchool(school);
        if (!coords) return;
        const { diameter, html } = getSchoolMarkerStyle(school, markerScale);
        const wrap = document.createElement('div');
        wrap.className = 'school-marker-yandex';
        wrap.style.width = `${diameter}px`;
        wrap.style.height = `${diameter}px`;
        wrap.style.cursor = 'pointer';
        wrap.title = schoolMarkerTitle(school);
        wrap.innerHTML = html;
        wrap.addEventListener('click', (e) => {
          e.stopPropagation();
          onSchoolClickRef.current?.(school);
        });

        const marker = new YMapMarker(
          {
            coordinates: coords,
            zIndex: selectedSchool?.school_id === school.school_id ? 20 : 10,
          },
          wrap
        );
        map.addChild(marker);
        layers.markers.push(marker);
      });
    }

    // Зона прикрепления: только точки домов (обводки/полигоны решим после полного
    // геокода всех адресов — см. .cursor/rules/geocoding.mdc)
    if (showAttachedLayer) {
      (addressesForSelected || []).forEach((row) => {
        if (row.lat == null || row.lon == null) return;
        const dot = document.createElement('div');
        dot.className = 'house-marker-yandex';
        dot.title = row.address || `${row.lat}, ${row.lon}`;
        const house = new YMapMarker({ coordinates: [row.lon, row.lat], zIndex: 15 }, dot);
        map.addChild(house);
        layers.houses.push(house);
      });
    }

    // Учреждения выбранной группы (не-школы): маркеры цветов по kind
    if (institutionsGroup && Array.isArray(institutionsGroup.items)) {
      const KIND_COLORS = {
        sport_do: '#16a34a',
        arts_do: '#a855f7',
        preschool: '#0ea5e9',
        internat_cadet: '#f59e0b',
        spo: '#64748b',
        vuz: '#dc2626',
        general: '#ea580c',
        other: '#64748b',
      };
      const list = [];
      institutionsGroup.items.forEach((it) => {
        const c = it.location?.coordinates;
        if (!c) return;
        const [lon, lat] = c;
        const el = document.createElement('div');
        el.className = 'institution-marker-yandex';
        el.style.background = KIND_COLORS[it.kind] || '#64748b';
        el.title = `${it.name}\n${it.address || ''}`;
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          window.__uchgradInstitutionClick?.(it);
        });
        const marker = new YMapMarker({ coordinates: [lon, lat], zIndex: 8 }, el);
        map.addChild(marker);
        list.push(marker);
      });
      layersRef.current.institutions = list;
    }

    // Подгонка вида
    if (showAttachedLayer) {
      const pts = [];
      const sc = lonLatOfSchool(selectedSchool);
      if (sc) pts.push(sc);
      (addressesForSelected || []).forEach((a) => {
        if (a.lat != null && a.lon != null) pts.push([a.lon, a.lat]);
      });
      // границы по самим точкам домов
      if (pts.length > 1) {
        const lats = pts.map((p) => p[1]);
        const lons = pts.map((p) => p[0]);
        pts.push([Math.min(lats), Math.min(lons)], [Math.max(lats), Math.max(lons)]);
      }
      const bounds = boundsFromLonLats(pts);
      if (bounds) {
        map.setLocation({ bounds, duration: 300 });
        viewRef.current = { ...viewRef.current, zoom: 16 };
      }
    } else if (selectedSchool) {
      const coords = lonLatOfSchool(selectedSchool);
      if (coords) {
        viewRef.current = { center: coords, zoom: 16 };
        map.setLocation({ center: coords, zoom: 16, duration: 800 });
      }
    } else if (validSchools.length > 0 && validSchools.length <= 80) {
      const bounds = boundsFromLonLats(validSchools.map(lonLatOfSchool).filter(Boolean));
      if (bounds) {
        map.setLocation({ bounds, duration: 300 });
      }
    }
  }, [
    mapReady,
    validSchools,
    markerScale,
    selectedSchool,
    showAttachedLayer,
    addressesForSelected,
    institutionsGroup,
  ]);

  const zoomBy = (delta) => {
    const map = mapRef.current;
    if (!map) return;
    const nextZoom = Math.max(1, Math.min(21, (viewRef.current.zoom ?? DEFAULT_ZOOM) + delta));
    viewRef.current = { ...viewRef.current, zoom: nextZoom };
    map.setLocation({
      center: viewRef.current.center || SARATOV_CENTER,
      zoom: nextZoom,
      duration: 150,
    });
  };

  return (
    <div className="map-wrap">
      {mapError && (
        <div className="map-error-banner">
          Карта: {mapError}. Нужен YANDEX_API_KEY в /opt/uchgrad/.env и Referrer
          https://uchgrad.ru/* в кабинете Яндекса.
        </div>
      )}
      <div className="ymap-zoom">
        <button type="button" className="ymap-zoom-btn" onClick={() => zoomBy(1)} title="Увеличить">
          +
        </button>
        <button type="button" className="ymap-zoom-btn" onClick={() => zoomBy(-1)} title="Уменьшить">
          −
        </button>
      </div>
      <div ref={containerRef} className="map-container" />
    </div>
  );
}
