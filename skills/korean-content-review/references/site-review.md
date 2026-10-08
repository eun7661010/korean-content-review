# 사이트와 UI 줄바꿈

`b`, `strong`, `em`, `i`, `u`, `mark`, `small`, `sup`, `sub`, `span`, `code`, `ruby`의 인라인 서식 경계만 이어 붙인다. 그 밖의 요소 양 경계는 블록을 끊는다. 링크·버튼·목록·라벨·표 셀·옵션·이미지 alt·br가 이웃 문구와 공백 없이 합쳐지지 않는다. NBSP는 보존한다. nav·footer와 사업자 정보·통신판매업 반복 문구는 제외한다.

각 블록은 original 여부 외에 quote/original 보호 종류, UI 여부, 표 여부를 전달한다. 인용·후기 안의 텍스트도 추출하되 검수 모듈에서는 보호해 억제 수만 센다. 표의 번역투 후보와 문서 말투 혼용은 해당 메타데이터를 사용해 검사 범위를 제한한다.

HTML에서 제목·문단·목록·버튼·라벨·표·접근성 라벨을 추출한다. script/style/nav/head/template/noscript, hidden, aria-hidden, 인라인 display:none·visibility:hidden을 제외하며 반복된 비원문 블록은 한 번만 검사한다. 외부 CSS와 JavaScript 렌더 결과는 알 수 없다. 이름표가 `.serif`인 일반 글도 원문으로 간주하므로 사이트 마크업을 확인한다.

각 블록의 선택자 힌트는 요소 경로와 nth-of-type이다. 속성 라벨은 끝에 `@aria-label` 또는 `@alt`를 붙인다. 이는 탐색 힌트이며 브라우저에 그대로 넣을 완전한 선택자가 아니다. 인라인 원문과 일반 설명은 별도 블록으로 나눠 보호 상태를 유지한다.

`site --linebreak`는 같은 skills 디렉터리의 `korean-line-break/scripts/ko-wrap-check.mjs`를 호출하고 폭·엔진·원문 `--ignore`를 넘긴다. 줄바꿈 검출기는 추가 브라우저 요청을 만들 수 있으므로 요청 제한이 있는 벤치마크에서는 실행하지 않는다. 줄바꿈 결과의 exit code와 JSON 또는 원출력을 보고서에 합친다. 줄바꿈의 실패는 텍스트 검수 성공과 별개로 보고한다.
