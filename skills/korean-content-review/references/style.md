<!-- 원칙 참고: https://github.com/snflkd/fluent-korean (MIT),
업스트림 지침·저작권은 ../..의 fluent-korean-content/references에서 보존. -->
# 결정론적 문체 규칙

명확한 문장 성분·자연스러운 조사·독자에게 익숙한 표현을 유지한다는 upstream 원칙을 바탕으로, 이중 피동과 자주 쓰는 번역투의 표면 패턴을 찾는다. 의미 판단 전체를 자동화했다는 뜻은 아니다. 원문·인용과 기술 용어는 항상 제외한다.

| 규칙군 | rule id | 등급·처리 |
|---|---|---|
| 이중 피동 | double-passive | warn, 검토 |
| 번역투 | translation-in, translation-possible, translation-by, translation-from | warn, 검토 |
| 반복된 매개 표현 | translation-through | 3회 이상 warn |
| 표기 사전 | spelling-doet, spelling-days, spelling-soon, spelling-role, spelling-wenji, spelling-how, spelling-andwae | how는 warn·미적용, 나머지 error |
| 외래어 | loan-content, loan-message, loan-leadership | error |
| 숫자와 단위 | number-unit | info, 띄어쓰기도 허용되므로 고치지 않음 |
| 긴 문장 | long-sentence | article에서만 120자 초과 info, ui에서는 꺼짐 |
| 문체 혼용 | mixed-register | ui에서만 화면/문서당 info 1건 + 예시 2개, article에서는 꺼짐 |
| 상투어 반복 | cliche-repeat | 같은 표현 3회 이상 info |

'다양한', '효과적으로', '결론적으로' 자체가 잘못된 표현은 아니다. 반복될 때만 검토 후보로 보고한다. `~에 의해`, `~로부터`도 문법 오류로 단정하지 않는다. `어떻게?`는 서술어 생략인지 '어떡해'인지 구분할 수 없어 자동 제안을 쓰지 않는다. 숫자+단위의 공백은 UI 줄바꿈 검토용이다.

기본 `--profile article`은 칼럼·후기에서 의도적으로 섞은 말투를 오류로 보고하지 않는다. `--profile ui`는 짧은 UI 문구 묶음만 점검한다. 사이트에서는 80자 이하 버튼·링크·라벨 문구를 화면별로 묶고, 원문·후기 종결어는 제외해 말투 혼용 한 건을 보고한다. 시간·날짜 기점(발표일로부터·그날로부터·그때로부터·숫자/날짜+로부터)은 제외한다. 에 의해서는 20자 이하 구·대조 표(표 블록 메타데이터 또는 Markdown 표)를 제외한다.

article 결과의 최대 40건 표본은 검수자가 `precision`을 판정해야 한다. 실제 후보가 적으면 전부 기록한다. 검출 수, error 등급, 확신도가 문맥 정밀도나 교육적 효과를 증명하지 않는다. 상위 의미 편집은 [전체 윤문 원칙](../../fluent-korean-content/references/fluent-korean-not-coding.md)을 읽고 수행한다.
