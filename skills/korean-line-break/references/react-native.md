# React Native(Expo) 한국어 줄바꿈 상세

확인일 2026-10-08. 기준 RN 0.86 / Expo 57 / targetSdk 36 / 최소 iOS 15.1. RN에는 CSS가 없으므로 웹 규칙을 그대로 옮길 수 없다.

## 1. 결론

| 플랫폼 | 기본 동작 | 처방 |
|---|---|---|
| iOS | RN `lineBreakStrategyIOS` 기본값 `none` → 음절 단위로 끊길 수 있음 | 공용 `T`·공용 Input에 `lineBreakStrategyIOS="hangul-word"`(iOS 14+, Apple: "prohibits breaking between Hangul characters") |
| Android | TextView·StaticLayout 기본 LineBreakConfig `NONE` → **음절 단위**. RN은 `setBreakStrategy`만 호출(TextLayoutManager.kt:674-690). Android 15+의 AUTO(ko→PHRASE)는 UNSPECIFIED일 때만 적용되므로 RN Text에는 자동 적용되지 않는다 | 단기: `T`가 Android에서만 한글 어절 안에 U+2060을 넣는다. 장기: 측정(StaticLayout)과 그리기(TextView) 양쪽에 PHRASE + ko 로캘 |
| 공통 | `textBreakStrategy="balanced"`는 "모든 줄을 비슷한 길이로" 만드는 설정이지 어절 보호가 아니다 | 제목에만 balanced, 본문은 기본 highQuality |

### 실측 (2026-10-08, Android 14 / API 34 에뮬레이터, RN 0.86.3 · Expo Go 57, 폭 120dp·14sp)

| 문장 | 기본(highQuality) | `balanced` | WJ 삽입 |
|---|---|---|---|
| 국어 공부는 매일 꾸준히 … 그래서 … | `그래⏎서` | `매⏎일`·`학⏎생`·`이깁니⏎다` | 어절 단위 |
| (가)와 〈보기〉에서 ㉠의 의미를 비교하고 … | `〈보기〉에⏎서`·`비⏎교` | 같음 | 어절 단위 |
| 2027학년도 EBS연계 … 수능특강연계문항분석서비스안내 확인하기 | `확인하⏎기` | `수⏎능` | 긴 어절만 강제 분할 |

- en-US와 ko-KR 로캘 결과가 **완전히 같다**(한국어 로캘이어도 RN Text는 음절 단위).
- `balanced`는 기본값보다 어절 중간 끊김이 많다 → 본문에 쓰지 않는다.
- 접근성 트리(`uiautomator dump`)의 text에 U+2060이 그대로 들어간다. `accessible`+`accessibilityLabel={원문}`을 함께 주면 content-desc가 WJ 없는 원문이 되지만, 모든 텍스트를 접근성 요소로 만들면 TalkBack 이동 단위가 바뀌므로 일괄 적용하지 않는다. 낭독 품질은 실기기에서 들어 보고 판단한다.

## 2. 공용 텍스트 컴포넌트

```tsx
// components/ui.tsx — 모든 텍스트가 거치는 T
import { Platform, Text, type TextProps } from "react-native";
import { useMemo } from "react";
import { insertWordJoiners } from "@/lib/text/ko-nobreak"; // 스킬 scripts/ko-nobreak.mjs를 옮겨 쓴다

type TProps = TextProps & { variant?: "title" | "body"; wrap?: "word" | "syllable" };

export function T({ variant = "body", wrap = "word", children, ...rest }: TProps) {
  const content = useMemo(() => {
    if (Platform.OS !== "android" || wrap !== "word" || typeof children !== "string") return children;
    return insertWordJoiners(children); // 한글 어절 안에만 WJ. URL·이메일·경로 토큰은 건너뜀
  }, [children, wrap]);
  return (
    <Text
      lineBreakStrategyIOS="hangul-word"
      textBreakStrategy={variant === "title" ? "balanced" : "highQuality"}
      {...rest}
    >
      {content}
    </Text>
  );
}
```

- 중첩된 children(문자열 배열·요소)은 문자열 조각마다 같은 변환을 적용하거나 그대로 둔다. 링크·코드 조각에는 넣지 않는다.
- `selectable` 텍스트는 복사 시 WJ가 따라간다. 복사 기능이 있는 화면은 `wrap="syllable"`로 끄거나, 복사 버튼에서 `stripWordJoiners`로 원문을 넘긴다.
- TalkBack 낭독·글자 수 세기·검색 하이라이트가 WJ에 영향받는지 실기기로 확인한다.
- `react-native`의 `Text` 직접 import를 막는다:

```js
// eslint 설정(앱 패키지)
"no-restricted-imports": ["error", { paths: [{ name: "react-native", importNames: ["Text"], message: "components/ui의 T를 쓰세요(한국어 줄바꿈 설정 포함)." }] }]
// components/ui.tsx만 예외로 overrides
```

## 3. 입력·사용자 글·마크다운

- **TextInput**: iOS TextInput도 `lineBreakStrategyIOS`를 받는다. 공용 `Input`을 만들어 `lineBreakStrategyIOS="hangul-word"`를 일괄 지정한다. 입력값에는 WJ를 넣지 않는다.
- **정규화 시점**: CRLF→LF, 줄 끝 공백 제거, 3줄 이상 빈 줄 축약은 blur·저장·제출 시점에 한다. `onChangeText`에서 값을 바꾸면 한글 조합이 깨진다(RN #32503).
- **사용자 글 표시**: RN Text는 `\n`과 연속 공백을 그대로 보존한다(CSS pre-wrap과 같음). 웹 pre-line과 모양을 맞추려면 위 정규화를 저장 시점에 한다.
- **마크다운 하드 브레이크**: 웹(marked)은 줄 끝 공백 2칸·백슬래시 하드 브레이크를 `<br>`로 만든다. 앱 마크다운이 줄을 `trim()` 후 `join(" ")`하면 시 구절 인용의 줄바꿈이 사라진다. 문단 내부 줄은 하드 브레이크 표식이 있으면 `\n`으로 잇는다.

## 4. 줄 수 제한·버튼·글자 크기

- `numberOfLines ≥ 2`이면 `ellipsizeMode`는 tail만 쓴다(RN 문서: Android 제약). 한 줄 URL·파일명은 `middle` 허용. iOS에서 hangul-word와 middle을 같이 쓰면 strategy가 무시될 수 있다(Apple: 여러 줄 미지원 lineBreakMode).
- 문항 번호·정답·날짜처럼 잘리면 안 되는 토큰은 별도 `T`로 빼서 말줄임 대상에서 제외한다.
- 버튼 라벨은 `numberOfLines={1}`로 자르지 말고 2줄까지 허용한다(minHeight 유지).
- 고정 크기 칩·탭·OMR 버블은 `allowFontScaling={false}` 대신 `maxFontSizeMultiplier`(예: 1.3)로 상한만 둔다. 고정 높이를 피하고 최대 글자 크기(Android 14+ 200%)에서 확인한다.
- 긴 URL은 라벨 링크로 보여 준다. URL에 ZWSP·WJ를 넣지 않는다.

## 5. 인앱 웹과의 일관성

- `expo-web-browser`의 `openBrowserAsync`는 iOS에서 SFSafariViewController(Safari 엔진), Android에서 Custom Tabs(기본 브라우저 — 한국에서는 Samsung Internet이 흔함)를 쓴다. 웹 화면은 keep-all을 기준선으로 하고 balance·pretty는 점진적 향상으로 다룬다.
- 같은 지문·해설을 웹(인앱)과 네이티브 iOS·Android에서 390px로 캡처해 줄바꿈을 나란히 비교한다. 200% 글자 크기에서도 본다.

## 6. 개발 빌드 감사

`scripts/rn-ko-lines.mjs`의 `auditKoLines`를 `T`의 `onTextLayout`에 연결한다(개발 빌드 전용).

```tsx
// 모든 텍스트에 경고가 쏟아지지 않게 환경변수로 켤 때만 돈다(EXPO_PUBLIC_*는 번들에 인라인됨)
const KO_WRAP_AUDIT = __DEV__ && process.env.EXPO_PUBLIC_KO_WRAP_AUDIT === "1";

onTextLayout={KO_WRAP_AUDIT ? (e) => {
  const out = auditKoLines(e.nativeEvent.lines);
  if (out.length) console.warn("[ko-wrap]", out);
  props.onTextLayout?.(e); // 호출부 콜백 유지
} : props.onTextLayout}
```

- Maestro 등으로 화면을 순회하며 Metro·logcat의 `[ko-wrap]`을 모은다.
- 기기 매트릭스: iOS 17/18(+iOS 27), Android API 34 이하와 35/36 × ko-KR·en-US 로캘, 최대 글자 크기 1회. 기대값: "RN Text는 API와 무관하게 음절 단위"(WJ 적용 전).
- 실기기 확인 문장: `2027학년도 EBS연계 3등급 컷`, `(가)는 화자의 정서를`, `수능특강연계문항분석서비스안내`(줄보다 긴 어절), 긴 URL, 2줄 제목, 500자 multiline 입력, 시 구절 하드 브레이크가 든 답변.
- Jest(레이아웃 없음)나 Expo web(브라우저가 줄을 바꿈)으로 네이티브 줄바꿈을 판정하지 않는다.

## 7. 장기 해법(선택)

RN을 소스 빌드하거나 Expo 모듈로 텍스트 뷰를 만들어 StaticLayout(측정)과 TextView(그리기) 양쪽에 `LineBreakConfig.Builder().setLineBreakWordStyle(LINE_BREAK_WORD_STYLE_PHRASE)`와 `setTextLocales(LocaleList("ko"))`를 함께 준다. 한쪽만 바꾸면(예: 테마 `android:lineBreakWordStyle`) 측정과 그리기가 어긋나 잘림·빈칸이 생긴다. API 33+ 한정이고 ICU 버전(73+에서 한국어 phrase = 공백 단위)에 따라 결과가 다를 수 있어 기기별로 실측한다.
