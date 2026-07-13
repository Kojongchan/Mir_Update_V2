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

## 재현 (레포 루트에서)
```bash
bash poc/build.sh                      # FBX→glb 변환 + xeokit 번들 준비
npx http-server poc -p 8099 -c-1       # 서빙
# → http://127.0.0.1:8099/index.html  (실 GPU 브라우저에서 열기)
```
산출물 `poc/out/`, `poc/vendor/` 는 gitignore 대상 — build.sh 로 재생성.

## 절차 & 도구
1. **`.pos` 파싱** — `ingest/pos_parser`:
   ```bash
   python ingest/pos_parser/pos_parser.py data/ground_수정.pos
   ```
2. **FBX 정점 bbox / 시나리오 판별** — `poc/fbx_bbox.py` (무거운 변환 없이
   FBX 바이너리에서 정점 double 배열 직접 파싱):
   ```bash
   python poc/fbx_bbox.py data/ground_수정.fbx
   ```
3. **FBX → glb** — FBX2glTF (`build.sh`). 오쏘 텍스처 glb 임베드 확인.
4. **xeokit 로딩** — `index.html`. Viewer(`dtxEnabled:true`), glTF 를 **실좌표 그대로**
   (re-center 없이) 로딩. 조명 + 오비트 + FPS HUD.

## 결과 (2026-07-13, 자동 검증)

### ✅ 코드로 확인된 것
| 항목 | 결과 |
|---|---|
| `.pos` → EPSG | **5186 (중부)** — 이름(127TM) 무시, central_meridian=127 + false_northing=600000 으로 판별 |
| FBX 정점 bbox | X **224,614 .. 226,055** (easting), Y **450,292 .. 451,558** (northing), Z 100 .. 331 m |
| 오프셋 시나리오 | **시나리오 1 (실좌표)** — 정점이 이미 중부원점 실좌표. re-center 불필요, `.pos`는 CRS 태그로만 |
| 지형 크기 | ≈ 1.4km × 1.3km, 정점 117,310 |
| FBX → glb | 성공. 오쏘 텍스처 4장 glb 임베드 |
| xeokit 로드 | 성공. 씬 AABB = 실 TM 좌표 (X 224,614 / Z −451,558; Y-up 변환으로 northing→−Z) |
| 오쏘 드래이핑 | **정상** (results/02 참조 — 항공영상이 지형에 얹힘, 디지털트윈 실사감) |
| 근접 렌더 | 실좌표 451,000 지점 **30m 근접**(float32 지터 최악 조건)에서 지오메트리 깨끗 |

스크린샷: `results/01_terrain_oblique.png`, `results/02_ortho_closeup.png`

### ⚠️ 발견된 함정 (인제스트 반영 필요)
- **FBX2glTF 단위 스케일:** FBX 단위를 cm 로 해석 → 정점을 0.01× 저장, 노드 scale=100 으로
  복원. 월드 좌표는 실 TM 로 보존되나, **인제스트에서 이 스케일 팩터를 명시 검증**해야 함
  (오해 시 100× 스케일 오류·지오레퍼런싱 손상 위험).
- glTF POSITION 은 float32 고정 → 절대 대좌표를 그대로 담으면 파일 단계에서 양자화(≈수 cm).
  지형엔 무해하나, 정밀 구조물(Phase 1)은 **XKT(더블 프리시전) 또는 RTC 원점 재기준** 필요.

### ⏳ 남은 확인 (실 GPU + 사람 눈 — 자동화 불가)
- [ ] **60fps 유지** — 여기 측정한 FPS 5~6 은 **헤드리스 SwiftShader(소프트웨어 렌더)** 값이라
      무의미. 실 GPU 브라우저에서 `index.html` 열어 확인.
- [ ] **카메라 이동 중 지터/z-fighting 없음** — 동적 현상이라 정지 스크린샷으론 최종 판정 불가.
      오비트/근접 이동하며 육안 확인.

### 판정
- 좌표·정합·오쏘·파이프라인은 **통과**. R1 의 정적 요소는 모두 확인됨.
- 남은 두 항목(60fps·이동 중 지터)만 실 GPU 육안 확인되면 **R1 최종 통과 → Phase 1(구조물 정합)** 진행.
- 결과 확정 후 PROJECT_BRIEF.md §11 R1 행에 반영.
