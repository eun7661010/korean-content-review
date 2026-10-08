import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { test } from 'node:test';

const require = createRequire(import.meta.url);
const playwright = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fixture = new URL('../skills/korean-line-break/scripts/fixture.html', import.meta.url);
const auditFile = new URL('../skills/korean-line-break/scripts/ko-wrap-audit.js', import.meta.url);

test('Chromium 400px: 기대 유형 검출, nowrap·keep-all+pretty 오탐 없음', async (t) => {
  const browser = await playwright.chromium.launch();
  try {
    const page = await browser.newPage({
      viewport: { width: 400, height: 900 }, locale: 'ko-KR', reducedMotion: 'reduce',
    });
    // 픽스처 외의 요청은 차단한다. 폰트와 기대값은 픽스처 원문 그대로 사용한다.
    await page.route('**/*', (route) => route.request().url().startsWith('file:')
      ? route.continue() : route.abort());
    await page.goto(fixture.href, { waitUntil: 'load' });
    const source = await readFile(auditFile, 'utf8');
    const result = await page.evaluate(`(${source})({ root: 'body' })`);
    assert.equal(result.vw, 400);
    assert.equal(result.truncated, false, '글자 수 한도로 검사가 잘리지 않아야 한다');
    assert.ok(result.scannedChars > 0, '실제 렌더된 글자가 있어야 한다');
    const expected = ['mid-eojeol', 'josa-head', 'overflow', 'orphan', 'num-unit', 'control-wrapped'];
    for (const type of expected) {
      const count = result.issues.filter((issue) => issue.type === type).length;
      t.diagnostic(`${type}: ${count}건`);
      assert.ok(count >= 1, `${type} 유형이 1건 이상 검출되어야 한다`);
    }
    for (const id of ['k4', 'k6', 'c2']) {
      assert.equal(await page.locator(`#${id}`).count(), 1, `#${id} 픽스처가 있어야 한다`);
      const violations = result.issues.filter((issue) =>
        new RegExp(`#${id}(?=$|[\\s.>:#\\[])`).test(issue.sel));
      assert.deepEqual(violations, [], `#${id}에는 심각도와 관계없이 위반이 없어야 한다`);
    }
  } finally {
    await browser.close();
  }
});
