# Fork/adaptation of NomaDamas/k-skill, korean_spell_check.py, MIT License.
# Upstream: https://github.com/NomaDamas/k-skill
# Copyright (c) NomaDamas. Full notice: ../../references/KSPELL-LICENSE
"""선택적 저빈도 nara-speller 검사. 보호 텍스트를 가리고 좌표를 원본으로 복원한다."""
import json
import re
import time
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from .findings import emit

DEFAULT_RESULTS_URL = "https://nara-speller.co.kr/old_speller/results"
RESULT_PAYLOAD_PATTERN = re.compile(r"data\s*=\s*(\[[\s\S]*?\]);\s*pageIdx\s*=")
NO_ISSUES_PATTERN = re.compile(r"맞춤법과\s*문법\s*오류를\s*찾지\s*못했습니다")


def strip_html(value):
    return unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", str(value or ""), flags=re.I))).strip()


def split_candidates(value):
    return [v.strip() for v in str(value or "").split("|") if v.strip()]


def extract_result_payload(html):
    match = RESULT_PAYLOAD_PATTERN.search(html)
    if not match:
        if NO_ISSUES_PATTERN.search(html):
            return []
        raise ValueError("검사 응답에서 결과를 찾지 못했습니다.")
    payload = json.loads(match.group(1))
    if not isinstance(payload, list) or any(not isinstance(p, dict) or
            not isinstance(p.get("errInfo", []), list) or
            any(not isinstance(e, dict) for e in p.get("errInfo", [])) for p in payload):
        raise ValueError("검사 결과의 페이지·오류 목록 형식이 맞지 않습니다.")
    return payload


@dataclass
class MaskedText:
    text: str
    mapping: list
    replacements: dict = field(default_factory=dict)

    def restore(self, value):
        for token, original in self.replacements.items():
            value = value.replace(token, original)
        return value


def mask_protected(text, spans):
    parts, mapping, replacements = [], [], {}
    prefix = "KCRPROTECTED"
    while prefix in text:
        prefix += "X"
    cursor = 0
    for i, span in enumerate(spans):
        parts.append(text[cursor:span.start])
        mapping.extend(range(cursor, span.start))
        token = f"{prefix}{i:06d}Z"
        parts.append(token)
        mapping.extend([span] * len(token))
        replacements[token] = text[span.start:span.end]
        cursor = span.end
    parts.append(text[cursor:])
    mapping.extend(range(cursor, len(text)))
    return MaskedText("".join(parts), mapping, replacements)


def split_chunks(text, max_chars=1500, tokens=()):
    """문장·문단 경계 우선. 원문 좌표를 잃지 않으며 자리표시자를 쪼개지 않는다."""
    if max_chars < 32:
        raise ValueError("max_chars는 32 이상이어야 합니다.")
    if not text.strip():
        return []
    boundaries = [m.end() for m in re.finditer(r"(?<=[.!?。！？])\s+|\n+", text)]
    ranges = [(m.start(), m.end()) for token in tokens for m in re.finditer(re.escape(token), text)]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            candidates = [b for b in boundaries if start < b <= end]
            if candidates:
                end = candidates[-1]
            for a, b in ranges:
                if a < end < b:
                    end = a if a > start else b
                    break
        chunks.append((start, text[start:end]))
        start = end
    return chunks


@dataclass
class RequestBudget:
    max_requests: int = 20
    interval: float = 2.0
    requests: int = 0
    last_request: float | None = None
    failures: list = field(default_factory=list)
    masked_spans: int = 0
    skipped_chunks: int = 0

    def request(self, text, requester, *, sleep_fn=time.sleep, clock=time.monotonic):
        if self.requests >= self.max_requests:
            self.skipped_chunks += 1
            return None
        if self.last_request is not None:
            delay = max(2.0, self.interval) - (clock() - self.last_request)
            if delay > 0:
                sleep_fn(delay)
        self.last_request = clock()
        self.requests += 1
        try:
            return requester(text)
        except (OSError, ValueError, RuntimeError) as exc:
            # 문장·응답·자격정보를 오류 보고에 포함하지 않는다.
            self.failures.append(f"요청 {self.requests}: {type(exc).__name__}")
            return None


def fetch_spell_check_html(text, timeout=30):
    data = urlencode({"text1": text, "chkKey": "", "btnModeChange": "on"}).encode("utf-8")
    request = Request(DEFAULT_RESULTS_URL, data=data, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8",
        "Origin": "https://nara-speller.co.kr",
        "Referer": "https://nara-speller.co.kr/old_speller/",
    })
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def postprocess(text, spans, response, *, counter=None, masked=None, offset=0, chunk=None, diagnostics=None, stats=None):
    """같은 원응답을 기존 후처리와 비교할 수도 있다. 불명확한 좌표는 추정하지 않는다."""
    pages = extract_result_payload(response) if isinstance(response, str) else response
    def count(key, n=1):
        if stats is not None:
            stats[key] = stats.get(key, 0) + n
    count("raw_issues", sum(len(p.get("errInfo", [])) for p in pages))
    sent = chunk if chunk is not None else (masked.text if masked else text)
    combined = "".join(str(p.get("str", "")) for p in pages)
    source_indices = [i for i, c in enumerate(combined) if not c.isspace()]
    sent_indices = [i for i, c in enumerate(sent) if not c.isspace()]
    if "".join(combined[i] for i in source_indices) != "".join(sent[i] for i in sent_indices):
        count("source_mismatch", sum(len(p.get("errInfo", [])) for p in pages))
        if pages and diagnostics is not None:
            diagnostics.append("응답 텍스트와 입력이 달라 해당 청크를 건너뜁니다.")
        return []
    visible_map = dict(zip(source_indices, sent_indices))
    findings = []
    page_offset = 0
    for page in pages:
        source = str(page.get("str", ""))
        for error in page.get("errInfo", []):
            suggestions = split_candidates(error.get("candWord"))
            if not suggestions:
                count("no_suggestion")
                continue
            try:
                a, b = int(error.get("start", -1)), int(error.get("end", -1)) + 1
            except (TypeError, ValueError):
                count("invalid_offsets")
                continue
            if a < 0 or b <= a or b > len(source):
                count("invalid_offsets")
                continue
            original = str(error.get("orgStr", ""))
            # 원본 도우미의 inclusive end 처리 계승. 끝 공백 한 칸도 보정한다.
            if original and source[a:b] != original and source[a:b-1] == original:
                b -= 1
            if original and re.sub(r"\s", "", source[a:b]) != re.sub(r"\s", "", original):
                count("original_mismatch")
                continue
            positions = [visible_map[i] + offset for i in range(page_offset + a, page_offset + b) if i in visible_map]
            if not positions:
                count("invalid_offsets")
                continue
            if masked:
                coords = [masked.mapping[i] for i in range(positions[0], positions[-1] + 1)]
                protected = next((v for v in coords if not isinstance(v, int)), None)
                if protected is None:
                    token = next((token for token in masked.replacements if token in suggestions[0]), None)
                    if token:
                        protected = masked.mapping[masked.text.index(token)]
                if protected:
                    if counter is not None:
                        counter.add("spell", protected.kind)
                    count("protected")
                    continue
                start, end = coords[0], coords[-1] + 1
                suggestion = suggestions[0]
            else:
                start, end = positions[0], positions[-1] + 1
                suggestion = suggestions[0]
            if text[start:end] == suggestion:
                count("no_change")
                continue
            f = emit(text, spans, counter, "spell", "nara-suggestion", "warn", start, end,
                     suggestion, strip_html(error.get("help")) or strip_html(error.get("errMsg")) or
                     "공개 맞춤법 검사기의 제안입니다. 문맥을 확인하세요.", 0.8)
            if f:
                findings.append(f)
                count("emitted")
            else:
                count("protected")
        page_offset += len(source)
    return findings


def check(text, spans, *, counter=None, max_chars=1500, max_requests=20,
          budget=None, requester=None, sleep_fn=time.sleep, diagnostics=None, **opts):
    budget = budget or RequestBudget(max_requests=max_requests)
    masked = mask_protected(text, spans)
    budget.masked_spans += len(spans)
    chunks = split_chunks(masked.text, max_chars, masked.replacements)
    results = []
    for offset, chunk in chunks:
        # 보호 원문뿐인 청크는 전송할 필요가 없다.
        unmasked_chars = [c for i, c in enumerate(chunk) if isinstance(masked.mapping[offset + i], int)]
        if not any("가" <= c <= "힣" for c in unmasked_chars):
            continue
        response = budget.request(chunk, requester or fetch_spell_check_html, sleep_fn=sleep_fn)
        if response is None:
            continue
        try:
            results.extend(postprocess(text, spans, response, counter=counter, masked=masked,
                                       offset=offset, chunk=chunk, diagnostics=diagnostics))
        except (ValueError, KeyError, TypeError):
            budget.failures.append(f"요청 {budget.requests}: 응답 해석 실패")
    return results
