async (opts = {}) => {
  // 한국어 줄바꿈 자동 검사(브라우저 함수). page.evaluate(`(${src})(${JSON.stringify(opts)})`)로 실행한다.
  // 렌더된 글자마다 Range.getClientRects()로 위치를 재서 줄을 복원하고 규칙을 판정한다.
  // 규칙 정의와 근거: ../references/qa-detector.md
  const o = { root: 'body', maxChars: 60000, orphanChars: 2, orphanRatio: 0.2, orphanMinChars: 12, maxIssues: 300, ...opts };
  if (document.fonts) await document.fonts.ready;
  const WS = /[\t\n\f\r \u1680\u2000-\u200a\u2028\u2029\u205f\u3000]/; // NBSP(U+00A0)는 끊을 수 없는 자리라 공백으로 세지 않는다
  const HAN = /[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]/;
  const CIRC = /[\u2460-\u2473\u2776-\u277f\u3260-\u327f\u24d0-\u24e9]/; // ①~⑳ ❶~❿ ㉠~㉿ ⓐ~ⓩ
  const CLOSE = /^[.,!?:;)\]}»」』》〉】〕”’…%、。·]/;
  const CLOSE_TAIL = /[)\]}»」』》〉】〕”’%…!?.]$/;
  const OPEN = /[(\[{«「『《〈【〔“‘]$/;
  const JOSA = [
    '에서는', '에서도', '으로는', '으로서', '으로써', '이라고', '이라는', '이었다', '이었고', '께서는', '이라서',
    '에서', '에게', '께서', '부터', '까지', '처럼', '보다', '이나', '이며', '이다', '이고', '이란', '라고', '라는',
    '였다', '였고', '에는', '에도', '와는', '과는', '와의', '과의', '로는', '로서', '로써', '조차', '마저', '밖에',
    '만큼', '대로', '하고', '이랑', '라서', '으로', '한테', '에게서', '입니다', '이에요', '예요',
    '은', '는', '이', '가', '을', '를', '의', '에', '께', '와', '과', '도', '만', '로', '나', '며', '요', '씩', '째', '란', '랑', '뿐', '인', '임',
  ].join('|');
  const JOSA_RE = new RegExp(`^(${JOSA})[.,!?)\\]」』》〉”’]*$`);
  const UNIT_RE = new RegExp(`^(%|점|문항|번|개|명|회|차|일|월|년|시|분|초|시간|주|주차|강|권|쪽|장|등급|학년도?|원|만|천|억|세|살|교시|편|세트|위|배|km|kg|cm|mm|MB|GB)(${JOSA})?[.,!?)]*$`);
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION', 'CODE', 'PRE', 'KBD', 'SAMP', 'RT', 'RP', 'IFRAME', 'CANVAS', 'VIDEO', 'AUDIO', 'IMG', 'PICTURE', 'OBJECT']);
  const XHTML = 'http://www.w3.org/1999/xhtml';
  // Firefox처럼 text-wrap pretty를 지원하지 않는 엔진에서는 외톨이 줄을 info로 낮춘다
  const prettyOK = !!(window.CSS && (CSS.supports('text-wrap-style', 'pretty') || CSS.supports('text-wrap', 'pretty')));
  const segr = typeof Intl !== 'undefined' && Intl.Segmenter ? new Intl.Segmenter('ko', { granularity: 'grapheme' }) : null;
  const graphemes = (s) => {
    if (segr) return Array.from(segr.segment(s), (x) => [x.segment, x.index]);
    let i = 0; return Array.from(s, (c) => { const r = [c, i]; i += c.length; return r; });
  };
  const sel = (el) => {
    const p = [];
    for (let e = el; e && e !== document.documentElement && p.length < 4; e = e.parentElement) {
      let t = e.tagName.toLowerCase();
      if (e.id) { p.unshift(`${t}#${e.id}`); break; }
      const c = [...e.classList].filter((x) => !/[:\[\]\/()%.]/.test(x)).slice(0, 2);
      if (c.length) t += '.' + c.join('.');
      p.unshift(t);
    }
    return p.join(' > ');
  };
  const visible = (el) => {
    if (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true, checkOpacity: true, checkVisibilityCSS: true })) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false; // sr-only·접힌 요소
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue;
      const q = a.getBoundingClientRect();
      if (q.width < 1 || q.height < 1 || r.right <= q.left || r.left >= q.right || r.bottom <= q.top || r.top >= q.bottom) return false; // 잘려서 안 보임(캐러셀·아코디언)
    }
    return true;
  };

  // 1) 블록 컨테이너별로 글자 스트림을 모은다. 인라인 요소 경계는 넘고, 원자 인라인·블록 경계는 'atomic'으로 끊는다.
  const streams = []; let budget = o.maxChars; const range = document.createRange();
  const newStream = (el, cs) => { const s = { el, cs, items: [] }; streams.push(s); return s; };
  function addText(node, s) {
    const ws = getComputedStyle(node.parentElement).whiteSpace;
    const keepNL = ws.startsWith('pre') || ws === 'break-spaces';
    for (const [g, i] of graphemes(node.data)) {
      if (g === '\u200b' || g === '\u00ad') { s.items.push({ sep: 'soft' }); continue; }
      if (WS.test(g)) { s.items.push({ sep: g === '\n' && keepNL ? 'forced' : 'space' }); continue; }
      range.setStart(node, i); range.setEnd(node, i + g.length);
      // 줄 경계 글자는 WebKit이 앞 줄 끝에 폭 0 사각형을 먼저 돌려준다 → 폭이 가장 큰 사각형을 쓴다
      let r = null;
      for (const q of range.getClientRects()) if (q.width > 0 && (!r || q.width > r.width)) r = q;
      if (!r) continue;
      s.items.push({ g, r });
      if (--budget <= 0) return;
    }
  }
  function walk(el, s) {
    for (const n of el.childNodes) {
      if (budget <= 0) return;
      if (n.nodeType === 3) { addText(n, s); continue; }
      if (n.nodeType !== 1) continue;
      if (n.tagName === 'BR') { s.items.push({ sep: 'forced' }); continue; }
      if (n.tagName === 'WBR') { s.items.push({ sep: 'soft' }); continue; }
      if (n.namespaceURI !== XHTML || SKIP.has(n.tagName) || n.isContentEditable || (n.dataset && n.dataset.wrapAudit === 'ignore') || (o.ignore && n.matches(o.ignore))) { s.items.push({ sep: 'atomic' }); continue; }
      const cs = getComputedStyle(n);
      if (cs.display === 'none') continue;
      if (cs.display === 'contents') { walk(n, s); continue; }
      if (cs.display === 'inline') {
        if (cs.visibility !== 'visible' || cs.opacity === '0') { s.items.push({ sep: 'atomic' }); continue; }
        walk(n, s); continue;
      }
      s.items.push({ sep: 'atomic' });
      if (visible(n) && cs.writingMode === 'horizontal-tb' && cs.direction === 'ltr') walk(n, newStream(n, cs));
    }
  }
  const rootEl = document.querySelector(o.root) || document.body;
  walk(rootEl, newStream(rootEl, getComputedStyle(rootEl)));

  // 2) 글자 사각형으로 줄을 복원한다(가로쓰기·LTR 전제).
  function toLines(items) {
    const lines = []; let cur = null, prev = null, gap = null;
    for (const it of items) {
      if (it.sep) { gap = gap || {}; gap[it.sep] = true; continue; }
      const r = it.r;
      const wrapped = prev && r.top > prev.r.top + prev.r.height * 0.5 && r.left <= prev.r.left + 1;
      it.spaceBefore = !!(gap && (gap.space || gap.forced));
      it.boundBefore = !!(gap && (gap.atomic || gap.soft));
      if (!cur || wrapped || (gap && gap.forced)) { cur = { items: [], forced: !cur || !!(gap && gap.forced) }; lines.push(cur); }
      cur.items.push(it); prev = it; gap = null;
    }
    for (const L of lines) {
      L.left = Math.min(...L.items.map((x) => x.r.left));
      L.right = Math.max(...L.items.map((x) => x.r.right));
      L.text = L.items.map((x, i) => (i && x.spaceBefore ? ' ' : '') + x.g).join('');
    }
    return lines;
  }
  const lastTok = (L) => { let t = ''; for (let i = L.items.length - 1; i >= 0; i--) { t = L.items[i].g + t; if (L.items[i].spaceBefore || L.items[i].boundBefore) break; } return t; };
  const firstTok = (L) => { let t = ''; for (let i = 0; i < L.items.length; i++) { if (i && (L.items[i].spaceBefore || L.items[i].boundBefore)) break; t += L.items[i].g; } return t; };

  // 3) 규칙 판정
  const issues = [];
  const add = (type, sev, s, extra) => issues.push({ type, sev, sel: sel(s.el), wordBreak: s.cs.wordBreak, ...extra });
  const CTL = 'button, [role=button], [role=tab], label, th, nav a, [class*=badge], [class*=chip], [class*=btn]';
  for (const s of streams) {
    const cs = s.cs; const er = s.el.getBoundingClientRect();
    let items = s.items; let clamped = false;
    if (cs.overflowY !== 'visible') { // line-clamp·고정 높이: 잘린 줄은 판정에서 뺀다
      const bottom = er.bottom - parseFloat(cs.paddingBottom) - parseFloat(cs.borderBottomWidth);
      const kept = items.filter((x) => x.sep || x.r.top < bottom - 1);
      clamped = kept.length !== items.length; items = kept;
    }
    const lines = toLines(items);
    if (!lines.length) continue;
    const contentRight = er.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth);
    if (!/auto|scroll/.test(cs.overflowX)) {
      const over = lines.find((L) => L.right > contentRight + 1);
      if (over) add(cs.textOverflow === 'ellipsis' ? 'truncated' : 'overflow', cs.textOverflow === 'ellipsis' ? 'info' : 'error', s, { text: over.text.slice(0, 40), px: Math.round(over.right - contentRight) });
    }
    if (lines.length < 2 || !items.some((x) => x.g && HAN.test(x.g))) continue;
    if (s.el.matches(CTL)) add('control-wrapped', 'warn', s, { text: lines.map((L) => L.text).join(' ⏎ ').slice(0, 60) });
    for (let k = 1; k < lines.length; k++) {
      const A = lines[k - 1], B = lines[k]; if (B.forced) continue;
      const a = A.items[A.items.length - 1], b = B.items[0];
      const lt = lastTok(A), rt = firstTok(B);
      const snip = `${A.text.slice(-12)}⏎${B.text.slice(0, 12)}`;
      if (CLOSE.test(b.g)) add('punct-head', 'error', s, { snip });
      else if (OPEN.test(a.g)) add('punct-tail', 'error', s, { snip });
      if (b.boundBefore || /^[(\[{«「『《〈【〔“‘]/.test(b.g) || /[-–—\/]$/.test(a.g)) continue; // <wbr>·ZWSP·원자 요소 경계, 여는 괄호 앞, 하이픈·슬래시 뒤는 의도된 끊김으로 본다
      if (!b.spaceBefore) {
        // 조사 줄머리는 word-break 값과 무관하게 판정한다. keep-all이어도 Chromium은 '(가)|와', '㉠|에서', '‘나’|는'으로 끊는다.
        const symbolBefore = CLOSE_TAIL.test(a.g) || CIRC.test(a.g);
        if (/\d$/.test(lt) && UNIT_RE.test(rt)) add('num-unit', 'error', s, { snip });
        else if (HAN.test(b.g) && JOSA_RE.test(rt) && (lt.length >= 2 || symbolBefore)) add('josa-head', 'error', s, { snip, afterSymbol: symbolBefore });
        else if (HAN.test(a.g) || HAN.test(b.g)) {
          if (cs.wordBreak === 'keep-all' || cs.wordBreak === 'auto-phrase') add('long-eojeol-split', 'warn', s, { snip });
          else add('mid-eojeol', 'error', s, { snip });
        } else if (/\p{L}|\d/u.test(a.g) && /\p{L}|\d/u.test(b.g)) add('word-split', 'info', s, { snip });
      } else if ((/\d$/.test(lt) && UNIT_RE.test(rt)) || (lt === '제' && /^\d/.test(rt))) add('num-unit', 'warn', s, { snip });
    }
    if (clamped) continue;
    const maxW = Math.max(...lines.map((L) => L.right - L.left));
    let seg = [];
    const segs = [];
    for (const L of lines) { if (L.forced && seg.length) { segs.push(seg); seg = []; } seg.push(L); }
    segs.push(seg);
    for (const sg of segs) {
      if (sg.length < 2) continue;
      // 12자 미만 짧은 라벨('이번 주⏎변화')은 좁은 칸에서 두 줄이 되는 것이 정상이라 외톨이로 보지 않는다
      if (sg.reduce((n, L) => n + L.items.length, 0) < o.orphanMinChars) continue;
      const L = sg[sg.length - 1];
      const oneTok = !L.items.slice(1).some((x) => x.spaceBefore);
      if (L.items.length <= o.orphanChars) add('orphan', prettyOK ? 'error' : 'info', s, { text: L.text });
      else if (oneTok && L.right - L.left < maxW * o.orphanRatio) add('orphan', prettyOK ? 'warn' : 'info', s, { text: L.text });
    }
    if (s.el.matches('h1, h2, h3, h4, .ko-heading') && lines.length <= 6) {
      const last = lines[lines.length - 1];
      if (last.right - last.left < maxW * 0.5 && cs.textWrapStyle !== 'balance' && cs.textWrap !== 'balance') add('heading-unbalanced', 'info', s, { text: lines.map((L) => L.text).join(' ⏎ ').slice(0, 60) });
    }
  }

  // 4) 페이지 가로 넘침(가장 깊은 원인 요소 5개). html에 overflow-x hidden·clip이 있으면 측정할 수 없으므로 알린다.
  const vw = document.documentElement.clientWidth;
  if (/hidden|clip/.test(getComputedStyle(document.documentElement).overflowX)) {
    issues.push({ type: 'page-overflow-unmeasurable', sev: 'info', sel: 'html', note: 'html overflow-x hidden/clip — overflow 항목으로 대신 판정' });
  } else if (document.documentElement.scrollWidth > vw + 1) {
    const off = [];
    for (const el of document.body.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.right <= vw + 1) continue;
      let clipped = false;
      for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) if (getComputedStyle(a).overflowX !== 'visible') { clipped = true; break; }
      if (!clipped) off.push(el);
    }
    const leaves = off.filter((el) => !off.some((x) => x !== el && el.contains(x))).slice(0, 5);
    issues.push({ type: 'page-overflow', sev: 'error', sel: leaves.map(sel).join(' | '), px: document.documentElement.scrollWidth - vw });
  }
  const counts = {};
  for (const i of issues) counts[`${i.sev}:${i.type}`] = (counts[`${i.sev}:${i.type}`] || 0) + 1;
  return { url: location.href, vw, ua: navigator.userAgent, prettySupported: prettyOK, counts, scannedChars: o.maxChars - budget, truncated: budget <= 0, issues: issues.slice(0, o.maxIssues) };
}
