import React, { useRef, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const SARATOV_CENTER = [51.532, 46.0];
const DEFAULT_ZOOM = 12;

// Иконка маркера по умолчанию (Leaflet теряет путь в бандле)
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

export default function MapView({ schools }) {
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
        <ZoomControls />
        {validSchools &&
          validSchools.map((s) => (
            <Marker
              key={s.school_id}
              position={[s.location.coordinates[1], s.location.coordinates[0]]}
              icon={defaultIcon}
            >
              <Popup>
                <strong>{s.name_2gis || s.name_ym || `Школа ${s.school_id}`}</strong>
                <br />
                {s.school_address}
                {s.rating_yandex != null && (
                  <>
                    <br />
                    Рейтинг: {s.rating_yandex}
                  </>
                )}
              </Popup>
            </Marker>
          ))}
        {validSchools && validSchools.length > 0 && <FitBounds schools={validSchools} />}
      </MapContainer>
    </div>
  );
}

function ZoomControls() {
  const map = useMap();
  return (
    <div className="leaflet-bottom leaflet-right zoom-controls-custom">
      <button
        type="button"
        className="zoom-btn"
        onClick={() => map.zoomIn()}
        aria-label="Увеличить"
      >
        +
      </button>
      <button
        type="button"
        className="zoom-btn"
        onClick={() => map.zoomOut()}
        aria-label="Уменьшить"
      >
        −
      </button>
    </div>
  );
}
