import {
  bearing,
  bbox,
  clustersDbscan,
  concave,
  convex,
  destination,
  featureCollection,
  point,
  polygon,
  union,
} from '@turf/turf';

/**
 * Максимум метров между соседними точками одного контура (DBSCAN).
 * Кластеры дальше друг от друга остаются раздельными полигонами (разрыв на карте).
 */
export const ADDRESS_CLUSTER_LINK_METERS = 200;

/**
 * Половина «толщины» четырёхугольника вдоль отрезка между двумя точками кластера, м.
 */
const SEGMENT_STRIP_HALF_WIDTH_M = 22;

/** Смещение от одиночной точки по сторонам света до вершины ромба, м. */
const LONE_POINT_CARDINAL_OFFSET_M = 22;

/**
 * Острый четырёхугольник вдоль отрезка AB.
 */
function sharpRectangleAlongSegment(lon1, lat1, lon2, lat2, halfWidthM) {
  const pA = point([lon1, lat1]);
  const pB = point([lon2, lat2]);
  const brg = bearing(pA, pB);
  const leftBearing = brg + 90;
  const rightBearing = brg - 90;
  const aL = destination(pA, halfWidthM, leftBearing, { units: 'meters' });
  const aR = destination(pA, halfWidthM, rightBearing, { units: 'meters' });
  const bL = destination(pB, halfWidthM, leftBearing, { units: 'meters' });
  const bR = destination(pB, halfWidthM, rightBearing, { units: 'meters' });
  const ring = [
    aL.geometry.coordinates,
    aR.geometry.coordinates,
    bR.geometry.coordinates,
    bL.geometry.coordinates,
    aL.geometry.coordinates,
  ];
  return polygon([ring]);
}

/** Малый квадрат с острыми углами вокруг одной точки (шум DBSCAN). */
function sharpSquareAround(lon, lat) {
  const c = point([lon, lat]);
  const d = LONE_POINT_CARDINAL_OFFSET_M;
  const corners = [0, 90, 180, 270].map((b) =>
    destination(c, d, b, { units: 'meters' }).geometry.coordinates
  );
  corners.push(corners[0]);
  return polygon([corners]);
}

/**
 * Полигон по кластеру точек: вогнутая оболочка с maxEdge = лимит связи (острые углы,
 * следует по «цепочке» адресов), иначе выпуклая. Точки строго внутри выпуклой оболочки
 * не входят в список вершин (см. monotone chain в @turf/convex).
 */
function hullForPointCluster(pointFeatures) {
  const n = pointFeatures.length;
  if (n === 0) return null;
  if (n === 1) {
    const [lon, lat] = pointFeatures[0].geometry.coordinates;
    return sharpSquareAround(lon, lat);
  }
  if (n === 2) {
    const [lon1, lat1] = pointFeatures[0].geometry.coordinates;
    const [lon2, lat2] = pointFeatures[1].geometry.coordinates;
    return sharpRectangleAlongSegment(lon1, lat1, lon2, lat2, SEGMENT_STRIP_HALF_WIDTH_M);
  }

  const fc = featureCollection(pointFeatures);
  let h = concave(fc, { maxEdge: ADDRESS_CLUSTER_LINK_METERS, units: 'meters' });
  if (!h) {
    h = convex(fc);
  }
  return h;
}

/**
 * Группирует точки после DBSCAN: шум — по одной фиче в группе.
 * @param {import('geojson').FeatureCollection<import('geojson').Point>} clustered
 * @returns {import('geojson').Feature<import('geojson').Point>[][]}
 */
function clusterGroups(clustered) {
  /** @type {Map<number, import('geojson').Feature<import('geojson').Point>[]>} */
  const dense = new Map();
  /** @type {import('geojson').Feature<import('geojson').Point>[][]} */
  const out = [];

  clustered.features.forEach((f) => {
    const id = f.properties?.cluster;
    if (typeof id === 'number' && id >= 0) {
      if (!dense.has(id)) dense.set(id, []);
      dense.get(id).push(f);
    } else {
      out.push([f]);
    }
  });

  dense.forEach((pts) => out.push(pts));
  return out;
}

/**
 * Острые полигоны по адресам: кластеры по расстоянию, затем concave/convex hull.
 * Внутренние точки не становятся вершинами оболочки.
 * @param {Array<{ lat?: number, lon?: number }>} addresses
 * @returns {import('geojson').Feature<import('geojson').Polygon|import('geojson').MultiPolygon>|null}
 */
export function buildAddressCoverageFeature(addresses) {
  const pts = [];
  for (const row of addresses || []) {
    const { lat, lon } = row;
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    pts.push(point([lon, lat]));
  }
  if (pts.length === 0) return null;

  const fc = featureCollection(pts);
  const clustered = clustersDbscan(fc, ADDRESS_CLUSTER_LINK_METERS, {
    units: 'meters',
    minPoints: 2,
  });

  const groups = clusterGroups(clustered);
  const hulls = [];
  for (const g of groups) {
    const h = hullForPointCluster(g);
    if (h) hulls.push(h);
  }
  if (hulls.length === 0) return null;
  if (hulls.length === 1) return hulls[0];
  return union(featureCollection(hulls));
}

/**
 * Bounding box GeoJSON-фичи в формате [[south, west], [north, east]] для Leaflet.
 * @param {import('geojson').Feature<import('geojson').Polygon|import('geojson').MultiPolygon>} feature
 * @returns {[[number, number], [number, number]]|null}
 */
export function featureBoundsLatLng(feature) {
  if (!feature) return null;
  const b = bbox(feature);
  return [
    [b[1], b[0]],
    [b[3], b[2]],
  ];
}
