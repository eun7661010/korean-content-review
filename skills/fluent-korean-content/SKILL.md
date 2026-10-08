---
name: fluent-korean-content
description: "한국어 윤문·문장 다듬기·표현 교정·문체 검수를 할 때 사용한다. 문서·교재 해설·안내문·보고서·사이트의 사용자 노출 글을 명확하고 자연스럽게 편집하며, 독자·목적·기존 용어·높임 수준과 의미를 유지한다. 인용·시 행·고전 원문·지문은 먼저 보호 표시를 하고 어떤 표현도 현대화하거나 교정하지 않는다. 전체 윤문 원칙을 읽어 의미를 검토하고, 통합 검수 엔진의 결정론적 문체 규칙으로 반복 표현·번역투·표기 후보를 따로 보고한다. 자동 검출의 범위를 넘어서는 문장 호응·정보 누락은 사람이 문맥을 확인한다."
license: MIT
updated: "2026-10-08T10:57:50+09:00"
---
<!-- snflkd/fluent-korean에서 들여온 비코딩 지침, MIT.
https://github.com/snflkd/fluent-korean
전체 저작권·허가 문구: references/UPSTREAM-LICENSE -->

# 의미를 유지하는 한국어 윤문

1. 원문·인용·고유 용어를 먼저 표시한다. 시·고전·지문과 원문의 행갈이를 절대 고치지 않는다. 보호 밖 해설·안내·UI 문구만 편집한다.
2. [전체 비코딩 윤문 지침](references/fluent-korean-not-coding.md)을 읽는다. 예시와 목적이 들어 있으므로 요약만으로 대체하지 않는다.
3. 독자·목적·기존 문체를 유지하고 불명확한 성분과 호응을 점검한다. 뜻을 새로 보태거나 삭제하지 않는다. 해석이 여러 갈래면 확실한 부분만 교정한다.
4. 문장 간 호응·높임·용어·마크업 보존을 확인한다. 인용·코드·식별자·링크·템플릿 변수는 유지한다.
5. 기계 규칙의 후보와 실제 편집 판단을 구분해 기록한다.

## 문체 모듈 단독 사용

```bash
python skills/korean-content-review/scripts/review.py text article.md --fmt md --modules style
python skills/korean-content-review/scripts/review.py text article.md --fmt md --modules style --terms glossary.txt --format json
python skills/korean-content-review/scripts/review.py text ui.md --fmt md --modules style --profile ui
```

LLM 윤문은 이 스킬 지침만으로 수행할 수 있다. 자동 규칙 검사는 묶음의 `korean-content-review` 엔진을 사용한다. [규칙과 등급](../korean-content-review/references/style.md), [통합 보호 계약](../korean-content-review/references/protect-spans.md)을 따른다. 후보는 원문·제안·메시지·확신도 형식으로 기록하고 원문에 걸린 후보는 억제 수로만 보고한다. 원문 표시가 없다면 먼저 표시한다.

error는 확실한 표기 후보, warn은 문맥 검토 후보, info는 길이·문체 혼용·반복 표현을 돌아보는 신호다. 정밀도는 검수자가 평가하며 검출 수를 기존 윤문 스킬보다 뛰어난 효과로 단정하지 않는다. 전체 윤문 원칙의 의미 판단을 정규식이 대신하지 않는다.

기본 article 프로필은 말투 혼용을 보고하지 않으며 120자를 넘는 문장만 info로 보고한다. ui 프로필은 긴 문장 검사를 끄고 문서/화면당 말투 혼용 한 건에 예시 두 개를 붙인다. 날짜·시간 기점의 로부터, 짧은 구와 대조 표의 에 의해서는 제외한다. 학생 후기·인용·출제 지문은 운영자가 고칠 글이 아니므로 보호한다.

업스트림 출처·라이선스와 동기화 판본은 `references/UPSTREAM-LICENSE`, `references/upstream.json`에 유지한다. 네트워크 갱신 도구는 포함하지 않는다. 공개판은 제공된 MIT 지침의 사용·보호·보고 절차를 개선한 것이다.
