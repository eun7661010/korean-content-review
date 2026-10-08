#!/usr/bin/env node
// 한국어 줄바꿈 동적 검사 실행기 — 페이지 × 폭 × 엔진 매트릭스로 ko-wrap-audit.js를 돌린다.
//
// 사용:
//   node ko-wrap-check.mjs <url|파일>... [--widths 320,390,768,1440] [--engines chromium,webkit,firefox]
//        [--root body] [--out report.json] [--baseline base.json] [--update-baseline]
//        [--shots dir] [--storage-state auth.json] [--fail-on error|warn|none] [--max-show 8]
//        [--ignore '<CSS 선택자>']  작품 원문처럼 검사하지 않을 컨테이너(예: '.work-verse, [data-original-text]')
//
// Playwright는 현재 폴더(프로젝트)의 node_modules에서 찾는다(playwright 또는 @playwright/test).
// 다른 위치면 PLAYWRIGHT_MODULE=<경로>를 준다. WebKit·Firefox가 없으면 `npx playwright install webkit firefox`.
// --baseline: 기존 부채를 고정하고 새로 생긴 error만 실패로 센다(래칫). --update-baseline으로 갱신한다.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const flags = {}; const targets = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a.startsWith('--')) {
    const k = a.slice(2);
    if (['update-baseline'].includes(k)) flags[k] = true;
    else flags[k] = argv[++i];
  } else targets.push(a);
}
if (!targets.length) {
  console.error('사용: node ko-wrap-check.mjs <url|파일>... [--widths 320,390,768,1440] [--engines chromium,webkit,firefox] [--baseline f] [--out f]');
  process.exit(2);
}
const widths = (flags.widths || '320,390,768,1440').split(',').map(Number);
const engines = (flags.engines || 'chromium').split(',');
const failOn = flags['fail-on'] || 'error';
const maxShow = Number(flags['max-show'] || 8);

function loadPlaywright() {
  const tries = [];
  if (process.env.PLAYWRIGHT_MODULE) tries.push(process.env.PLAYWRIGHT_MODULE);
  tries.push('playwright', '@playwright/test');
  const req = createRequire(path.join(process.cwd(), 'noop.js'));
  for (const t of tries) { try { return req(t); } catch {} }
  console.error('Playwright를 찾지 못했습니다. 프로젝트 폴더에서 실행하거나 PLAYWRIGHT_MODULE을 지정하세요.');
  process.exit(2);
}
const pw = loadPlaywright();
const src = fs.readFileSync(path.join(here, 'ko-wrap-audit.js'), 'utf8');
const toUrl = (t) => (/^(https?|file):/.test(t) ? t : 'file:///' + path.resolve(t).replace(/\\/g, '/'));
const BLOCK = /google-analytics|googletagmanager|facebook\.net|doubleclick|clarity\.ms|_vercel\/(insights|speed)|wcs\.naver|kakao.*pixel|t1\.daumcdn|hotjar|mixpanel|amplitude|segment\.io/;

const results = [];
for (const engine of engines) {
  let browser;
  try { browser = await pw[engine].launch(); } catch (e) {
    console.warn(`[skip] ${engine} 실행 실패: ${String(e.message).split('\n')[0]}`);
    continue;
  }
  const version = browser.version();
  for (const t of targets) {
    for (const vw of widths) {
      const ctx = await browser.newContext({
        viewport: { width: vw, height: 900 }, reducedMotion: 'reduce', locale: 'ko-KR',
        ...(flags['storage-state'] ? { storageState: flags['storage-state'] } : {}),
      });
      const page = await ctx.newPage();
      await page.route(BLOCK, (r) => r.abort());
      const url = toUrl(t);
      try {
        await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
        const t0 = Date.now();
        const res = await page.evaluate(`(${src})(${JSON.stringify({ root: flags.root || 'body', ignore: flags.ignore || '' })})`);
        res.ms = Date.now() - t0; res.engine = engine; res.engineVersion = version; res.target = t;
        if (flags.shots) {
          fs.mkdirSync(flags.shots, { recursive: true });
          const name = `${engine}-${vw}-${t.replace(/^https?:\/\//, '').replace(/[^\w.-]+/g, '_').slice(0, 60)}.png`;
          await page.screenshot({ path: path.join(flags.shots, name), fullPage: true });
          res.shot = path.join(flags.shots, name);
        }
        results.push(res);
      } catch (e) {
        results.push({ target: t, engine, vw, error: String(e.message).split('\n')[0], issues: [], counts: {} });
      }
      await ctx.close();
    }
  }
  await browser.close();
}

const keyOf = (r, i) => [r.engine, r.vw, r.target, i.type, i.sel, i.snip || i.text || ''].join('|');
let baseline = null;
if (flags.baseline && fs.existsSync(flags.baseline)) baseline = new Set(JSON.parse(fs.readFileSync(flags.baseline, 'utf8')));

const rank = { error: 3, warn: 2, info: 1 };
let failing = 0;
console.log('\n한국어 줄바꿈 검사 결과');
for (const r of results) {
  const head = `${r.engine} ${r.vw}px ${r.target}`;
  if (r.error) { console.log(`\n■ ${head}\n  실행 오류: ${r.error}`); failing++; continue; }
  const sum = ['error', 'warn', 'info'].map((s) => `${s} ${r.issues.filter((i) => i.sev === s).length}`).join(' · ');
  console.log(`\n■ ${head} — ${sum}${r.truncated ? ' (글자 수 한도로 일부만 검사)' : ''}`);
  const shown = r.issues.filter((i) => i.sev !== 'info').sort((a, b) => rank[b.sev] - rank[a.sev]);
  for (const i of shown.slice(0, maxShow)) {
    const isNew = baseline ? !baseline.has(keyOf(r, i)) : true;
    console.log(`  ${i.sev.padEnd(5)} ${i.type.padEnd(18)} ${(i.snip || i.text || '').replace(/\s+/g, ' ')}${i.px ? ` (+${i.px}px)` : ''}  ← ${i.sel}${baseline && !isNew ? '  [기존]' : ''}`);
  }
  if (shown.length > maxShow) console.log(`  … 외 ${shown.length - maxShow}건(--out으로 전체 저장)`);
  for (const i of r.issues) {
    if (baseline && baseline.has(keyOf(r, i))) continue;
    if (failOn === 'none') continue;
    if (rank[i.sev] >= rank[failOn]) failing++;
  }
}
if (flags.out) { fs.writeFileSync(flags.out, JSON.stringify(results, null, 1)); console.log(`\n전체 결과: ${flags.out}`); }
if (flags['update-baseline'] && flags.baseline) {
  const keys = results.flatMap((r) => (r.issues || []).filter((i) => i.sev !== 'info').map((i) => keyOf(r, i)));
  fs.writeFileSync(flags.baseline, JSON.stringify([...new Set(keys)].sort(), null, 1));
  console.log(`기준선 갱신: ${flags.baseline} (${keys.length}건)`);
  failing = 0;
}
console.log(`\n판정: ${failing ? `실패 — ${failOn} 이상 ${baseline ? '신규 ' : ''}${failing}건` : '통과'}`);
process.exit(failing ? 1 : 0);
