# 웹(CSS·Tailwind) 한국어 줄바꿈 상세

확인일 2026-10-08. 실측 환경 Playwright 1.59.1 — Chromium 147.0.7727.15, Firefox 148.0.2, WebKit 26.4. 근거는 `sources.md`.

## 1. 엔진별로 다르게 끊기는 곳 (실측)

| 경우 | Chromium 147 | Firefox 148 | WebKit 26.4 | Safari 27(iOS 27, 2026-09-14) |
|---|---|---|---|---|
| keep-all 문단의 어절 | 공백에서만 | 공백에서만 | 공백에서만 | 공백 + 모든 구두점 뒤 |
| `(가)\|와`, `〈보기〉\|에서`, `[A]\|에서`, `「춘향전」\|에서` | **끊음** | **끊음** | 붙임(대신 넘침) | 끊을 수 있음(소스 판독) |
| `‘나’\|는`, `“나”\|는` | 끊음 | 붙임 | 붙임 | 끊을 수 있음 |
| `㉠\|에서`, `ⓐ\|와`, `①\|에서` | 끊음 | 붙임 | 붙임 | — |
| `45%\|였다`, `…\|라고`, `!\|라고` | 끊음 | 일부 | 붙임 | 끊을 수 있음 |
| 가운뎃점 `독서\|·문학`, `독서·\|문학` | 앞뒤 모두 끊음 | 붙임(넘침) | 붙임(넘침) | 뒤에서 끊을 수 있음 |
| `국어/\|수학` | 끊음 | 끊음 | 붙임 | — |
| 공백 없는 한자열 `春眠不覺曉…` + keep-all | 통째(넘침) | 통째 | 통째 | 통째 |
| `text-wrap: pretty` | 지원(마지막 몇 줄 조정) | **미지원** | 지원(26+, 문단 전체) | 지원 |
| `text-wrap: balance` | 6줄 이하만 | 10줄 이하만 | 무제한 | 무제한, line-clamp와 함께 동작(27) |

**WebKit 27.2(Playwright 1.64, 2026-10-08 실측)**: `(가)⏎와`·`〈보기〉⏎에서`·`등급컷·⏎운영`으로 끊는다(26.4는 붙이고 넘침). **WJ(U+2060)를 넣어도 똑같이 끊긴다** — WJ 무시 확인. nowrap span만 막힌다. 실서비스 학생 화면은 WebKit 27.2 기준 오류 43 → 3(남은 3은 손대지 않은 작품 원문).

결론: keep-all만으로는 "기호 + 조사"가 Chromium(국내 모바일 1위, Samsung Internet·Whale·인앱 WebView 포함)에서 갈린다. 짧은 묶음은 `white-space: nowrap` span으로 묶는 것이 엔진과 무관한 1순위 해법이다. U+2060(WORD JOINER)은 Chromium·Firefox에서 효과를 확인했지만 Safari 27의 새 경로는 다음 글자를 보지 않아 무시될 수 있으므로 보조 수단이다.

## 2. 지원 버전 (MDN browser-compat-data, 2026-10-07)

| 기능 | Chrome | Safari | Firefox | 비고 |
|---|---|---|---|---|
| `word-break: keep-all` | 44 | 9 | 15 | 기준선 |
| `overflow-wrap: anywhere` | 80 | 15.4 | 65 | min-content에 반영됨 |
| `text-wrap: balance`(단축) | 114 | 17.5 | 121 | |
| `text-wrap: pretty`(단축) | 117 | 26 | 미지원 | |
| `text-wrap-style`(정식 속성) | 130 | 17.5 | 124 | Samsung Internet 28+ |
| `word-break: auto-phrase` | 119(ko·ja) | preview | 미지원 | ko는 ICU 73+ 기준 공백 단위 → keep-all과 같음 |

국내 모바일 점유(참고): Chrome 34.4%, Safari 32.5%, Samsung Internet 18.8%, Whale 12.5%. 카카오톡 인앱은 Android System WebView(Chromium)다.

## 3. 전역 기본값 (Tailwind v4 전역 CSS 예)

```css
@layer base {
  body {
    word-break: keep-all;          /* 어절 단위 */
    overflow-wrap: break-word;     /* 줄보다 긴 어절·URL만 강제로 자른다. 전역에 anywhere는 쓰지 않는다 */
  }
  /* 작품 원문 컨테이너(이름은 프로젝트 것으로)와 그 하위는 대상에서 뺀다. 원문에 값을 덮어쓰지 않는다 */
  :where(h1, h2, h3):not(:where(.work-verse, [data-original-text]), :where(.work-verse, [data-original-text]) *) { text-wrap-style: balance; }
  :where(p, li, blockquote, figcaption, dd):not(:where(.work-verse, [data-original-text]), :where(.work-verse, [data-original-text]) *) { text-wrap-style: pretty; } /* td·th·대형 블록 제외(성능) */
  :where([lang|="zh"], [lang|="ja"], .hanmun) { word-break: normal; } /* 공백 없는 한문·일본어 원문 */
  textarea { text-wrap-style: stable; }                             /* 선택: 편집 중 줄이 흔들리지 않게 */
}

@layer components {
  .ko-heading { word-break: keep-all; text-wrap-style: balance; }
  .ko-copy    { word-break: keep-all; overflow-wrap: break-word; text-wrap-style: pretty; }
  .ko-user-text { white-space: pre-line; word-break: keep-all; overflow-wrap: anywhere; } /* 평문 사용자 글 */
  .ko-nobreak { white-space: nowrap; }                                                    /* 기호+조사 묶음 */
}
```

- 레이어 밖(unlayered) 선언은 `@layer utilities` 안의 Tailwind 유틸리티를 모두 이긴다. 그래서 `.ko-heading truncate`가 말줄임되지 않는다. 직접 쓰는 줄바꿈 클래스는 반드시 `@layer components`에 둔다.
- 손으로 쓰는 CSS에는 단축 속성 `text-wrap` 대신 `text-wrap-style`을 쓴다. 단축 속성은 `text-wrap-mode`까지 `wrap`으로 덮어 nowrap·truncate를 풀 수 있다.
- `word-break`·`text-wrap-style`·`overflow-wrap`은 상속된다. balance·pretty는 래퍼가 아니라 글자를 직접 담은 요소에 붙인다(카드 래퍼에 붙이면 하위 전체가 balance된다).
- `line-break: strict`는 한국어에 거의 효과가 없다(일본어 작은 가나 등 대상). 기존 코드에 있으면 둬도 된다. `line-break: anywhere`는 금지.

## 4. Tailwind 4.2 클래스 대응

| 목적 | 클래스 | 출력 | 주의 |
|---|---|---|---|
| 어절 단위 | `break-keep` | `word-break: keep-all` | |
| 긴 어절·URL만 자르기 | `wrap-break-word` | `overflow-wrap: break-word` | 구 `break-words`. flex·grid 자식이면 `min-w-0` 같이 |
| 최소 폭까지 줄이기 | `wrap-anywhere` | `overflow-wrap: anywhere` | min-content가 1글자가 되어 좁은 칸에서 '학/생'처럼 세로로 쌓일 수 있음 |
| 되돌리기 | `break-normal` | `word-break: normal` **+** `overflow-wrap: normal` | overflow-wrap까지 지운다 |
| 제목 균형 | `text-balance` | `text-wrap: balance`(단축) | truncate·whitespace-nowrap과 한 요소에 쓰지 않는다 |
| 본문 외톨이 방지 | `text-pretty` | `text-wrap: pretty`(단축) | 위와 같음 |
| 줄바꿈 금지 | `whitespace-nowrap` / `text-nowrap` | | 짧은 토큰에만 |
| 사용자 글 개행 보존 | `whitespace-pre-line` | | 평문 요소에만. 마크다운 컨테이너 금지 |
| 말줄임 1줄 | `truncate` | overflow·ellipsis·nowrap | flex 자식이면 `min-w-0` |
| 말줄임 N줄 | `line-clamp-N` | `-webkit-line-clamp` | Safari 26 이하는 balance와 같이 안 됨 |

## 5. 표면별 처방

| 표면 | 처방 | 이유 |
|---|---|---|
| 페이지·섹션 제목, 카드 제목, CTA 문구 | `break-keep` + balance(`h1~h3`는 전역) | 짧은 블록의 줄 길이를 고르게. 6줄 넘으면 Chromium에서 효과 없음 |
| 본문 문단·목록·인용·캡션 | `break-keep` + pretty(전역) | 마지막 줄 1~2글자 외톨이 방지. Firefox는 외톨이가 남는다 |
| flex·grid 칸 안의 가변 텍스트 | 칸에 `min-w-0`, 글에 `wrap-break-word`. grid 열은 `minmax(0,1fr)` | flex 항목의 기본 `min-width:auto` 때문에 긴 단어가 칸을 밀어낸다 |
| 표 셀·말풍선처럼 min-w-0을 보장 못 하는 칸 | `wrap-anywhere` | anywhere만 min-content에 반영된다 |
| 짧은 버튼·탭·배지·칩 라벨 | `whitespace-nowrap`(shadcn Button·Badge 기본) + 320px 넘침 검사 | 라벨이 2줄이 되면 높이가 들쭉날쭉 |
| 긴 버튼 라벨 | `whitespace-normal break-keep text-balance`로 2줄 허용하거나 문구를 줄인다 | nowrap만 걸면 좁은 화면에서 넘친다 |
| 여러 줄 버튼(문장 선택·근거 버튼, 회상 카드) | `break-keep` + pretty(문단처럼 보여야 하므로 balance 아님) | 320px에서 `비교`·`사례`만 다음 줄에 남는 외톨이 실측 |
| 숫자 + 단위 | 붙여 쓴다(`45문항`, `3,000원`). 띄어야 하면 렌더 단계 NBSP | keep-all도 공백에서는 끊는다(`45⏎문항`). 하우스 규칙 |
| 기호 + 조사 (`(가)와`, `〈보기〉에서`, `㉠은`, `‘나’는`, `45%였다`, 한자 병기 `혼백(魂魄)조차`·`침변(枕邊)*에`) | 렌더 도우미로 `<span class="whitespace-nowrap">` 묶음(앞 어절·각주 `*` 포함) | Chromium·Firefox는 keep-all이어도 끊는다. 고전 시가 원문에서 특히 잦다 |
| 가운뎃점 묶음 (`수능·모의고사`, `(등급컷·운영·독서·문학)`) | 짧으면 nowrap span | Chromium은 `·` 앞뒤를 끊어 줄머리 `·`가 생긴다 |
| 평문 사용자 글(질문·답변·채팅·후기·피드백·쪽지·알림 본문) | `whitespace-pre-line break-keep wrap-break-word`(말풍선이면 `wrap-anywhere`). 들여쓰기가 의미면 pre-wrap | 개행 보존 + 긴 URL 넘침 방지 |
| 마크다운·HTML로 렌더한 출력 | pre-line·pre-wrap **금지**. 줄바꿈은 렌더러가 `<br>`로 만든다. 링크는 `[&_a]:wrap-anywhere` | 태그 사이 개행이 빈 줄로 살아난다(실측 80→140px) |
| URL·이메일·ID·해시·토큰 | `wrap-anywhere`(또는 ASCII 전용 칸에 `break-all` + `font-mono`) | break-all은 한글을 음절마다 끊는다 |
| 한문·한시·일본어 원문 블록 | `word-break: normal` + 해당 `lang` | keep-all이면 공백 없는 한자열이 통째로 넘친다 |
| 고전 시가·의도된 행갈이 | `<br>` 또는 pre-line 허용 | 레이아웃용 `<br>`과 구분 |
| **작품 원문(시 행·연·고전 원문)** | **건드리지 않는다.** 텍스트·행갈이·`word-break`·내어쓰기 등 원문 조판 설정을 바꾸지 않고, 전역 규칙의 선택자에서 원문 컨테이너와 그 하위를 뺀다(`:not(원문, 원문 *)`). `text-wrap-style: auto` 같은 값을 원문에 덮어쓰면 원문 자체의 상속(부모 balance 등)이 끊겨 줄 나뉨이 바뀐다(시안 원문 460곳 대조에서 덮어쓰기 25곳 변화, 선택자 제외 0곳). 렌더 도우미·WJ도 적용하지 않는다 | 고유 콘텐츠다. 검출기에서는 `--ignore`로 빼고, 변경 전후 원문 줄 나뉨이 같은지 대조한다 |
| 너무 긴 합성어(`수능특강연계분석`) | 형태소 경계에 `<wbr>` | overflow-wrap이 임의 지점에서 자르는 것 방지 |
| 알림 미리보기·OG·메일 템플릿 | 문자열 단계에서는 줄바꿈 문자 삽입 금지. HTML 메일·iframe 리포트는 템플릿 `<style>`에 body 기본값 | 별도 문서라 전역 CSS가 닿지 않는다 |
| 편집 영역(textarea·contenteditable) | 선택: `text-wrap-style: stable` | 입력 중 위 줄이 다시 흐르지 않게 |

## 6. 렌더 도우미 (React)

`scripts/ko-nobreak.mjs`의 `koNoBreakSegments`를 프로젝트 `lib/`로 옮겨 쓴다. 글자를 끼워 넣지 않고 span으로만 감싸므로 복사·검색·스크린리더 결과가 그대로다.

```tsx
import { koNoBreakSegments } from "@/lib/text/ko-nobreak";

export function KoText({ children }: { children: string }) {
  return (
    <>
      {koNoBreakSegments(children).map((s, i) =>
        s.nobreak ? <span key={i} className="whitespace-nowrap">{s.text}</span> : s.text,
      )}
    </>
  );
}
```

- 적용 우선순위: 문항 발문·선지·해설·지문 훈련 카드처럼 `(가)`, `㉠`, `〈보기〉`가 많은 화면 → 마크다운 렌더러의 텍스트 노드 → 일반 카피.
- 16자 넘는 묶음은 묶지 않는다(nowrap이 넘침을 만든다). 동적 검사의 overflow가 0인지 확인한다.
- 마크다운 렌더러에 넣을 때는 텍스트 노드에만 적용하고 코드·링크 href에는 적용하지 않는다.

## 7. 금지

- 한국어가 들어갈 수 있는 요소의 `break-all`(ID·해시·URL 전용 칸만 예외).
- `word-break: break-word`(비권장 값) → `overflow-wrap: anywhere`로 바꾸고 keep-all 유지.
- `line-break: anywhere`(keep-all·NBSP·WJ·nowrap을 모두 무시).
- `word-break: auto-phrase`(한국어 이득 없음, Safari·Firefox에서 normal로 떨어짐).
- 전역 `overflow-wrap: anywhere`(짧은 라벨까지 min-content가 1글자로 줄어 세로로 쌓인다).
- 레이아웃 맞추기용 `<br>`(폭이 바뀌면 짧은 줄이 생긴다).
- WJ·NBSP·ZWSP를 DB 원문·`<title>`·meta·OG·JSON-LD·aria-label·복사 페이로드·검색 색인에 넣기.
- `hyphens`·`text-spacing-trim`·`hanging-punctuation` 설정(한국어 사전·효과 없음). `text-autospace` 실제 초기값은 no-autospace.

## 8. 기존 코드에 적용하는 순서

1. 정적 검사로 현황을 뽑는다: `node skills/korean-line-break/scripts/ko-wrap-static.mjs src`.
2. 동적 검사 기준선을 만든다: 대표 페이지 × 320·390·768·1440 × chromium(+webkit) → `--baseline ko-wrap-baseline.json --update-baseline`.
3. 전역 `@layer base` 기본값 추가, `.ko-*`를 `@layer components`로 이동(단축 속성 → text-wrap-style).
4. 사용자 글 표면(pre-line + wrap), 한국어 `break-all` 제거, 마크다운 컨테이너의 pre-line 제거.
5. 기호+조사 렌더 도우미를 문항·해설·훈련 화면에 적용.
6. 동적 검사를 기준선과 비교해 신규 error 0을 확인한다. 줄어든 기준선은 갱신한다(래칫).
7. 별도 문서(iframe 리포트·HTML 메일·인쇄용 HTML)는 템플릿 `<style>`에 같은 기본값을 넣는다. 인쇄 교재 조판은 해당 환경의 별도 조판·렌더 검수 지침을 따른다.
