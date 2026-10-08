# 근거·출처·반박 기록

확인일 2026-10-08. 실측 환경 Playwright 1.59.1(Chromium 147.0.7727.15, Firefox 148.0.2, WebKit 26.4), Windows 11, 글꼴 Malgun Gothic·Pretendard.

## 출발점

Threads 게시글(@ddal_kkak_, 2026-10 초, 한국어 UI 줄바꿈 정리): `word-break: keep-all`, `text-wrap: balance/pretty`, `white-space`(nowrap·pre-line), `overflow-wrap` 네 축을 소개하고 break-word와 anywhere의 차이는 모른다고 적었다. 이 스킬은 그 글이 빠뜨린 것을 조사·실측해 보탰다.

원 글에 없던 것: 기호+조사 분리(Chromium·Firefox), Safari 27 keep-all 변경, 가운뎃점 분할, 숫자+단위 공백 분리, anywhere와 break-word의 min-content 차이, 전역 기본값의 레이어 문제, text-wrap 단축 속성의 nowrap 해제, balance 줄 수 한도·상속, Firefox pretty 미지원, 마크다운 컨테이너의 pre-line 빈 줄, 한문 블록 넘침, `line-break: anywhere`의 무력화, auto-phrase 무익, RN iOS hangul-word·Android 음절 단위, 자동 검사 방법.

## 표준·문서

- CSS Text 3/4 word-break·line-break·overflow-wrap: https://www.w3.org/TR/css-text-3/ · https://www.w3.org/TR/css-text-4/ (line-break: anywhere는 GL·WJ·ZWJ·word-break 금지를 무시)
- KLREQ(한국어 조판 요구사항) §7.1.2 줄머리 금칙·§7.1.3 줄끝 금칙·§7.1.4 숫자 분리 금지: https://www.w3.org/TR/klreq/ (숫자+단위 띄어쓰기 NBSP는 KLREQ 근거가 아니라 하우스 규칙)
- UAX #14 줄바꿈 알고리즘(WJ, LB25): https://www.unicode.org/reports/tr14/
- MDN word-break·overflow-wrap·text-wrap-style·white-space·@layer·checkVisibility·scrollWidth: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/
- MDN browser-compat-data: https://github.com/mdn/browser-compat-data (css/properties/word-break.json·text-wrap.json·text-wrap-style.json, browsers/samsunginternet_android.json)
- Tailwind 4 overflow-wrap·word-break·text-wrap: https://tailwindcss.com/docs/ (4.2.2 `break-normal`은 overflow-wrap까지 normal)
- Chrome text-wrap balance·pretty: https://developer.chrome.com/docs/css-ui/css-text-wrap-balance · https://developer.chrome.com/blog/css-text-wrap-pretty
- WebKit pretty(2025-04-08, Chromium 마지막 4줄 조정 수치의 출처 — 이차 출처라 실측으로 재확인): https://webkit.org/blog/16547/better-typography-with-text-wrap-pretty/
- WebKit 311090@main(2026-04-13, keep-all이 CJK 구두점 뒤 줄바꿈 허용): https://commits.webkit.org/311090@main · Safari 27 release notes(174658701, line-clamp+balance 수정)
- ICU 73 릴리스 노트("Phrase-based line breaking for Korean now breaks at spaces"): https://icu.unicode.org/download/73
- WCAG 2.2 1.4.10 Reflow·1.4.4 Resize text: https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
- React Native Text·TextInput(0.86/0.87): https://reactnative.dev/docs/text · CoreEventTypes.js(TextLayoutLine.text) · TextLayoutManager.kt:674-690 · issue #32503(onChangeText 상태 갱신과 한글 조합)
- Apple NSParagraphStyle.LineBreakStrategy.hangulWordPriority: https://developer.apple.com/documentation/uikit/nsparagraphstyle/linebreakstrategy-swift.struct/hangulwordpriority
- Android LineBreakConfig(WORD_STYLE_PHRASE·AUTO): https://developer.android.com/reference/android/graphics/text/LineBreakConfig · AOSP TextView.java:533(기본 NONE)·StaticLayout.java·Layout.java:105-109(balanced 정의)
- Expo WebBrowser v57: https://docs.expo.dev/versions/v57.0.0/sdk/webbrowser/
- Figma Text wrap(2026-08-14) Plugin API TextWrapStyle: https://developers.figma.com/docs/plugins/api/TextWrapStyle/

## 반박되어 고친 주장

| 처음 주장 | 고친 결론 | 근거 |
|---|---|---|
| 조사 줄머리는 word-break가 normal·break-all일 때만 생긴다 | keep-all에서도 닫는 부호·원문자 뒤에서 생긴다. word-break와 무관하게 판정 | 기호·조사 분리 실측(Chromium 147 `(가)\|와` 등 13종) |
| 가운뎃점만 조심하면 된다 | "닫는 부호+조사"가 더 흔하다. Safari 27은 모든 구두점 뒤를 허용 | 311090@main, Safari 27 노트 |
| auto-phrase를 keep-all 뒤에 덮어 쓰면 낫다 | 한국어는 ICU 73+ 공백 단위라 keep-all과 같다. 쓰지 않는다 | ICU 73, BCD |
| 근본 원인은 text-wrap 단축 속성 | `.ko-*`가 @layer 밖이라 모든 유틸리티를 이긴다 | 실서비스 전역 CSS에서 확인한 사례, MDN @layer |
| balance 한도는 6줄 | Chromium 6줄, Firefox 10줄, Safari 무제한. 상속됨 | MDN, WebKit 블로그 |
| 사용자 글 표면 전체에 pre-line | 평문 요소에만. 마크다운 컨테이너는 빈 줄 생김 | 마크다운 렌더 실측: 높이 80→140px |
| body에 overflow-x hidden이면 page-overflow를 못 잡는다 | html(또는 html+body)에 있을 때만 못 잡는다 | 가로 넘침 검출 실험 |
| 숫자+단위 NBSP는 KLREQ §7.1.4 근거 | 하우스 규칙. §7.1.4는 연속 숫자·숫자 앞뒤 기호 | KLREQ 원문 |
| Android 15+는 한국어를 자동으로 어절 단위로 끊는다 | AUTO는 UNSPECIFIED일 때만. RN Text는 NONE이라 음절 단위 | AOSP, RN 소스 |
| ellipsizeMode middle·head·clip 전면 금지 | 2줄 이상이면 tail만(Android 제약), 1줄 URL은 middle 허용 | RN 문서 |

## 미확인으로 남긴 것

- ~~Safari 27 실제 렌더~~ → 2026-10-08 WebKit 27.2(Playwright 1.64)로 확인: 구두점·원문자 뒤 조사 분리, WJ 무시, nowrap만 유효. iOS 27 실기기 확인은 여전히 권장.
- Samsung Internet 30·카카오톡 인앱 WebView 실측.
- RN `onTextLayout` lines[].text에 줄 끝 공백·개행이 포함되는지, numberOfLines로 잘린 줄 처리.
- ~~Android 기본 동작~~ → API 34 에뮬레이터 실측: RN Text는 en-US·ko-KR 모두 음절 단위, WJ 삽입 시 어절 단위. API 35+·실기기 TalkBack 낭독은 미확인.
- iOS hangul-word가 라틴·숫자와 한글이 붙은 곳(`EBS연계`, `3등급`, `(가)는`)을 어떻게 다루는지.
