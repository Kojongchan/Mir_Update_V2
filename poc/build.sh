#!/usr/bin/env bash
# PoC 1 빌드: FBX → glb 변환 + xeokit 번들 준비.
# 산출물(out/, vendor/)은 gitignore 대상 — 이 스크립트로 재생성한다.
#
# 사용:  bash poc/build.sh   (레포 루트에서 실행)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p poc/out poc/vendor

echo "[1/3] npm 의존성 (fbx2gltf, xeokit-sdk) 설치…"
npm install --no-save fbx2gltf @xeokit/xeokit-sdk >/dev/null

echo "[2/3] FBX → glb 변환…"
BIN="node_modules/fbx2gltf/bin/Linux/FBX2glTF"   # macOS 는 Darwin/, Windows 는 Windows_NT/
chmod +x "$BIN" || true
"$BIN" -i "data/ground_수정.fbx" -o "poc/out/ground" -b --pbr-metallic-roughness

echo "[3/3] xeokit 번들 복사…"
cp node_modules/@xeokit/xeokit-sdk/dist/xeokit-sdk.min.es.js poc/vendor/

cat <<'MSG'

완료. 로컬에서 열기:
    npx http-server poc -p 8099 -c-1
    → http://127.0.0.1:8099/index.html  (실 GPU 브라우저에서 60fps·지터 육안 확인)

주의: FBX2glTF 가 FBX 단위를 cm 로 해석해 정점을 0.01× 저장하고,
      노드 scale=100 으로 되돌린다. 월드 좌표는 실 TM(≈22만/45만)로 보존됨.
      (인제스트 파이프라인에서 이 스케일 팩터 검증 필요 — poc/README.md 참조.)
MSG
