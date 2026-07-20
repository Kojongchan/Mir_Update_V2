# dwg2gltf — DWG → 선형 지오메트리 (LibreDWG WASM, ODA 불필요)

폐쇄 포맷 DWG 를 **ODA/AutoCAD 없이** 읽는다 — `@mlightcad/libredwg-web`(LibreDWG WASM).
LINE·SPLINE·POLYLINE 등 **선형/곡선**을 실좌표 그대로 추출해, 뷰어가 xeokit
SceneModel(lines)로 지형과 **같은 씬**에 자동 정합해 얹는다.

## 검증 (실제 DWG `경사갱 솔리드.dwg`, AC2018)
- 엔티티: **LINE 3849, SPLINE 1512, 3DSOLID 15**
- 좌표: **중부원점 실좌표**(E 225018~225066, N 450831~450887, 표고 166~187m) — 지형과 동일 CRS
- 12,547 선분 추출 → 지형 위 실제 위치에 정합, **60fps·지터 없음** (`poc/dwg_demo.html`)

## 한계 (폐쇄 포맷 벽의 잔여)
- **3DSOLID 는 ACIS(satCache)** → 서피스 테셀레이션에 ODA/ACIS 커널 필요(미포함).
  선형(LINE/SPLINE/POLYLINE)만 추출. 토목 DWG 상당수(선형·등고·단면)는 선형이라 이걸로 커버.
- 3D 솔리드 형상까지 필요하면 → AutoCAD/Civil3D 에서 **IFC 또는 FBX export**(권장) 후
  `ifc2xkt`/`fbx2gltf` 경로, 또는 Phase 2 서버에 ODA/DDC 도입.

## 사용
```bash
npm install                       # @mlightcad/libredwg-web
node extract_dwg.mjs <in.dwg> <out.json>
```
출력 JSON: { origin(실좌표 RTC 중심), positions(origin 상대), indices(lines), entityCounts }.
뷰어는 SceneModel `createMesh({primitive:"lines", positions, indices, origin})` 로 로드.

## 좌표 규약
DWG(x=easting, y=northing, z=elev) → xeokit world Y-up (X=easting, Y=elev, Z=-northing).
지형과 동일 실좌표계면 re-center 없이 자동 정합.
