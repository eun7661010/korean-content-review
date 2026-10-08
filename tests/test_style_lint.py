import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/korean-content-review/scripts"))
import pytest
from kcr.style_lint import check, RULES, DYNAMIC_RULES
from kcr.protect import find_protected
from kcr.findings import SuppressedCounter

CASES = [
    ("double-passive", "계획이 되어지는 과정", "계획이 되는 과정"),
    ("translation-in", "교육에 있어서 중요한 점", "교육에서 중요한 점"),
    ("translation-possible", "공부하는 것이 가능합니다.", "공부할 수 있습니다."),
    ("translation-by", "연습 문제의 전체 구성은 학생에 의해 선택되었다.", "학생이 연습 문제의 전체 구성을 선택했다."),
    ("translation-from", "학교로부터 받았다.", "학교에서 받았다."),
    ("spelling-doet", "잘됬다.", "잘됐다."),
    ("spelling-days", "몇일 동안", "며칠 동안"),
    ("spelling-soon", "금새 끝났다.", "금세 끝났다."),
    ("spelling-role", "역활을 맡다.", "역할을 맡다."),
    ("spelling-wenji", "웬지 좋다.", "왠지 좋다. 웬 사람이 왔다."),
    ("spelling-how", "이제 어떻게?", "어떻게 할까? 이제 어떡해?"),
    ("spelling-andwae", "그러면 안되요.", "그러면 안 돼요. 안 되는 일."),
    ("loan-content", "컨텐츠를 읽다.", "콘텐츠를 읽다."),
    ("loan-message", "메세지가 왔다.", "메시지가 왔다."),
    ("loan-leadership", "리더쉽을 발휘하다.", "리더십을 발휘하다."),
    ("number-unit", "45 문항", "45문항"),
    ("translation-through", "학습을 통해 익힌다. 연습을 통해 익힌다. 문제를 통해 익힌다.", "학습을 통해 익힌다."),
    ("long-sentence", "가" * 120 + ".", "가" * 119 + "."),
    ("mixed-register", "시작해요. 감사합니다.", "시작합니다. 감사합니다."),
    ("cliche-repeat", "다양한 책. 다양한 글. 다양한 활동.", "다양한 책. 다양한 글."),
]


@pytest.mark.parametrize("rule,bad,good", CASES)
def test_detect(rule, bad, good):
    assert any(f.rule == rule for f in check(bad, [], profile="ui" if rule == "mixed-register" else "article"))


@pytest.mark.parametrize("rule,bad,good", CASES)
def test_leave_correct(rule, bad, good):
    assert not any(f.rule == rule for f in check(good, [], profile="ui" if rule == "mixed-register" else "article"))


def test_every_rule_has_positive_and_negative_case():
    assert {c[0] for c in CASES} == {r.id for r in RULES} | DYNAMIC_RULES


@pytest.mark.parametrize("rule,bad,good", CASES)
def test_every_rule_protected(rule, bad, good):
    text = ":::original\n" + bad + "\n:::"
    counter = SuppressedCounter()
    assert not check(text, find_protected(text, "md"), counter=counter, profile="ui" if rule == "mixed-register" else "article")
    assert counter.total > 0


def test_info_only_and_context_caution():
    findings = check("다양한 글. 다양한 글. 다양한 글. 45 문항", [])
    assert all(f.severity == "info" for f in findings)
    assert not check("안되는 것과 안되면, 웬일인지, 어떻게 생각해?", [])


def test_protected_register_does_not_trigger_mixture():
    text = '“시작해요.” 감사합니다.'
    assert not any(f.rule == "mixed-register" for f in check(text, find_protected(text), profile="ui"))


def test_profiles_and_one_mixed_finding_with_two_examples():
    text = "시작해요.\n감사합니다.\n선택해요.\n확인합니다."
    assert not any(f.rule == "mixed-register" for f in check(text, []))
    findings = [f for f in check(text, [], profile="ui") if f.rule == "mixed-register"]
    assert len(findings) == 1 and "예시 1:" in findings[0].message and "예시 2:" in findings[0].message
    assert not any(f.rule == "long-sentence" for f in check("가" * 130, [], profile="ui"))
    assert [f.severity for f in check("가" * 130, []) if f.rule == "long-sentence"] == ["info"]


@pytest.mark.parametrize("text", ["성적 발표일로부터 14일 이내", "그날로부터 시작했다.", "그때로부터 기다렸다.",
                                  "2026년 10월 8일로부터", "2026.10.8로부터", "3개월로부터", "오후 3시부터"])
def test_time_from_is_normal(text):
    assert not any(f.rule == "translation-from" for f in check(text, []))


@pytest.mark.parametrize("text", ["학생에 의해 선택", "교사에 의해 검토", "| 교사에 의해 검토 | 직접 검토 |"])
def test_by_short_phrase_and_comparison_table_excluded(text):
    assert not any(f.rule == "translation-by" for f in check(text, []))
def test_comparison_table_metadata_omits_translation_by():
    text = "스스로 움직이는 경우 / 외부의 힘에 의해 움직이는 경우"
    assert any(f.rule == "translation-by" for f in check(text, []))
    assert not any(f.rule == "translation-by" for f in check(text, [], table=True))
