#!/usr/bin/env bash
# IFC → XKT 변환 (xeokit convert2xkt). 서버측 배치. 런타임 파싱 금지(§6.3).
#
# 사용:  bash ingest/ifc2xkt/convert.sh <structure.ifc> <out.xkt>
#
# PoC 1(Phase 1)에서 검증: convert2xkt → XKT → xeokit XKTLoaderPlugin 로드 OK.
# 구조물은 색상 지오메트리(텍스처 없음)라 basis(KTX2) 인코더 불필요.
set -euo pipefail

IN="${1:?usage: convert.sh <in.ifc> <out.xkt>}"
OUT="${2:?usage: convert.sh <in.ifc> <out.xkt>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "[ifc2xkt] npm 의존성 확인…"
npm install --no-save @xeokit/xeokit-convert >/dev/null
CVT="node_modules/@xeokit/xeokit-convert/convert2xkt.js"

echo "[ifc2xkt] IFC → XKT: $IN → $OUT"
# -f ifc : IFC 직접 입력. 텍스처 있는 모델이면 아래 주의 참조.
node "$CVT" -s "$IN" -f ifc -o "$OUT"

echo "[ifc2xkt] 완료. 뷰어는 XKTLoaderPlugin 으로 로드 (실좌표 그대로, re-center 없음)."
cat <<'NOTE'

주의(텍스처 모델만): convert2xkt 는 KTX2 인코딩에
  modules/textures/dist/libs/basis_encoder.wasm 를 CWD 기준 상대경로로 찾는다.
  텍스처 있는 소스면 그 경로를 링크/복사하거나 -t(텍스처 무시)로 우회.
  BIM 구조물은 색상 지오메트리라 보통 불필요.
NOTE
