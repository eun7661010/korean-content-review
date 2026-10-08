import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/korean-content-review/scripts"))
import pytest
from kcr import spell_nara as spell
from kcr.protect import find_protected
from kcr.findings import SuppressedCounter


def response(text, original, suggestion):
    start = text.index(original)
    payload = [{"str": text, "errInfo": [{"orgStr": original, "candWord": suggestion,
                "start": start, "end": start + len(original) - 1, "help": "<b>표기를 확인하세요.</b>"}]}]
    return "<script>data = " + json.dumps(payload, ensure_ascii=False) + "; pageIdx = 0;</script>"


def test_same_response_filters_original_marker_term():
    text = ":::original\n컨텐츠\n:::\n[A] 컨텐츠은행 메세지"
    spans = find_protected(text, "md", ["컨텐츠은행"])
    counter = SuppressedCounter()
    assert not spell.postprocess(text, spans, response(text, "컨텐츠", "콘텐츠"), counter=counter)
    assert not spell.postprocess(text, spans, response(text, "[A]", "A"), counter=counter)
    assert not spell.postprocess(text, spans, response(text, "컨텐츠은행", "콘텐츠 은행"), counter=counter)
    findings = spell.postprocess(text, spans, response(text, "메세지", "메시지"), counter=counter)
    assert len(findings) == 1 and findings[0].original == "메세지"
    assert counter.to_dict() == {"spell:marker": 1, "spell:original": 1, "spell:term": 1}


def test_mask_restore_and_positions():
    text = ":::original\n비밀원문\n:::\n메세지"
    spans = find_protected(text, "md")
    masked = spell.mask_protected(text, spans)
    assert "비밀원문" not in masked.text
    assert masked.restore(masked.text) == text
    calls = []
    def requester(value):
        calls.append(value)
        return response(value, "메세지", "메시지")
    findings = spell.check(text, spans, requester=requester)
    assert "비밀원문" not in calls[0]
    assert findings[0].start == text.index("메세지")


def test_placeholder_proposal_is_suppressed():
    text = "‘컨텐츠’와 메세지"
    spans = find_protected(text)
    masked = spell.mask_protected(text, spans)
    token = next(iter(masked.replacements))
    counter = SuppressedCounter()
    assert not spell.postprocess(text, spans, response(masked.text, token, "수정"), masked=masked, counter=counter)
    assert counter.total == 1
    assert not spell.postprocess(text, spans, response(masked.text, "메세지", token), masked=masked, counter=counter)
    assert counter.total == 2


def test_normalized_server_whitespace_and_multiple_pages():
    text = "메세지\n역활"
    payload = [{"str": "메세지 ", "errInfo": [{"orgStr": "메세지", "candWord": "메시지", "start": 0, "end": 3}]},
               {"str": "역활", "errInfo": [{"orgStr": "역활", "candWord": "역할", "start": 0, "end": 1}]}]
    findings = spell.postprocess(text, [], payload)
    assert [(f.start, f.end, f.suggestion) for f in findings] == [(0, 3, "메시지"), (4, 6, "역할")]


def test_sentence_chunks_and_token_boundaries():
    text = "첫 문장입니다. " * 40
    chunks = spell.split_chunks(text, 64)
    assert "".join(c for _, c in chunks) == text
    assert all(len(c) <= 64 for _, c in chunks)
    masked = spell.mask_protected("가" * 20 + '“원문”' + "나" * 30, find_protected('가' * 20 + '“원문”' + '나' * 30))
    chunks = spell.split_chunks(masked.text, 32, masked.replacements)
    token = next(iter(masked.replacements))
    assert any(token in c for _, c in chunks)


def test_interval_limit_and_failure():
    budget = spell.RequestBudget(max_requests=2, interval=0)
    waits, calls = [], []
    def failure(value):
        calls.append(value)
        raise OSError("연결 실패")
    for _ in range(3):
        budget.request("검사", failure, sleep_fn=waits.append, clock=lambda: 1)
    assert len(calls) == 2 and budget.requests == 2 and waits == [2.0]
    assert len(budget.failures) == 2 and budget.skipped_chunks == 1


def test_no_issues_and_bad_payload():
    assert spell.extract_result_payload("맞춤법과 문법 오류를 찾지 못했습니다") == []
    with pytest.raises(ValueError):
        spell.extract_result_payload("<html>접속 차단</html>")
    with pytest.raises(ValueError):
        spell.extract_result_payload("data = [7]; pageIdx = 0;")
    diagnostics = []
    assert not spell.postprocess("메세지", [], response("다른 메세지", "메세지", "메시지"), diagnostics=diagnostics)
    assert diagnostics


def test_only_original_does_not_request():
    text = ":::original\n메세지\n:::"
    def forbidden(value):
        raise AssertionError("원문만 있는 입력을 전송함")
    assert not spell.check(text, find_protected(text, "md"), requester=forbidden)


def test_mask_collision_and_budget_across_calls():
    text = "KCRPROTECTED000000Z ‘보호’ 메세지"
    masked = spell.mask_protected(text, find_protected(text))
    assert "KCRPROTECTEDX000000Z" in masked.text
    assert masked.restore(masked.text) == text
    budget = spell.RequestBudget(max_requests=1)
    requester = lambda value: response(value, "메세지", "메시지")
    assert spell.check("메세지", [], budget=budget, requester=requester)
    assert not spell.check("메세지", [], budget=budget, requester=requester)
    assert budget.requests == 1 and budget.skipped_chunks == 1


def test_rejection_stats_account_for_raw_issues():
    text = "메세지 역활"
    pages = [{"str": text, "errInfo": [
        {"orgStr": "메세지", "candWord": "메시지", "start": 0, "end": 2},
        {"orgStr": "역활", "candWord": "", "start": 4, "end": 5},
        {"orgStr": "메세지", "candWord": "메시지", "start": -1, "end": 2},
    ]}]
    stats = {}
    assert len(spell.postprocess(text, [], pages, stats=stats)) == 1
    assert stats == {"raw_issues": 3, "emitted": 1, "no_suggestion": 1, "invalid_offsets": 1}


def test_http_request_is_single_post_with_no_redirect(monkeypatch):
    requests = []
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return "맞춤법과 문법 오류를 찾지 못했습니다".encode()
    class Opener:
        def open(self, request, **opts):
            requests.append(request)
            return FakeResponse()
    handlers = []
    def builder(handler):
        handlers.append(handler)
        return Opener()
    monkeypatch.setattr(spell, "build_opener", builder)
    assert spell.fetch_spell_check_html("메세지")
    assert len(requests) == 1 and requests[0].get_method() == "POST"
    assert handlers[0].redirect_request(None, None, None, None, None, None) is None
