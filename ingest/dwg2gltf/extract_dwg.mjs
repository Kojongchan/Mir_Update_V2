/**
 * DWG → 선형 지오메트리 추출 (LibreDWG WASM, ODA 불필요).
 *
 * 폐쇄 포맷 DWG 를 ODA 없이 브라우저/Node 에서 읽는다(@mlightcad/libredwg-web).
 * LINE·SPLINE·(LW)POLYLINE 등 선형/곡선 지오메트리를 실좌표 그대로 추출해
 * 뷰어가 SceneModel(lines) 로 지형과 같은 씬에 얹을 수 있는 JSON 을 만든다.
 *
 * 한계: 3DSOLID 는 ACIS(satCache) → 테셀레이션에 ODA/ACIS 커널 필요(별도).
 *       토목 DWG 의 상당수(선형·등고·단면·와이어프레임)는 선형이라 이걸로 커버.
 *
 * 좌표: DWG(x=easting, y=northing, z=elev) → xeokit world Y-up (X=easting, Y=elev, Z=-northing).
 *
 * 사용: node extract_dwg.mjs <in.dwg> <out.json>
 */
import { LibreDwg } from '@mlightcad/libredwg-web';
import { readFileSync, writeFileSync } from 'fs';

const [inPath, outPath] = process.argv.slice(2);
if (!inPath || !outPath) { console.error('usage: node extract_dwg.mjs <in.dwg> <out.json>'); process.exit(2); }

const buf = readFileSync(inPath);
const dwg = await LibreDwg.create();
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const db = dwg.convert(dwg.dwg_read_data(ab, 0));
const ents = db.entities || [];

// 실좌표 세그먼트 수집 (원점부근 노이즈 제외)
const REAL = 1000;
const isReal = p => p && Math.abs(p.x) > REAL && Math.abs(p.y) > REAL;
const segs = []; // [[p0,p1], ...]  p={x,y,z}
const typeCount = {};
for (const e of ents) {
  typeCount[e.type] = (typeCount[e.type] || 0) + 1;
  if (e.type === 'LINE') {
    const a = e.startPoint, b = e.endPoint;
    if (isReal(a) && isReal(b)) segs.push([a, b]);
  } else if (e.type === 'SPLINE') {
    const pts = (e.fitPoints && e.fitPoints.length ? e.fitPoints : e.controlPoints) || [];
    for (let i = 0; i + 1 < pts.length; i++)
      if (isReal(pts[i]) && isReal(pts[i + 1])) segs.push([pts[i], pts[i + 1]]);
  } else if (e.type === 'LWPOLYLINE' || e.type === 'POLYLINE') {
    const pts = e.vertices || e.points || [];
    for (let i = 0; i + 1 < pts.length; i++) {
      const a = pts[i], b = pts[i + 1];
      if (isReal(a) && isReal(b)) segs.push([a, b]);
    }
  }
}

if (!segs.length) { console.error('추출된 실좌표 선형 세그먼트 없음'); process.exit(1); }

// bbox / origin (RTC 더블프리시전 중심)
let mnE = 1e18, mxE = -1e18, mnN = 1e18, mxN = -1e18, mnZ = 1e18, mxZ = -1e18;
for (const [a, b] of segs) for (const p of [a, b]) {
  mnE = Math.min(mnE, p.x); mxE = Math.max(mxE, p.x);
  mnN = Math.min(mnN, p.y); mxN = Math.max(mxN, p.y);
  const z = p.z || 0; mnZ = Math.min(mnZ, z); mxZ = Math.max(mxZ, z);
}
const cE = (mnE + mxE) / 2, cN = (mnN + mxN) / 2, cZ = (mnZ + mxZ) / 2;
const origin = [cE, cZ, -cN]; // xeokit world Y-up 기준 RTC 중심

// 포지션(원점 상대) + 라인 인덱스
const positions = [], indices = [];
let vi = 0;
for (const [a, b] of segs) {
  positions.push(a.x - cE, (a.z || 0) - cZ, -a.y + cN);
  positions.push(b.x - cE, (b.z || 0) - cZ, -b.y + cN);
  indices.push(vi, vi + 1); vi += 2;
}

const out = {
  source: inPath,
  crsNote: 'DWG x=easting,y=northing,z=elev → xeokit world X=easting,Y=elev,Z=-northing',
  entityCounts: typeCount,
  bbox_real: { E: [mnE, mxE], N: [mnN, mxN], Z: [mnZ, mxZ] },
  origin,               // 실좌표 RTC 중심 (지형과 같은 좌표계 → 자동 정합)
  primitive: 'lines',
  positions,            // origin 상대 (더블프리시전 origin 으로 복원)
  indices,
  note3dsolid: `3DSOLID ${typeCount['3DSOLID'] || 0}개는 ACIS(satCache) — 테셀레이션 ODA 필요(미포함)`,
};
writeFileSync(outPath, JSON.stringify(out));
console.log(`wrote ${outPath}`);
console.log(`  entities:`, JSON.stringify(typeCount));
console.log(`  segments: ${segs.length}, origin(E,elev,-N): [${origin.map(v=>v.toFixed(1))}]`);
console.log(`  real bbox: E ${mnE.toFixed(0)}..${mxE.toFixed(0)}  N ${mnN.toFixed(0)}..${mxN.toFixed(0)}  Z ${mnZ.toFixed(1)}..${mxZ.toFixed(1)}`);
