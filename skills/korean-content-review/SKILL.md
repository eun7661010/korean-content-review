---
name: korean-content-review
description: "한국어 검수·윤문·띄어쓰기·맞춤법·문체 검사와 사이트 문구 점검을 할 때 사용한다. 문서·교재 해설·칼럼·공지·버튼 라벨에서 교정 후보를 찾아 원문, 제안, 근거, 확신도와 보호 구간 억제 건수를 함께 보고한다. 시 행·고전 원문·지문·인용은 먼저 표시하고 모든 검사에서 제외한다. 기본 검수는 로컬 Kiwi와 결정론적 문체 규칙으로 실행하며, 맞춤법은 외부 전송을 알린 뒤 선택적으로 사용한다. 공개 페이지의 보이는 문구 추출과 UI 줄바꿈 스킬 연계, 검토 후 명시적인 적용까지 같은 계약으로 처리한다."
license: MIT
updated: "2026-10-08T10:57:50+09:00"
---
<!-- 문체 지침 출처: https://github.com/snflkd/fluent-korean (MIT).
맞춤법 파서 출처: https://github.com/NomaDamas/k-skill (MIT).
각 저작권·허가 문구는 references의 라이선스 파일을 유지한다. -->

# 작품 원문을 보호하는 한국어 검수

작품 원문은 고유 콘텐츠다. 시의 행·연, 고전 표기, 지문, 인용 문장을 어떤 모듈도 고치거나 교정 후보로 보고하지 않는다. 원문에 오류처럼 보이는 표기가 있어도 먼저 원전과 대조한다. 원문 표시가 없는 현대 문학을 자동으로 알아보는 기능은 없으므로 검사 전에 표시한다.

## 순서

1. 원문과 용어를 표시한다. Markdown·평문은 `<!-- original -->`…`<!-- /original -->` 또는 `:::original`…`:::`를 쓰고, HTML은 `data-original-text`, 작품 클래스 또는 `.passage`, `.excerpt`, `.exam-passage`, `.exam-box`로 표시한다. 학생 후기·리뷰·인용도 작성자의 글로 보호한다. Markdown의 `>`와 HTML의 `blockquote`, `q`, `itemprop="reviewBody"`, `data-user-content`, 후기·인용 클래스가 해당한다.
2. 띄어쓰기를 로컬 Kiwi로 검사한다. 기본 `--spacing strict`는 확실한 범주만 보고한다. 사전은 한 줄에 용어 하나를 UTF-8로 적는다.
3. 맞춤법 검사가 필요하면 외부 전송을 고지한다. `spell`은 기본 꺼짐이며, 보호 구간을 자리표시자로 가린 텍스트를 nara-speller로 보낸다. 나머지 설명문도 외부로 나가므로 비공개 정보가 있으면 실행하지 않는다.
4. 문체·표기 후보를 검토한다. 독자, 뜻, 기존 높임 수준을 유지하며 자연스러운 원문은 그대로 둔다.
5. 사이트 화면은 `korean-line-break`로 검사한다. 원문 선택자는 `--ignore`로 제외한다. 텍스트 검수 통과만으로 화면 줄바꿈까지 통과했다고 판단하지 않는다.

## 실행

Python 3.10 이상과 kiwipiepy가 필요하다. 저장소 루트에서 실행한다.

```bash
python skills/korean-content-review/scripts/review.py text article.md --fmt md
python skills/korean-content-review/scripts/review.py text article.md --modules spacing,style --terms glossary.txt --format json --out report.json
python skills/korean-content-review/scripts/review.py text article.md --spacing all --profile article
python skills/korean-content-review/scripts/review.py text ocr.md --spacing repair --modules spacing
python skills/korean-content-review/scripts/review.py text ocr.md --spacing repair --modules spacing --apply --quiet
python skills/korean-content-review/scripts/review.py text ui.md --profile ui --modules style
python skills/korean-content-review/scripts/review.py text article.md --modules spell --max-requests 5
python skills/korean-content-review/scripts/review.py text article.md --fmt md --apply
python skills/korean-content-review/scripts/review.py site https://example.org --linebreak --widths 320,390,768,1440 --engines chromium,webkit
```

평문은 `--fmt plain`, HTML 파일은 `--fmt html`, 표준 입력은 파일명 대신 `-`를 사용한다. 기본 출력은 Markdown이다. `--apply`(별칭 `--write`)를 지정해야 파일을 쓰며, 보호 밖 띄어쓰기와 확신도 0.95 이상의 표기·외래어 사전 규칙만 적용하고 diff를 보고한다. 문체와 nara 제안은 자동 적용하지 않는다. 겹친 적용 구간은 거부한다. 원문 개행은 보존한다.

기본값은 `--spacing strict --profile article`이다. strict는 의존명사·한글 수사와 단위·떨어진 조사/어미·확실한 부정 문맥만 보고한다. 보조용언·합성명사·전문용어·기호·영문/숫자 경계는 제외하고 NBSP는 보존한다. `all`은 선택적 후보도 범주와 확신도를 붙여 보고한다. `repair`는 OCR 공백 복원용으로 범주 필터 없이 분석하고 변경된 줄만 `[line N]` / `전:` / `후:`로 보여 준다. 세 모드 모두 원문을 보호하며 파일 쓰기는 명시해야 한다. 검수에서 공백 없는 한글 20자 이상 줄을 만나면 머리에 repair 안내를 표시한다. article은 말투 혼용을 보고하지 않고, 120자를 넘는 문장만 info로 알린다. ui는 긴 문장 검사를 끄며 화면/문서당 말투 혼용 한 건에 예시 두 개를 붙인다.

## 보고서 읽기

요약 표에는 모듈별 심각도와 억제 수가 있다. 발견 목록은 파일·줄, 원문 ±10자 문맥 → 제안 적용 문맥, 이유, 확신도 순서다. 바뀌는 자리를 `⟦…⟧`로 표시하므로 공백 삽입도 `올⟦⟧것` → `올⟦ ⟧것`처럼 보인다. JSON은 기존 Finding 필드와 함께 `context_before`, `context_after`를 담고, 제안 없는 항목의 후 문맥은 null이다. repair의 줄별 전후는 `items[].line_changes`에 있다. 보고서의 `spacing`, `profile`, `items[].findings`, `suppressed`, `diagnostics`, `external`과 사이트 항목의 `selector`, `original_block`, `protection`도 유지한다. `--quiet`는 발견·변경 없는 파일 출력을 생략한다. 보호 비율은 `protected_chars / chars`로 계산한다.

| 등급 | 해석 |
|---|---|
| error | 확실한 표기 후보. 작품·고유명사는 표시로 제외한다. |
| warn | 띄어쓰기·번역투·문법 후보. 문맥 확인이 필요하다. |
| info | 긴 문장·문체 혼용·상투어 남발·숫자와 단위의 화면 배치 검토. 오류 판정이 아니다. |

억제는 보호 구간에 걸린 후보 수이지 원문 오류 수가 아니다. 외부 전송에서 가린 구간 수는 `external.masked_spans`로 별도 기록한다. 확신도는 규칙의 보수성 또는 형태소 분석 점수차에 따른 휴리스틱이며 정답 확률이 아니다. 후보가 0개여도 내용·출처·의미 검증을 대신하지 않는다.

## 한계와 참조

- 보호: 표시 없는 작품을 완벽하게 식별하지 못한다. 원문 표시·옛한글 줄·한자·인용·코드·URL·이메일·태그·표지·용어를 보수적으로 제외한다. [보호 계약](references/protect-spans.md)
- 띄어쓰기: 사전 밖 고유명사, 잘못 끊긴 행, 문장 경계에서는 오분석할 수 있다. [띄어쓰기](references/spacing.md)
- 맞춤법: 비공식 웹 응답 형식과 서비스 제한에 의존한다. 연결·해석 실패를 건너뛰고 보고한다. [맞춤법](references/spelling.md)
- 문체: 의미·사실·논리·누락된 성분 전체를 판정하지 못한다. [문체](references/style.md)
- 사이트: CSS 렌더·클라이언트 로딩·로그인 콘텐츠는 HTML 추출만으로 볼 수 없다. [사이트 검수](references/site-review.md)
