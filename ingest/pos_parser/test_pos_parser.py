"""pos_parser 테스트. 표준 라이브러리만으로 실행 가능 (pytest 없어도 됨).

실행:
    python -m pytest ingest/pos_parser/test_pos_parser.py
    또는
    python ingest/pos_parser/test_pos_parser.py   # 자체 러너
"""

from __future__ import annotations

import os

from pos_parser import (
    OffsetScenario,
    classify_offset_scenario,
    parse_pos_file,
    parse_pos_text,
    resolve_epsg,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


# --- EPSG 판별표 (PROJECT_BRIEF.md §5.2) -----------------------------------
def test_resolve_epsg_all_zones():
    for cm, (zone, epsg) in {
        125: ("서부", 5185),
        127: ("중부", 5186),
        129: ("동부", 5187),
        131: ("동해", 5188),
    }.items():
        w: list[str] = []
        got_epsg, got_zone = resolve_epsg(cm, 600000, w)
        assert got_epsg == epsg, f"cm={cm}"
        assert got_zone == zone
        assert w == [], f"표준값인데 경고 발생: {w}"


def test_central_meridian_float_rounds():
    w: list[str] = []
    assert resolve_epsg(127.0, 600000.0, w)[0] == 5186
    assert w == []


# --- 실제 샘플 (.pos, 중부원점) --------------------------------------------
def test_sample_fixture_resolves_5186():
    result = parse_pos_file(os.path.join(FIXTURES, "ground_sample.pos"))
    assert result.epsg == 5186
    assert result.zone_name == "중부"
    assert result.central_meridian == 127.0
    assert result.false_northing == 600000.0
    assert result.false_easting == 200000.0
    assert result.latitude_of_origin == 38.0
    assert result.datum in ("GRS1980", "GRS80", "GRS_1980")
    # coordinates [0,0,0] → 시나리오 판별 필요 경고가 있어야 한다.
    assert any("시나리오" in w for w in result.warnings)


def test_name_string_is_ignored_for_epsg():
    """이름이 127TM 이어도, 실제 파라미터가 129면 EPSG는 129(동부)여야 한다.

    이름 문자열을 믿지 않는다는 규칙(§5.2 step 1)의 회귀 방지.
    """
    wkt = (
        'PROJCS["KOREA_GRS80_127TM",'  # 이름은 127TM (거짓)
        'PARAMETER["false_easting",200000.0],'
        'PARAMETER["false_northing",600000.0],'
        'PARAMETER["central_meridian",129.0],'  # 실제는 129 (동부)
        'PARAMETER["latitude_of_origin",38.0]]'
    )
    text = '{"crs":{"properties":{"name":%s}},"coordinates":[0,0,0]}' % _json_str(wkt)
    result = parse_pos_text(text)
    assert result.epsg == 5187, "이름(127TM) 이 아니라 파라미터(129) 를 따라야 함"
    assert result.zone_name == "동부"


# --- false_northing 교차검증 (구 좌표계 방어) -------------------------------
def test_legacy_false_northing_blocks_auto_epsg():
    w: list[str] = []
    epsg, zone = resolve_epsg(127, 500000, w)
    assert epsg is None, "false_northing=500000(구 좌표계 의심) 이면 자동 확정 금지"
    assert zone == "중부"
    assert any("구 좌표계" in x or "5174" in x for x in w)


def test_unknown_meridian_warns():
    w: list[str] = []
    epsg, zone = resolve_epsg(126, 600000, w)  # 표준 아님
    assert epsg is None
    assert zone is None
    assert w  # 경고 존재


def test_missing_meridian_warns():
    w: list[str] = []
    epsg, zone = resolve_epsg(None, None, w)
    assert epsg is None
    assert w


# --- 축약형 WKT (JSON 아님) 방어 파싱 ---------------------------------------
def test_shorthand_non_json():
    text = (
        "PROJCS[KOREA_GRS80_127TM] central_meridian 127 "
        "false_northing 600000 false_easting 200000 GRS1980"
    )
    result = parse_pos_text(text)
    assert result.epsg == 5186
    assert any("JSON" in w for w in result.warnings)


# --- 오프셋 시나리오 판별 (§5.2 step 3) ------------------------------------
def test_scenario_1_real_coords():
    # 본 프로젝트: 정점이 중부원점 실좌표 (easting 20만대, northing 40만대)
    s = classify_offset_scenario((198000.0, 410000.0, 0.0), (205000.0, 480000.0, 120.0))
    assert s == OffsetScenario.REAL_COORDS


def test_scenario_2_needs_origin():
    # 정점이 원점 근처 로컬 재센터링 값
    s = classify_offset_scenario((-500.0, -800.0, 0.0), (500.0, 800.0, 30.0))
    assert s == OffsetScenario.NEEDS_ORIGIN


# --- helpers ---------------------------------------------------------------
def _json_str(s: str) -> str:
    import json

    return json.dumps(s)


# --- 자체 러너 (pytest 미설치 환경 대비) ------------------------------------
def _run_all():
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
        except Exception:  # noqa: BLE001
            print(f"FAIL: {fn.__name__}")
            traceback.print_exc()
        else:
            passed += 1
            print(f"ok:   {fn.__name__}")
    print(f"\n{passed}/{len(fns)} passed")
    return passed == len(fns)


if __name__ == "__main__":
    import sys

    sys.exit(0 if _run_all() else 1)
