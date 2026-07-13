"""
FBX(바이너리) 정점 bbox 추출기 — PoC 1 / R1 검증용.

무거운 변환 도구(Blender/FBX2glTF) 없이, FBX 바이너리에서 "Vertices" 노드의
double 배열을 직접 읽어 정점 좌표의 bounding box 를 계산한다.

목적: FBX 정점이 한국 TM 실좌표(20만/60만대)인지(시나리오 1) vs
      원점 근처 로컬 재센터링 값인지(시나리오 2) 판별. (PROJECT_BRIEF.md §5.2 step 3)

FBX 바이너리 포맷 참고:
  - 헤더 27바이트: "Kaydara FBX Binary  \\x00" + 0x1A 0x00 + uint32 version
  - version >= 7500 이면 노드 오프셋이 uint64, 아니면 uint32
  - 정점은 "Vertices" 노드의 'd'(double array) 프로퍼티에 xyz 인터리브로 저장
"""

from __future__ import annotations

import struct
import sys
import zlib
from dataclasses import dataclass

MAGIC = b"Kaydara FBX Binary  \x00"


@dataclass
class BBox:
    minx: float
    miny: float
    minz: float
    maxx: float
    maxy: float
    maxz: float
    vertex_count: int

    def as_min(self) -> tuple[float, float, float]:
        return (self.minx, self.miny, self.minz)

    def as_max(self) -> tuple[float, float, float]:
        return (self.maxx, self.maxy, self.maxz)


class _Reader:
    def __init__(self, buf: bytes):
        self.buf = buf
        self.pos = 0

    def read(self, n: int) -> bytes:
        b = self.buf[self.pos : self.pos + n]
        self.pos += n
        return b

    def u8(self) -> int:
        v = self.buf[self.pos]
        self.pos += 1
        return v

    def u32(self) -> int:
        (v,) = struct.unpack_from("<I", self.buf, self.pos)
        self.pos += 4
        return v

    def u64(self) -> int:
        (v,) = struct.unpack_from("<Q", self.buf, self.pos)
        self.pos += 8
        return v


def _read_property(r: _Reader, out_vertices: list[float]) -> None:
    type_code = chr(r.u8())

    if type_code == "Y":
        r.read(2)
    elif type_code == "C":
        r.read(1)
    elif type_code == "I":
        r.read(4)
    elif type_code == "F":
        r.read(4)
    elif type_code == "D":
        r.read(8)
    elif type_code == "L":
        r.read(8)
    elif type_code in ("f", "d", "l", "i", "b"):
        array_len = r.u32()
        encoding = r.u32()
        comp_len = r.u32()
        raw = r.read(comp_len)
        if encoding == 1:
            raw = zlib.decompress(raw)
        elem = {"f": ("f", 4), "d": ("d", 8), "l": ("q", 8), "i": ("i", 4), "b": ("b", 1)}[
            type_code
        ]
        fmt, size = elem
        # double array 는 정점 후보 → 호출부에서 노드 이름으로 필터.
        if type_code in ("d", "f") and array_len > 0:
            values = struct.unpack("<%d%s" % (array_len, fmt), raw[: array_len * size])
            out_vertices.extend(values)
    elif type_code == "S" or type_code == "R":
        length = r.u32()
        r.read(length)
    else:
        raise ValueError(f"알 수 없는 프로퍼티 타입: {type_code!r} @ {r.pos}")


def _parse_node(r: _Reader, is64: bool, bbox_acc: list, depth: int = 0) -> bool:
    """노드 하나를 파싱. NULL 레코드면 False 반환(리스트 종료)."""
    if is64:
        end_offset = r.u64()
        num_props = r.u64()
        r.u64()  # prop_list_len
    else:
        end_offset = r.u32()
        num_props = r.u32()
        r.u32()  # prop_list_len

    name_len = r.u8()
    if end_offset == 0 and num_props == 0 and name_len == 0:
        return False  # NULL record

    name = r.read(name_len).decode("utf-8", "replace")

    is_vertices = name == "Vertices"
    prop_values: list[float] = []
    for _ in range(num_props):
        _read_property(r, prop_values if is_vertices else [])

    if is_vertices and prop_values:
        _accumulate(bbox_acc, prop_values)

    # 중첩 노드 파싱 (end_offset 까지)
    while r.pos < end_offset:
        if not _parse_node(r, is64, bbox_acc, depth + 1):
            break

    r.pos = end_offset  # 안전하게 정렬
    return True


def _accumulate(acc: list, coords: list[float]) -> None:
    """xyz 인터리브 배열의 min/max/count 를 누적."""
    n = len(coords) // 3
    for i in range(n):
        x = coords[3 * i]
        y = coords[3 * i + 1]
        z = coords[3 * i + 2]
        if not acc:
            acc.extend([x, y, z, x, y, z, 0])
        if x < acc[0]:
            acc[0] = x
        if y < acc[1]:
            acc[1] = y
        if z < acc[2]:
            acc[2] = z
        if x > acc[3]:
            acc[3] = x
        if y > acc[4]:
            acc[4] = y
        if z > acc[5]:
            acc[5] = z
    acc[6] += n


def extract_bbox(path: str) -> BBox:
    with open(path, "rb") as f:
        buf = f.read()

    if buf[: len(MAGIC)] != MAGIC:
        raise ValueError("FBX 바이너리 매직이 아님 (ASCII FBX 이거나 다른 포맷).")

    (version,) = struct.unpack_from("<I", buf, 23)
    is64 = version >= 7500

    r = _Reader(buf)
    r.pos = 27  # 헤더 스킵
    acc: list = []

    # 최상위 노드 리스트 파싱
    while r.pos < len(buf) - 13:
        try:
            if not _parse_node(r, is64, acc):
                break
        except (ValueError, struct.error, IndexError):
            break

    if not acc:
        raise ValueError("Vertices 노드를 찾지 못함.")

    return BBox(acc[0], acc[1], acc[2], acc[3], acc[4], acc[5], acc[6])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python fbx_bbox.py <file.fbx>", file=sys.stderr)
        raise SystemExit(2)

    with open(sys.argv[1], "rb") as f:
        (ver,) = struct.unpack_from("<I", f.read(27), 23)
    print(f"FBX version: {ver}")

    bb = extract_bbox(sys.argv[1])
    print(f"vertex count : {bb.vertex_count:,}")
    print(f"X: {bb.minx:,.3f} .. {bb.maxx:,.3f}   (범위 {bb.maxx - bb.minx:,.1f} m)")
    print(f"Y: {bb.miny:,.3f} .. {bb.maxy:,.3f}   (범위 {bb.maxy - bb.miny:,.1f} m)")
    print(f"Z: {bb.minz:,.3f} .. {bb.maxz:,.3f}   (범위 {bb.maxz - bb.minz:,.1f} m)")

    # 시나리오 판별 (pos_parser 재사용)
    sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/ingest/pos_parser")
    try:
        from pos_parser import classify_offset_scenario

        s = classify_offset_scenario(bb.as_min(), bb.as_max())
        print(f"\n=> 오프셋 시나리오: {s.value}")
    except Exception as e:  # noqa: BLE001
        print(f"(시나리오 판별 스킵: {e})")
