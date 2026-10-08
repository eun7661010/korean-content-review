"""공통 결과와 보호 구간 억제 집계. 위치는 Python 문자 인덱스, 끝은 exclusive."""
from collections import Counter
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Finding:
    module: str
    rule: str
    severity: str
    start: int
    end: int
    line: int
    original: str
    suggestion: str | None
    message: str
    confidence: float
    context_before: str = ""
    context_after: str | None = None

    def to_dict(self):
        return asdict(self)


def context_window(text, start, end, suggestion, radius=10):
    """원문 좌표 양옆 같은 창에서 바뀌는 자리만 표시한다. 삽입도 빈 괄호로 보인다."""
    left, right = text[max(0, start - radius):start], text[end:end + radius]
    before = f"{left}⟦{text[start:end]}⟧{right}"
    after = None if suggestion is None else f"{left}⟦{suggestion}⟧{right}"
    return before, after


class SuppressedCounter:
    def __init__(self):
        self.counts = Counter()

    def add(self, module, kind, count=1):
        self.counts[(module, kind)] += count

    @property
    def total(self):
        return sum(self.counts.values())

    def to_dict(self):
        return {f"{module}:{kind}": count for (module, kind), count
                in sorted(self.counts.items()) if count}


def overlaps(start, end, span):
    # 삽입은 구간 내부에서만 침범이다. 경계 밖의 공백은 원문 글자를 바꾸지 않는다.
    return (span.start < start < span.end if start == end
            else start < span.end and span.start < end)


def emit(text, spans, counter, module, rule, severity, start, end,
         suggestion, message, confidence):
    for span in spans:
        if overlaps(start, end, span):
            if counter is not None:
                counter.add(module, span.kind)
            return None
    before, after = context_window(text, start, end, suggestion)
    return Finding(module, rule, severity, start, end, text.count("\n", 0, start) + 1,
                   text[start:end], suggestion, message, round(confidence, 4), before, after)


def apply_findings(text, findings):
    """중복·겹침 없이 원문 좌표 기준으로 적용한다."""
    ordered = sorted(findings, key=lambda f: (f.start, f.end))
    last_end = -1
    last_start = -1
    for f in ordered:
        if f.start < last_end or f.start == last_start:
            raise ValueError("교정 구간이 겹칩니다. 모듈을 나눠 검토하세요.")
        if text[f.start:f.end] != f.original or f.suggestion is None:
            raise ValueError("교정 좌표 또는 제안이 원문과 맞지 않습니다.")
        last_start, last_end = f.start, f.end
    for f in reversed(ordered):
        text = text[:f.start] + f.suggestion + text[f.end:]
    return text
