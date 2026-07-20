# ifc2xkt — IFC → XKT 변환 (서버 배치)

xeokit `convert2xkt` 로 IFC(구조물)를 XKT 로 사전변환. **런타임 IFC 파싱 금지**
(That Open 실패 원인 #1, §6.3) — 프로젝트 생성 시 배치로 굽고 브라우저는 XKT 스트리밍만.

## 사용
```bash
bash ingest/ifc2xkt/convert.sh structure.ifc structure.xkt
```

## Phase 1에서 검증된 것 (R2)
- `convert2xkt` (glTF/IFC → XKT) 이 환경에서 동작 ✓
- 생성된 XKT 가 xeokit `XKTLoaderPlugin` 으로 로드 ✓
- 구조물을 **실좌표 그대로** 지형과 **같은 xeokit 씬**에 얹으면 자동 정합 + 지터 없음 ✓
  (`poc/phase1.html` — 더블프리시전 SceneModel/XKT origin. R2 (a)안 성립.)

## 좌표 규약 (중요 — 지형과 정합의 핵심)
- 구조물 IFC 정점이 지형과 **동일 CRS·실좌표**(중부원점 EPSG 5186 등)여야
  re-center 없이 자동 정합된다. Revit 좌표계는 자동판별 금지 → 프로젝트당 1회 지정(§5.4).
- xeokit world Y-up: X=easting, Y=표고, Z=-northing. (glTF 지형과 동일 규약)

## 다음 (실제 구조물 IFC 필요)
현재 phase1.html 은 R2 메커니즘 검증용 **합성 구조물**(박스). 실제 자동 정합 확정에는
**본 프로젝트 구조물의 IFC**(Revit→IFC, 지형과 같은 실좌표) 1개가 필요:
1. `/data` (Git LFS)에 업로드
2. `convert.sh` 로 XKT 변환
3. phase1 뷰어에 얹어 지형과 자동 정합 확인 (R4: Revit→IFC 품질/ GUID 안정성도 점검)
