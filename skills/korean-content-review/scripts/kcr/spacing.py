"""기존 kiwi_space.py의 줄별 처리·사용자 사전·잖아/찮아 후처리를 계승 (MIT)."""
import math
import re
from difflib import SequenceMatcher
from functools import lru_cache
from .findings import emit


@lru_cache(maxsize=4)
def get_kiwi(terms=()):
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
    for word in terms:
        if word and not any(c.isspace() for c in word):
            kiwi.add_user_word(word, "NNP")
    return kiwi


def post_fix(text):
    for pattern in (r"([가-힣])잖 아", r"([가-힣])찮 아"):
        text = re.sub(pattern, r"\1" + ("잖아" if "잖" in pattern else "찮아"), text)
    return text


def score_confidence(kiwi, text, analyses=None):
    analyses = analyses if analyses is not None else kiwi.analyze(text, top_n=2)
    if len(analyses) < 2:
        return 0.8
    # 형태소 경로 간 점수 차이를 토큰 수로 정규화한 휴리스틱이다.
    # 정답 확률로 교정된 값이 아니며, 같은 분석 경로면 0.60으로 보수적으로 둔다.
    margin = max(0, analyses[0][1] - analyses[1][1]) / max(1, len(analyses[0][0]))
    return min(0.95, 0.60 + 0.35 * (1 - math.exp(-margin)))


BOUND_NOUNS = {"것", "수", "때문", "만큼", "뿐", "데", "지", "등", "줄", "바", "채", "척", "듯"}
UNITS = {"시간", "분", "초", "번", "회", "개", "명", "권", "장", "쪽", "달", "해", "살", "잔", "대", "마리", "벌", "켤레"}
NUMERALS = {"한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉", "열", "스무", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔", "백", "천", "몇"}
STRICT_RULES = {"spacing-bound-noun", "spacing-unit", "spacing-particle", "spacing-ending", "spacing-negation"}


def sparse_line_count(text):
    """공백 없는 긴 한글 줄을 센다. 검수 모드를 자동으로 바꾸지는 않는다."""
    return sum(bool(re.search(r"[가-힣]{20,}", line)) and not any(c.isspace() for c in line)
               for line in text.splitlines())


def changed_lines(text, revised):
    """개행을 보존하는 공백 교정의 줄별 전후 보고(원문 기준 1부터)."""
    return [dict(line=n, original=old.rstrip("\r"), corrected=new.rstrip("\r"))
            for n, (old, new) in enumerate(zip(text.split("\n"), revised.split("\n")), 1)
            if old != new]


def classify(source, a, b, old, new, analyses):
    """상위 두 분석이 같은 경계 품사에 동의하는 범주만 strict에 포함한다."""
    if not a or b >= len(source) or not ("가" <= source[a - 1] <= "힣" and "가" <= source[b] <= "힣"):
        return "spacing-optional", "기호·영문·숫자 경계 또는 문장 가장자리"
    votes = []
    for tokens, _ in analyses:
        lefts = [t for t in tokens if t.start < a and t.start + t.len <= a]
        rights = [t for t in tokens if t.start == b]
        if not lefts or not rights:
            votes.append(None)
            continue
        left, right = lefts[-1], rights[0]
        category = None
        if old == "" and new == " ":
            if right.form in UNITS and left.form in NUMERALS and left.tag in {"MM", "NR"}:
                # '한번 해 보자'의 부사 한번과 횟수 한 번은 형태소 분석만으로 구분 못 한다.
                if (left.form, right.form) != ("한", "번") or re.search(r"(?:딱|단)$", source[:left.start].rstrip()):
                    category = "spacing-unit"
            elif right.tag == "NNB" and right.form in BOUND_NOUNS:
                suffix = source[right.start + right.len:]
                # Kiwi 두 경로 모두 '없는데'를 NNB로 읽는 사례가 있다.
                # 데는 장소/용도의 조사·명시적 목적, 지는 시간 경과 문맥까지 확인한다.
                certain = (right.form != "데" or bool(re.match(r"(?:[가를에의]|[ \t]+(?:필요|시간|걸리|들[었어]))", suffix)))
                certain &= right.form != "지" or (left.tag == "ETM" and left.form != "는" and bool(re.match(
                    r"(?:만|[가를는도]|[ \t]+(?:오래|지나|되|넘|\d+[ \t]*(?:초|분|시간|일|주|개월|년)|[한두세네][ \t]+(?:시간|달|해)))", suffix)))
                if certain:
                    category = "spacing-bound-noun"
            elif left.form == "안" and left.tag == "MAG" and right.tag in {"VV", "VA", "XSV"}:
                # 안되다(불쌍하다)와 안 되다(부정)는 Kiwi 품사만으로 확정할 수 없다.
                # 되다 앞은 금지 문맥이 명시된 경우만, 나머지 용언은 부정 부사 분석을 쓴다.
                prefix = source[:left.start].rstrip()
                if right.form != "되" or re.search(r"(?:면|서는|절대)$", prefix):
                    category = "spacing-negation"
        elif old and old.strip(" ") == "" and new == "":
            if right.tag.startswith("J") and left.tag.startswith(("N", "S")):
                category = "spacing-particle"
            elif right.tag in {"EP", "EF", "EC", "ETM", "ETN"} and left.tag in {"VV", "VA", "VX", "XSV", "XSA"}:
                category = "spacing-ending"
        votes.append(category)
    if votes and votes[0] is not None and all(v == votes[0] for v in votes):
        explanations = {
            "spacing-unit": "한글 수사와 단위 명사의 경계",
            "spacing-bound-noun": "의존명사 앞 경계(NNB 분석 일치)",
            "spacing-particle": "떨어진 조사 결합(J 품사 분석 일치)",
            "spacing-ending": "떨어진 어미 결합(E 품사 분석 일치)",
            "spacing-negation": "문맥을 제한한 부정 부사와 용언의 경계",
        }
        return votes[0], explanations[votes[0]]
    return "spacing-optional", "보조용언·합성명사·전문용어 등 선택적 표기 또는 분석이 불확실한 경계"


def check(text, spans, *, counter=None, terms=(), kiwi=None, sentence=True, spacing="strict", **opts):
    if spacing not in {"strict", "all", "repair"}:
        raise ValueError("spacing은 strict, all 또는 repair입니다.")
    kiwi = kiwi or get_kiwi(tuple(sorted(set(terms))))
    findings = []
    # 개행을 삭제·재배치하지 않는다. 긴 줄은 문장 경계에서 자른다.
    # repair는 OCR 복원용이다. 문장/범주 필터 없이 각 줄을 기존 Kiwi처럼 분석한다.
    pattern = r"[^\r\n.!?]+[.!?]*" if sentence and spacing != "repair" else r"[^\r\n]+"
    for segment in re.finditer(pattern, text):
        source = segment.group()
        if sum("가" <= c <= "힣" for c in source) < 2:
            continue
        corrected = post_fix(kiwi.space(source, reset_whitespace=False))
        if source == corrected:
            continue
        analyses = kiwi.analyze(source, top_n=2)
        confidence = score_confidence(kiwi, source, analyses)
        for op, a, b, c, d in SequenceMatcher(None, source, corrected, autojunk=False).get_opcodes():
            if op == "equal":
                continue
            old, new = source[a:b], corrected[c:d]
            if "\u00a0" in source[max(0, a - 1):min(len(source), b + 1)]:
                continue
            # space()의 문자 정규화 등은 띄어쓰기 제안으로 내지 않는다. ASCII 공백만 허용.
            if old.replace(" ", "") != new.replace(" ", ""):
                continue
            start, end = segment.start() + a, segment.start() + b
            rule, reason = classify(source, a, b, old, new, analyses)
            f = emit(text, spans, counter, "spacing", rule, "warn" if rule in STRICT_RULES else "info", start, end, new,
                     f"형태소 분석 기반 제안: {reason}. 확신도는 분석 점수차 휴리스틱이며 문맥을 확인하세요.", confidence)
            # 보호 후보는 범주 필터보다 먼저 억제해 전체 분석에서 원문을 보존한 건수로 집계한다.
            if f and (spacing in {"all", "repair"} or rule in STRICT_RULES):
                findings.append(f)
    return findings
