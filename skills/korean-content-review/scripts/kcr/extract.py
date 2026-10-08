"""서로 다른 UI 요소는 이어 붙이지 않고 원문·사용자 글의 보호 상태를 유지한다."""
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from .protect import element_protection


@dataclass(frozen=True)
class TextBlock:
    text: str
    selector: str
    original: bool = False
    protection: str | None = None
    ui: bool = False
    table: bool = False


class BlockParser(HTMLParser):
    # 이 목록만 주변 본문과 연결한다. a·button 등 모든 다른 요소는 양 경계를 끊는다.
    INLINE = {"b", "strong", "em", "i", "u", "mark", "small", "sup", "sub", "span", "code", "ruby"}
    UI = {"a", "button", "label", "option", "input", "select"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.blocks = []
        self.parts = []
        self.key = None
        self.root_counts = {}

    def flush(self):
        if self.parts:
            text = re.sub(r"[ \t\r\f\v]+", " ", "".join(self.parts)).strip(" \t\r\n\f\v")
            if text:
                selector, protection, ui, table = self.key
                self.blocks.append(TextBlock(text, selector, protection == "original", protection, ui, table))
        self.parts = []
        self.key = None

    def context(self):
        if not self.stack:
            return ("body", None, False, False)
        parent = self.stack[-1]
        owner = next((p for p in reversed(self.stack) if p["tag"] not in self.INLINE), parent)
        return (owner["selector"], parent["protection"], owner["ui"], any(p["tag"] == "table" for p in self.stack))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        parent = self.stack[-1] if self.stack else None
        counts = parent["counts"] if parent else self.root_counts
        counts[tag] = counts.get(tag, 0) + 1
        own = tag + f":nth-of-type({counts[tag]})"
        selector = (parent["selector"] + " > " if parent else "") + own
        protection = element_protection(tag, attrs, parent["protection"] if parent else None)
        hidden = bool((parent and parent["hidden"]) or tag in {"script", "style", "nav", "footer", "head", "template", "noscript"}
                      or "hidden" in attrs or attrs.get("aria-hidden") == "true"
                      or re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", attrs.get("style", "") or "", re.I))
        if tag not in self.INLINE or (parent and parent["protection"] != protection):
            self.flush()
        entry = dict(tag=tag, selector=selector, protection=protection, hidden=hidden,
                     ui=tag in self.UI or bool(parent and parent["ui"]), counts={})
        if tag not in self.VOID:
            self.stack.append(entry)
        if not hidden:
            for attr in ("aria-label", "alt"):
                if attrs.get(attr):
                    self.flush()
                    self.blocks.append(TextBlock(attrs[attr], selector + f"@{attr}", protection == "original", protection, True))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag not in self.INLINE:
            self.flush()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                previous = self.stack[-1]["protection"]
                del self.stack[i:]
                current = self.stack[-1]["protection"] if self.stack else None
                if previous != current:
                    self.flush()
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1]["hidden"]:
            return
        key = self.context()
        if key != self.key:
            self.flush()
            self.key = key
        self.parts.append(data)


def extract_blocks(html: str):
    parser = BlockParser()
    parser.feed(html)
    parser.close()
    parser.flush()
    # 메뉴·푸터는 위에서 제외. 반복 사업자 문구와 비원문 블록은 제외한다.
    seen = set()
    blocks = []
    for block in parser.blocks:
        if block.protection is None and re.search(r"사업자\s*(?:등록|정보)|통신판매업", block.text):
            continue
        key = (block.text, block.protection, block.ui, block.table)
        if block.protection is None and key in seen:
            continue
        seen.add(key)
        blocks.append(block)
    return blocks


extract = extract_blocks
