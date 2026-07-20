# MIR_SMART 자체 3D 뷰어

ACC(Autodesk) 뷰어를 대체하는 **사내 전용 웹 3D BIM 디지털트윈 뷰어**.
rvt·dwg·ifc·fbx 를 좌표 포함 3D 로 렌더링하고 MIR_SMART(물량/진도/RFI)와 연동한다.
**최우선 가치는 "가벼움".**

> 전체 설계·근거·리스크는 [`PROJECT_BRIEF.md`](./PROJECT_BRIEF.md) (단일 진실 소스).
> 세션마다 지킬 핵심 규칙은 [`CLAUDE.md`](./CLAUDE.md).
> **v1 통합/인수인계: [`docs/V1_INTEGRATION.md`](./docs/V1_INTEGRATION.md).**

## 아키텍처 (듀얼 엔진 / 모드 분리)
- **BIM 검토 모드** = xeokit SDK (더블 프리시전, 실좌표 네이티브) — 주력.
- **지도 모드** = CesiumJS (위성/지도 배경, CAD 오버레이).
- 두 모드는 카메라만 공유. 한 씬에 전부 안 올림 = 가벼움의 핵심.

## 레포 구조
```
/viewer         프론트 (xeokit + cesium 듀얼 모드)          — 예정
/ingest         서버측 변환 파이프라인
  /pos_parser   .pos → EPSG 판별 (§5.2)                     ✅ 구현·테스트 완료
  /ifc2xkt      IFC → XKT                                   — 예정
  /fbx2gltf     FBX → glTF (+ .fbm 오쏘)                    — 예정
  /ortho_ktx2   오쏘 텍스처 KTX2 압축                        — 예정
/integration    MIR_SMART DB 연동 (GUID↔레코드)            — 예정
/data           PoC 샘플 (Git LFS): ground_수정.*           — 파일 업로드 대기
/poc            Phase 0 PoC 1                              — 스캐폴드
```

## 현재 상태 (Phase 0)
- ✅ 프로젝트 브리프·규칙 문서화, 레포 스캐폴드, Git LFS 설정.
- ✅ `.pos` 파서 구현 + 테스트 10/10 통과 (샘플 → EPSG 5186 중부).
- ⏳ **PoC 1 (R1 검증)**: 60만대 실좌표 FBX 지형이 xeokit 에서 지터 없이 60fps 로
  뜨는지 확인. `ground_수정.fbx/.fbm/.pos` 원본이 `/data`(LFS)에 올라오면 착수.
  자세한 절차는 [`poc/README.md`](./poc/README.md).

## 개발
```bash
# .pos 파서 테스트
python ingest/pos_parser/test_pos_parser.py
```
언어: 프론트=TypeScript, 인제스트/좌표=Python 3.11+.
