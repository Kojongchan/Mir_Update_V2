"""Supabase Storage 클라이언트 (인제스트용).

MIR_SMART v1 이 이미 쓰는 Supabase 를 재사용한다. 대용량 원본(rvt/dwg/ifc/fbx)은
GitHub 가 아니라 Supabase Storage 에 둔다(§15.2). 인제스트 서버가 원본을 내려받아
변환하고, 작은 산출물(XKT/glTF)을 다시 올린다.

의존성: requests (supabase-py 대신 Storage REST API 직접 호출 — 가볍고 충돌 없음).

설정 (환경변수 — 절대 커밋 금지):
  SUPABASE_URL          예: https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY  service_role 키 (서버 전용 비밀). 브라우저/깃에 노출 금지.
  MIR_RAW_BUCKET        기본 "raw"       (원본)
  MIR_DERIVED_BUCKET    기본 "derived"   (변환 산출물)

REST 참조: {SUPABASE_URL}/storage/v1/object/...
"""
from __future__ import annotations

import os
import mimetypes
import requests


class SupabaseStorage:
    def __init__(self, url: str | None = None, service_key: str | None = None):
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.key = service_key or os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not self.url or not self.key:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_KEY 환경변수가 필요합니다 "
                "(service_role 키는 서버 전용 비밀 — 커밋/노출 금지)."
            )
        self._base = f"{self.url}/storage/v1"
        self._h = {"Authorization": f"Bearer {self.key}", "apikey": self.key}

    # --- 다운로드: 원본 → 로컬 (인제스트 서버가 변환 전 받음) ---
    def download(self, bucket: str, path: str, dest: str) -> str:
        r = requests.get(f"{self._base}/object/{bucket}/{path}", headers=self._h, stream=True)
        r.raise_for_status()
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        return dest

    # --- 업로드: 변환 산출물 → derived (뷰어가 소비) ---
    def upload(self, bucket: str, path: str, local: str, upsert: bool = True) -> None:
        ctype = mimetypes.guess_type(local)[0] or "application/octet-stream"
        h = dict(self._h)
        h["Content-Type"] = ctype
        if upsert:
            h["x-upsert"] = "true"
        with open(local, "rb") as f:
            r = requests.post(f"{self._base}/object/{bucket}/{path}", headers=h, data=f)
        r.raise_for_status()

    # --- 서명 URL: 뷰어가 private derived 에셋을 임시 로드 ---
    def signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        r = requests.post(
            f"{self._base}/object/sign/{bucket}/{path}",
            headers={**self._h, "Content-Type": "application/json"},
            json={"expiresIn": expires_in},
        )
        r.raise_for_status()
        return self.url + "/storage/v1" + r.json()["signedURL"]

    def list(self, bucket: str, prefix: str = "") -> list[dict]:
        r = requests.post(
            f"{self._base}/object/list/{bucket}",
            headers={**self._h, "Content-Type": "application/json"},
            json={"prefix": prefix, "limit": 1000, "sortBy": {"column": "name", "order": "asc"}},
        )
        r.raise_for_status()
        return r.json()


RAW_BUCKET = os.environ.get("MIR_RAW_BUCKET", "raw")
DERIVED_BUCKET = os.environ.get("MIR_DERIVED_BUCKET", "derived")


if __name__ == "__main__":
    # 연결 스모크 테스트: 환경변수 설정 후  python supabase_storage.py list raw <prefix>
    import sys, json

    s = SupabaseStorage()
    if len(sys.argv) >= 3 and sys.argv[1] == "list":
        prefix = sys.argv[3] if len(sys.argv) > 3 else ""
        print(json.dumps(s.list(sys.argv[2], prefix), indent=2, ensure_ascii=False))
    else:
        print("usage: python supabase_storage.py list <bucket> [prefix]")
