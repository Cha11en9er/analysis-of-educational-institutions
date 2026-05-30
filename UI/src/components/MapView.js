import React, { useEffect, useMemo, useRef } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Tooltip,
  GeoJSON,
  CircleMarker,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  ADDRESS_CLUSTER_LINK_METERS,
  buildAddressCoverageFeature,
  featureBoundsLatLng,
} from '../utils/buildAddressCoverageGeoJSON';
import {
  getAttachedAddressesForKey,
  getSchoolAttachmentKey,
  schoolHasAttachedHouseData,
} from '../utils/schoolAttachment';
import { createSchoolMapIcon, tooltipOffsetForMarker } from '../utils/schoolMapMarkerIcon';

const SARATOV_CENTER = [51.532, 46.0];
const DEFAULT_ZOOM = 12;

function FitBounds({ schools, maxCount = 80 }) {
  const map = useMap();
  useEffect(() => {
    if (!schools || schools.length === 0 || schools.length > maxCount) return;
    const valid = schools.filter(
      (s) => s.location?.coordinates && s.location.coordinates.length === 2
    );
    if (valid.length === 0) return;
    const bounds = L.latLngBounds(
      valid.map((s) => [s.location.coordinates[1], s.location.coordinates[0]])
    );
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
  }, [map, schools, maxCount]);
  return null;
}

function FitSchool({ school }) {
  const map = useMap();
  useEffect(() => {
    if (!school?.location?.coordinates || school.location.coordinates.length !== 2) return;
    const [lon, lat] = school.location.coordinates;
    map.setView([lat, lon], 16);
  }, [map, school]);
  return null;
}

/** Подгонка: школа + точки домов + полигон */
function FitAttachedAddressesBounds({ school, addresses, coverageFeature }) {
  const map = useMap();
  useEffect(() => {
    if (!school || !schoolHasAttachedHouseData(school)) return;
    const latLngs = [];

    if (school.location?.coordinates?.length === 2) {
      const [lon, lat] = school.location.coordinates;
      latLngs.push([lat, lon]);
    }
    (addresses || []).forEach((a) => {
      if (a.lat != null && a.lon != null) latLngs.push([a.lat, a.lon]);
    });
    const bb = featureBoundsLatLng(coverageFeature);
    if (bb) {
      latLngs.push(bb[0], bb[1]);
    }

    if (latLngs.length === 0) return;
    const bounds = L.latLngBounds(latLngs);
    map.fitBounds(bounds, { padding: [48, 48], maxZoom: 17 });
  }, [map, school, addresses, coverageFeature]);
  return null;
}

export default function MapView({ schools, selectedSchool, onSchoolClick, preferencesActive }) {
  const validSchools =
    schools &&
    schools.filter(
      (s) => s.location?.coordinates && s.location.coordinates.length === 2
    );

  const markerScale = useMemo(() => {
    const active = Boolean(preferencesActive);
    if (!active || !validSchools?.length) return { prefsActive: false, scoreMin: null, scoreMax: null };
    const scores = validSchools.map((s) => s.preference_score).filter((x) => x != null);
    if (scores.length === 0) return { prefsActive: false, scoreMin: null, scoreMax: null };
    return {
      prefsActive: true,
      scoreMin: Math.min(...scores),
      scoreMax: Math.max(...scores),
    };
  }, [validSchools, preferencesActive]);

  const attachmentKey = selectedSchool ? getSchoolAttachmentKey(selectedSchool) : null;
  const addressesForSelected = useMemo(
    () => (attachmentKey ? getAttachedAddressesForKey(attachmentKey) : []),
    [attachmentKey]
  );

  const showAttachedLayer = Boolean(
    selectedSchool && attachmentKey && addressesForSelected.length > 0
  );

  const addressCoverageFeature = useMemo(
    () => buildAddressCoverageFeature(addressesForSelected),
    [addressesForSelected]
  );

  return (
    <div className="map-wrap">
      <MapContainer
        center={SARATOV_CENTER}
        zoom={DEFAULT_ZOOM}
        className="map-container"
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ZoomControl />
        {validSchools &&
          validSchools.map((s) => {
            const icon = createSchoolMapIcon(s, markerScale);
            const tipOff = tooltipOffsetForMarker(s, markerScale);
            return (
              <Marker
                key={s.school_id}
                position={[s.location.coordinates[1], s.location.coordinates[0]]}
                icon={icon}
                eventHandlers={{
                  click: () => onSchoolClick && onSchoolClick(s),
                }}
              >
                <Tooltip permanent={false} direction="top" offset={tipOff}>
                  <strong>{s.name_2gis || s.name_ym || `Школа ${s.school_id}`}</strong>
                  <br />
                  {s.school_address}
                  {s.preference_score != null && (
                    <>
                      <br />
                      <span style={{ color: '#0d6efd' }}>Совпадение: {s.preference_score}%</span>
                    </>
                  )}
                  <br />
                  <span style={{ fontSize: '0.85em', color: '#6c757d' }}>
                    {s.has_review_analysis
                      ? 'Малиновая точка: есть финальные отзывы (rd_3_stage), как в графиках. '
                      : 'Синяя точка: нет файла school_review_separately_*_final.json в rd_3_stage. '}
                    {schoolHasAttachedHouseData(s)
                      ? 'Полоски внутри — прикреплённые адреса домов.'
                      : ''}
                  </span>
                </Tooltip>
              </Marker>
            );
          })}
        {validSchools && validSchools.length > 0 && !selectedSchool && (
          <FitBounds schools={validSchools} />
        )}
        {selectedSchool?.location?.coordinates?.length === 2 && (
          <FitSchool school={selectedSchool} />
        )}
        {showAttachedLayer && (
          <>
            <FitAttachedAddressesBounds
              school={selectedSchool}
              addresses={addressesForSelected}
              coverageFeature={addressCoverageFeature}
            />
            {addressCoverageFeature && (
              <GeoJSON
                key={`address-coverage-${attachmentKey}`}
                data={addressCoverageFeature}
                style={{
                  color: '#2563eb',
                  weight: 2,
                  fillColor: '#3b82f6',
                  fillOpacity: 0.18,
                }}
                onEachFeature={(_feature, layer) => {
                  layer.bindTooltip(
                    `Полигон: кластеры ≤ ${ADDRESS_CLUSTER_LINK_METERS} м, затем вогнутая или выпуклая оболочка ` +
                      '(острые углы; внутренние точки не являются вершинами).',
                    { sticky: true, direction: 'top' }
                  );
                }}
              />
            )}
            {(addressesForSelected || []).map((row, idx) =>
              row.lat != null && row.lon != null ? (
                <CircleMarker
                  key={`debug-addr-${attachmentKey}-${idx}-${row.address || idx}`}
                  center={[row.lat, row.lon]}
                  radius={5}
                  pathOptions={{
                    color: '#9a3412',
                    weight: 2,
                    fillColor: '#f97316',
                    fillOpacity: 0.9,
                  }}
                >
                  <Tooltip direction="top" offset={[0, -4]}>
                    <span style={{ whiteSpace: 'pre-wrap', maxWidth: 240, display: 'block' }}>
                      [отладка] {row.address || `${row.lat}, ${row.lon}`}
                    </span>
                  </Tooltip>
                </CircleMarker>
              ) : null
            )}
          </>
        )}
      </MapContainer>
    </div>
  );
}

function ZoomControl() {
  const map = useMap();
  const ref = useRef(null);

  useEffect(() => {
    if (!map || !ref.current) return;
    const Control = L.Control.extend({
      onAdd: function () {
        const div = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
        const zoomIn = L.DomUtil.create('a', 'zoom-in', div);
        zoomIn.innerHTML = '+';
        zoomIn.href = '#';
        zoomIn.title = 'Увеличить';
        const zoomOut = L.DomUtil.create('a', 'zoom-out', div);
        zoomOut.innerHTML = '−';
        zoomOut.href = '#';
        zoomOut.title = 'Уменьшить';
        L.DomEvent.on(zoomIn, 'click', L.DomEvent.stopPropagation)
          .on(zoomIn, 'click', L.DomEvent.preventDefault)
          .on(zoomIn, 'click', () => map.zoomIn());
        L.DomEvent.on(zoomOut, 'click', L.DomEvent.stopPropagation)
          .on(zoomOut, 'click', L.DomEvent.preventDefault)
          .on(zoomOut, 'click', () => map.zoomOut());
        return div;
      },
    });
    const control = new Control({ position: 'bottomright' });
    control.addTo(map);
    return () => {
      control.remove();
    };
  }, [map]);

  return <div ref={ref} />;
}
