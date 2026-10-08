---
name: kiwi-spacing
description: "한국어 띄어쓰기 검수·키위 교정·OCR 공백 복원을 할 때 사용한다. Kiwi 형태소 분석으로 문서·칼럼·안내문·해설의 띄어쓰기 후보를 찾아 문맥, 제안, 근거, 확신도와 억제 건수를 보고한다. strict는 확실한 범주를 검수하고 all은 넓게 검사하며 repair는 공백이 사라진 줄의 전후를 보여 준다. 원문 표시, 옛한글 줄, 한자, 인용, 코드, URL, 문항 표지와 사용자 용어를 보존하고 개행을 유지한다. 파일·폴더 배치, 문장 단위 처리, 사용자 사전과 quiet 출력을 지원한다. 외부 전송 없이 실행하며 명시적인 쓰기 옵션을 사용한 경우에만 보호 구간 밖 공백 차이를 반영한다."
license: MIT
updated: "2026-10-08T10:57:50+09:00"
---

# 원문을 보호하는 로컬 띄어쓰기

작품 원문과 행갈이는 고유 콘텐츠이므로 교정하지 않는다. 먼저 `:::original` 또는 `<!-- original -->` 블록으로 표시한다. HTML은 원문 컨테이너를 사용한다. 표시법·억제·Finding 형식은 [통합 계약](../korean-content-review/references/protect-spans.md)을 따른다.

```bash
python skills/kiwi-spacing/kiwi_space.py --text "할수 있다." --check
python skills/kiwi-spacing/kiwi_space.py --file article.md --check --format json
python skills/kiwi-spacing/kiwi_space.py --dir documents --ext md,txt --terms glossary.txt --check
python skills/kiwi-spacing/kiwi_space.py --file article.md --write
python skills/kiwi-spacing/kiwi_space.py --file article.md --no-sentence --check
python skills/kiwi-spacing/kiwi_space.py --file article.md --spacing all --check
python skills/kiwi-spacing/kiwi_space.py --text "논증은크게연역과귀납으로나뉜다전제가참이면결론이참이다" --spacing repair
python skills/kiwi-spacing/kiwi_space.py --dir ocr --spacing repair --check --quiet
python skills/kiwi-spacing/kiwi_space.py --dir ocr --spacing repair --write --quiet
```

별도 스킬 명령으로 실행하지만 같은 skills 디렉터리의 `korean-content-review/scripts/kcr`를 상대 경로로 불러온다. 보호 로직을 복제하면 한쪽만 개선됐을 때 원문 보호가 달라질 수 있으므로 공통 엔진을 공유한다. 배포할 때 두 스킬을 함께 포함한다. 기존 사용자 스킬이나 내부 프로젝트의 경로에는 의존하지 않는다.

`--check`가 기본 동작이다. `--write`에서만 파일에 쓰고 diff를 출력한다. `--quiet`는 변경 없는 파일 출력을 생략하며, 변경과 별도 안내가 모두 없으면 Markdown 표준 출력도 비운다. JSON은 항상 유효한 보고서를 출력하고 quiet에서 변경 없는 파일 항목만 생략한다. `--fmt` 기본은 md이며 plain·html도 지원한다. UTF-8 사전은 한 줄에 용어 하나로 작성한다. `correct_spacing(text, kiwi, fmt=..., terms=..., spacing="repair")` 함수는 `(교정문, Finding 목록)`을 반환한다.

| 모드 | 용도 | Markdown 보고 형식 | 자동 적용 여부 |
|---|---|---|---|
| strict (기본) | 확실한 범주의 띄어쓰기 검수 | ±10자 문맥에서 `⟦변경 자리⟧` 전후·범주·확신도 | 기본 제안만, `--write`에서만 반영 |
| all | 선택적 표기까지 넓게 검수 | strict와 같은 문맥형 Finding 목록 | 기본 제안만, `--write`에서만 반영 |
| repair | OCR로 공백이 사라진 줄 복원, 범주 필터 없음 | 변경된 줄만 `[line N]` / `전:` / `후:` | 기본 미적용, `--write`에서 보호 밖 변경만 반영 |

repair는 문장 단위 옵션과 관계없이 줄 전체를 `kiwi.space(text, reset_whitespace=False)`로 분석한다. 작품·지문 원문, 인용과 사용자 용어 보호는 세 모드에서 같다. 검수 모드에서 공백 없이 한글이 20자 이상 이어진 줄이 있으면 보고서 머리에 repair 안내를 한 줄 넣는다. 모드는 자동으로 바뀌지 않는다. JSON Finding은 기존 좌표·원문·제안 필드와 함께 `context_before`, `context_after`를 제공하며 repair의 줄별 전후는 `items[].line_changes`에 담는다.

기본 `--spacing strict`는 의존명사·한글 수사와 단위·떨어진 조사/어미·확실한 부정 문맥만 보고한다. 보조용언·합성명사·전문용어·기호·영문/숫자 경계는 둘 다 허용하며 NBSP를 바꾸지 않는다. `all`은 선택적 공백 후보도 info로 보고한다. 각 Finding의 rule은 spacing-bound-noun·spacing-unit·spacing-particle·spacing-ending·spacing-negation·spacing-optional 범주를 구분한다. 학생 후기·인용·출제 지문도 통합 계약으로 보호한다.

`reset_whitespace=False`, 줄·문장 단위 분석, 잖아·찮아 오분리 후처리를 계승했다. Kiwi가 제안한 공백 차이만 보고하며 원문·개행·문장부호는 바꾸지 않는다. 모든 제안은 '형태소 분석 기반 제안'이다. 확신도 산식과 한계는 [분석 설명](../korean-content-review/references/spacing.md)을 읽는다. repair의 넓은 제안은 합성명사·전문용어도 바꿀 수 있으므로 쓰기 전에 전후를 검토한다. PDF 단락 구조·맞춤법·사실은 별도로 검수한다.
