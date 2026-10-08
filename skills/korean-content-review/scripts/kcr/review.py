"""CLI와 Markdown/JSON 보고서. 기본은 외부 전송 없는 제안 모드."""
import argparse
from collections import Counter
import difflib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from . import spacing, spell_nara, style_lint
from .extract import extract_blocks
from .findings import SuppressedCounter, apply_findings, overlaps
from .protect import Span, ORIGINAL_SELECTOR, QUOTE_SELECTOR, find_protected, merge_spans


def review_text(text, fmt="plain", modules=("spacing", "style"), terms=(), *, original=False,
                protection=None, protected_spans=(), counter=None, budget=None, **opts):
    counter = counter if counter is not None else SuppressedCounter()
    protection = "original" if original else protection
    spans = [Span(0, len(text), protection)] if protection and text else merge_spans(
        find_protected(text, fmt, terms) + list(protected_spans))
    findings, diagnostics = [], []
    for name in modules:
        module = {"spacing": spacing, "spell": spell_nara, "style": style_lint}[name]
        findings += module.check(text, spans, counter=counter, terms=terms, budget=budget,
                                 diagnostics=diagnostics, **opts)
    return dict(findings=findings, spans=spans, counter=counter, diagnostics=diagnostics)


def eligible_apply(findings, spans):
    return [f for f in findings if f.suggestion is not None and
            (f.module == "spacing" or (f.module == "style" and f.rule in style_lint.SAFE_RULES and f.confidence >= .95))
            and not any(overlaps(f.start, f.end, s) for s in spans)]


def markdown_report(report):
    if report.get("quiet") and not report["items"] and not report["diagnostics"] and not report.get("sparse_lines"):
        return ""
    lines = ["# 한국어 텍스트 검수", ""]
    if report.get("sparse_lines"):
        lines += [f"공백이 거의 없는 줄 {report['sparse_lines']}개 — OCR 복원은 `--spacing repair`", ""]
    lines += ["| 모듈 | error | warn | info | 억제 |", "|---|---:|---:|---:|---:|"]
    counts = Counter((f["module"], f["severity"]) for item in report["items"] for f in item["findings"])
    for module in report["modules"]:
        suppressed = sum(n for k, n in report["suppressed"].items() if k.startswith(module + ":"))
        lines.append(f"| {module} | {counts[module, 'error']} | {counts[module, 'warn']} | {counts[module, 'info']} | {suppressed} |")
    lines += ["", "억제는 보호 구간에 겹친 후보 수이며, 오류 수가 아닙니다.", "", "## 발견 목록", ""]
    def safe(v):
        return str(v).replace("\r\n", "↵").replace("\n", "↵").replace("\r", "↵").replace("`", "\\`").replace("<", "&lt;")

    def code(v):
        value = str(v).replace("\r\n", "↵").replace("\n", "↵").replace("\r", "↵")
        # 보호된 인라인 코드가 문맥 창에 들어와도 백틱이 보고서를 끊지 않도록 한다.
        fence = "`" * (1 + max((len(run) for run in re.findall(r"`+", value)), default=0))
        if value.startswith("`") or value.endswith("`") or (value.startswith(" ") and value.endswith(" ")):
            value = " " + value + " "
        return fence + value + fence
    for item in report["items"]:
        if report.get("spacing") == "repair":
            changes = item.get("line_changes", [])
            if changes:
                lines += [f"### {safe(item['source'])}", "", f"총 {len(changes)}줄 변경:", ""]
                for change in changes:
                    # 전후 줄은 기존 OCR 복원 보고 형식으로 그대로 표시한다.
                    # 들여쓴 코드 블록은 원문에 백틱 펜스가 있어도 보고 구조를 깨뜨리지 않는다.
                    lines += [f"[line {change['line']}]", "",
                              "    전: " + change["original"], "    후: " + change["corrected"], ""]
            elif not item["findings"]:
                lines += [f"- {safe(item['source'])}: 변경 없음", ""]
        for f in item["findings"]:
            if report.get("spacing") == "repair" and f["module"] == "spacing":
                continue
            before = f.get("context_before") or f"⟦{f['original']}⟧"
            after = f.get("context_after")
            if after is None and f["suggestion"] is not None:
                after = f"⟦{f['suggestion']}⟧"
            lines.append(f"- {safe(item['source'])}:{f['line']} [{f['severity']}/{f['rule']}] "
                         f"{code(before)} → {code(after) if after is not None else '검토'} "
                         f"(확신도 {f['confidence']:.2f}) — {safe(f['message'])}")
        if item.get("diff"):
            lines += ["", "```diff", item["diff"], "```"]
    if report["diagnostics"]:
        lines += ["", "## 건너뛴 검사", ""] + ["- " + safe(d) for d in report["diagnostics"]]
    return "\n".join(lines) + "\n"


def positive(value):
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("1 이상이어야 합니다.")
    return n


def parser():
    p = argparse.ArgumentParser(description="작품 원문을 보호하는 한국어 검수")
    sub = p.add_subparsers(dest="mode", required=True)
    for mode in ("text", "site"):
        c = sub.add_parser(mode)
        c.add_argument("inputs", nargs="+")
        c.add_argument("--modules", default="spacing,style")
        c.add_argument("--spacing", choices=("strict", "all", "repair"), default="strict",
                       help="strict: 확실한 범주 검수(기본), all: 넓은 검수, repair: OCR 공백 복원(범주 필터 없이 줄별 전/후 보고)")
        c.add_argument("--quiet", action="store_true", help="발견·변경 없는 파일의 출력을 생략")
        c.add_argument("--profile", choices=("article", "ui"), default="article")
        c.add_argument("--terms", type=Path)
        c.add_argument("--format", choices=("md", "json"), default="md")
        c.add_argument("--out", type=Path)
        c.add_argument("--max-requests", type=positive, default=20)
        if mode == "text":
            c.add_argument("--fmt", choices=("plain", "md", "html"), default="plain")
            c.add_argument("--apply", "--write", dest="apply", action="store_true",
                           help="보호 밖 적용 가능 제안을 파일에 반영(--write는 --apply의 별칭, repair도 명시해야 쓰기)")
        else:
            c.add_argument("--linebreak", action="store_true")
            c.add_argument("--widths", default="320,390,768,1440")
            c.add_argument("--engines", default="chromium,webkit")
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    modules = list(dict.fromkeys(v.strip() for v in args.modules.split(",")))
    if not modules or set(modules) - {"spacing", "spell", "style"}:
        p.error("modules는 spacing,spell,style 중에서 고릅니다.")
    terms = tuple(v.strip() for v in args.terms.read_text(encoding="utf-8").splitlines()
                  if v.strip() and not v.lstrip().startswith("#")) if args.terms else ()
    if "spell" in modules:
        print("고지: 보호 구간을 가린 나머지 텍스트를 nara-speller 외부 서비스로 전송합니다.", file=sys.stderr)
    counter = SuppressedCounter()
    budget = spell_nara.RequestBudget(args.max_requests)
    report = dict(modules=modules, spacing=args.spacing, profile=args.profile, quiet=args.quiet,
                  sparse_lines=0, items=[], suppressed={}, diagnostics=[], external={})
    site_gets = 0

    def add(source, text, fmt="plain", original=False, selector=None, protection=None, table=False):
        reviewed = review_text(text, fmt, modules, terms, original=original, protection=protection,
                               counter=counter, budget=budget, spacing=args.spacing, profile=args.profile,
                               mixed_register=args.mode != "site", table=table)
        item = dict(source=source, selector=selector, original_block=original, protection=protection, chars=len(text),
                    protected_chars=sum(s.end - s.start for s in reviewed["spans"]),
                    findings=[f.to_dict() for f in reviewed["findings"]])
        if args.spacing != "repair" and "spacing" in modules:
            report["sparse_lines"] += spacing.sparse_line_count(text)
        if args.spacing == "repair" and "spacing" in modules:
            repaired = apply_findings(text, [f for f in reviewed["findings"] if f.module == "spacing"])
            item["line_changes"] = spacing.changed_lines(text, repaired)
        report["diagnostics"].extend(reviewed["diagnostics"])
        if getattr(args, "apply", False):
            accepted = eligible_apply(reviewed["findings"], reviewed["spans"])
            revised = apply_findings(text, accepted)
            item["applied"] = len(accepted)
            item["diff"] = "".join(difflib.unified_diff(text.splitlines(True), revised.splitlines(True),
                                                      fromfile=source, tofile=source + " (교정)"))
            if source == "-":
                item["corrected_text"] = revised
            elif revised != text:
                # newline=''로 Windows에서도 원문의 개행을 그대로 보존한다.
                with Path(source).open("w", encoding="utf-8", newline="") as stream:
                    stream.write(revised)
        if not args.quiet or item["findings"]:
            report["items"].append(item)

    try:
        for source in args.inputs:
            if args.mode == "text":
                if source == "-":
                    text = sys.stdin.read()
                else:
                    with Path(source).open(encoding="utf-8", newline="") as stream:
                        text = stream.read()
                add(source, text, args.fmt)
            else:
                if urlsplit(source).scheme not in {"http", "https"}:
                    p.error("site에는 http/https URL을 사용하세요.")
                site_gets += 1
                with urlopen(Request(source, headers={"User-Agent": "korean-content-review/1.0"}), timeout=30) as response:
                    html = response.read().decode("utf-8", "replace")
                blocks = extract_blocks(html)
                for block in blocks:
                    add(source, block.text, original=block.original, selector=block.selector, protection=block.protection, table=block.table)
                if args.profile == "ui" and "style" in modules:
                    text, spans = "", []
                    for block in blocks:
                        if not block.ui or len(block.text) > 80:
                            continue
                        offset = len(text)
                        if block.protection:
                            spans.append(Span(offset, offset + len(block.text), block.protection))
                        text += block.text + "\n"
                    spans = merge_spans(spans + find_protected(text, terms=terms))
                    findings = style_lint.check_register(text, spans, counter=counter)
                    if findings:
                        report["items"].append(dict(source=source, selector="UI 문구 묶음", original_block=False,
                                                    chars=len(text), findings=[f.to_dict() for f in findings]))
        if args.mode == "site" and args.linebreak:
            helper = Path(__file__).resolve().parents[3] / "korean-line-break/scripts/ko-wrap-check.mjs"
            command = ["node", str(helper), *args.inputs, "--widths", args.widths, "--engines", args.engines,
                       "--ignore", ORIGINAL_SELECTOR + "," + QUOTE_SELECTOR]
            done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            report["linebreak"] = dict(exit_code=done.returncode)
            try:
                report["linebreak"]["result"] = json.loads(done.stdout)
            except ValueError:
                report["linebreak"]["output"] = done.stdout
            if done.returncode:
                report["diagnostics"].append("줄바꿈 검사 실패: " + done.stderr[:300])
    except (OSError, ValueError) as exc:
        print(f"검수 실패: {exc}", file=sys.stderr)
        return 2
    report["suppressed"] = counter.to_dict()
    report["diagnostics"] += budget.failures
    if budget.skipped_chunks:
        report["diagnostics"].append(f"요청 한도로 {budget.skipped_chunks}청크를 건너뛰었습니다.")
    report["external"] = dict(site_gets=site_gets, nara_posts=budget.requests,
                               masked_spans=budget.masked_spans, skipped_chunks=budget.skipped_chunks)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else markdown_report(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0
