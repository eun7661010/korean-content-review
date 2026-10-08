# 자동 검사 — 동적 검출기와 정적 검사

줄바꿈은 폭·글꼴·DB 데이터·엔진에 따라 바뀐다. 눈으로 몇 화면 보는 것으로는 부족하므로 렌더 후 글자 위치로 줄을 복원해 판정한다. 판정의 중심은 동적 검사이고, 정적 검사는 "규칙이 빠진 곳"을 찾는 보조다.

## 1. 실행

```bash
# 프로젝트 폴더에서(Playwright를 프로젝트 node_modules에서 찾는다)
S=skills/korean-line-break/scripts

# 정적 검사
node $S/ko-wrap-static.mjs src --max 10 --json .tmp/ko-wrap-static.json

# 동적 검사 — 페이지 × 폭 × 엔진
node $S/ko-wrap-check.mjs http://localhost:3000/ http://localhost:3000/example \
  --widths 320,390,768,1440 --engines chromium,webkit,firefox --out .tmp/ko-wrap.json --shots .tmp/ko-wrap-shots

# 기준선(래칫): 기존 부채를 고정하고 새 error만 실패로 센다
node $S/ko-wrap-check.mjs <urls…> --baseline ko-wrap-baseline.json --update-baseline   # 처음 1회
node $S/ko-wrap-check.mjs <urls…> --baseline ko-wrap-baseline.json                     # 이후 매번

# 로그인 화면: Playwright storageState 파일을 넘긴다(자격증명 파일은 커밋하지 않는다)
node $S/ko-wrap-check.mjs http://localhost:3000/dashboard --storage-state .tmp/auth.json

# 검출기 회귀 확인
node $S/ko-wrap-check.mjs $S/fixture.html --widths 400 --engines chromium,webkit,firefox --fail-on none
```

- WebKit·Firefox가 없으면 `npx playwright install webkit firefox`. 실행에 실패한 엔진은 건너뛰고 알린다.
- 운영 사이트는 GET만 한다. 실행기는 분석·광고 요청(GA·GTM·Meta·Clarity·Vercel Insights·네이버·카카오 픽셀)을 막는다.
- 결과 요약은 error·warn만 보여 준다. 전체(info 포함)는 `--out` JSON에 있다.
- 브라우저 함수만 쓰려면: `page.evaluate(\`(${fs.readFileSync('ko-wrap-audit.js','utf8')})({ root: 'main' })\`)`.

## 2. 동적 규칙 (ko-wrap-audit.js)

| 유형 | 판정 | 심각도 |
|---|---|---|
| `mid-eojeol` | 줄 경계 앞뒤에 공백이 없고 한쪽이 한글이며 word-break가 normal·break-all | error |
| `josa-head` | 다음 줄 첫 토큰이 조사(+부호)뿐이고, 앞 토큰이 2자 이상이거나 앞 글자가 닫는 부호·원문자. **word-break 값과 무관**(keep-all에서도 Chromium은 `(가)⏎와`로 끊는다) | error |
| `long-eojeol-split` | keep-all인데 공백 없이 갈림(줄보다 긴 어절을 overflow-wrap이 자름, Chromium `·` 분할) | warn |
| `punct-head` / `punct-tail` | 줄머리에 닫는 부호(`. , ! ? : ; ) ] 」 』 》 ” ’ · %` 등) / 줄끝에 여는 부호 | error |
| `num-unit` | 숫자 뒤 단위(+조사)가 다음 줄로. 붙여 쓴 경우 error, 띄어 쓴 `45⏎문항`·`제⏎3회`는 warn | error/warn |
| `orphan` | 강제 줄바꿈으로 나뉜 구간마다 2줄 이상·12자 이상(`orphanMinChars`)이고 마지막 줄 2자 이하 → error, 한 어절이고 최장 줄의 20% 미만 → warn. 12자 미만 짧은 라벨은 제외. pretty 미지원 엔진(Firefox)은 info | error/warn/info |
| `control-wrapped` | button·[role=button]·[role=tab]·label·th·nav a·*badge*·*chip*·*btn*이 2줄 이상 | warn |
| `overflow` / `truncated` | 줄 오른쪽 끝이 콘텐츠 박스를 1px 넘게 벗어남(overflow-x auto·scroll 제외). ellipsis면 truncated | error/info |
| `page-overflow` | documentElement.scrollWidth > clientWidth. 원인 요소 최대 5개 | error |
| `page-overflow-unmeasurable` | html에 overflow-x hidden·clip이 있어 가로 넘침을 측정할 수 없음 → overflow 항목으로 대신 본다 | info |
| `heading-unbalanced` | h1~h4·.ko-heading이 6줄 이하이고 마지막 줄이 최장 줄 50% 미만인데 balance가 아님 | info |
| `word-split` | 라틴 문자·숫자 낱말이 공백 없이 갈림(대개 URL의 정상 분할) | info |

### 오탐 방지 장치

- 블록 컨테이너마다 글자 스트림을 하나로 만든다. 인라인 요소 경계(`학생<strong>들이</strong>`)는 이어서 판정하고, inline-block·flex/grid 항목·img·svg·`<wbr>`·ZWSP·SHY는 경계로 보고 판정하지 않는다.
- `<br>`과 pre 계열의 `\n`은 의도된 강제 줄바꿈으로 본다. 외톨이는 그 구간마다 따로 본다.
- 숨은 글 제외: display none·contents, checkVisibility(opacity 0·visibility hidden), 2px 미만(sr-only), overflow로 잘린 조상 밖(캐러셀·아코디언).
- 건너뜀: code·pre·kbd·samp·textarea·input·select·rt·svg·iframe·contenteditable, `data-wrap-audit="ignore"`(의도한 예외 표시), `--ignore` 선택자(작품 원문 컨테이너 — 고유 콘텐츠라 판정하지 않는다).
- line-clamp·고정 높이 요소는 잘린 줄을 빼고 외톨이 판정을 생략한다.
- 여는 괄호 앞, 하이픈·슬래시 뒤의 끊김은 정상으로 본다. NBSP는 공백으로 세지 않는다.
- WebKit은 줄 맨 앞 글자의 Range에 앞 줄 끝의 폭 0 사각형을 먼저 돌려준다 → 폭이 가장 큰 사각형을 쓴다(이 처리 전 가짜 punct-head 3건).
- 측정 전 `document.fonts.ready`, reducedMotion. 가로쓰기·LTR이 아닌 컨테이너는 건너뛴다. `::before/::after` 생성 콘텐츠는 Range로 잴 수 없어 빠진다.
- 기본 한도 6만 자(`maxChars`). 넘으면 `truncated: true`로 알린다.

### 검증 기록 (2026-10-08)

- 픽스처 16종 + 기호·조사 8종(`scripts/fixture.html`)에서 기대한 위반을 모두 잡았고, 숨은 글·`<br>`·flex column·pre-line·line-clamp·NBSP·nowrap 묶음에서 오탐 0건.
- 엔진 비교 306문단: keep-all만 → 외톨이 4건(3엔진), keep-all+pretty → Chromium·WebKit 0건, Firefox 4건(미지원).
- 기호+조사: Chromium 147 `(가)⏎와`·`〈보기〉⏎에서`·`㉠⏎에서` josa-head, Firefox 148 괄호류 josa-head, WebKit 26.4는 끊지 않고 넘침. nowrap span 적용 시 Chromium 0건.
- 실서비스에서 확인한 사례: 홈 1440px `(등급컷·운영·독서⏎·문학)`(keep-all+pretty 상태), 수업 안내 화면 390px 후기 표 `올랐어요.”` 외톨이, 홈 1440px `만들어집니다.` 외톨이 — 뒤 두 건은 `.ko-copy`가 빠진 text-wrap auto 요소.
- 페이지당 30~55ms.
- 실서비스 학생 화면의 초기 오프라인 실험(12시나리오, 2026-10-08): 320~1440px × 3엔진에서 Chromium error 58·WebKit 58·Firefox 33. 대부분 keep-all이 닿지 않은 공용 화면 레이아웃의 어절 중간 끊김(`확인하⏎세요`, 좁은 링크 `도⏎움⏎말`)과 320px 빠른 메뉴 라벨 외톨이. 최종 적용 전후 집계는 [공개 벤치마크](../../../benchmarks/line-break/README.md)의 별도 측정이다.
- 디자인 시안(58개 HTML, 320·390): 고전 시가 한자 병기 뒤 조사 분리(`혼백(魂魄)⏎조차`, `건덕궁(乾德宮)⏎에`), 따옴표 뒤 조사(`‘반기실가’⏎는`), 판정 버튼 `적절⏎○` 외톨이.

## 3. 정적 규칙 (ko-wrap-static.mjs)

| 규칙 | 심각도 | 잡는 것 |
|---|---|---|
| `break-word-deprecated` | error | `word-break: break-word` |
| `line-break-anywhere` | error | `line-break: anywhere` |
| `break-all-ko` | warn | 한국어가 들어갈 수 있는 `break-all`(font-mono·code·`{x.id}`·`{url}` 같은 ASCII 칸은 제외) |
| `wrap-shorthand-conflict` | warn | `text-balance/pretty`와 `truncate/whitespace-nowrap` 동시 사용 |
| `pre-on-markdown` | warn | pre-line·pre-wrap이 마크다운·HTML 출력 근처(4줄 창)에 있음 |
| `pre-without-wrap` | warn | pre-line·pre-wrap에 wrap-break-word·wrap-anywhere 짝이 없음 |
| `unlayered-wrap-css` | warn | 줄바꿈 속성을 가진 단일 클래스 선택자가 @layer 밖 |
| `no-global-keep-all` | warn | `@import "tailwindcss"` 진입 CSS에 keep-all이 없음 |
| `html-lang` | warn | `<html>`에 lang="ko" 없음 |
| `rn-direct-text` | warn | react-native `Text` 직접 import(공용 래퍼 파일 제외, `--rn-text-wrapper`) |
| `break-all-links` | info | `[&_a]:break-all`(URL 링크면 허용) |
| `auto-phrase` | info | `word-break: auto-phrase` |
| `layout-br` | info | tsx·html의 `<br>` |
| `num-space-unit` | info | 한글 줄의 `45 문항` 같은 띄어 쓴 숫자+단위 |
| `rn-balanced-body` | info | `textBreakStrategy="balanced"` |
| `rn-textinput-no-hangul` | info | `lineBreakStrategyIOS` 없는 파일의 TextInput |

같은 줄만 보는 휴리스틱이라 className이 부모·다른 줄에 있으면 놓치거나 잘못 잡는다. 결과는 사람이 분류하고, 최종 판정은 동적 검사로 한다. 테스트·node_modules·.next·.tmp는 기본 제외(`--include-tests`로 포함).

## 4. 검수 매트릭스

- 폭: 320(WCAG 1.4.10 Reflow)·390·768·1440. nowrap 버튼·배지는 320px과 200% 확대에서 넘침 확인.
- 엔진: Chromium, WebKit(macOS·**iOS 27 실기기 필수** — keep-all 구두점 변경), Firefox, Samsung Internet. 카카오톡 인앱(Android System WebView).
- 데이터: 가장 긴 실제 DB 문구(긴 작품명·긴 닉네임·긴 URL·띄어쓰기 없는 학생 글)로 본다. 더미 문구는 짧아서 결함을 숨긴다.
- 앱: `react-native.md` 6절의 기기 매트릭스.

## 5. 디자인 시안 검수

- Figma 텍스트 스타일: 제목 Balance, 본문 Pretty(2026-08-14 추가, Balance는 6줄 이하). keep-all에 해당하는 설정이 없으므로 Figma의 한국어 줄바꿈 위치를 명세로 쓰지 않는다. 판정은 운영 CSS·실기기 렌더로 한다.
- 'Korean Word Wrap' 류 플러그인은 보이지 않는 문자가 Dev Mode 복사·핸드오프에 섞이는지 확인한 뒤에만 쓴다.
- HTML 시안(Claude Design 캔버스 등): `lang="ko"`, 운영과 같은 줄바꿈 클래스, `<br>`로 줄 맞추기 금지, 기호+조사 nowrap. 시안 HTML에도 동적 검출기를 돌린다(file 경로를 그대로 넘긴다).
- 네이티브 앱 화면을 HTML로 그린 시안에는 "Android 네이티브는 WJ 적용 전까지 음절 단위로 끊김"을 메모한다.
