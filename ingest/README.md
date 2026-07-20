# ingest — 서버측 변환 파이프라인

프로젝트 생성 시 배치로 포맷 변환(§6). **런타임 파싱 금지.** 사용자는 변환을 못 느끼고
브라우저는 작은 산출물(XKT/glTF)만 스트리밍 → 가벼움.

## 대용량 파일 = Supabase Storage (MIR_SMART v1 재사용)
GB 원본(rvt/dwg/ifc/fbx)은 GitHub 가 아니라 **Supabase Storage** 에 둔다(§15.2).
→ `storage/` (클라이언트) + `pipeline.py` (오케스트레이터). 설정: `.env.example`.

```
raw/{project}/원본  ──►  pipeline.py(변환)  ──►  derived/{project}/{terrain.glb, *.xkt, *.crs.json, manifest.json}  ──►  뷰어
```

## 구성
- `storage/`     — Supabase Storage REST 클라이언트 (다운/업로드/서명URL). §storage/README
- `pipeline.py`  — 원본 1개 → 포맷별 변환 → derived 업로드 + manifest
- `pos_parser/`  — .pos → EPSG 판별 (§5.2) — **구현·테스트 완료**
- `fbx2gltf/`    — FBX → glTF (**V-flip 필수** — PoC 1에서 확인) + .pos CRS
- `ifc2xkt/`     — IFC → XKT (convert2xkt) — **파이프라인 검증 완료**
- `ortho_ktx2/`  — 오쏘 KTX2 압축/타일 병합 (예정)

## 포맷 경로
| 입력 | 변환 | 산출/로더 |
|---|---|---|
| FBX(지형) | FBX2glTF → **V-flip+CLAMP**(fix_gltf_uv) | terrain.glb (glTF) |
| IFC(구조물) | convert2xkt | {name}.xkt (XKT) |
| .pos | pos_parser | {name}.crs.json (EPSG 메타) |
| **RVT/DWG** | ODA/DDC or 사내 Revit → IFC → 재인제스트 | (폐쇄 포맷 — 변환 레이어 §6.1) |

## 실행
```
cp ingest/.env.example ingest/.env   # Supabase 값 입력 (커밋 금지)
python ingest/pipeline.py <project> <raw_path>
python ingest/storage/supabase_storage.py list raw   # 연결 확인
```
