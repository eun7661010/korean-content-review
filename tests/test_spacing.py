import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/korean-content-review/scripts"))
import pytest
from kcr import spacing
from kcr.findings import SuppressedCounter, apply_findings, overlaps
from kcr.protect import find_protected
from kcr.review import review_text

FIXTURES = Path(__file__).parent / "fixtures"


def test_spacing_suggestion_and_reason():
    text = "다음문장을확인하세요."
    findings = spacing.check(text, [], spacing="all")
    assert findings
    assert all("형태소 분석 기반 제안" in f.message and 0 <= f.confidence <= 1 for f in findings)
    assert apply_findings(text, findings) == "다음 문장을 확인하세요."


def test_correct_and_newlines():
    text = "다음 문장을 확인하세요.\r\n좋잖아. 괜찮아.\n"
    assert spacing.check(text, []) == []


@pytest.mark.parametrize("fixture", ["classical.md", "classical_prose.md", "questions.md", "original.html"])
@pytest.mark.parametrize("prefix", ["", "설명을확인하세요.\n", "컨텐츠 안내\n\n"])
@pytest.mark.parametrize("mode", ["strict", "all", "repair"])
def test_original_never_changes(fixture, prefix, mode):
    fmt = "html" if fixture.endswith("html") else "md"
    text = prefix + (FIXTURES / fixture).read_text(encoding="utf-8")
    spans = find_protected(text, fmt, ["지국총", "살어리랏다", "컨텐츠은행"])
    reviewed = review_text(text, fmt, terms=["지국총", "살어리랏다", "컨텐츠은행"], spacing=mode)
    assert all(not overlaps(f.start, f.end, s) for f in reviewed["findings"] for s in spans)
    findings = spacing.check(text, spans, spacing=mode)
    revised = apply_findings(text, findings)
    # 적용 전후 위치 변화량을 계산해 모든 보호 문자열을 정확히 대조한다.
    for s in spans:
        delta = sum(len(f.suggestion) - (f.end - f.start) for f in findings if f.end <= s.start)
        assert revised[s.start + delta:s.end + delta] == text[s.start:s.end]
    assert revised.count("\n") == text.count("\n")


def test_suppression_and_dictionary():
    text = ":::original\n다음문장을확인하세요.\n:::\n컨텐츠은행"
    counter = SuppressedCounter()
    findings = spacing.check(text, find_protected(text, "md", ["컨텐츠은행"]), counter=counter, terms=["컨텐츠은행"])
    assert not findings
    assert counter.total > 0


def test_postfix_and_sentence_option():
    assert spacing.post_fix("좋잖 아. 괜찮 아.") == "좋잖아. 괜찮아."
    assert spacing.check("다음문장을확인하세요.", [], sentence=False, spacing="all")


@pytest.mark.parametrize("source,expected,rule", [
    ("할수 있다.", "할 수 있다.", "spacing-bound-noun"),
    ("하는것은 좋다.", "하는 것은 좋다.", "spacing-bound-noun"),
    ("할만큼 했다.", "할 만큼 했다.", "spacing-bound-noun"),
    ("할뿐이다.", "할 뿐이다.", "spacing-bound-noun"),
    ("갈데가 없다.", "갈 데가 없다.", "spacing-bound-noun"),
    ("공부한지 오래됐다.", "공부한 지 오래됐다.", "spacing-bound-noun"),
    ("아는바를 쓴다.", "아는 바를 쓴다.", "spacing-bound-noun"),
    ("앉은채 읽는다.", "앉은 채 읽는다.", "spacing-bound-noun"),
    ("아는척 한다.", "아는 척 한다.", "spacing-bound-noun"),
    ("읽은듯 하다.", "읽은 듯 하다.", "spacing-bound-noun"),
    ("두시간 동안 세번 읽었다.", "두 시간 동안 세 번 읽었다.", "spacing-unit"),
    ("학생 이 왔다.", "학생이 왔다.", "spacing-particle"),
    ("학생 에게 알렸다.", "학생에게 알렸다.", "spacing-particle"),
    ("좋 은 일이다.", "좋은 일이다.", "spacing-ending"),
    ("수업을 안했다.", "수업을 안 했다.", "spacing-negation"),
    ("들어가면 안된다.", "들어가면 안 된다.", "spacing-negation"),
])
def test_strict_categories(source, expected, rule):
    findings = spacing.check(source, [])
    assert any(f.rule == rule for f in findings)
    assert apply_findings(source, findings) == expected


@pytest.mark.parametrize("source", [
    "해보다.", "해 보다.", "읽어보다.", "회원가입", "회원 가입", "인지과부하", "인지 과부하",
    "독서·문학", "독서 · 문학", "AI학습", "AI 학습", "45문항", "45 문항",
    "너만큼 한다.", "그뿐이다.", "어디인지 모르겠다.", "오는데 비가 온다.",
    "잘 안된다.", "시험에 떨어져 안됐다.", "구속력이 없는데 왜 지키나?", "한번 해 보자.",
    "틀린 부분은 없는지 4. 시간을 분석한다.",
])
def test_strict_excludes_optional_or_ambiguous(source):
    assert not spacing.check(source, [])


@pytest.mark.parametrize("mode", ["strict", "all", "repair"])
def test_nbsp_is_preserved(mode):
    source = "두\u00a0시간 45\u00a0문항 할\u00a0수 있다."
    findings = spacing.check(source, [], spacing=mode)
    assert not findings


def test_all_has_category_and_strict_reduces_scope():
    source = "회원가입을 해보다. 할수 있다."
    broad = spacing.check(source, [], spacing="all")
    strict = spacing.check(source, [])
    assert any(f.rule == "spacing-optional" for f in broad)
    assert all(f.rule in spacing.STRICT_RULES for f in strict)
    assert len(broad) > len(strict) > 0


def test_repair_restores_ocr_without_category_filter():
    source = "논증은크게연역과귀납으로나뉜다전제가참이면결론이참이다"
    assert not spacing.check(source, [])
    findings = spacing.check(source, [], spacing="repair")
    assert any(f.rule == "spacing-optional" for f in findings)
    assert apply_findings(source, findings) == "논증은 크게 연역과 귀납으로 나뉜다 전제가 참이면 결론이 참이다"


def test_repair_analyzes_whole_lines_with_existing_whitespace():
    class FakeKiwi:
        def __init__(self):
            self.calls = []

        def space(self, text, *, reset_whitespace):
            self.calls.append((text, reset_whitespace))
            return text.replace("할수", "할 수")

        def analyze(self, text, top_n):
            return []

    kiwi = FakeKiwi()
    source = "할수 있다. 할수 없다.\r\n할수 있다.\n"
    findings = spacing.check(source, [], kiwi=kiwi, spacing="repair")
    assert kiwi.calls == [("할수 있다. 할수 없다.", False), ("할수 있다.", False)]
    revised = apply_findings(source, findings)
    assert revised == "할 수 있다. 할 수 없다.\r\n할 수 있다.\n"
    assert spacing.changed_lines(source, revised) == [
        {"line": 1, "original": "할수 있다. 할수 없다.", "corrected": "할 수 있다. 할 수 없다."},
        {"line": 2, "original": "할수 있다.", "corrected": "할 수 있다."},
    ]


@pytest.mark.parametrize("source,count", [
    ("논증은크게연역과귀납으로나뉜다전제가참이면결론이참이다", 1),
    ("가" * 20 + "\n" + "나" * 25, 2),
    ("가" * 19, 0),
    ("가" * 20 + " 나", 0),
    ("가" * 20 + "\u00a0나", 0),
    ("A" * 30, 0),
])
def test_sparse_line_count(source, count):
    assert spacing.sparse_line_count(source) == count
