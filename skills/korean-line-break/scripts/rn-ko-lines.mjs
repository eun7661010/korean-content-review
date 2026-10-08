// React Native 개발 빌드용 줄바꿈 감사 — 공용 T의 onTextLayout에서 e.nativeEvent.lines를 넘긴다.
// lines[].text는 RN 0.86 CoreEventTypes.js(TextLayoutLine)에 있지만 공식 문서에는 없다. 줄 끝 공백·개행 포함 여부는 실기기로 확인한다.
// Jest·Expo web으로는 줄바꿈을 판정하지 않는다(레이아웃이 없거나 브라우저가 줄을 바꾼다).
//
// 사용(TypeScript 프로젝트에 복사해 쓴다):
//   onTextLayout={__DEV__ ? (e) => { const out = auditKoLines(e.nativeEvent.lines); if (out.length) console.warn('[ko-wrap]', out); } : undefined}
// 자체 시험: node rn-ko-lines.mjs --selftest

const HAN = /[가-힣]/;
const CIRC = /[①-⑳❶-❿㉠-㉿ⓐ-ⓩ]/;
const CLOSE_TAIL = /[)\]」』》〉”’%…]$/;
const JOSA = /^(은|는|이|가|을|를|의|에|에서|에게|와|과|도|만|로|으로|부터|까지|처럼|보다|라고|라는|였다|이다|입니다)(?![가-힣])/;
const UNIT = /^(문항|문제|지문|개|명|회|강|점|등급|일|시간|분|원|권|쪽|%)/;

export function auditKoLines(lines, boxWidth) {
  const out = [];
  for (let k = 1; k < lines.length; k++) {
    const A = lines[k - 1].text, B = lines[k].text;
    if (/\n$/.test(A)) continue; // 사용자 개행
    const At = A.trimEnd(), Bt = B.trimStart();
    const spaced = /\s$/.test(A) || /^\s/.test(B);
    const a = At.slice(-1), b = Bt[0] ?? '';
    const snip = `${At.slice(-8)}⏎${Bt.slice(0, 8)}`;
    if (/^[.,!?:;)\]」』》”’·%]/.test(Bt)) out.push(`punct-head ${snip}`);
    if (/[(\[「『《“‘]$/.test(At)) out.push(`punct-tail ${snip}`);
    const lastTok = At.split(/\s/).pop() ?? '';
    if (/\d$/.test(At) && UNIT.test(Bt)) out.push(`num-unit ${snip}`);
    else if (!spaced && JOSA.test(Bt) && (CLOSE_TAIL.test(At) || CIRC.test(a) || (HAN.test(a) && [...lastTok].length >= 2))) out.push(`josa-head ${snip}`);
    else if (!spaced && !/^[(\[「『《“‘]/.test(b) && (HAN.test(a) || HAN.test(b))) out.push(`mid-eojeol ${snip}`);
  }
  const n = lines.length;
  if (n > 1) {
    const last = lines[n - 1], t = last.text.trim(), maxW = Math.max(...lines.map((l) => l.width));
    if (!/\n$/.test(lines[n - 2].text) && ([...t].length <= 2 || (!/\s/.test(t) && last.width < maxW * 0.2))) out.push(`orphan ${t}`);
  }
  if (boxWidth && lines.some((l) => l.width > boxWidth + 1)) out.push('overflow');
  return out;
}

if (process.argv.includes('--selftest')) {
  const L = (...rows) => rows.map(([text, width]) => ({ text, width }));
  const cases = [
    [L(['국어 공부는 매일 꾸준히 하', 200], ['는 학생이 이깁니다', 150]), 'mid-eojeol'],
    [L(['비교해 보면 (가)', 200], ['와 (나)는 다르다', 150]), 'josa-head'],
    [L(['정답률이 45', 200], ['%였다', 40]), 'punct-head'],
    [L(['총 45', 200], ['문항입니다', 80]), 'num-unit'],
    [L(['매일 지문 하나를 끝까지 읽어 ', 200], ['내면 됩', 60], ['다', 12]), 'orphan'],
    [L(['국어 공부는 매일 꾸준히 ', 200], ['하는 학생이 이깁니다', 180]), null],
  ];
  let fail = 0;
  for (const [lines, want] of cases) {
    const got = auditKoLines(lines);
    const ok = want ? got.some((x) => x.startsWith(want)) : got.length === 0;
    if (!ok) fail++;
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${lines.map((l) => l.text).join('⏎')} → ${got.join(', ') || '위반 없음'}`);
  }
  process.exit(fail ? 1 : 0);
}
