# snflkd/fluent-korean의 비코딩 지침을 참고한 결정론적 검사, MIT.
# 원본: https://github.com/snflkd/fluent-korean (라이선스는 references 참조).
"""윤문 후보를 보수적으로 찾는다. 문체 후보는 자동 적용하지 않는다."""
import re
from dataclasses import dataclass
from .findings import emit, overlaps


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    severity: str
    message: str
    replacement: str | None = None
    confidence: float = 0.8


RULES = [
    Rule("double-passive", r"되어지|돼어지|보여지|쓰여지|읽혀지|잊혀지", "warn", "이중 피동 후보입니다. 피동 표현을 한 번만 쓰는지 확인하세요."),
    Rule("translation-in", r"에 있어서", "warn", "번역투 후보입니다. '에서', '에 관해' 등으로 뜻을 분명히 하세요."),
    Rule("translation-possible", r"하는 것이 가능(?:하다|합니다|해요)", "warn", "'할 수 있다'로 간결하게 표현할 수 있는지 확인하세요."),
    Rule("translation-by", r"에 의(?:해|하여)(?=[\s,.])", "warn", "행위자를 주어로 바꿀 수 있는지 확인하세요. 필요한 피동은 유지합니다."),
    Rule("translation-from", r"로부터", "warn", "'에서', '에게서' 등 문맥에 맞는 표현인지 확인하세요."),
    Rule("spelling-doet", r"됬", "error", "'됐'이 바른 표기입니다.", "됐", 0.99),
    Rule("spelling-days", r"(?<![가-힣])몇일(?![가-힣])|몇일(?=동안|간|이나|째|을|이|에|은)", "error", "'며칠'로 씁니다.", "며칠", 0.99),
    Rule("spelling-soon", r"(?<![가-힣])금새(?=[\s,.!?]|$)", "error", "시간 부사 '금세'의 표기를 확인하세요.", "금세", 0.96),
    Rule("spelling-role", r"역활", "error", "'역할'로 씁니다.", "역할", 0.99),
    Rule("spelling-wenji", r"웬지", "error", "'왜인지'의 준말은 '왠지'입니다. '웬'은 관형사입니다.", "왠지", 0.99),
    Rule("spelling-how", r"어떻게(?=\s*(?:[.!?]|$))", "warn", "서술어가 빠졌는지 확인하세요. '어떻게 해'의 뜻이면 '어떡해'로 씁니다.", None, 0.7),
    Rule("spelling-andwae", r"(?<![가-힣])안되(?=요(?:[\s.!?]|$)|[.!?]|$)", "error", "종결 표현은 '안 돼(요)'로 씁니다. '안 되는'은 별도 문맥입니다.", "안 돼", 0.98),
    Rule("loan-content", r"컨텐츠", "error", "외래어 표기는 '콘텐츠'입니다.", "콘텐츠", 0.99),
    Rule("loan-message", r"메세지", "error", "외래어 표기는 '메시지'입니다.", "메시지", 0.99),
    Rule("loan-leadership", r"리더쉽", "error", "외래어 표기는 '리더십'입니다.", "리더십", 0.99),
    Rule("number-unit", r"(?<![\w.])\d+(?:\.\d+)?[ \t]+(?:개|명|회|번|문항|쪽|장|분|시간|초|원|kg|cm|mm|km|%)(?![A-Za-z가-힣])", "info", "숫자와 단위는 띄어 쓸 수 있습니다. UI에서 한 묶음으로 표시할지 검토하세요.", None, 0.9),
]
SAFE_RULES = {r.id for r in RULES if r.id.startswith(("spelling-", "loan-")) and r.confidence >= 0.95}
DYNAMIC_RULES = {"translation-through", "long-sentence", "mixed-register", "cliche-repeat"}


def check_register(text, spans, *, counter=None):
    """UI 화면/문서당 한 건. 서로 다른 종결 말투의 실제 예시 두 개를 남긴다."""
    def visible(pattern):
        matches = []
        for m in re.finditer(pattern, text):
            protected = next((s for s in spans if overlaps(m.start(), m.end(), s)), None)
            if protected:
                if counter is not None:
                    counter.add("style", protected.kind)
            else:
                matches.append(m)
        return matches
    polite = visible(r"(?:해요|돼요|어요|아요|예요|이에요)[.!?]?(?=\s|$)")
    formal = visible(r"(?:합니다|됩니다|습니다|입니다)[.!?]?(?=\s|$)")
    if not polite or not formal:
        return []
    def example(m):
        start = max(text.rfind("\n", 0, m.start()) + 1, m.start() - 30)
        return text[start:m.end()].strip()
    m = polite[0]
    f = emit(text, spans, counter, "style", "mixed-register", "info", m.start(), m.end(), None,
             f"UI 문구 묶음의 말투를 확인하세요. 예시 1: {example(polite[0])} / 예시 2: {example(formal[0])}", 0.75)
    return [f] if f else []


def check(text, spans, *, counter=None, max_sentence=120, profile="article", mixed_register=True, table=False, **opts):
    if profile not in {"article", "ui"}:
        raise ValueError("profile은 article 또는 ui입니다.")
    result = []

    def add(rule, severity, start, end, suggestion, message, confidence):
        f = emit(text, spans, counter, "style", rule, severity, start, end, suggestion, message, confidence)
        if f:
            result.append(f)

    for rule in RULES:
        for m in re.finditer(rule.pattern, text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            block = text[line_start:line_end if line_end >= 0 else len(text)].strip()
            if rule.id == "translation-by" and (table or len(block) <= 20 or "|" in block):
                continue
            if rule.id == "translation-from" and re.search(
                    r"(?:일|날|때|\d|\d+[ \t]*(?:년|월|개월|시간|분|초|주))$", text[:m.start()].rstrip()):
                continue
            add(rule.id, rule.severity, m.start(), m.end(), rule.replacement, rule.message, rule.confidence)

    def eligible(pattern):
        matches = list(re.finditer(pattern, text))
        visible = []
        for m in matches:
            span = next((s for s in spans if overlaps(m.start(), m.end(), s)), None)
            if span:
                if counter is not None:
                    counter.add("style", span.kind)
            else:
                visible.append(m)
        return visible

    through = eligible(r"[을를] 통해")
    if len(through) >= 3:
        for m in through:
            add("translation-through", "warn", m.start(), m.end(), None,
                "'을/를 통해'가 문서에서 3회 이상 반복됩니다. 직접 동사로 표현할지 검토하세요.", 0.75)
    if profile == "article":
        for m in re.finditer(r"[^\n.!?]+[.!?]?", text):
            body = m.group().strip()
            if len(body) > max_sentence:
                add("long-sentence", "info", m.start(), m.end(), None,
                    f"문장이 {len(body)}자로 기준 {max_sentence}자를 넘습니다. 의미 단위로 나눌지 검토하세요.", 0.8)
    if profile == "ui" and mixed_register:
        result.extend(check_register(text, spans, counter=counter))
    for word in ("결론적으로", "다양한", "효과적으로", "중요합니다", "혁신적인", "궁극적으로"):
        matches = eligible(re.escape(word))
        if len(matches) >= 3:
            for m in matches:
                add("cliche-repeat", "info", m.start(), m.end(), None,
                    f"'{word}'이 3회 이상 반복됩니다. 구체적인 내용으로 바꿀 수 있는지 확인하세요.", 0.6)
    return sorted(result, key=lambda f: (f.start, f.rule))
