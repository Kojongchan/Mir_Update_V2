# fbx2gltf — FBX → glTF 변환 (지형)

FBX2glTF/Blender CLI 로 지형 FBX 를 glTF/glb 로 변환. `.pos` 로 CRS 태깅.

## ⚠️ 필수: UV V-flip (PoC 1에서 확인된 실제 버그)
InfraWorks FBX 는 UV **V=0 이 텍스처 아래쪽**(OpenGL/FBX 규약), glTF 는
**V=0 이 위쪽**. FBX2glTF·assimp 모두 이 V-flip 을 **적용하지 않는다** →
glTF 렌더러가 오쏘 타일의 엉뚱한 행을 샘플 → **오쏘가 실제와 다르게 얹히고
특정 지형지물(예: 교량)이 누락**되며 타일 경계에서 내용이 밀려 보인다.
Navisworks 는 FBX 네이티브라 정상.

→ 변환 후 **모든 TEXCOORD_0 의 V 를 뒤집어야 한다 (v → 1-v)**.
   참조 구현: `poc/fix_gltf_uv.py` (V-flip + 샘플러 CLAMP+밉맵off).
   프로덕션에서는 변환 시점(FBX2glTF 옵션 or Blender 익스포트 설정)에서 처리.

## 오쏘 이음새 (별도 이슈)
오쏘 타일 경계의 밉맵 번짐 → 샘플러 CLAMP_TO_EDGE + 밉맵 조정.
근본 해결(밉맵 유지 + 이음새 제거)은 `ortho_ktx2/` 에서 타일 병합/거터 + KTX2.
