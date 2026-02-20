import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const SARATOV_CENTER = [51.532, 46.0];
const DEFAULT_ZOOM = 12;

const defaultIcon = L.icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

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

export default function MapView({ schools, selectedSchool, onSchoolClick }) {
  const validSchools =
    schools &&
    schools.filter(
      (s) => s.location?.coordinates && s.location.coordinates.length === 2
    );

  return (
    <div className="map-wrap">
      <MapContainer
        center={SARATOV_CENTER}
        zoom={DEFAULT_ZOOM}
        className="map-container"
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ZoomControl />
        {validSchools &&
          validSchools.map((s) => (
            <Marker
              key={s.school_id}
              position={[s.location.coordinates[1], s.location.coordinates[0]]}
              icon={defaultIcon}
              eventHandlers={{
                click: () => onSchoolClick && onSchoolClick(s),
              }}
            >
              <Tooltip permanent={false} direction="top" offset={[0, -41]}>
                <strong>{s.name_2gis || s.name_ym || `Школа ${s.school_id}`}</strong>
                <br />
                {s.school_address}
              </Tooltip>
            </Marker>
          ))}
        {validSchools && validSchools.length > 0 && !selectedSchool && (
          <FitBounds schools={validSchools} />
        )}
        {selectedSchool?.location?.coordinates?.length === 2 && (
          <FitSchool school={selectedSchool} />
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
