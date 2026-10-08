#!/usr/bin/env node
// 한국어 줄바꿈 정적 검사 — 코드에서 "규칙이 빠졌거나 잘못 쓰인 곳"을 찾는다. 실제 줄은 동적 검사(ko-wrap-check.mjs)로 판정한다.
//
// 사용: node ko-wrap-static.mjs [경로...] [--json out.json] [--max 10] [--strict] [--include-tests] [--rn-text-wrapper components/ui.tsx]
// 규칙 정의와 근거: ../references/qa-detector.md (S 규칙)
import fs from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
const flags = {}; const roots = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a.startsWith('--')) {
    const k = a.slice(2);
    if (['strict', 'include-tests'].includes(k)) flags[k] = true; else flags[k] = argv[++i];
  } else roots.push(a);
}
if (!roots.length) roots.push('.');
const MAX = Number(flags.max || 10);
const RN_WRAPPER = (flags['rn-text-wrapper'] || 'components/ui.tsx').replace(/\\/g, '/');
const SKIP_DIR = new Set(['node_modules', '.next', '.git', 'dist', 'build', 'out', '.pnpm-store', 'coverage', '.turbo', '.vercel', '.expo', 'ios', 'android', '.tmp']);
const EXT = new Set(['.tsx', '.jsx', '.ts', '.js', '.mjs', '.css', '.html', '.mdx']);
const isTest = (p) => /(\.test\.|\.spec\.|__tests__|\/tests?\/|\/e2e\/)/.test(p);

const files = [];
function walk(p) {
  let st; try { st = fs.statSync(p); } catch { return; }
  if (st.isDirectory()) {
    if (SKIP_DIR.has(path.basename(p))) return;
    for (const n of fs.readdirSync(p)) walk(path.join(p, n));
  } else if (EXT.has(path.extname(p)) && !/\.min\.(js|css)$/.test(p) && st.size < 2_000_000) {
    const rel = p.replace(/\\/g, '/');
    if (!flags['include-tests'] && isTest(rel)) return;
    files.push(rel);
  }
}
roots.forEach(walk);

const RULES = {
  'break-all-ko': ['warn', 'break-all은 한글을 음절마다 끊는다. ASCII 전용 칸(ID·해시·토큰)에만 쓰고 나머지는 wrap-anywhere(또는 wrap-break-word)로 바꾼다'],
  'break-all-links': ['info', '[&_a]:break-all — 링크가 URL이면 허용. 링크 글자가 한국어일 수 있으면 [&_a]:wrap-anywhere로 바꾼다'],
  'break-word-deprecated': ['error', 'word-break: break-word는 비권장 값이다 → overflow-wrap: anywhere(+keep-all 유지)'],
  'line-break-anywhere': ['error', 'line-break: anywhere는 keep-all·NBSP·WJ·nowrap을 모두 무시한다. 쓰지 않는다'],
  'auto-phrase': ['info', 'word-break: auto-phrase는 한국어에서 keep-all과 결과가 같고 Chrome 전용이다. keep-all을 기준으로 둔다'],
  'wrap-shorthand-conflict': ['warn', 'text-balance/text-pretty(단축 속성 text-wrap)와 truncate/whitespace-nowrap을 한 요소에 같이 쓰면 순서에 따라 nowrap이 풀린다'],
  'pre-on-markdown': ['warn', 'pre-line/pre-wrap을 마크다운·HTML 출력 컨테이너에 걸면 태그 사이 개행이 빈 줄로 살아난다. 평문을 직접 담은 요소에만 쓴다'],
  'pre-without-wrap': ['warn', 'pre-line/pre-wrap에는 긴 URL 대비 wrap-break-word(또는 wrap-anywhere)를 짝으로 붙인다'],
  'unlayered-wrap-css': ['warn', '줄바꿈 속성을 가진 단일 클래스가 @layer 밖에 있다 → Tailwind 유틸리티(truncate·whitespace-*·break-*)를 이긴다. @layer components로 옮긴다'],
  'layout-br': ['info', '<br>로 줄을 고정하면 폭이 바뀔 때 짧은 줄이 생긴다. 시처럼 의도된 줄바꿈이 아니면 balance로 대체한다'],
  'num-space-unit': ['info', '숫자와 단위를 띄어 썼다(keep-all도 공백에서는 끊는다) → 붙여 쓰거나 NBSP(렌더 단계)'],
  'html-lang': ['warn', '<html>에 lang="ko"가 없다'],
  'no-global-keep-all': ['warn', 'Tailwind 진입 CSS에 keep-all 전역 기본값이 없다(@layer base body)'],
  'rn-direct-text': ['warn', "react-native Text를 직접 import한다 → 공용 T(hangul-word 등)를 거치게 하고 ESLint no-restricted-imports로 막는다"],
  'rn-balanced-body': ['info', "textBreakStrategy='balanced'는 어절 보호가 아니다. 제목에만 쓰고 본문은 기본값 highQuality"],
  'rn-textinput-no-hangul': ['info', "TextInput에 lineBreakStrategyIOS='hangul-word'가 없다(공용 Input으로 통일)"],
};
const hits = Object.fromEntries(Object.keys(RULES).map((k) => [k, []]));
const hit = (rule, file, line, text) => hits[rule].push({ file, line, text: String(text).trim().slice(0, 140) });

const HANGUL = /[가-힣]/;
// {job.id}·{row.trace_id}·{lc.url}·href={...permalink}처럼 ASCII 값만 담는 칸으로 보이는 break-all은 허용한다
const ASCII_CELL = /\{[\w.?!]*(\.id|_id|Id|uuid|hash|token|url|Url|URL|key|email|path|sha|slug|permalink)\b[^}]*\}/;
const UNITS = '문항|문제|지문|명|개|회|강|점|등급|시간|분|원|권|쪽|주차|교시|세트';
const NUM_UNIT = new RegExp(`\\d (${UNITS})(?:으로|에서|까지|부터|[은는이가을를의에와과도만로])?(?![가-힣])`);

// 괄호(:is()·:where()) 안의 쉼표는 건너뛰고 최상위 쉼표로만 선택자 목록을 나눈다
function splitTop(sel) {
  const out = []; let depth = 0, cur = '';
  for (const ch of sel) {
    if (ch === '(') depth++; else if (ch === ')') depth--;
    if (ch === ',' && depth === 0) { out.push(cur.trim()); cur = ''; } else cur += ch;
  }
  out.push(cur.trim());
  return out;
}

function scanCss(file, src) {
  const clean = src.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
  const stack = []; let last = 0;
  const lineAt = (i) => clean.slice(0, i).split('\n').length;
  for (let i = 0; i < clean.length; i++) {
    const c = clean[i];
    if (c === '{') { stack.push({ prelude: clean.slice(last, i).split(/[;}]/).pop().trim(), start: i + 1 }); last = i + 1; }
    else if (c === '}') {
      const blk = stack.pop(); last = i + 1;
      if (!blk) continue;
      const pre = blk.prelude;
      if (pre.startsWith('@')) continue;
      const inLayer = stack.some((b) => /^@layer\b/.test(b.prelude));
      const body = clean.slice(blk.start, i);
      if (inLayer || !/(word-break|text-wrap|white-space|overflow-wrap|line-break)\s*:/.test(body)) continue;
      const sels = splitTop(pre);
      if (sels.some((s) => /^\.[A-Za-z][\w-]*$/.test(s))) hit('unlayered-wrap-css', file, lineAt(blk.start), pre.replace(/\s+/g, ' '));
    }
  }
  if (/@import\s+["']tailwindcss["']/.test(src) && !/keep-all/.test(src)) hit('no-global-keep-all', file, 1, '@import "tailwindcss"');
}

for (const file of files) {
  const src = fs.readFileSync(file, 'utf8');
  const ext = path.extname(file);
  const lines = src.split(/\r?\n/);
  if (ext === '.css') scanCss(file, src);
  const isMarkup = ['.tsx', '.jsx', '.html', '.mdx'].includes(ext);
  lines.forEach((l, idx) => {
    const n = idx + 1;
    if (/^\s*(\/\/|\/\*|\*|import\s)/.test(l)) return;
    if (/\bbreak-all\b|word-break\s*:\s*break-all/.test(l)) {
      if (/\[&_a\]:break-all/.test(l)) hit('break-all-links', file, n, l);
      else if (!/font-mono|tabular|data-ascii|\bmono\b|<code\b/.test(l) && !ASCII_CELL.test(l)) hit('break-all-ko', file, n, l);
    }
    if (/word-break\s*:\s*break-word|\[word-break:break-word\]/.test(l)) hit('break-word-deprecated', file, n, l);
    if (/line-break\s*:\s*anywhere|\[line-break:anywhere\]/.test(l)) hit('line-break-anywhere', file, n, l);
    if (/auto-phrase/.test(l)) hit('auto-phrase', file, n, l);
    if (/\btext-(balance|pretty)\b/.test(l) && /\b(truncate|whitespace-nowrap|text-nowrap)\b/.test(l)) hit('wrap-shorthand-conflict', file, n, l);
    const pre = /whitespace-pre-(line|wrap)\b|white-space\s*:\s*pre-(line|wrap)|whiteSpace\s*:\s*['"]pre-(line|wrap)/.test(l);
    if (pre) {
      const win = lines.slice(idx, idx + 4).join('\n');
      if (/dangerouslySetInnerHTML|<(React)?Markdown\b|renderMarkdown|markdownTo(Html|HTML)|\bprose\b/.test(win)) hit('pre-on-markdown', file, n, l);
      else if (!/wrap-break-word|wrap-anywhere|break-words|break-all|overflow-wrap|overflowWrap|ko-user-text/.test(l)) hit('pre-without-wrap', file, n, l);
    }
    if (isMarkup && /<br\s*\/?>/.test(l)) hit('layout-br', file, n, l);
    if (isMarkup && HANGUL.test(l) && NUM_UNIT.test(l)) hit('num-space-unit', file, n, l);
    if (/<html[\s>]/.test(l) && !/lang=\{?["']ko/.test(lines.slice(idx, idx + 3).join(' '))) hit('html-lang', file, n, l);
    if (/textBreakStrategy\s*[=:]\s*\{?\s*["']balanced/.test(l)) hit('rn-balanced-body', file, n, l);
  });
  if (/from\s+["']react-native["']/.test(src)) {
    const m = src.match(/import\s*\{([^}]*)\}\s*from\s*["']react-native["']/g) || [];
    if (m.some((x) => /\bText\b/.test(x)) && !file.endsWith(RN_WRAPPER)) hit('rn-direct-text', file, 1, m.find((x) => /\bText\b/.test(x)).replace(/\s+/g, ' '));
    if (/<TextInput\b/.test(src) && !/lineBreakStrategyIOS/.test(src)) hit('rn-textinput-no-hangul', file, src.split(/\r?\n/).findIndex((x) => /<TextInput\b/.test(x)) + 1, '<TextInput');
  }
}

const order = { error: 0, warn: 1, info: 2 };
const report = Object.entries(hits).filter(([, v]) => v.length).sort((a, b) => order[RULES[a[0]][0]] - order[RULES[b[0]][0]] || b[1].length - a[1].length);
console.log(`한국어 줄바꿈 정적 검사 — 파일 ${files.length}개`);
for (const [rule, list] of report) {
  const [sev, msg] = RULES[rule];
  console.log(`\n[${sev}] ${rule} ${list.length}건 — ${msg}`);
  for (const h of list.slice(0, MAX)) console.log(`  ${h.file}:${h.line}  ${h.text}`);
  if (list.length > MAX) console.log(`  … 외 ${list.length - MAX}건`);
}
if (!report.length) console.log('위반 없음');
if (flags.json) fs.writeFileSync(flags.json, JSON.stringify(Object.fromEntries(report.map(([k, v]) => [k, { sev: RULES[k][0], count: v.length, hits: v }])), null, 1));
const errors = report.filter(([k]) => RULES[k][0] === 'error').reduce((s, [, v]) => s + v.length, 0);
console.log(`\n요약: ${report.map(([k, v]) => `${k} ${v.length}`).join(' · ') || '0건'}`);
process.exit(flags.strict && errors ? 1 : 0);
