import { buffer, convex, distance } from '@turf/turf';

/**
 * Зона прикрепления школы: полигоны по внешним точкам домов.
 *
 * Точки домов разбиваются на группы: если между двумя домами больше
 * GAP_KM (большое расстояние — например, два разных микрорайона),
 * они рисуются РАЗНЫМИ фигурами, а не одним общим полигоном.
 * Каждая группа обрамляется буфером (буферная зона вокруг домов).
 *
 * @param {Array<{lat:number, lon:number}>} points точки домов (lat/lon)
 * @param {{gapKm?:number, bufferKm?:number}} opts
 * @returns {Array<{geometry: object, count: number, kind: string}>} полигоны в [lon,lat]
 */
export function buildCatchmentPolygons(points, opts = {}) {
  const gapKm = opts.gapKm ?? 0.2;
  const bufferKm = opts.bufferKm ?? 0.03;
  if (!points || points.length === 0) return [];

  const pts = points
    .filter((p) => p && p.lat != null && p.lon != null)
    .map((p) => ({ lon: +p.lon, lat: +p.lat }));
  if (pts.length === 0) return [];

  // 1) группировка: связные компоненты по расстоянию (сетка для скорости)
  const parent = pts.map((_, i) => i);
  const find = (i) => {
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]];
      i = parent[i];
    }
    return i;
  };
  const union = (a, b) => {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) parent[rb] = ra;
  };

  const CELL = 0.002; // ~150-220 м
  const grid = new Map();
  pts.forEach((p, i) => {
    const key = `${Math.floor(p.lon / CELL)}:${Math.floor(p.lat / CELL)}`;
    if (!grid.has(key)) grid.set(key, []);
    grid.get(key).push(i);
  });

  for (let i = 0; i < pts.length; i++) {
    const p = pts[i];
    const cx = Math.floor(p.lon / CELL);
    const cy = Math.floor(p.lat / CELL);
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        const bucket = grid.get(`${cx + dx}:${cy + dy}`);
        if (!bucket) continue;
        for (const j of bucket) {
          if (j <= i) continue;
          const d = distance(
            [p.lon, p.lat],
            [pts[j].lon, pts[j].lat],
            { units: 'kilometers' }
          );
          if (d <= gapKm) union(i, j);
        }
      }
    }
  }

  // 2) группируем по корню
  const groups = new Map();
  pts.forEach((_, i) => {
    const root = find(i);
    if (!groups.has(root)) groups.set(root, []);
    groups.get(root).push(pts[i]);
  });

  // 3) полигон для каждой группы: выпуклая оболочка + буфер
  const out = [];
  for (const group of groups.values()) {
    let geom;
    try {
      const coords = group.map((p) => [p.lon, p.lat]);
      geom = group.length >= 3 ? convex({ type: 'Feature', geometry: { type: 'MultiPoint', coordinates: coords } }) : null;
      if (!geom) {
        geom = {
          type: 'Feature',
          geometry: { type: 'MultiPoint', coordinates: coords },
        };
      }
      const buffered = buffer(geom, bufferKm, { units: 'kilometers' });
      const poly = buffered?.geometry;
      if (!poly) continue;
      out.push({ geometry: poly, count: group.length, kind: poly.type });
    } catch {
      // отдельную точку/линию обрабатываем консервативно
      const c = group.map((p) => [p.lon, p.lat]);
      if (c.length >= 2) {
        out.push({
          geometry: { type: 'LineString', coordinates: c },
          count: group.length,
          kind: 'LineString',
        });
      }
    }
  }

  // крупные группы первыми — чтобы их контур читался поверх остальных
  out.sort((a, b) => b.count - a.count);
  return out;
}
