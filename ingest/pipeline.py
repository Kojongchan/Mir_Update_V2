"""인제스트 오케스트레이터 — 원본(Supabase raw) → 변환 → 산출물(Supabase derived).

프로젝트 생성 시 배치로 실행(§6.2). 런타임 파싱 금지. 사용자는 변환을 못 느낌 →
브라우저는 작은 XKT/glTF 만 스트리밍(가벼움).

포맷 디스패치:
  .fbx  → FBX2glTF → glb → fix_gltf_uv(V-flip+CLAMP) → derived/{proj}/terrain.glb
  .ifc  → convert2xkt → derived/{proj}/{name}.xkt
  .pos  → pos_parser → derived/{proj}/{name}.crs.json  (EPSG/CRS 메타)
  .rvt/.dwg → 변환 레이어(ODA/DDC or 사내 Revit) 필요 → 표시만(이 환경 실행 불가)

좌표: 지형·구조물이 동일 실좌표(EPSG 5186 등)면 뷰어에서 자동 정합(re-center 없음).

실행:
  export SUPABASE_URL=... SUPABASE_SERVICE_KEY=...
  python ingest/pipeline.py <project> <raw_path_in_bucket>
    예: python ingest/pipeline.py demo demo/ground_수정.fbx
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pos_parser"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "poc"))

from supabase_storage import SupabaseStorage, RAW_BUCKET, DERIVED_BUCKET  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FBX2GLTF = os.environ.get("FBX2GLTF_BIN", os.path.join(ROOT, "node_modules/fbx2gltf/bin/Linux/FBX2glTF"))
CONVERT2XKT = os.environ.get("CONVERT2XKT", os.path.join(ROOT, "node_modules/@xeokit/xeokit-convert/convert2xkt.js"))


def _run(cmd: list[str]) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, check=True)


def process(project: str, raw_path: str) -> dict:
    """raw 버킷의 파일 1개를 변환해 derived 에 올리고, manifest 항목을 반환."""
    st = SupabaseStorage()
    ext = os.path.splitext(raw_path)[1].lower()
    name = os.path.splitext(os.path.basename(raw_path))[0]
    tmp = tempfile.mkdtemp(prefix="ingest_")
    local = os.path.join(tmp, os.path.basename(raw_path))
    print(f"[ingest] download {RAW_BUCKET}/{raw_path}")
    st.download(RAW_BUCKET, raw_path, local)
    entry: dict = {"source": raw_path, "type": ext}

    if ext == ".fbx":
        glb = os.path.join(tmp, name + ".glb")
        _run([FBX2GLTF, "-i", local, "-o", os.path.join(tmp, name), "-b", "--pbr-metallic-roughness"])
        # InfraWorks V-flip + 오쏘 이음새 방지 (PoC 1에서 확인된 필수 후처리)
        from fix_gltf_uv import fix
        fixed = os.path.join(tmp, "terrain.glb")
        fix(glb, fixed)
        dst = f"{project}/terrain.glb"
        st.upload(DERIVED_BUCKET, dst, fixed)
        entry.update(kind="terrain", asset=dst, loader="gltf")

    elif ext == ".ifc":
        xkt = os.path.join(tmp, name + ".xkt")
        _run(["node", CONVERT2XKT, "-s", local, "-f", "ifc", "-o", xkt])
        dst = f"{project}/{name}.xkt"
        st.upload(DERIVED_BUCKET, dst, xkt)
        entry.update(kind="structure", asset=dst, loader="xkt")

    elif ext == ".pos":
        from pos_parser import parse_pos_file
        r = parse_pos_file(local)
        crs = {"epsg": r.epsg, "zone": r.zone_name, "central_meridian": r.central_meridian,
               "false_northing": r.false_northing, "offset": r.offset, "warnings": r.warnings}
        cj = os.path.join(tmp, name + ".crs.json")
        with open(cj, "w", encoding="utf-8") as f:
            json.dump(crs, f, ensure_ascii=False, indent=2)
        dst = f"{project}/{name}.crs.json"
        st.upload(DERIVED_BUCKET, dst, cj)
        entry.update(kind="crs", asset=dst, epsg=r.epsg, zone=r.zone_name)

    elif ext == ".dwg":
        # DWG 선형(LINE/SPLINE/POLYLINE) → LibreDWG WASM(ODA 불필요)로 추출.
        # 3DSOLID(ACIS)는 테셀레이션에 ODA 필요 → 선형만.
        lines = os.path.join(tmp, name + ".lines.json")
        _run(["node", os.path.join(ROOT, "ingest/dwg2gltf/extract_dwg.mjs"), local, lines])
        dst = f"{project}/{name}.lines.json"
        st.upload(DERIVED_BUCKET, dst, lines)
        entry.update(kind="structure_lines", asset=dst, loader="scenemodel-lines",
                     note="선형만 (3DSOLID ACIS 는 ODA 필요)")

    elif ext in (".rvt", ".nwd"):
        # 폐쇄 포맷 — ODA/DDC 또는 사내 Revit 변환 레이어 필요(§6.1). 이 환경 실행 불가.
        entry.update(kind="needs_conversion_layer",
                     note="rvt/nwd 는 ODA/DDC 또는 Revit IFC export 로 IFC 화 후 재인제스트")
        print("  [!] 폐쇄 포맷 — 변환 레이어 필요. IFC 로 export 후 재업로드 권장.")

    else:
        entry.update(kind="skip", note=f"미지원 확장자 {ext}")

    return entry


def update_manifest(project: str, entries: list[dict]) -> None:
    """derived/{project}/manifest.json 갱신 — 뷰어가 이걸 읽어 에셋/CRS 파악."""
    st = SupabaseStorage()
    tmp = tempfile.mkdtemp()
    mpath = os.path.join(tmp, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump({"project": project, "assets": entries}, f, ensure_ascii=False, indent=2)
    st.upload(DERIVED_BUCKET, f"{project}/manifest.json", mpath)
    print(f"[ingest] manifest → {DERIVED_BUCKET}/{project}/manifest.json")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python ingest/pipeline.py <project> <raw_path>", file=sys.stderr)
        raise SystemExit(2)
    proj, path = sys.argv[1], sys.argv[2]
    e = process(proj, path)
    print(json.dumps(e, ensure_ascii=False, indent=2))
