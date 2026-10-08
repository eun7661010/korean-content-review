import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "benchmarks/text/injection.py"
spec = importlib.util.spec_from_file_location("text_injection", SCRIPT)
injection = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = injection
spec.loader.exec_module(injection)


@pytest.fixture(scope="module")
def kiwi():
    return injection.spacing.get_kiwi()


@pytest.mark.parametrize("kind,source,original,replacement", [
    ("bound-noun-join", "문제를 풀 수 있는 방법이다.", " ", ""),
    ("unit-join", "두 시간 동안 연습을 이어 갔다.", " ", ""),
    ("particle-split", "학생이 문제를 교실에서 풀었다.", "", " "),
    ("misspelling", "각자의 역할을 분명히 정한다.", "역할", "역활"),
    ("double-passive", "결과가 분명하게 보였다.", "보였", "보여졌"),
])
def test_each_type_and_exact_coordinates(kiwi, kind, source, original, replacement):
    mutation = next(m for m in injection.candidates(source, kiwi) if m.kind == kind)
    changed = injection.apply_mutation(source, mutation)
    assert source[changed.clean_start:changed.clean_end] == original
    assert changed.original == original and changed.replacement == replacement
    assert changed.text[changed.start:changed.end] == replacement
    assert changed.start == changed.clean_start
    assert changed.end == changed.start + len(replacement)
    assert changed.text[:changed.start] + original + changed.text[changed.end:] == source
    assert len(injection.diff_edits(source, changed.text)) == 1


@pytest.mark.parametrize("source", ["너만큼 잘한다.", "그뿐이다.", "어디인지 궁금하다."])
def test_particle_and_question_ending_not_injected_as_bound_noun(kiwi, source):
    assert not any(m.kind == "bound-noun-join" for m in injection.candidates(source, kiwi))


def test_temporal_ji_is_injectable(kiwi):
    source = "공부한 지 오래되어 다시 시작한다."
    mutation = next(m for m in injection.candidates(source, kiwi) if m.kind == "bound-noun-join")
    assert "공부한지" in injection.apply_mutation(source, mutation).text


def test_exact_and_near_hits_have_distinct_meaning():
    f = injection.Finding("spacing", "test", "warn", 9, 9, 1, "", " ", "", 1.0)
    assert injection.hits(f, 9, 9)
    assert not injection.hits(f, 11, 11)
    assert injection.hits(f, 11, 11, 2)
    assert not injection.hits(f, 12, 12, 2)
    f = injection.Finding("spacing", "test", "warn", 9, 10, 1, " ", "", "", 1.0)
    assert injection.hits(f, 9, 10)
    assert not injection.hits(f, 10, 11)  # 끝 exclusive: 접하기만 하는 두 구간은 겹치지 않음
    assert not injection.hits(f, 8, 9)
    assert not injection.hits(f, 10, 10)


def test_zero_denominators_are_null():
    stats = injection.rates(injection.empty_stat())
    assert stats["recall"] is None and stats["precision"] is None


def test_unsupported_sentence_is_skipped_not_rewritten(kiwi):
    clean = [dict(text="행복하세요.", source="https://example.org", selector="p", table=False)]
    changed, counts, available, skipped = injection.inject_dataset(clean, kiwi)
    assert changed == [] and counts == {} and available == {} and skipped == [0]
    assert clean[0]["text"] == "행복하세요."


def test_ambiguous_hanbeon_not_treated_as_known_unit_error(kiwi):
    assert not any(m.kind == "unit-join" for m in injection.candidates("한 번 해 보자.", kiwi))


def test_selection_is_unique_deterministic_and_excludes_quotes(kiwi):
    blocks = [dict(text=f"독서 계획 {i}번 항목을 자세히 확인하세요.", source="https://example.org", selector="p", table=False) for i in range(8)]
    blocks += [blocks[0], dict(text="“인용문 안의 표현과 문장은 고치지 않습니다.”", source="https://example.org", selector="p", table=False)]
    a, count = injection.select_clean(blocks, kiwi, count=5)
    b, count_again = injection.select_clean(blocks, kiwi, count=5)
    assert a == b and count == count_again == 8
    assert len({item["text"] for item in a}) == 5
    assert not any("인용문" in item["text"] for item in a)


def test_dataset_is_reproducible_and_only_one_error(kiwi):
    clean = [dict(text="학생이 두 시간 동안 문제를 풀 수 있다.", source="https://example.org", selector="p", table=False)] * 8
    a = injection.inject_dataset(clean, kiwi)
    assert a == injection.inject_dataset(clean, kiwi)
    for item in a[0]:
        original = clean[item["clean_index"]]["text"]
        assert item["text"][:item["start"]] + item["original"] + item["text"][item["end"]:] == original
        assert len(injection.diff_edits(original, item["text"])) == 1


def test_missing_cache_has_clear_failure(tmp_path):
    done = subprocess.run([sys.executable, "-B", str(SCRIPT), "--cached", "--cache-dir", str(tmp_path)],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 2
    assert "manifest.json" in done.stderr and "네트워크로 대체 수집하지 않습니다" in done.stderr
    assert "Traceback" not in done.stderr
    assert not list(tmp_path.iterdir())


def test_page_cache_hash_mismatch_fails(tmp_path):
    (tmp_path / "page.html").write_text("<p>캐시 문장입니다.</p>", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(dict(pages=[dict(status=200, file="page.html", sha256="wrong", url="https://example.org")])), encoding="utf-8")
    with pytest.raises(ValueError, match="해시"):
        injection.read_blocks(tmp_path)


def test_public_fragments_never_exceed_twenty_chars():
    assert len(injection.fragment("가" * 90, 40, 50)) == 20
    assert len(injection.fragment("가" * 90, 0, 70)) == 20


def test_measure_counts_clean_uninjectable_and_exact_precision_separately(monkeypatch):
    def outputs(text, table, legacy, kiwi):
        # 근처 1개와 정확한 위치 1개: 재현율은 검출, 정밀도는 1/2이어야 한다.
        coordinates = [(5, 5), (7, 7)] if text == "오염" else [(0, 0)]
        fs = [injection.Finding("spacing", "test", "warn", a, b, 1, "", " ", "", 1.0) for a, b in coordinates]
        return {name: fs for name in injection.TOOLS}
    monkeypatch.setattr(injection, "tool_findings", outputs)
    clean = [dict(text="원문", table=False), dict(text="주입 불가", table=False)]
    contaminated = [dict(text="오염", table=False, kind="particle-split", clean_index=0, start=5, end=5)]
    overall, by_type, raw = injection.measure(clean, contaminated, None, None)
    stat = overall["spacing-strict"]
    assert stat["clean_sentences"] == 2 and stat["clean_findings"] == 2
    assert stat["injected_sentences"] == stat["detected_sentences_near"] == 1
    assert stat["recall"] == 1 and stat["precision"] == .5
    assert stat["off_target_findings"] == 1 and stat["off_target_findings_near"] == 0
    assert by_type["particle-split"]["spacing-strict"]["clean_sentences"] == 1
    assert len(raw["clean"]) == 2 and len(raw["corrupted"]) == 1
