# aps — ACC 파일을 우리 뷰어로 열기 (APS 통합)

## 무엇을 바꾸나 (핵심)
MIR_SMART v1 은 이미 **APS API 로 ACC 파일을 받아 Autodesk 뷰어**로 표시한다.
그 뷰어(SVF2 스트리밍)가 **렉의 원인**. 우리는 **뷰어만 xeokit 으로 교체**한다.
APS 파일 접근·인증·목록(자료관리 탭)은 v1 것을 그대로 재사용.

```
[v1 자료관리 탭] 파일 열기 (모델 URN 보유)
        │
        ▼  URN
우리 백엔드: APS 파생(SVF/SVF2) → svf-utils → glTF (+ 속성 dbId/GUID)
        │        (오토데스크가 이미 변환 → rvt/dwg/nwd/ifc 다 됨. 폐쇄포맷 벽 우회)
        ▼  캐시(Supabase derived)
우리 뷰어(xeokit): 렌더 + 속성패널 → MIR_SMART DB 연동
```

## 왜 이게 rvt/dwg 문제까지 푸나
버리는 건 ACC 의 **뷰어(렉)** 이지 **변환**이 아니다. 오토데스크가 자기 포맷을
변환(파생 SVF)하고, 우린 그 geometry 만 받아 **빠른 뷰어**로 그린다. ODA/DDC 불필요.

## 사용 (URN → glTF)
```bash
npm install                       # svf-utils
export APS_CLIENT_ID=...  APS_CLIENT_SECRET=...   # v1 APS 앱 크리덴셜 재사용 (비밀)
node convert_urn.mjs <base64_urn> ./out_gltf
```
- 파생(SVF)이 없으면 먼저 Model Derivative translate 잡(output=svf) 필요.
- 산출 glTF 는 Supabase derived 캐시 → 같은 버전 재열람 시 즉시 로드.

## ⚠️ 검증 포인트
- **좌표:** SVF geometry 가 실좌표(공유좌표)로 나오는지 — 지형(EPSG 5186)과 자동 정합의 관건(R4).
  오프셋 있으면 매니페스트/메타에서 읽어 뷰어 origin(RTC)으로 보정.
- **인증 범위:** ACC 사용자 프로젝트 데이터는 3-legged(사용자 OAuth) 필요할 수 있음.
  v1 이 이미 처리 중이므로 그 토큰/플로우 재사용이 최선.
- **SVF vs SVF2:** svf-utils 는 SVF 계열을 읽는다. ACC 자동파생이 SVF2 전용이면
  Model Derivative 로 svf(v1) 파생을 추가 요청.

## 필요한 것 (라이브 연결)
1. **APS Client ID / Secret** (v1 이 쓰는 앱) — env 로 주입(커밋 금지).
2. 이미 번역된 **3D 모델 URN** 1개(테스트용).
그러면 URN→glTF→xeokit end-to-end 검증.
