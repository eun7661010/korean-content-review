---
name: korean-line-break
description: "한국어 줄바꿈·어절 끊김·조사 줄머리·외톨이 줄·word-break keep-all·text-wrap balance/pretty·white-space pre-line·overflow-wrap·React Native hangul-word를 웹·앱·디자인 시안에 적용하고 Playwright로 자동 검사할 때 사용한다. 한국어 UI·랜딩·카드·버튼·채팅·사용자 글 표시를 만들거나 고칠 때, 시안·컴포넌트 리뷰, '글자가 이상하게 끊긴다'는 제보를 다룰 때 쓴다. 인쇄 교재 조판은 별도 검수 범위다."
updated: "2026-10-08T10:01:40+09:00"
---

# korean-line-break: 한국어 UI 줄바꿈

한국어 화면에서 글자가 어절 중간·조사 앞·부호 앞에서 갈리거나, 마지막 줄에 한두 글자가 남거나, 긴 URL이 칸을 밀어내는 문제를 막고 자동으로 검사한다. 확인일 2026-10-08(Chromium 147·Firefox 148·WebKit 26.4 실측, Safari 27 변경 반영).

## 원칙: 작품 원문은 고유 콘텐츠

시 행·연, 고전 원문, 지문 원문의 **텍스트와 행갈이, 원문 조판 설정은 바꾸지 않는다.** 줄바꿈 작업은 UI 문구·해설·사용자 글에만 한다. 전역 규칙은 선택자 단계에서 원문 컨테이너와 그 하위를 대상에서 뺀다(`:not(원문, 원문 *)`). 원문에 `text-wrap-style: auto` 같은 값을 덮어쓰지 않는다 — 원문 자체 스타일(예: 부모의 balance)의 상속이 끊겨 원문 줄 나뉨이 바뀐다(시안 25곳 실측). 렌더 도우미·WJ를 적용하지 않으며, 검출기에서는 `--ignore`로 뺀다. 변경 뒤에는 원문 요소의 줄 나뉨이 변경 전과 같은지 렌더로 대조한다.

## 범위

- 대상: 웹(CSS·Tailwind·React), React Native(Expo) 앱, HTML·Figma 디자인 시안, HTML 메일·iframe 리포트.
- 제외: 인쇄 교재 조판(Vivliostyle·PDF)과 홍보 스크린샷 제작은 별도 작업이다. 해당 환경의 글꼴·조판·렌더 검수 지침을 따른다.
- 환경별 메모: `references/local-*.md`가 있으면 먼저 읽는다(공개판에는 포함되지 않는 사용 환경 정보).

## 놓치기 쉬운 것 (keep-all만으로 끝나지 않는다)

1. **기호 + 조사**: keep-all이어도 Chromium(국내 모바일 다수·인앱 WebView)은 `(가)⏎와`, `〈보기〉⏎에서`, `㉠⏎에서`, `‘나’⏎는`, `45%⏎였다`로 끊는다. Firefox도 괄호류는 같다. 짧은 묶음을 `whitespace-nowrap` span으로 묶는다(`scripts/ko-nobreak.mjs`).
2. **Safari 27(iOS 27, 2026-09-14)**: keep-all이 한글 문자열 안의 모든 구두점 뒤를 줄바꿈 가능 지점으로 바꿨다. `(`가 줄 끝에 남을 수 있다. nowrap span이 1순위, iOS 27 실기기 회귀 검사 필수.
3. **가운뎃점 묶음**: Chromium은 `독서·문학`의 `·` 앞뒤를 끊어 줄머리 `·`가 생긴다.
4. **숫자 + 단위**: keep-all도 공백에서는 끊는다(`45⏎문항`). 붙여 쓰거나 렌더 단계 NBSP.
5. **레이어**: 직접 만든 줄바꿈 클래스가 `@layer` 밖이면 Tailwind `truncate`·`whitespace-*`·`break-*`를 모두 이긴다. 전역 기본값은 `@layer base`, 클래스는 `@layer components`.
6. **단축 속성**: `text-wrap: balance|pretty`(Tailwind `text-balance`·`text-pretty`)는 `text-wrap-mode`까지 덮어 nowrap을 풀 수 있다. 직접 쓰는 CSS는 `text-wrap-style`.
7. **anywhere vs break-word**: anywhere만 min-content에 반영된다. flex·grid 칸은 `min-w-0` + break-word가 기본, min-w-0을 보장 못 하는 칸(표 셀·말풍선)만 anywhere. 전역 anywhere는 짧은 라벨을 세로로 쌓는다.
8. **pretty·balance 한도**: pretty는 Firefox 미지원. balance는 Chromium 6줄·Firefox 10줄 이하만. 둘 다 상속되므로 래퍼가 아니라 글자를 담은 요소에 붙인다.
9. **사용자 글**: 평문은 `whitespace-pre-line`이 없으면 개행이 사라진다. 그러나 마크다운·HTML 출력 컨테이너에 pre-line을 걸면 빈 줄이 생긴다.
10. **앱은 CSS가 없다**: iOS는 `lineBreakStrategyIOS="hangul-word"`, Android RN Text는 OS 버전과 무관하게 음절 단위다. `textBreakStrategy="balanced"`는 어절 보호가 아니다.

## 웹 기본값

```css
@layer base {
  body { word-break: keep-all; overflow-wrap: break-word; }
  /* 원문(.work-verse 등)과 그 하위는 대상에서 뺀다. :where로 우선순위 0 */
  :where(h1, h2, h3):not(:where(.work-verse, [data-original-text]), :where(.work-verse, [data-original-text]) *) { text-wrap-style: balance; }
  :where(p, li, blockquote, figcaption, dd):not(:where(.work-verse, [data-original-text]), :where(.work-verse, [data-original-text]) *) { text-wrap-style: pretty; } /* td·th 제외 */
  :where([lang|="zh"], [lang|="ja"], .hanmun) { word-break: normal; } /* 공백 없는 한문 원문 */
}
@layer components {
  .ko-heading   { word-break: keep-all; text-wrap-style: balance; }
  .ko-copy      { word-break: keep-all; overflow-wrap: break-word; text-wrap-style: pretty; }
  .ko-user-text { white-space: pre-line; word-break: keep-all; overflow-wrap: anywhere; }
  .ko-nobreak   { white-space: nowrap; }
}
```

`<html lang="ko">`를 유지하고 외국어 블록에는 lang을 단다.

## 표면별 처방 (요약 — 상세 `references/web-css.md` 5절)

| 표면 | 처방 |
|---|---|
| 제목·카드 제목·CTA | `break-keep` + balance |
| 본문·목록·캡션 | `break-keep` + pretty |
| flex·grid 칸의 가변 텍스트 | 칸 `min-w-0`, 글 `wrap-break-word`, grid 열 `minmax(0,1fr)` |
| 표 셀·말풍선 | `wrap-anywhere` |
| 짧은 버튼·탭·배지 | `whitespace-nowrap` + 320px 넘침 검사. 긴 라벨은 2줄 허용 + balance 또는 문구 축약 |
| 평문 사용자 글(질문·답변·채팅·후기·피드백·쪽지·알림) | `whitespace-pre-line break-keep wrap-break-word`(말풍선 `wrap-anywhere`) |
| 마크다운·HTML 출력 | pre-line 금지, 링크 `[&_a]:wrap-anywhere` |
| URL·ID·해시 | `wrap-anywhere`(ASCII 전용 칸만 `break-all font-mono`) |
| 기호+조사·가운뎃점 묶음·띄어 쓴 숫자+단위 | 렌더 도우미로 nowrap span(16자 이하) |
| 한문·한시·일본어 원문 | `word-break: normal` + lang |
| HTML 메일·iframe 리포트·OG 템플릿 | 템플릿 `<style>`에 같은 기본값(전역 CSS가 닿지 않음) |

## 금지

- 한국어 칸의 `break-all`, `word-break: break-word`, `line-break: anywhere`, `word-break: auto-phrase`, 전역 `overflow-wrap: anywhere`.
- 레이아웃 맞추기용 `<br>`(시처럼 의도된 행갈이만 예외).
- WJ(U+2060)·NBSP·ZWSP를 DB 원문·`<title>`·meta·OG·JSON-LD·aria-label·복사 페이로드·검색 색인에 넣기. 화면 렌더 단계에서만 쓴다.
- `hyphens`·`text-spacing-trim`·`hanging-punctuation` 설정.

## 앱(React Native) 요약 — 상세 `references/react-native.md`

- 모든 텍스트는 공용 `T`를 거치고, react-native `Text` 직접 import는 ESLint로 막는다.
- `T`·공용 Input에 `lineBreakStrategyIOS="hangul-word"`. `textBreakStrategy`는 제목만 balanced, 본문 highQuality.
- Android 단기 대응: `T`가 한글 어절 안에 U+2060을 넣는다(`insertWordJoiners`, URL·입력값 제외, 복사 화면은 opt-out).
- 입력 정규화는 저장·제출 시점에(onChangeText에서 하면 한글 조합이 깨진다). 마크다운 하드 브레이크를 웹과 같게 처리한다.
- `numberOfLines ≥ 2`이면 tail만. 고정 칩은 `maxFontSizeMultiplier`로 상한.

## 디자인 시안

- Figma: 제목 Balance, 본문 Pretty. Figma의 한국어 줄바꿈 위치는 명세가 아니다. 판정은 운영 CSS·실기기 렌더로 한다.
- HTML 시안: `lang="ko"`, 운영과 같은 줄바꿈 클래스, `<br>`로 줄 맞추기 금지, 기호+조사 nowrap. 시안 HTML에도 동적 검출기를 돌린다.

## 검사 절차

```bash
S=skills/korean-line-break/scripts
node $S/ko-wrap-static.mjs src                                   # 1) 규칙 누락·오용(정적)
node $S/ko-wrap-check.mjs <url|html>... --widths 320,390,768,1440 \
     --engines chromium,webkit,firefox --out .tmp/ko-wrap.json       # 2) 실제 줄(동적)
node $S/ko-wrap-check.mjs <urls> --baseline ko-wrap-baseline.json   # 3) 기준선 대비 신규 error 0
```

- 프로젝트 폴더에서 실행한다(Playwright를 그 node_modules에서 찾는다). 규칙·심각도·오탐 방지 장치는 `references/qa-detector.md`.
- 운영 사이트는 GET만 하고 분석 요청은 막는다. 로그인 화면은 `--storage-state`.
- 앱은 개발 빌드에서 `rn-ko-lines.mjs`의 `auditKoLines`를 `onTextLayout`에 연결한다. Jest·Expo web으로 판정하지 않는다.

## 완료 기준

- 정적 검사 error 0, 한국어 칸 `break-all` 0, unlayered 줄바꿈 클래스 0(예외는 사유 기록).
- 대표 화면 × 320·390·768·1440 × Chromium·WebKit에서 신규 error 0(기준선 대비), page-overflow 0.
- 사용자 글 표면에서 개행이 보존되고 긴 URL이 넘치지 않는 것을 실제 긴 데이터로 확인.
- 앱 변경 시 iOS·Android(API 34 이하 포함) 실기기 캡처, 최대 글자 크기 1회. iOS 27 실기기 확인은 웹·앱 공통.

## 파일

| 파일 | 내용 |
|---|---|
| `references/web-css.md` | 엔진별 실측 차이, 지원 버전, 전역 CSS, Tailwind 대응표, 표면별 처방, 렌더 도우미, 적용 순서 |
| `references/react-native.md` | iOS·Android 동작, 공용 T·Input 코드, WJ, 입력·마크다운, 기기 매트릭스, 장기 해법 |
| `references/qa-detector.md` | 동적·정적 규칙표, 오탐 방지, 검증 기록, 검수 매트릭스, 시안 검수 |
| `references/sources.md` | 출처, 출발점 게시글, 반박되어 고친 주장, 미확인 항목 |
| `scripts/ko-wrap-audit.js` | 브라우저 검출 함수(page.evaluate) |
| `scripts/ko-wrap-check.mjs` | 페이지×폭×엔진 실행기, 기준선 래칫, 스크린샷 |
| `scripts/ko-wrap-static.mjs` | 코드 정적 검사 |
| `scripts/ko-nobreak.mjs` | 기호+조사 nowrap 조각 나누기, Android WJ 삽입(`--selftest`) |
| `scripts/rn-ko-lines.mjs` | RN onTextLayout 감사 함수(`--selftest`) |
| `scripts/fixture.html` | 검출기 회귀 픽스처 |
