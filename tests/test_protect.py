import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/korean-content-review/scripts"))
import pytest
from kcr.protect import Span, find_protected, merge_spans
from kcr.extract import extract_blocks


@pytest.mark.parametrize("text,fmt,kind", [
    ("<!-- original -->컨텐츠<!-- /original -->", "md", "original"),
    (":::original\n역활\n:::", "plain", "original"),
    (":::original\n끝나지 않은 원문", "md", "original"),
    ("<!-- original -->끝나지 않은 원문", "md", "original"),
    ("`컨텐츠`", "md", "code"), ("```py\n컨텐츠\n```", "md", "code"),
    ("~~~\n컨텐츠\n~~~", "md", "code"),
    ("https://example.org/컨텐츠", "plain", "url"),
    ("hello@example.org", "plain", "email"),
    ("<b>컨텐츠</b>", "html", "tag"),
    ("불휘 기픈 남ᄀᆞᆫ", "plain", "old-hangul"),
    ("ㆍ아래아가 든 줄", "plain", "old-hangul"),
    ("江湖病", "plain", "hanja"), ("“컨텐츠”", "plain", "quote"),
    ("> 컨텐츠\n> 역활", "md", "quote"),
    ("---\n컨텐츠: 역활\n---\n설명", "md", "code"),
    ("[[컨텐츠]]", "md", "code"), ("{{컨텐츠}}", "plain", "code"),
])
def test_protection_kinds(text, fmt, kind):
    spans = find_protected(text, fmt)
    assert any(s.kind == kind for s in spans)
    assert all(a.end <= b.start for a, b in zip(spans, spans[1:]))


@pytest.mark.parametrize("marker", ["(가)", "[A]", "〈보기〉", "㉠", "①", "ⓐ"])
def test_marker_does_not_protect_particle(marker):
    text = marker + "와 비교한다"
    spans = find_protected(text)
    assert spans == [Span(0, len(marker), "marker")]


def test_merge_priority_and_term():
    assert merge_spans([Span(1, 5, "term"), Span(3, 8, "original")]) == [Span(1, 8, "original")]
    assert find_protected("컨텐츠은행을 이용", terms=["컨텐츠은행"]) == [Span(0, 5, "term")]


@pytest.mark.parametrize("attr", ["data-original-text", 'class="lit-verse"', 'class="verse"',
                                 'class="serif"', 'class="original-text"', 'class="poem"', 'class="stanza"'])
def test_html_nested_entities_and_multiline(attr):
    text = f"<div {attr}>컨텐츠\n<span>역활&amp;메세지</span></div><p>설명</p>"
    spans = find_protected(text, "html")
    for value in ["컨텐츠", "역활", "&amp;", "메세지"]:
        i = text.index(value)
        assert any(s.kind == "original" and s.start <= i and i + len(value) <= s.end for s in spans)
    i = text.index("설명")
    assert not any(s.start <= i < s.end for s in spans)


def test_extract_visible_blocks_and_inline_original():
    html = '<nav>반복메뉴</nav><script>코드</script><h1>제목</h1><p>설명 <span class="poem">원문&amp;시</span> 후기</p><button aria-label="누르기">시작</button><p hidden>숨김</p><p style="display: none">감춤</p>'
    blocks = extract_blocks(html)
    assert [b.text for b in blocks] == ["제목", "설명", "원문&시", "후기", "누르기", "시작"]
    assert [b.text for b in blocks if b.original] == ["원문&시"]
    assert all(b.selector for b in blocks)


def test_extract_duplicate_menu_and_br():
    blocks = extract_blocks('<p>안내</p><p>안내</p><div class="verse">가<br>나</div>')
    assert [b.text for b in blocks] == ["안내", "가", "나"]


@pytest.mark.parametrize("html,expected", [
    ('<div><a>로그인</a><button>메뉴</button><a>무료 시작</a></div>', ["로그인", "메뉴", "무료 시작"]),
    ('<div><button>특강 후기 보내기</button><span>후기를 작성하세요.</span></div>', ["특강 후기 보내기", "후기를 작성하세요."]),
    ('<header><a>학부모</a><a>가이드</a><time>2026. 0</time></header>', ["학부모", "가이드", "2026. 0"]),
    ('<div><label>80분 실전</label><output>상한·보류</output></div>', ["80분 실전", "상한·보류"]),
    ('<p>앞<img alt="그림 설명">뒤</p>', ["앞", "그림 설명", "뒤"]),
    ('<select><option>선택 하나</option><option>선택 둘</option></select>', ["선택 하나", "선택 둘"]),
    ('<table><tr><td>첫 칸</td><th>둘째 칸</th></tr></table>', ["첫 칸", "둘째 칸"]),
])
def test_element_boundaries(html, expected):
    assert [b.text for b in extract_blocks(html)] == expected


@pytest.mark.parametrize("tag", ["b", "strong", "em", "i", "u", "mark", "small", "sup", "sub", "span", "code", "ruby"])
def test_only_inline_formatting_keeps_text_joined(tag):
    assert [b.text for b in extract_blocks(f"<p>읽을<{tag}>수</{tag}> 있다.</p>")] == ["읽을수 있다."]


def test_nav_footer_and_business_repetition_excluded():
    html = '<nav>메뉴</nav><footer>반복 푸터</footer><p>사업자 정보: 안내</p><p>통신판매업 신고</p><p>안내문</p><p>안내문</p>'
    assert [b.text for b in extract_blocks(html)] == ["안내문"]


def test_extract_nbsp_and_table_metadata():
    html = '<p>\u00a0두\u00a0시간\u00a0</p><table><tr><td>대조 설명</td></tr></table><p>대조 설명</p>'
    blocks = extract_blocks(html)
    assert blocks[0].text == "\u00a0두\u00a0시간\u00a0"
    assert [b.table for b in blocks[1:]] == [True, False]


@pytest.mark.parametrize("tag,attrs,kind", [
    ("blockquote", "", "quote"), ("q", "", "quote"),
    ("p", 'itemprop="reviewBody"', "quote"), ("div", "data-user-content", "quote"),
    ("div", 'class="student-review"', "quote"), ("div", 'class="testimonial-card"', "quote"),
    ("span", 'class="quote-body"', "quote"),
    ("div", 'class="passage"', "original"), ("div", 'class="excerpt"', "original"),
    ("div", 'class="exam-passage"', "original"),
    ("div", 'class="exam-box"', "original"),
    ("section", 'id="reviews"', "quote"),
    ("section", 'data-section="course-reviews"', "quote"),
])
def test_user_content_and_passage_protected_in_both_paths(tag, attrs, kind):
    html = f'<{tag} {attrs}><b>할수 있다.</b> 역활과 컨텐츠</{tag}><p>운영자 안내</p>'
    spans = find_protected(html, "html")
    i = html.index("할수")
    assert any(s.kind == kind and s.start <= i < s.end for s in spans)
    blocks = extract_blocks(html)
    assert blocks[0].protection == kind
    assert blocks[0].original == (kind == "original")
    assert blocks[-1].protection is None


def test_child_quote_utility_does_not_protect_author_article():
    html = '<div class="[&_blockquote]:my-8 [&_blockquote_p]:text-sm"><p>운영자의 할수 있다.</p><blockquote>학생의 할수 있다.</blockquote></div>'
    blocks = extract_blocks(html)
    assert blocks[0].protection is None
    assert blocks[1].protection == "quote"
    spans = find_protected(html, "html")
    assert not any(s.kind == "quote" and s.start <= html.index("운영자") < s.end for s in spans)
    assert any(s.kind == "quote" and s.start <= html.index("학생") < s.end for s in spans)


@pytest.mark.parametrize("fmt,text", [
    ("md", "> 할수 있다. 컨텐츠를 써요.\n> 역활을 설명합니다."),
    ("html", '<blockquote>할수 있다. 컨텐츠</blockquote>'),
    ("html", '<section id="reviews"><article>할수 있다. 역활</article></section>'),
    ("html", '<div class="exam-box">할수 있다. 컨텐츠</div>'),
])
def test_quoted_or_original_author_text_has_no_findings(fmt, text):
    from kcr.review import review_text
    from kcr.findings import apply_findings
    result = review_text(text, fmt, spacing="all", profile="ui")
    assert not result["findings"]
    assert result["counter"].total > 0
    assert apply_findings(text, result["findings"]) == text
