# 보호 구간 계약

학생 후기·리뷰와 인용은 운영자의 작성 글이 아니므로 교정하지 않는다. Markdown의 `>` 인용문과 HTML의 `blockquote`, `q`, `[itemprop=reviewBody]`, `[data-user-content]`, review·testimonial·quote가 들어간 의미 클래스는 quote로 보호한다. 상위 section/article/div의 후기 id·data-section도 계승한다. `[&_blockquote]:...` 같은 Tailwind 자식 서식 지정은 부모의 인용 표시로 해석하지 않는다.

출제 원문은 `[data-original-text]`, `.passage`, `.excerpt`, `.exam-passage`, `.exam-box`와 기존 작품 클래스로 original 보호한다. 원문 안에 후기가 중첩돼도 original을 우선한다. 보호 표시가 일반 해설에 잘못 붙어 있으면 그 해설도 검사에서 제외되므로 마크업을 확인한다.

`find_protected(text, fmt, terms)`는 시작 포함·끝 제외의 Python 문자 좌표 `Span(start, end, kind)`를 반환한다. 겹치는 구간은 합치고 원문 보호를 우선한다. 구간이 접할 때는 합치지 않아 보호 종류별 집계를 유지한다.

원문·인용·옛한글 줄·한자열·코드·URL·이메일·HTML 태그·문항 표지·사용자 용어를 보호한다. `(가)`, `[A]`, `〈보기〉`, `㉠`, `①`, `ⓐ`는 표지만 보호하고 뒤 조사는 검사한다. 한자열 전체 문맥이 원문이면 원문 컨테이너로 표시한다. 옛한글 자모나 아래아가 든 줄은 줄 전체를 보호한다.

HTML은 정규식으로 원문 요소를 찾지 않는다. 표준 `HTMLParser`의 원문 위치와 요소 스택으로 중첩 요소·엔티티의 실제 텍스트 범위를 보존한다. 원문 표시가 닫히지 않으면 남은 텍스트를 보수적으로 보호한다. HTML 태그와 script/style/pre/code/nav 내용도 보호한다. CSS가 `.serif`를 일반 문구에 쓰면 해당 문구도 제외되므로 마크업을 검토한다.

모든 모듈은 `emit`에서 구간 겹침을 다시 확인한다. 삽입은 구간 내부 좌표일 때 억제하며 경계 밖 공백은 허용한다. `SuppressedCounter`는 모듈과 종류별 후보 수를 센다. 한 후보가 여러 보호 구간에 걸리면 첫 구간으로 한 번만 센다. 사용자 사전은 의미를 바꾸기 위한 수단이 아니라 고유 용어를 보존하는 수단이다.
