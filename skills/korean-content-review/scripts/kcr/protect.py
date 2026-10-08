"""표시된 작품·인용 원문을 우선 보호한다. 표시 없는 현대 작품은 자동 판별할 수 없다."""
import re
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass(frozen=True, order=True)
class Span:
    start: int
    end: int
    kind: str


ORIGINAL_CLASSES = {"lit-verse", "verse", "serif", "original-text", "poem", "stanza", "passage", "excerpt", "exam-passage", "exam-box"}
ORIGINAL_SELECTOR = "[data-original-text],.lit-verse,.verse,.serif,.original-text,.poem,.stanza,.passage,.excerpt,.exam-passage,.exam-box"
QUOTE_SELECTOR = 'blockquote,q,[itemprop="reviewBody"],[data-user-content],[class~="review"],[class*="review-"],[class*="-review"],[class*="testimonial"],[class~="quote"],[class*="quote-"],[class*="-quote"],[id="reviews"],[id="testimonials"],[id="quotes"],[data-section*="reviews"]'
OLD = r"[\u1100-\u11ff\ua960-\ua97f\ud7b0-\ud7ff\u318d\u318e]"
PRIORITY = {kind: i for i, kind in enumerate(
    ["original", "old-hangul", "quote", "code", "term", "url", "email", "hanja", "marker", "tag"])}


def element_protection(tag, attrs, inherited=None):
    """원문·사용자 글의 같은 판정을 HTML 보호기와 추출기가 공유한다."""
    classes = attrs.get("class", "") or ""
    # Tailwind [&_blockquote]:...는 자식의 서식 지정이지 부모의 인용 표시가 아니다.
    semantic_classes = [name for name in classes.split() if "[" not in name and "]" not in name]
    # 후기 묶음은 개별 article 대신 상위 section의 id/data-section에 표시되기도 한다.
    semantic = " ".join(attrs.get(key, "") or "" for key in ("id", "data-section"))
    if inherited == "original" or "data-original-text" in attrs or ORIGINAL_CLASSES & set(classes.split()):
        return "original"
    if (inherited == "quote" or tag in {"blockquote", "q"} or "data-user-content" in attrs
            or "reviewBody" in (attrs.get("itemprop", "") or "").split()
            or any(word in name.lower() for name in semantic_classes for word in ("review", "testimonial", "quote"))
            or (tag in {"section", "article", "div"} and re.search(
                r"(?:^|[-_\s])(?:reviews?|testimonials?|quotes?)(?:$|[-_\s])", semantic, re.I))):
        return "quote"
    return inherited


def merge_spans(spans):
    """겹친 구간을 합치고 가장 강한 보호 종류를 유지한다. 접한 구간은 구분한다."""
    result = []
    for s in sorted(spans, key=lambda x: (x.start, x.end)):
        if s.end <= s.start:
            continue
        if result and s.start < result[-1].end:
            p = result.pop()
            kind = min((p.kind, s.kind), key=lambda k: PRIORITY[k])
            result.append(Span(p.start, max(p.end, s.end), kind))
        else:
            result.append(s)
    return result


class OriginalParser(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.starts = [0] + [m.end() for m in re.finditer("\n", text)]
        self.stack = []
        self.spans = []

    def source_offset(self):
        line, col = self.getpos()
        return self.starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        inherited = self.stack[-1][1] if self.stack else None
        kind = element_protection(tag, attrs, inherited)
        if kind is None and tag in {"script", "style", "pre", "code", "nav", "footer"}:
            kind = "code"
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}:
            self.stack.append((tag, kind))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1][1]:
            self.spans.append(Span(self.source_offset(), self.source_offset() + len(data), self.stack[-1][1]))

    def handle_entityref(self, name):
        self.handle_data("&" + name + ";")

    def handle_charref(self, name):
        self.handle_data("&#" + name + ";")


def find_protected(text: str, fmt="plain", terms=()):
    if fmt not in {"plain", "md", "html"}:
        raise ValueError("fmt는 plain, md, html 중 하나입니다.")
    spans = []
    patterns = [
        (r"<!--\s*original\s*-->[\s\S]*?(?:<!--\s*/original\s*-->|\Z)", "original"),
        (r"(?m)^\s*:::original[^\n]*\n[\s\S]*?(?:^\s*:::\s*$|\Z)", "original"),
        (r"(?m)^.*" + OLD + r".*$", "old-hangul"),
        (r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]+", "hanja"),
        (r"https?://[^\s<>\"']+", "url"),
        (r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "email"),
        (r"\([가-힣]\)|\[[A-Za-z가-힣]\]|〈[^〉\n]+〉|[㉠-㉻①-⑳ⓐ-ⓩ❶-❿]", "marker"),
        (r"<[^>]*>", "tag"),
        (r"`[^`\n]*`", "code"),
        (r"\{\{[^}\n]*\}\}|\$\{[^}\n]*\}", "code"),
        (r"“[^”]*”|‘[^’]*’|\"[^\"\n]+\"|「[^」]*」|『[^』]*』", "quote"),
    ]
    if fmt in {"md", "plain"}:
        patterns += [
            (r"(?m)^\s*(`{3,}|~{3,})[^\n]*\n[\s\S]*?(?:^\s*\1[^\n]*$|\Z)", "code"),
            (r"\A---\r?\n[\s\S]*?\r?\n---(?:\r?\n|\Z)", "code"),
            (r"\[\[[^\]\n]+\]\]", "code"),
            (r"(?m)^\s*>[^\n]*(?:\n\s*>[^\n]*)*", "quote"),
        ]
    for pattern, kind in patterns:
        spans.extend(Span(m.start(), m.end(), kind) for m in re.finditer(pattern, text))
    for term in terms:
        if term:
            spans.extend(Span(m.start(), m.end(), "term") for m in re.finditer(re.escape(term), text))
    if fmt == "html":
        parser = OriginalParser(text)
        parser.feed(text)
        parser.close()
        spans.extend(parser.spans)
    return merge_spans(spans)
