# pos_parser — `.pos` → EPSG 판별

PROJECT_BRIEF.md §5.2 의 확정 규칙 구현. InfraWorks 가 FBX 와 함께 내보내는
`.pos`(GeoJSON) 파일에서 한국 평면직각(TM) 좌표계의 **EPSG 코드**를 판별한다.

## 규칙 (요약)
1. 좌표계 **이름 문자열은 무시**한다 (`KOREA_GRS80_127TM` = Civil 3D 사용자 정의 이름일 뿐).
2. `central_meridian` + `false_northing` 값으로만 EPSG 를 확정한다.

   | central_meridian | 원점 | EPSG |
   |---|---|---|
   | 125 | 서부 | 5185 |
   | 127 | 중부 | 5186 |
   | 129 | 동부 | 5187 |
   | 131 | 동해 | 5188 |

   `false_northing == 500000` 이면 구 좌표계(5174 계열) 의심 → 자동 확정하지 않고 경고.
3. `coordinates` 오프셋이 `[0,0,0]` 이면 FBX 정점 bbox 를 검사해
   시나리오 1(실좌표, 오프셋 불필요) / 시나리오 2(원점 입력 필요)를 판별
   (`classify_offset_scenario`).

## 사용법
```python
from pos_parser import parse_pos_file, classify_offset_scenario

r = parse_pos_file("ground_수정.pos")
print(r.epsg, r.zone_name)   # 5186 중부
if not r.confident:
    for w in r.warnings:
        print("확인 필요:", w)

# FBX 정점 bbox 로 오프셋 시나리오 확정
scenario = classify_offset_scenario(bbox_min, bbox_max)
```

CLI:
```bash
python pos_parser.py fixtures/ground_sample.pos
```

## 테스트
```bash
python test_pos_parser.py            # 자체 러너 (표준 라이브러리만)
python -m pytest test_pos_parser.py  # pytest 있으면
```

## 의존성
없음 (Python 3.11+ 표준 라이브러리만). 좌표 **재투영**(5186↔WGS84)은
지도 모드 전용이므로 여기서 하지 않는다 — `pyproj` 는 지도 모드 모듈에서 사용.
