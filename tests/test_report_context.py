import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/korean-content-review/scripts"))
from kcr.findings import context_window, emit
from kcr.review import markdown_report, review_text


@pytest.mark.parametrize("text,start,end,suggestion,before,after", [
    ("크게연역과", 2, 2, " ", "크게⟦⟧연역과", "크게⟦ ⟧연역과"),
    ("학생 이 왔다", 2, 3, "", "학생⟦ ⟧이 왔다", "학생⟦⟧이 왔다"),
    ("컨텐츠 안내", 0, 3, "콘텐츠", "⟦컨텐츠⟧ 안내", "⟦콘텐츠⟧ 안내"),
    ("긴 문장", 0, 4, None, "⟦긴 문장⟧", None),
])
def test_context_window_and_json_fields(text, start, end, suggestion, before, after):
    finding = emit(text, [], None, "spacing", "example", "info", start, end, suggestion, "근거", .7)
    data = finding.to_dict()
    assert data["context_before"] == before
    assert data["context_after"] == after
    assert data["original"] == text[start:end] and data["suggestion"] == suggestion
    assert (data["start"], data["end"]) == (start, end)


def test_context_window_is_ten_characters_on_each_side():
    source = "가" * 15 + "역활" + "나" * 15
    assert context_window(source, 15, 17, "역할") == (
        "가" * 10 + "⟦역활⟧" + "나" * 10,
        "가" * 10 + "⟦역할⟧" + "나" * 10,
    )


def test_markdown_finding_shows_insertion_deletion_and_replacement_context():
    source = "올것이다. 학생 이 왔다. 컨텐츠 안내."
    reviewed = review_text(source)
    report = dict(modules=["spacing", "style"], items=[dict(source="sample", findings=[
        f.to_dict() for f in reviewed["findings"]])], suppressed={}, diagnostics=[])
    output = markdown_report(report)
    assert "올⟦⟧것이다" in output and "올⟦ ⟧것이다" in output
    assert "학생⟦ ⟧이 왔다" in output and "학생⟦⟧이 왔다" in output
    assert "⟦컨텐츠⟧" in output and "⟦콘텐츠⟧" in output
    assert "`` → ` `" not in output


def test_markdown_context_backticks_do_not_end_code_span():
    reviewed = review_text("`버튼` 컨텐츠", modules=["style"])
    report = dict(modules=["style"], items=[dict(source="sample", findings=[
        f.to_dict() for f in reviewed["findings"]])], suppressed={}, diagnostics=[])
    output = markdown_report(report)
    assert "`` `버튼` ⟦컨텐츠⟧ ``" in output and "`` `버튼` ⟦콘텐츠⟧ ``" in output
