"""
.pos 파일 파서 — 한국 평면직각(TM) 좌표계 EPSG 판별.

PROJECT_BRIEF.md §5.2 의 확정 규칙을 구현한다.

핵심 원칙 (CLAUDE.md 절대 규칙):
  1. `.pos`의 좌표계 "이름 문자열"(예: KOREA_GRS80_127TM)은 믿지 않는다.
     Civil 3D 사용자 정의 이름일 뿐이므로 EPSG 판별에 쓰지 않는다.
  2. `central_meridian` + `false_northing` 값으로만 EPSG를 확정한다.
  3. `coordinates` 오프셋이 [0,0,0](미기재)이면, FBX 정점 bbox 를 별도로 검사해
     시나리오 1(정점이 이미 실좌표) / 시나리오 2(정점이 원점 근처, 오프셋 필요)를 판별한다.
     → 이 파일은 (1)(2)(3)의 "선언"까지만 담당. 정점 bbox 검사는 fbx 측에서 수행하고
        classify_offset_scenario()로 결합한다.

`.pos` 는 InfraWorks 가 FBX 와 함께 내보내는 GeoJSON 형태 파일이며,
crs.properties.name 필드에 WKT(PROJCS[...]) 문자열이 들어 있다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# EPSG 판별표 (PROJECT_BRIEF.md §5.2 / CLAUDE.md)
# central_meridian(경도) → (원점 이름, EPSG, 표준 false_northing)
# ---------------------------------------------------------------------------
KOREA_TM_ZONES: dict[int, tuple[str, int]] = {
    125: ("서부", 5185),
    127: ("중부", 5186),
    129: ("동부", 5187),
    131: ("동해", 5188),
}

# 현행(GRS80) 평면직각 좌표계의 표준 false_northing.
STANDARD_FALSE_NORTHING = 600000
# 구 좌표계(5174 계열, Bessel 원점) 의심 값.
LEGACY_FALSE_NORTHING = 500000


class OffsetScenario(Enum):
    """`.pos` coordinates 오프셋 + FBX 정점 좌표 조합으로 판별한 시나리오."""

    REAL_COORDS = "scenario_1_real_coords"  # 정점이 이미 실좌표 → 오프셋 이동 불필요
    NEEDS_ORIGIN = "scenario_2_needs_origin"  # 정점이 원점 근처 → 실세계 원점 입력 필요
    UNKNOWN = "scenario_unknown"  # 판별 불가 (FBX bbox 미제공)


@dataclass
class PosParseResult:
    epsg: Optional[int]
    zone_name: Optional[str]  # 서부/중부/동부/동해
    central_meridian: Optional[float]
    false_northing: Optional[float]
    false_easting: Optional[float]
    latitude_of_origin: Optional[float]
    datum: Optional[str]  # 예: GRS1980
    raw_crs_name: Optional[str]  # 무시하되 감사(audit)용으로 보존
    offset: Optional[tuple[float, float, float]]  # coordinates
    warnings: list[str] = field(default_factory=list)

    @property
    def confident(self) -> bool:
        """경고 없이 EPSG 를 확정했는가."""
        return self.epsg is not None and not self.warnings


# ---------------------------------------------------------------------------
# WKT 파라미터 추출
# ---------------------------------------------------------------------------
def _extract_number(wkt: str, key: str) -> Optional[float]:
    """WKT 문자열에서 `PARAMETER["key", <num>]` 또는 `key <num>` 형태의 숫자를 뽑는다.

    InfraWorks .pos 의 name 필드는 표준 WKT가 아니라 축약형일 수 있어
    두 형태(파라미터 배열 / 공백 구분)를 모두 지원한다.
    """
    # 표준 WKT: PARAMETER["central_meridian",127]
    m = re.search(
        r'PARAMETER\s*\[\s*"?' + re.escape(key) + r'"?\s*,\s*(-?\d+(?:\.\d+)?)',
        wkt,
        re.IGNORECASE,
    )
    if m:
        return float(m.group(1))
    # 축약형: central_meridian 127  또는  central_meridian=127 / central_meridian, 127
    m = re.search(
        re.escape(key) + r'\s*["\s,=:]+\s*(-?\d+(?:\.\d+)?)',
        wkt,
        re.IGNORECASE,
    )
    if m:
        return float(m.group(1))
    return None


def _extract_datum(wkt: str) -> Optional[str]:
    for token in ("GRS1980", "GRS_1980", "GRS80", "Bessel", "WGS84", "WGS_1984"):
        if re.search(re.escape(token), wkt, re.IGNORECASE):
            return token
    return None


def _extract_projcs_name(wkt: str) -> Optional[str]:
    m = re.search(r'PROJCS\s*\[\s*"([^"]+)"', wkt, re.IGNORECASE)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# EPSG 판별 (이름 문자열 무시, meridian + northing 사용)
# ---------------------------------------------------------------------------
def resolve_epsg(
    central_meridian: Optional[float],
    false_northing: Optional[float],
    warnings: list[str],
) -> tuple[Optional[int], Optional[str]]:
    if central_meridian is None:
        warnings.append(
            "central_meridian 을 .pos 에서 찾지 못함 → EPSG 자동 확정 불가. "
            "프로젝트 생성 UI에서 좌표계를 사용자가 지정해야 함."
        )
        return None, None

    cm = int(round(central_meridian))
    if cm not in KOREA_TM_ZONES:
        warnings.append(
            f"central_meridian={central_meridian} 가 한국 TM 표준 경도"
            f"(125/127/129/131) 에 해당하지 않음 → 사용자 확인 필요."
        )
        return None, None

    zone_name, epsg = KOREA_TM_ZONES[cm]

    # false_northing 교차검증: 500000 이면 구 좌표계(5174 계열) 의심.
    if false_northing is not None:
        fn = int(round(false_northing))
        if fn == LEGACY_FALSE_NORTHING:
            warnings.append(
                f"false_northing={false_northing} → 구 좌표계(5174 계열, Bessel 원점) "
                f"의심. GRS80 EPSG {epsg} 로 자동 확정하지 말고 사용자 확인 필요."
            )
            return None, zone_name
        if fn != STANDARD_FALSE_NORTHING:
            warnings.append(
                f"false_northing={false_northing} 가 표준값 {STANDARD_FALSE_NORTHING} 과 "
                f"다름 → EPSG {epsg} 확정에 주의 필요."
            )

    return epsg, zone_name


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
def parse_pos_text(text: str) -> PosParseResult:
    """`.pos` 파일 내용(문자열)을 파싱한다."""
    warnings: list[str] = []

    crs_name_wkt: Optional[str] = None
    offset: Optional[tuple[float, float, float]] = None

    # .pos 는 GeoJSON 형태를 기대하나, 손상/축약 케이스를 위해 방어적으로 처리.
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        data = None
        warnings.append(
            ".pos 를 JSON 으로 파싱하지 못함 → 원문에서 직접 WKT/좌표를 추출."
        )

    if isinstance(data, dict):
        crs = data.get("crs")
        if isinstance(crs, dict):
            props = crs.get("properties")
            if isinstance(props, dict):
                name = props.get("name")
                if isinstance(name, str):
                    crs_name_wkt = name
        coords = data.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            x = float(coords[0])
            y = float(coords[1])
            z = float(coords[2]) if len(coords) >= 3 else 0.0
            offset = (x, y, z)

    # WKT 후보: crs.name 이 있으면 그것, 없으면 전체 원문(축약형 대비).
    wkt_source = crs_name_wkt if crs_name_wkt else text

    projcs_name = _extract_projcs_name(wkt_source) or crs_name_wkt
    central_meridian = _extract_number(wkt_source, "central_meridian")
    false_northing = _extract_number(wkt_source, "false_northing")
    false_easting = _extract_number(wkt_source, "false_easting")
    latitude_of_origin = _extract_number(wkt_source, "latitude_of_origin")
    datum = _extract_datum(wkt_source)

    epsg, zone_name = resolve_epsg(central_meridian, false_northing, warnings)

    # 오프셋이 없거나 (0,0,0) 이면 시나리오 판별 필요 안내 (FBX bbox 필요).
    if offset is None:
        warnings.append(
            "coordinates 오프셋이 .pos 에 없음 → FBX 정점 bbox 로 "
            "시나리오 1/2 판별 필요 (classify_offset_scenario)."
        )
    elif offset[0] == 0 and offset[1] == 0:
        warnings.append(
            "coordinates 오프셋이 [0,0,...] → FBX 정점 bbox 로 "
            "시나리오 1/2 이중 확인 필요 (classify_offset_scenario)."
        )

    return PosParseResult(
        epsg=epsg,
        zone_name=zone_name,
        central_meridian=central_meridian,
        false_northing=false_northing,
        false_easting=false_easting,
        latitude_of_origin=latitude_of_origin,
        datum=datum,
        raw_crs_name=projcs_name,
        offset=offset,
        warnings=warnings,
    )


def parse_pos_file(path: str) -> PosParseResult:
    with open(path, "r", encoding="utf-8-sig") as f:
        return parse_pos_text(f.read())


# ---------------------------------------------------------------------------
# 시나리오 판별 (PROJECT_BRIEF.md §5.2 step 3)
# FBX 정점 bbox 를 받아 오프셋 시나리오를 확정한다.
# ---------------------------------------------------------------------------
def classify_offset_scenario(
    fbx_bbox_min: tuple[float, float, float],
    fbx_bbox_max: tuple[float, float, float],
    real_coord_threshold: float = 100_000.0,
) -> OffsetScenario:
    """FBX 정점 bbox 로 시나리오 1/2 를 판별한다.

    시나리오 1 (REAL_COORDS): 정점이 이미 실세계 TM 실좌표(20만/60만대).
        → 오프셋 이동 불필요. `.pos` 는 CRS 태그로만 사용. (본 프로젝트 케이스.)
    시나리오 2 (NEEDS_ORIGIN): 정점이 원점(0) 근처의 로컬 재센터링 값.
        → 프로젝트 생성 UI에서 실세계 원점 1개 입력받아 이동 필요.

    한국 TM 실좌표는 easting 20만대, northing 40만~80만대이므로
    bbox 절대값이 threshold(기본 10만) 를 넘으면 실좌표로 판단한다.
    """
    max_abs = max(
        abs(fbx_bbox_min[0]),
        abs(fbx_bbox_min[1]),
        abs(fbx_bbox_max[0]),
        abs(fbx_bbox_max[1]),
    )
    if max_abs >= real_coord_threshold:
        return OffsetScenario.REAL_COORDS
    return OffsetScenario.NEEDS_ORIGIN


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: python pos_parser.py <file.pos>", file=sys.stderr)
        raise SystemExit(2)
    result = parse_pos_file(sys.argv[1])
    print(f"PROJCS name (무시됨, audit용): {result.raw_crs_name}")
    print(f"central_meridian : {result.central_meridian}")
    print(f"false_northing   : {result.false_northing}")
    print(f"datum            : {result.datum}")
    print(f"=> EPSG          : {result.epsg}  ({result.zone_name})")
    print(f"offset           : {result.offset}")
    if result.warnings:
        print("\n[warnings]")
        for w in result.warnings:
            print(f"  - {w}")
