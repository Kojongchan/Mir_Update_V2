# MIR_SMART v1 통합 가이드 — "3D뷰(신규 테스트)" 메뉴

> 목적: 지금까지 이 레포(mir_update_v2)에서 검증한 **자체 3D 뷰어**를 v1에 붙여,
> v1의 **자료관리 / ACC / APS 연결을 그대로 쓰면서** 새 뷰어로 여는 것을 테스트한다.
> 방식: v1에 **"3D뷰(신규 테스트)" 메뉴**를 추가하고, 우리 뷰어를 **iframe 임베드**.

---

## 0. 지금까지 검증된 것 (한 줄 요약)

| 항목 | 상태 | 근거 |
|---|---|---|
| 60만대 실좌표 지형 60fps·지터 없음 (R1) | ✅ | xeokit 더블프리시전, re-center 없음 |
| 오쏘 드래이핑 (InfraWorks V-flip 버그 수정) | ✅ | `poc/fix_gltf_uv.py`, Navisworks 일치 |
| 구조물 실좌표 자동 정합 (한 씬, R2) | ✅ | `poc/phase1.html` (SceneModel origin) |
| IFC → XKT 변환 | ✅ | `ingest/ifc2xkt` (convert2xkt) |
| DWG → 선형 (ODA 없이) | ✅ | `ingest/dwg2gltf` (LibreDWG WASM), 경사갱 |
| 대용량 업로드 (Supabase) | ✅ 스캐폴딩 | `ingest/storage`, 키 대기 |
| ACC/APS → glTF (Autodesk 뷰어 교체) | ✅ 스캐폴딩 | `integration/aps` (svf-utils), 크리덴셜 대기 |
| **임베드 뷰어 (iframe + postMessage)** | ✅ | `poc/embed.html` |

배포: 이 레포는 Vercel 로 자동 배포됨 → 뷰어 URL = `https://<your>.vercel.app/embed.html`

---

## 1. v1에 "3D뷰(신규 테스트)" 메뉴 추가 (핵심, iframe)

우리 뷰어는 **정적 웹페이지(`embed.html`)** 라 v1 프레임워크(React/Vue/Django 등) 상관없이
**iframe 하나로** 박으면 된다. v1 코드는 거의 안 건드린다.

### 1-1. 가장 빠른 확인 (데모 렌더)
새 메뉴/페이지에 iframe 하나:
```html
<iframe
  src="https://<your>.vercel.app/embed.html?demo=1"
  style="width:100%;height:100%;border:0"
  allow="fullscreen">
</iframe>
```
→ 열면 **지형 + 경사갱 DWG** 가 뜬다. 이게 뜨면 "v1 안에서 우리 뷰어가 돈다" 는 확인 끝.

### 1-2. React 예시
```jsx
function ThreeDTestView() {
  const VIEWER = "https://<your>.vercel.app/embed.html";
  return (
    <iframe src={`${VIEWER}?demo=1`} title="MIR 3D"
      style={{ width: "100%", height: "100%", border: 0 }} allow="fullscreen" />
  );
}
```
v1 라우팅/메뉴에 `ThreeDTestView` 를 "3D뷰(신규 테스트)" 로 등록.

---

## 2. v1 ↔ 뷰어 통신 (postMessage 계약)

정적 데모를 넘어 **원하는 모델을 로드**하고 **클릭 이벤트를 받으려면** postMessage 를 쓴다.

### 2-1. 부모(v1) → 뷰어(iframe): 모델 로드
```js
const iframe = document.getElementById("mir3d");           // <iframe id="mir3d" src=".../embed.html">
iframe.contentWindow.postMessage({
  type: "load",
  assets: [
    { kind: "terrain", url: "<지형 glTF URL>" },           // InfraWorks 지형
    { kind: "xkt",     url: "<구조물 XKT URL>" },           // IFC→XKT
    { kind: "gltf",    url: "<APS SVF→glTF URL>" },         // ACC 모델(APS 변환)
    { kind: "lines",   url: "<DWG 선형 JSON URL>" },        // DWG 선형
  ],
}, "*");
// 그 외: {type:"clear"}  전부 제거 / {type:"flyToAll"}  전체 보기
```
URL 은 Supabase `derived` 서명 URL 또는 아무 https 접근 가능 주소.

### 2-2. 뷰어(iframe) → 부모(v1): 이벤트
```js
window.addEventListener("message", (e) => {
  const m = e.data || {};
  if (m.type === "viewerReady") { /* iframe 준비됨 → 이때 load 보내기 */ }
  if (m.type === "loaded")      { /* {kind,url} 로드 완료 */ }
  if (m.type === "pick")        { /* m.objectId 클릭됨 → MIR_SMART DB 조인/패널 */ }
});
```
> **MIR_SMART 연동 지점:** `pick` 의 `objectId`(= 오브젝트 GUID/ID)로 v1 DB(Supabase)에서
> 물량/진도/RFI 를 조회해 패널에 띄우면 트윈 b형 완성.

### 2-3. 파라미터 로드 (postMessage 대신 URL 로도 가능)
```
embed.html?terrain=<glbUrl>&xkt=<url>&xkt=<url>&lines=<url>
embed.html?gltf=<apsGltfUrl>
```

---

## 3. ACC 파일을 우리 뷰어로 여는 흐름 (다음 단계, APS)

지금은 APS 실연결을 미뤘지만, v1 이 이미 APS 를 하므로 붙이는 지점만 정리:

```
[v1 자료관리 탭] 파일 열기 → v1 이 이미 아는 모델 URN
      │
      ▼  (백엔드) integration/aps/convert_urn.mjs
   APS 파생(SVF/SVF2) → svf-utils → glTF   (rvt/dwg/ifc 다 됨 — 오토데스크가 변환)
      │  Supabase derived 에 캐시
      ▼
iframe.postMessage({type:"load", assets:[{kind:"gltf", url:<변환 glTF>}]})
```
- 필요: `APS_CLIENT_ID` / `APS_CLIENT_SECRET` (v1 앱 것 재사용, env).
- ⚠️ **좌표:** APS glTF 가 실좌표(공유좌표)로 나오는지 확인 — 지형과 자동 정합의 관건(R4).
  오프셋 있으면 뷰어에 `origin` 보정 파라미터 추가 예정.
- 상세: `integration/aps/README.md`.

---

## 4. 인제스트 파이프라인 (파일 → 뷰어 에셋)

`ingest/` — 원본을 뷰어용 작은 에셋으로 변환. 뷰어는 GB 원본을 절대 안 받고 XKT/glTF 만 로드.

| 입력 | 변환 | 산출 (뷰어 로드) | 코드 |
|---|---|---|---|
| FBX(지형) | FBX2glTF → **V-flip+CLAMP** | terrain.glb | `ingest/fbx2gltf` + `poc/fix_gltf_uv.py` |
| IFC(구조물) | convert2xkt | {name}.xkt | `ingest/ifc2xkt` |
| DWG(선형) | LibreDWG WASM | {name}.lines.json | `ingest/dwg2gltf` |
| .pos | pos_parser | {name}.crs.json (EPSG) | `ingest/pos_parser` |
| ACC(rvt/dwg/ifc) | APS SVF→glTF | {name}.gltf | `integration/aps` |
| 저장/캐시 | Supabase raw/derived | 서명 URL | `ingest/storage` |

실행: `python ingest/pipeline.py <project> <raw_path>` (env: SUPABASE_URL/KEY).

---

## 5. 핵심 기술 노트 / 함정 (반드시 인지)

1. **V-flip (오쏘 필수):** InfraWorks FBX 는 UV V=0 아래(OpenGL), glTF 는 위. FBX2glTF/assimp
   가 V-flip 을 안 함 → 오쏘 어긋남/지형지물 누락. `fix_gltf_uv.py` 로 V 뒤집기 필수.
2. **실좌표 규약:** xeokit world Y-up → **X=easting, Y=표고, Z=-northing**. 모든 모델이
   동일 실좌표(EPSG 5186 등)면 re-center 없이 자동 정합. 큰 좌표는 SceneModel/XKT `origin`(RTC).
3. **DWG lines = VBO:** SceneModel `primitive:"lines"` 는 dtx 모드 미지원 → `dtxEnabled:false`.
   (지형도 VBO 로 60fps 유지됨.)
4. **DWG 3DSOLID:** ACIS(satCache) → 면 테셀레이션엔 ODA 필요. 선형만 추출됨. 솔리드까지
   필요하면 AutoCAD 에서 IFC/FBX export 또는 APS 경로.
5. **런타임 파싱 금지:** IFC 등은 서버 사전변환(XKT). 브라우저는 스트리밍만.
6. **좌표 재투영(5186↔WGS84):** 지도 모드(Cesium)에서만. BIM 모드는 평면 TM 그대로.

---

## 6. 레포 파일 인벤토리

```
PROJECT_BRIEF.md          단일 진실 소스 (전체 설계·근거)
CLAUDE.md                 세션 규칙 + 함정 체크리스트
poc/
  embed.html              ★ v1 임베드용 뷰어 (iframe + postMessage)
  index.html              PoC1 지형 뷰어 (좌표/오쏘 검증)
  phase1.html             구조물 정합 데모 (합성 구조물)
  dwg_demo.html           DWG(경사갱) 정합 데모
  fix_gltf_uv.py          ★ 오쏘 V-flip + 샘플러 수정 (필수 후처리)
  raster_ortho.py         드래이핑 정확도 검증 도구 (뷰어 무관)
  fbx_bbox.py             FBX 정점 bbox (시나리오 판별)
  build.sh                FBX→glb→V-flip + xeokit 번들
  out/                    ground_clamp.glb, dwg_lines.json (배포 에셋)
  vendor/                 xeokit-sdk 번들
ingest/
  pipeline.py             오케스트레이터 (포맷 디스패치)
  storage/                Supabase Storage 클라이언트
  pos_parser/             .pos → EPSG (구현·테스트)
  fbx2gltf/ ifc2xkt/ dwg2gltf/ ortho_ktx2/
integration/
  aps/                    ACC/APS → glTF (svf-utils) — Autodesk 뷰어 교체
data/                     PoC 샘플 (ground_수정.*, 경사갱.dwg)
docs/V1_INTEGRATION.md    이 문서
vercel.json               정적 배포 (poc/ 서빙)
```

---

## 7. 배포 (v1 이 iframe 으로 가리킬 URL)

- 이 레포는 Vercel 자동 배포. 뷰어 = `https://<your-project>.vercel.app/embed.html`.
- Production 브랜치를 `claude/mir-smart-3d-viewer-djxloi` 로 두면 그 URL 이 항상 최신.
- v1 에서 그 URL 을 iframe `src` 로.
- (선택) 사내 배포/도메인으로 옮겨도 정적 파일이라 동일하게 동작.

---

## 8. 남은 작업 (v1에서 이어서)

1. **v1에 "3D뷰(신규 테스트)" 메뉴 + iframe** 추가 → `?demo=1` 로 렌더 확인. (1번)
2. **자료관리 탭 "열기" → 우리 뷰어** 배선: 파일 열 때 postMessage 로 에셋 전달.
3. **APS 실연결:** `integration/aps` 에 APS 크리덴셜(env) → URN→glTF→뷰어. 좌표(R4) 검증.
4. **MIR_SMART DB 연동:** `pick.objectId` → Supabase 조회 → 물량/진도/RFI 패널.
5. **DWG 3D솔리드 / KTX2 오쏘 / 지도 모드(Cesium)** — 로드맵 Phase 4~5.

문의/설계 근거는 `PROJECT_BRIEF.md`. 뷰어 임베드 계약은 `poc/embed.html` 상단 주석.
