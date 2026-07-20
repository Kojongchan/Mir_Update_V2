#!/usr/bin/env python3
"""FBX2glTF/assimp 산출 glb 후처리 — 오쏘 드래이핑 정확도 수정.

배경 (PoC 1에서 확인된 실제 버그):
  InfraWorks FBX 는 UV V=0 이 텍스처 '아래쪽'(OpenGL/FBX 규약)인데,
  glTF 는 V=0 이 '위쪽'이다. FBX2glTF 와 assimp 모두 이 V-flip 을 적용하지
  않아서, glTF 렌더러(xeokit/three.js)가 오쏘 타일의 '엉뚱한 행'을 샘플한다.
  → 지형에 실제와 다른 이미지가 얹히고(예: 교량 등 특정 지형지물 누락),
    타일 경계에서 내용이 밀려 보인다. Navisworks 는 FBX 를 네이티브로 읽어
    올바른 V 규약을 쓰므로 정상으로 보였다.

이 스크립트가 하는 일:
  1. 모든 TEXCOORD_0 의 V 를 뒤집는다 (v -> 1 - v).
  2. 텍스처 샘플러를 CLAMP_TO_EDGE + 밉맵 off 로 설정한다
     (오쏘 타일 경계의 밉맵 번짐/이음새 방지).

사용:
  python fix_gltf_uv.py in.glb out.glb

주의: 근본적으로는 인제스트 파이프라인(§6.2 fbx2gltf)에서 변환 시점에
  V-flip 을 적용해야 한다. 이 후처리는 그 규칙의 참조 구현이다.
"""
import struct, json, sys


def fix(src: str, dst: str, flip_v: bool = True, clamp: bool = True) -> None:
    with open(src, "rb") as f:
        data = bytearray(f.read())
    magic, ver, total = struct.unpack_from("<III", data, 0)
    (json_len,) = struct.unpack_from("<I", data, 12)
    joff = 20
    j = json.loads(bytes(data[joff : joff + json_len]))
    bin_start = joff + json_len + 8  # + BIN chunk header
    bvs, acc = j["bufferViews"], j["accessors"]

    if flip_v:
        uv_accs = set()
        for mesh in j["meshes"]:
            for p in mesh["primitives"]:
                t = p["attributes"].get("TEXCOORD_0")
                if t is not None:
                    uv_accs.add(t)
        for ai in uv_accs:
            a = acc[ai]
            bv = bvs[a["bufferView"]]
            start = bin_start + bv.get("byteOffset", 0) + a.get("byteOffset", 0)
            stride = bv.get("byteStride") or 8
            for k in range(a["count"]):
                base = start + k * stride
                u, v = struct.unpack_from("<ff", data, base)
                struct.pack_into("<ff", data, base, u, 1.0 - v)

    if clamp:
        # magFilter LINEAR, minFilter LINEAR(밉맵 off), wrap CLAMP_TO_EDGE
        j["samplers"] = [
            {"magFilter": 9729, "minFilter": 9729, "wrapS": 33071, "wrapT": 33071}
        ]
        for t in j.get("textures", []):
            t["sampler"] = 0

    new_json = json.dumps(j, separators=(",", ":")).encode("utf-8")
    new_json += b" " * ((4 - len(new_json) % 4) % 4)
    bin_chunk = bytes(data[joff + json_len :])  # BIN header + (V-modified) data
    out = bytearray()
    out += struct.pack("<III", magic, ver, 20 + len(new_json) + len(bin_chunk))
    out += struct.pack("<II", len(new_json), 0x4E4F534A)  # 'JSON'
    out += new_json
    out += bin_chunk
    with open(dst, "wb") as f:
        f.write(out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python fix_gltf_uv.py <in.glb> <out.glb>", file=sys.stderr)
        raise SystemExit(2)
    fix(sys.argv[1], sys.argv[2])
    print(f"wrote {sys.argv[2]} (V-flip + CLAMP + no-mip)")
