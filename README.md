# korean-content-review

사이트와 콘텐츠의 한국어를 띄어쓰기·맞춤법·문체·UI 줄바꿈까지 한 번에 검수하는 Claude Code·Codex 스킬

[김은광 수능국어](https://ekkorean.com)에서 만들고 실서비스에서 쓰는 스킬을 공개용으로 정리했습니다. 텍스트 교정 제안과 실제 브라우저 줄바꿈 검사를 함께 제공하며, 작품 원문을 보호하는 것을 첫 원칙으로 삼습니다.

## 실서비스 효과

2026-10-08, ekkorean.com 학생 화면 12개를 합성 데이터로 오프라인 렌더했습니다. 폭 320·390·768·1440px × Chromium 147·WebKit 26.4·Firefox 148, 총 144회 검사 결과입니다. 웹 69파일과 앱 21파일에 줄바꿈 규칙을 적용했습니다.

| 엔진 | 오류: 적용 전 → 후 | 경고: 적용 전 → 후 |
|---|---|---|
| Chromium | 41 → **3** | 23 → 8 |
| WebKit | 41 → **3** | 21 → 4 |
| Firefox | 33 → **2** | 0 → 0 |

| 줄바꿈 유형 | 적용 전 | 적용 후 |
|---|---|---|
| 어절 중간 끊김 | 93 | 6 |
| 조사 줄머리 | 6 | 0 |
| 외톨이 줄 오류(12자 이상 문단) | 16 | 2 |
| 외톨이 줄 경고 | 44 | 8 |
| 긴 어절 분할 경고 | 0 | 4 |

남은 오류 8건은 모두 보호한 작품 원문의 시 행에서 발생했습니다. 원문 요소의 줄 나뉨은 적용 전후 **36/36 동일**했습니다. 캡처 72장에서도 가로 넘침은 0 → 0으로 유지됐습니다. 긴 어절 분할 경고 4건은 오류와 구분해서 검토합니다.

| 코드 정적 검사 | 적용 전 | 적용 후 | 남은 항목 |
|---|---|---|---|
| 비권장 `word-break: break-word` | 1 | 0 | |
| 한국어 칸의 `break-all` | 10 | 3 | ASCII ID·scope 칸 |
| 링크 하위 `[&_a]:break-all` | 6 | 0 | `wrap-anywhere`로 교체 |
| `pre-wrap/pre-line`에 넘침 대비 없음 | 76 | 7 | 부모·다음 줄 선언을 놓치는 정적 검사 한계 |
| `@layer` 밖 줄바꿈 클래스 | 107 | 104 | 전역 클래스 3건 이동, 나머지는 지면별 스코프 CSS |

좁은 도움말 링크의 글자가 세로로 쌓이던 문제를 한 줄로 고친 사례입니다. 왼쪽이 적용 전, 오른쪽이 적용 후입니다.

![도움말 링크 줄바꿈 적용 전후](benchmarks/line-break/before-after-help-button.png)

[전체 측정 기록·엔진 비교·재현 명령](benchmarks/line-break/README.md)을 제공합니다. 실서비스 화면 전체는 공개하지 않으므로 공개 픽스처는 검출 유형과 오탐 방지를 재현합니다.

### Safari 27·안드로이드 앱에서도 확인했습니다

**Safari 27(iOS 27) 계열 엔진** — WebKit 27.2(Playwright 1.64)로 같은 학생 화면 12개 × 4폭을 다시 검사했습니다. Safari 27은 `keep-all` 상태에서도 구두점 뒤를 줄바꿈 지점으로 바꿨기 때문에 `(가)⏎와`, `〈보기〉⏎에서`, `등급컷·⏎운영`처럼 갈립니다.

| 엔진 | 오류: 적용 전 → 후 |
|---|---|
| WebKit 27.2 | 43 → **3** (남은 3은 보호한 작품 원문) |

같은 엔진에서 줄바꿈 금지 문자 WJ(U+2060)를 넣어도 `(가)⁠⏎와`로 그대로 갈렸습니다. **WJ는 무시되고, `white-space: nowrap` 묶음만 막습니다.** 이 스킬의 렌더 도우미가 글자를 끼워 넣지 않고 nowrap 묶음을 쓰는 이유입니다.

**안드로이드 앱(React Native 0.86)** — Android 14(API 34) 에뮬레이터, 폭 120dp에서 같은 문장을 세 방식으로 비교했습니다.

| 문장 | 기본값 | `textBreakStrategy="balanced"` | 어절 안 WJ 삽입(이 스킬) |
|---|---|---|---|
| 국어 공부는 매일 꾸준히 … 그래서 … | `그래⏎서` | `매⏎일`·`학⏎생` | 어절 단위 |
| (가)와 〈보기〉에서 ㉠의 의미를 비교하고 … | `〈보기〉에⏎서`·`비⏎교` | 같음 | 어절 단위 |

기기 언어를 한국어로 바꿔도 결과가 같았습니다. 안드로이드 RN 텍스트는 언어와 상관없이 음절 단위로 끊고, 흔히 쓰는 `balanced`는 오히려 더 잘게 끊습니다. iOS는 `lineBreakStrategyIOS="hangul-word"`로 해결됩니다.

<!-- TEXT-BENCH:START -->
### 텍스트 검수: 기존 스킬과 비교

**작품 원문을 고치지 않습니다.** 같은 입력에서 기존 띄어쓰기 스킬은 고전 시가 원문을 8곳 바꿨고(예: `靑山애 살어리랏다` → `靑山 애 살어리랏다`, `일이런가` → `일 이런가`), 사이트 글의 보호 구간(인용·표지·용어 등)도 301곳 고쳤습니다. 개선판은 둘 다 **0곳**입니다. 맞춤법 검사 결과에서 보호 구간을 건드리는 후보도 57 → **0**건입니다.

**헛지적을 없앴습니다.** 사이트 실제 문장 300개 가운데 233개에 띄어쓰기·표기 오류를 하나씩 넣고 찾게 했습니다.

| 지표 | 기존 띄어쓰기 스킬 | 개선판 기본값 |
|---|---:|---:|
| 넣은 오류를 찾은 비율(재현율) | 98.7% | 88.4% |
| 지적 중 실제 오류 비율(정밀도) | 67.6% | **100%** |
| 깨끗한 문장 300개에서 헛지적 | 146건 | **0건** |

| 오류 유형(건수) | 기존 재현율·정밀도 | 개선판 재현율·정밀도 |
|---|---|---|
| 의존명사 붙여 씀 `올것`·`할수`(38) | 100% · 59.4% | 97.4% · 100% |
| 수사·단위 붙여 씀 `두시간`(5) | 100% · 62.5% | 100% · 100% |
| 조사 앞 공백 `학생 이`(189) | 98.9% · 69.8% | 86.2% · 100% |
| 표기 `됬`·`컨텐츠` 등(1) | 0% | 100% |

기존 스킬은 많이 찾는 대신 지적 셋 중 하나가 헛지적이라, 결국 사람이 전부 다시 봐야 했습니다. 개선판은 확실한 범주만 보고해 놓치는 것이 일부 있지만, 보고한 것은 모두 고칠 대상이었습니다. 놓친 것이 걱정되면 `--spacing all`로 넓혀 볼 수 있습니다(재현율 98.7%·정밀도 63.5%). 표기·이중 피동은 사이트 문장에 해당 어휘가 드물어 주입 건수가 적으므로 문체 규칙 전체의 성능으로 일반화하지 않습니다.

맞춤법은 **선택 모듈**입니다. 외부 서비스(nara-speller)로 글을 보내며, 측정 중 19회 요청 가운데 13회가 HTTP 403으로 거절됐습니다. 기본 검수(띄어쓰기·문체·줄바꿈)는 외부 전송 없이 로컬에서 돕니다. [측정 방법·유형별 표·재현 명령](benchmarks/text/README.md)
<!-- TEXT-BENCH:END -->

## 무엇을 검사하나요?

| 모듈 | 검사 내용 |
|---|---|
| 원문 보호 | 작품·지문·인용 원문, 코드·URL·태그·용어 등 보호 구간을 먼저 식별하고 겹치는 제안을 억제 |
| 띄어쓰기 | Kiwi 형태소 분석과 보수적인 표기 사전으로 교정 후보 제시 |
| 맞춤법 | 명시적으로 켤 때만 외부 바른한글(nara-speller) 서비스로 검사 |
| 문체 | 한국어 편집 지침과 문체 규칙으로 어색한 표현·호응 검토 |
| UI 줄바꿈 | 어절 중간 끊김·조사 줄머리·외톨이 줄·숫자와 단위 분리·버튼 줄바꿈·가로 넘침 검출 |

## 원칙

- **작품 원문은 고유 콘텐츠입니다.** 시의 행·연, 고전 원문, 지문·인용 원문의 텍스트·행갈이·조판을 바꾸거나 교정 제안을 내지 않습니다. 원문 컨테이너는 줄바꿈 검사에서도 `--ignore`로 제외합니다.
- **보수적으로 교정합니다.** 기본 결과는 원문·제안·근거·확신도 목록입니다. 자동 적용은 하지 않으며, 명시적인 `--apply`도 보호 구간 밖의 확신도 높은 띄어쓰기·표기 사전 항목으로 제한합니다.
- **맞춤법 검사는 외부로 글을 보냅니다.** 기본은 꺼짐입니다. `--modules spell`로 켜면 보호 구간을 제외한 검사 대상 글이 nara-speller로 전송됩니다. 개인정보·미공개 글은 전송 범위를 확인하고 서비스 이용 조건을 따라야 합니다. 요청 간격은 2초, 기본 최대 요청 수는 20회입니다.

원문에는 HTML의 `data-original-text`를 붙이거나 Markdown·평문에서 `<!-- original -->` … `<!-- /original -->`, `:::original` … `:::` 표시를 사용합니다. 프로젝트별 원문 CSS 선택자는 동적 검사기의 `--ignore`로 지정합니다.

## 설치

### 1. Claude Code 플러그인

Claude Code에서 실행합니다. `skills/` 아래 스킬은 플러그인이 자동으로 인식합니다.

```text
/plugin marketplace add eun7661010/korean-content-review
/plugin install korean-content-review@korean-content-review
```

### 2. Claude Code 수동 설치

이 저장소의 `skills/*` 폴더를 `~/.claude/skills/`에 복사합니다. 각 폴더의 `SKILL.md`, `references/`, `scripts/`를 함께 복사해야 합니다.

### 3. Codex

`skills/*` 폴더를 `~/.codex/skills/` 또는 `~/.agents/skills/`에 복사합니다. 아래 CLI 예제는 저장소 루트 기준이며, 복사해서 설치했다면 실제 스킬 위치로 바꿉니다.

### 의존성

텍스트 검사에는 Python 3.10+가 필요합니다.

```bash
pip install kiwipiepy
```

줄바꿈 동적 검사에는 Node.js 18+와 Playwright·브라우저가 필요합니다. 검수할 프로젝트 폴더에서 설치합니다. 이 저장소의 개발 의존성은 실측에 사용한 Playwright 1.59.1로 고정했습니다.

```bash
npm i -D playwright
npx playwright install chromium webkit firefox
```

정적 줄바꿈 검사와 두 렌더 도우미의 자체 시험은 Playwright 없이 실행할 수 있습니다. 맞춤법 모듈은 별도 외부 서비스 연결과 이용 조건 확인이 필요합니다.

## 사용 예

스킬을 설치한 뒤 대화로 요청할 수 있습니다.

> 이 안내문의 띄어쓰기와 문체를 검수해 줘. 작품 인용은 그대로 두고 원문·제안·근거만 보여 줘.

> 이 사이트를 모바일 폭 320·390px에서 검수해 줘. 한국어 어절이 끊기거나 버튼이 두 줄이 되는 곳을 찾아 줘. 작품 원문은 제외해 줘.

> 이 초안의 맞춤법도 외부 바른한글 검사기로 확인해 줘. 개인정보와 원문 보호 구간은 제외하고 최대 5회만 요청해 줘.

텍스트·사이트 통합 검사:

```bash
python skills/korean-content-review/scripts/review.py text draft.md \
  --fmt md --modules spacing,style --format md --out review.md
python skills/korean-content-review/scripts/review.py text draft.md \
  --fmt md --modules spell --max-requests 5 --format json --out spelling.json
python skills/korean-content-review/scripts/review.py site https://example.com \
  --modules spacing,style --linebreak --widths 320,390,768,1440 \
  --engines chromium,webkit
```

줄바꿈만 검사:

```bash
node skills/korean-line-break/scripts/ko-wrap-static.mjs src --strict
node skills/korean-line-break/scripts/ko-wrap-check.mjs public/example.html \
  --widths 320,390,768,1440 --engines chromium,webkit,firefox \
  --ignore '.work-verse, [data-original-text]' --out linebreak-report.json
```

동적 검사는 실제 줄을 측정합니다. 정적 검사는 규칙 누락을 찾는 보조 검사이며, 오탐은 사람이 검토합니다. 검출기의 기준선·로그인 상태·예외 옵션은 [검사 지침](skills/korean-line-break/references/qa-detector.md)을 참고하세요.

## 저장소 구조

```text
.claude-plugin/          플러그인·마켓플레이스 설정
.github/workflows/       공개 패키지 CI
skills/
  korean-content-review/ 통합 CLI·원문 보호·맞춤법·문체 검사
  kiwi-spacing/          띄어쓰기 검사
  fluent-korean-content/ 한국어 편집 지침
  korean-line-break/     CSS·React Native 지침과 줄바꿈 검출기
benchmarks/
  text/                  텍스트 엔진 측정
  line-break/            실서비스 집계·전후 이미지·일반화 기록
tests/                   네트워크 없는 텍스트 테스트·브라우저 픽스처
tools/
  export_skills.py        정본에서 공개 폴더로 내보내기
  scan_private.py         공개 금지 정보 검사
LICENSE
THIRD_PARTY_NOTICES.md
```

## 한계

- Safari 27은 WebKit 27.2, Android는 API 34 에뮬레이터로 확인했습니다. iOS 27 실기기, Android 15 이상 기기, TalkBack 낭독(앱 텍스트에 WJ가 들어감)은 실기기에서 한 번 더 확인하세요.
- 줄바꿈 결과는 글꼴·데이터·폭·브라우저에 따라 달라집니다. Firefox의 pretty 미지원, 최대 글자 크기, 긴 실제 문구도 확인하세요.
- 문체 규칙은 제안입니다. 문맥과 독자, 기존 문체·용어를 고려한 사람의 판단이 필요합니다.
- 보호 표시가 없는 원문은 자동 식별이 완전하지 않을 수 있습니다. 원문 범위를 명시하고 억제 집계를 검토하세요.
- 외부 맞춤법 서비스의 응답·접근 방식·이용 정책은 바뀔 수 있습니다. 무료 공개 화면을 상업적 대량 처리 API로 간주하지 마세요.

## 기여와 공개 내보내기

합성 문구나 공개 가능한 예제, 기대 결과, 브라우저·폭·글꼴 정보를 함께 제안해 주세요. 작품 원문을 교정 대상으로 삼지 않고 오탐·보호 구간·줄바꿈 회귀를 검토합니다. 실사용자의 글이나 자격증명은 포함하지 않습니다.

정본 내보내기를 미리 확인할 수 있습니다.

```bash
python tools/export_skills.py --dry-run --skills korean-line-break
python tools/export_skills.py --skills korean-line-break
python tools/scan_private.py
```

`--from`으로 정본 폴더를 지정할 수 있습니다(기본 `~/.claude/skills`). 내보내기는 `references/local-*`, `__pycache__`, `*.pyc`, `.DS_Store`를 제외하고 원본과 다른 파일을 복사합니다. 정본 문구가 그대로 공개되므로 먼저 `--dry-run` 미리보기를 확인하세요. 복사 후 저장소 전체 검사에 실패하면 종료 코드 1을 반환합니다. 복사한 파일을 자동으로 되돌리거나 공개용 문구를 자동 변환하지 않습니다.

검사기는 개인 홈 경로·내부 작업명·환경변수 자격증명 값·권한 키·토큰·이메일·IPv4·내부 ID를 찾고 파일:줄과 유형을 출력합니다. 기본 허용 목록은 없습니다. 꼭 필요한 공개 예외는 `--allow '정규식'`을 명시하면 일치한 값에만 적용됩니다. 자격증명 파일은 내용을 열지 않고 존재를 보고합니다. 바이너리 안의 문자열도 검사하지만 이미지에 그려진 글자는 읽지 못하므로 공개 이미지도 직접 확인하세요.

검증 명령:

```bash
pytest -q tests
node skills/korean-line-break/scripts/ko-nobreak.mjs --selftest
node skills/korean-line-break/scripts/rn-ko-lines.mjs --selftest
node --test tests/linebreak_fixture.test.mjs
python tools/scan_private.py
```

Python 테스트에는 `pytest`가 필요합니다. 테스트는 외부 맞춤법 서비스에 요청하지 않습니다.

## 라이선스와 출처

자체 코드·문서는 [MIT](LICENSE)입니다. 한국어 편집 지침은 [snflkd/fluent-korean](https://github.com/snflkd/fluent-korean), 맞춤법 모듈은 [NomaDamas/k-skill](https://github.com/NomaDamas/k-skill)의 `korean-spell-check`를 바탕으로 만들었습니다. [kiwipiepy](https://github.com/bab2min/kiwipiepy)는 LGPL-3.0 의존성으로 별도 설치하며, Playwright는 Apache-2.0 개발 의존성입니다.

[nara-speller](https://nara-speller.co.kr/speller/)는 저장소에 포함되지 않은 외부 서비스입니다. 이용 조건은 해당 서비스 정책을 따릅니다. 원본 MIT 라이선스 전문과 포크·의존성·서비스 고지는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 정리했습니다. 줄바꿈의 공식 문서·표준 출처는 [sources.md](skills/korean-line-break/references/sources.md)에 있습니다.
