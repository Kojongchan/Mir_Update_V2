# storage — Supabase Storage (대용량 원본/산출물)

MIR_SMART v1 이 쓰는 **Supabase 재사용**. GitHub(25MB 웹/100MB 하드캡)로는 GB 원본을
못 올리므로, 원본은 Supabase Storage 에 둔다(§15.2). 뷰어는 GB 원본을 절대 안 받고,
변환된 **작은 XKT/glTF 만** 로드한다(예: IFC 186MB → XKT 12MB).

## 흐름
```
사용자 업로드(GB rvt/dwg/ifc/fbx)  ──►  Supabase Storage: raw/{project}/...
                                              │
                              ingest/pipeline.py (서버 배치)
                                              │ 다운로드→변환→업로드
                                              ▼
                                   Supabase Storage: derived/{project}/
                                     terrain.glb, {name}.xkt, *.crs.json, manifest.json
                                              │ 서명 URL
                                              ▼
                                        뷰어(xeokit) 로드
```

## 1) 버킷 생성 (Supabase 대시보드 → Storage)
- `raw` (Private) — 원본
- `derived` (Private) — 변환 산출물 (뷰어는 서명 URL 로 접근)
- 대용량: 버킷 설정에서 **File size limit** 를 GB 로 상향. GB 업로드는 대시보드의
  재개형(resumable/TUS) 업로드 또는 Supabase CLI/JS resumable 사용.

## 2) 환경변수 (비밀 — 커밋 금지)
`ingest/.env.example` 참고. 이 세션/서버 환경에 설정:
```
SUPABASE_URL, SUPABASE_SERVICE_KEY, MIR_RAW_BUCKET, MIR_DERIVED_BUCKET
```
> service_role 키는 **서버 전용**. 뷰어(브라우저)는 anon 키 + RLS + 서명 URL 만 쓴다.
> 키를 채팅/깃에 붙이지 말고 환경변수로만 주입.

## 3) 원본 업로드
- 작은 파일: 대시보드 드래그.
- **GB 파일: 대시보드 재개형 업로드** 또는 `supabase storage cp`(CLI). GitHub 아님.

## 4) 인제스트 실행 (변환)
```
python ingest/pipeline.py <project> raw경로
  예: python ingest/pipeline.py demo demo/structure.ifc
```
연결 스모크 테스트:
```
python ingest/storage/supabase_storage.py list raw
```

## 보안
- service_role 키 노출 시 스토리지 전체 접근 → 반드시 서버 비밀로 관리.
- derived 는 Private + 서명 URL(만료). 공개 배포 시 RLS/정책 재검토.
