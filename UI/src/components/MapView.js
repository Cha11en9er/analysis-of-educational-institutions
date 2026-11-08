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
  const lastSchoolsKeyRef = useRef(null);
  const cameraAdjustedRef = useRef(false);
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

    // Зона прикрепления: точки домов при открытой карточке
    document.title = 'DBG sel=' + (selectedSchool ? selectedSchool.school_id : 'null') + ' catch=' + (selectedSchool?.catchment?.length ?? 'u') + ' sal=' + showAttachedLayer + ' ready=' + mapReady;
    if (showAttachedLayer) {
      const houseFeatures = (addressesForSelected || [])
        .filter((row) => row.lat != null && row.lon != null)
        .map((row, idx) => ({
          type: 'Feature',
          id: idx,
          geometry: { type: 'Point', coordinates: [row.lon, row.lat] },
          properties: { address: row.address || `${row.lat}, ${row.lon}` },
        }));

      const clustererMod = window.__ymaps3Clusterer;
      if (clustererMod && houseFeatures.length > 0) {
        const { YMapClusterer, methodGrid } = clustererMod;
        const clusterer = new YMapClusterer({
          method: methodGrid({ gridSize: 48 }),
          features: houseFeatures,
          marker: (feature) => {
            const dot = document.createElement('div');
            dot.className = 'house-marker-yandex';
            dot.title = feature.properties.address;
            return new YMapMarker(
              { coordinates: feature.geometry.coordinates, zIndex: 15 },
              dot
            );
          },
          cluster: (cluster) => {
            const el = document.createElement('div');
            el.className = 'house-cluster-yandex';
            el.textContent = String(cluster.features.length);
            return new YMapMarker({ coordinates: cluster.coordinates, zIndex: 14 }, el);
          },
        });
        map.addChild(clusterer);
        layers.houses.push(clusterer);
      } else if (houseFeatures.length > 0) {
        // fallback: модуль кластеризации не загрузился — рисуем как раньше
        houseFeatures.forEach((f) => {
          const dot = document.createElement('div');
          dot.className = 'house-marker-yandex';
          dot.title = f.properties.address;
          const house = new YMapMarker({ coordinates: f.geometry.coordinates, zIndex: 15 }, dot);
          map.addChild(house);
          layers.houses.push(house);
        });
      }
      document.title = 'DBG att=' + showAttachedLayer + ' feats=' + houseFeatures.length + ' clusMod=' + !!window.__ymaps3Clusterer;
    }

    // Учреждения выбранной группы (не-школы): маркеры цветов по kind
    if (institutionsGroup && Array.isArray(institutionsGroup.items)) {
      // один цвет на всю группу (садики голубые, вузы красные, иные зелёные)
      const GROUP_COLORS = {
        preschool: '#0ea5e9',
        vuz: '#dc2626',
        other: '#16a34a',
      };
      const groupColor = GROUP_COLORS[institutionsGroup.group] || '#64748b';
      const list = [];
      institutionsGroup.items.forEach((it) => {
        const c = it.location?.coordinates;
        if (!c) return;
        const [lon, lat] = c;
        const el = document.createElement('div');
        el.className = 'institution-marker-yandex';
        el.style.background = groupColor;
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

    // Подгонка вида: только при смене набора школ (не при закрытии карточки)
    const schoolsKey = validSchools.map((s2) => s2.school_id).join(',');
    if (lastSchoolsKeyRef.current !== schoolsKey) {
      lastSchoolsKeyRef.current = schoolsKey;
      cameraAdjustedRef.current = false; // новый набор разрешает одну подгонку
    }
    if (selectedSchool) {
      const coords = lonLatOfSchool(selectedSchool);
      if (coords) {
        // камера не «отдаляется»: центр на школу, текущий зум сохраняем
        // (поднимаем только если смотрели на весь город)
        const currentZoom = map.location?.zoom ?? viewRef.current.zoom ?? DEFAULT_ZOOM;
        const zoom = Math.max(currentZoom, 15);
        viewRef.current = { center: coords, zoom };
        map.setLocation({ center: coords, zoom, duration: 600 });
      }
    } else if (!cameraAdjustedRef.current && validSchools.length > 0) {
      const bounds = boundsFromLonLats(validSchools.map(lonLatOfSchool).filter(Boolean));
      if (bounds) {
        map.setLocation({ bounds, duration: 300 });
        cameraAdjustedRef.current = true;
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
