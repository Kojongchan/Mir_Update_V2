# PoC 1 — 좌표 지터 검증 (Phase 0, R1)

PROJECT_BRIEF.md §13. **가장 위험한 가정(R1)을 코드로 먼저 깬다.**

## 목표
"중부원점 **60만대 실좌표** FBX 지형을 **xeokit** 에서 **지터 없이 60fps** 로 렌더"
를 검증한다. (That Open 실패의 float32 좌표 원인이 xeokit 더블 프리시전에서
소멸하는지 확인.)

## 입력 (Git LFS `/data` 에 업로드 필요)
- `ground_수정.fbx` (지오메트리, ~14.6MB)
- `ground_수정.fbm` (오쏘 텍스처, ~9.7MB / 4파일)
- `ground_수정.pos` (지오레퍼런싱, ~1KB)

> ⚠️ 이 원본들은 채팅으로 못 올린다. GitHub + Git LFS 또는 스토리지로 넣어야
> PoC 를 실제로 돌릴 수 있다. 아직 없으면 아래 절차만 준비 상태로 둔다.

## 절차
1. **FBX → glTF** — `FBX2glTF` CLI 또는 Blender headless.
   `.fbm` 외부참조 텍스처를 glTF 에 임베드/복사했는지 확인.
2. **`.pos` 파싱** — `ingest/pos_parser` 사용. central_meridian/false_northing →
   EPSG(→ 5186 예상). FBX 정점 bbox 로 `classify_offset_scenario()` →
   시나리오 1(실좌표) 확인.
   ```bash
   python ../ingest/pos_parser/pos_parser.py ../data/ground_수정.pos
   ```
3. **xeokit 로딩** — Viewer(`dtxEnabled: true`) 생성, glTF 를 **실좌표 그대로**
   (re-center 없이) 로딩.
4. **측정** — Stats.js 로 FPS·메모리. 카메라 조작 시 **지터·z-fighting 육안 확인**.
5. **오쏘 드래이핑** — 텍스처 정상 표시 확인 (안 되면 KTX2 변환·UV 점검).

## 성공 기준
- [ ] 60만대 좌표에서 모델 떨림 없음.
- [ ] 인터랙션 60fps 유지.
- [ ] 오쏘가 지형에 정상 드래이핑.

## 실패 시 대응
- 지터 → xeokit 좌표 옵션 재확인, 최악의 경우 프로젝트 원점 re-center 도입.
- 성능 미달 → LOD/컬링/DTX 튜닝, 지형 메시 데시메이션.

## 결과 기록
PoC 완료 후 결과(성공/실패 + 수치 + 스크린샷)를 여기 하단과
PROJECT_BRIEF.md §11 R1 행에 반영한다. R1 이 통과해야 Phase 1(구조물 정합)로 간다.

### 실행 로그
- _(원본 업로드 후 채움)_
