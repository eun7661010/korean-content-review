// 한국어 렌더 도우미 — 화면에 그리는 단계에서만 쓴다. DB 원문·meta·aria-label·복사 페이로드는 건드리지 않는다.
//
// 1) koNoBreakSegments(text): '(가)와'·'〈보기〉에서'·'㉠은'·'‘나’는'·'45%였다'·'수능·모의고사'·'45 문항' 같은
//    짧은 묶음을 찾아 { text, nobreak } 조각으로 나눈다. 웹에서는 nobreak 조각을 <span class="whitespace-nowrap">으로 감싼다.
//    글자를 끼워 넣지 않으므로 복사·검색 결과가 바뀌지 않는다.
// 2) insertWordJoiners(text): Android RN Text 전용. 한글이 낀 어절 안에 U+2060(WORD JOINER)을 넣어 음절 단위 줄바꿈을 막는다.
//    URL·이메일·코드처럼 보이는 토큰은 건너뛴다. 복사·접근성 낭독은 실기기로 확인한다(references/react-native.md).
//
// 자체 시험: node ko-nobreak.mjs --selftest

const JOSA = [
  '에서는', '에서도', '으로는', '으로서', '으로써', '이라고', '이라는', '이었다', '이라서',
  '에서', '에게', '께서', '부터', '까지', '처럼', '보다', '이나', '이며', '이다', '이고', '이란', '라고', '라는',
  '였다', '였고', '에는', '에도', '와는', '과는', '와의', '과의', '로는', '로서', '조차', '마저', '만큼', '대로', '으로', '입니다',
  '은', '는', '이', '가', '을', '를', '의', '에', '와', '과', '도', '만', '로', '나', '란', '뿐', '인',
].join('|');
const UNITS = '문항|문제|지문|명|개|회|강|점|등급|시간|분|원|권|쪽|주차|교시|세트';
const MAX_GROUP = 16; // 이보다 긴 묶음은 nowrap이 넘침을 만들 수 있어 묶지 않는다

const PATTERNS = [
  // 괄호·꺾쇠·따옴표 묶음(+각주 *)(+조사): (가)와 〈보기〉에서 [A]에서 「춘향전」에서 ‘나’는 “나”는
  // 앞에 붙은 어절도 함께 묶는다: 혼백(魂魄)조차 · 침변(枕邊)*에 · 건덕궁(乾德宮)에
  new RegExp(`[가-힣A-Za-z0-9]{0,8}[(\\[〈《「『‘“][^\\s()\\[\\]〈〉《》「」『』‘’“”]{1,10}[)\\]〉》」』’”]\\*?(?:${JOSA})`, 'g'),
  // 원문자(+조사): ㉠은 ⓐ와 ①에서
  new RegExp(`[①-⑳❶-❿㉠-㉿ⓐ-ⓩ](?:${JOSA})`, 'g'),
  // 퍼센트(+조사·서술격): 45%였다 30%의
  new RegExp(`\\d[\\d,.]*%(?:${JOSA})`, 'g'),
  // 가운뎃점 묶음: 수능·모의고사 (등급컷·운영·독서·문학) — 괄호째로 묶는다
  /[(\[]?[가-힣A-Za-z0-9]{1,8}(?:·[가-힣A-Za-z0-9]{1,8}){1,4}[)\]]?/g,
  // 띄어 쓴 숫자+단위(+조사): 45 문항으로
  new RegExp(`\\d[\\d,.]* (?:${UNITS})(?:${JOSA})?(?![가-힣])`, 'g'),
];

export function koNoBreakSegments(text) {
  if (!text) return [];
  const marks = [];
  for (const re of PATTERNS) {
    re.lastIndex = 0;
    for (let m; (m = re.exec(text));) {
      if (m[0].length <= MAX_GROUP) marks.push([m.index, m.index + m[0].length]);
    }
  }
  marks.sort((a, b) => a[0] - b[0] || b[1] - a[1]);
  const merged = [];
  for (const [s, e] of marks) {
    const last = merged[merged.length - 1];
    if (last && s < last[1]) { last[1] = Math.max(last[1], e); continue; }
    merged.push([s, e]);
  }
  const out = []; let pos = 0;
  for (const [s, e] of merged) {
    if (s > pos) out.push({ text: text.slice(pos, s), nobreak: false });
    out.push({ text: text.slice(s, e), nobreak: true });
    pos = e;
  }
  if (pos < text.length) out.push({ text: text.slice(pos), nobreak: false });
  return out;
}

const WJ = String.fromCharCode(0x2060);
const HAN = /[가-힣ㄱ-ㅎㅏ-ㅣ]/;
const SKIP_TOKEN = /^(https?:|www\.)|@|[/\\]|^[`<]/;

export function insertWordJoiners(text) {
  if (!text || !HAN.test(text)) return text;
  return text.split(/(\s+)/).map((tok) => {
    if (!tok || /^\s+$/.test(tok) || SKIP_TOKEN.test(tok) || !HAN.test(tok)) return tok;
    const chars = Array.from(tok);
    return chars.join(WJ);
  }).join('');
}

export function stripWordJoiners(text) {
  return text ? text.split(WJ).join('') : text;
}

if (process.argv.includes('--selftest')) {
  const show = (t) => koNoBreakSegments(t).map((s) => (s.nobreak ? `[${s.text}]` : s.text)).join('');
  const cases = [
    ['(가)와 (나)를 비교하라', '[(가)와] [(나)를] 비교하라'],
    ['〈보기〉에서 ㉠은 무엇인가', '[〈보기〉에서] [㉠은] 무엇인가'],
    ['정답률이 45%였다', '정답률이 [45%였다]'],
    ['이 강의는 (등급컷·운영·독서·문학) 순서다', '이 강의는 [(등급컷·운영·독서·문학)] 순서다'],
    ['총 45 문항으로 구성', '총 [45 문항으로] 구성'],
    ['‘나’는 이렇게 말했다', '[‘나’는] 이렇게 말했다'],
    ['그냥 평범한 문장입니다', '그냥 평범한 문장입니다'],
    ['넋이 싀여지어 혼백(魂魄)조차 흩어지고', '넋이 싀여지어 [혼백(魂魄)조차] 흩어지고'],
    ['꽃이 피어 침변(枕邊)*에 시드는 듯', '꽃이 피어 [침변(枕邊)*에] 시드는 듯'],
    ['(나)의 ‘반기실가’는 미래 상황', '[(나)의] [‘반기실가’는] 미래 상황'],
  ];
  let fail = 0;
  for (const [input, want] of cases) {
    const got = show(input);
    const ok = got === want; if (!ok) fail++;
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${input} → ${got}${ok ? '' : `  (기대: ${want})`}`);
  }
  const wj = insertWordJoiners('국어 공부는 https://ekkorean.com 에서');
  const okWj = stripWordJoiners(wj) === '국어 공부는 https://ekkorean.com 에서' && wj.includes('국' + WJ + '어') && wj.includes('https://ekkorean.com');
  console.log(`${okWj ? 'ok  ' : 'FAIL'} insertWordJoiners: 어절 안에만 WJ, URL 제외, strip으로 원복`);
  if (!okWj) fail++;
  process.exit(fail ? 1 : 0);
}
