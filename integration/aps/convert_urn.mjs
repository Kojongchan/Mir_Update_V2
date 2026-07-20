/**
 * APS(ACC) 모델 URN → glTF (우리 xeokit 뷰어용).
 *
 * 배경: MIR_SMART v1 은 이미 APS API 로 파일을 받아 **Autodesk 뷰어**로 표시한다.
 *       그 뷰어가 렉의 원인 → 우리는 **뷰어만** xeokit 으로 바꾼다(APS 접근은 그대로).
 *
 * 방법: APS 가 이미 만든 파생(SVF/SVF2)을 svf-utils 로 glTF 로 변환 → xeokit 로드.
 *       rvt·dwg·nwd·ifc 전부 오토데스크가 변환하므로 폐쇄 포맷 벽을 우회한다(§6.1).
 *       속성(dbId→ExternalId/GUID)도 함께 나와 MIR_SMART 연동에 쓴다.
 *
 * 좌표(중요): SVF 지오메트리는 모델 로컬 + 글로벌 오프셋(Revit 공유좌표/측량점).
 *   지형과 자동 정합하려면 실좌표(EPSG 5186)로 나와야 함 → 매니페스트/메타의
 *   오프셋을 확인·적용(R4). Revit 이 공유좌표를 실좌표로 설정했으면 그대로 정합.
 *
 * 설정(env, 비밀 — 커밋 금지): APS_CLIENT_ID, APS_CLIENT_SECRET
 *   (v1 이 쓰는 APS 앱의 크리덴셜 재사용). ACC 사용자 데이터는 3-legged 필요할 수 있음.
 *
 * 사용: node convert_urn.mjs <base64_urn> <outDir>
 */
import { SVFReader, GLTFWriter, TwoLeggedAuthenticationProvider } from 'svf-utils';

const [urn, outDir] = process.argv.slice(2);
if (!urn || !outDir) { console.error('usage: node convert_urn.mjs <urn> <outDir>'); process.exit(2); }

const CLIENT_ID = process.env.APS_CLIENT_ID, CLIENT_SECRET = process.env.APS_CLIENT_SECRET;
if (!CLIENT_ID || !CLIENT_SECRET) { console.error('APS_CLIENT_ID / APS_CLIENT_SECRET 필요 (env)'); process.exit(2); }
const BASE = 'https://developer.api.autodesk.com';

// 2-legged 토큰 (매니페스트 조회용). 리더는 자체 auth provider 사용.
async function token() {
  const r = await fetch(`${BASE}/authentication/v2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded',
      Authorization: 'Basic ' + Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString('base64') },
    body: 'grant_type=client_credentials&scope=data:read viewables:read',
  });
  if (!r.ok) throw new Error('APS auth 실패: ' + r.status + ' ' + await r.text());
  return (await r.json()).access_token;
}

// 매니페스트에서 3D viewable 의 derivative GUID 찾기
async function find3dGuid(tok) {
  const r = await fetch(`${BASE}/modelderivative/v2/designdata/${urn}/manifest`,
    { headers: { Authorization: 'Bearer ' + tok } });
  if (!r.ok) throw new Error('매니페스트 조회 실패: ' + r.status + ' (파생이 아직 없으면 translate 필요)');
  const m = await r.json();
  // SVF/SVF2 파생의 3d geometry guid 탐색
  const stack = [...(m.derivatives || [])];
  while (stack.length) {
    const d = stack.shift();
    if ((d.outputType === 'svf' || d.outputType === 'svf2') && d.children) {
      for (const c of d.children) {
        if (c.type === 'geometry' && c.role === '3d' && c.guid) return c.guid;
        if (c.children) stack.push({ children: c.children, outputType: d.outputType });
      }
    } else if (d.children) stack.push(...d.children.map(c => ({ ...c, outputType: d.outputType })));
  }
  throw new Error('3D viewable(SVF) guid 없음 — 모델을 SVF 로 translate 했는지 확인');
}

const tok = await token();
const guid = await find3dGuid(tok);
console.log('3D viewable guid:', guid);

const auth = new TwoLeggedAuthenticationProvider(CLIENT_ID, CLIENT_SECRET);
const reader = await SVFReader.FromDerivativeService(urn, guid, auth);
const scene = await reader.read({ log: (s) => process.stdout.write('.') });
console.log('\nSVF read 완료. glTF 작성…');
const writer = new GLTFWriter({ deduplicate: true, skipUnusedUvs: true, center: false, log: () => {} });
await writer.write(scene, outDir);
console.log('glTF →', outDir);
console.log('[!] 좌표 검증: 지형(EPSG 5186)과 정합되는지 확인. 오프셋 있으면 뷰어 origin 으로 보정.');
