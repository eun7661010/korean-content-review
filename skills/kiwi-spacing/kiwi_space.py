"""kiwi_space.py 공개 개선판 (MIT). 통합 엔진과 같은 보호·결과 계약을 사용한다."""
import argparse
import json
from pathlib import Path
import sys

ENGINE = Path(__file__).resolve().parents[1] / "korean-content-review/scripts"
sys.path.insert(0, str(ENGINE))
try:
    from kcr.findings import SuppressedCounter, apply_findings
    from kcr.protect import find_protected
    from kcr.spacing import check, get_kiwi, post_fix, changed_lines, sparse_line_count
except ModuleNotFoundError as exc:
    raise SystemExit("같은 skills 폴더에 korean-content-review를 함께 배치하세요.") from exc


def correct_spacing(text, kiwi=None, *, fmt="md", terms=(), counter=None, spacing="strict"):
    findings = check(text, find_protected(text, fmt, terms), kiwi=kiwi, terms=terms, counter=counter, spacing=spacing)
    return apply_findings(text, findings), findings


def main(argv=None):
    p = argparse.ArgumentParser(description="원문을 보호하는 로컬 한국어 띄어쓰기 검수")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--file", type=Path)
    group.add_argument("--dir", type=Path)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="제안만 보고(기본), 파일에 쓰지 않음")
    mode.add_argument("--write", action="store_true", help="보호 구간 밖 공백 변경을 파일에 반영")
    p.add_argument("--ext", default="md,txt")
    p.add_argument("--fmt", choices=("plain", "md", "html"), default="md")
    p.add_argument("--spacing", choices=("strict", "all", "repair"), default="strict",
                   help="strict: 확실한 범주 검수(기본), all: 넓은 검수, repair: OCR 공백 복원(범주 필터 없이 줄별 전/후 보고)")
    p.add_argument("--quiet", action="store_true", help="변경 없는 파일의 출력을 생략")
    p.add_argument("--terms", type=Path)
    p.add_argument("--sentence", action=argparse.BooleanOptionalAction, default=True,
                   help="strict·all의 문장 단위 분석(repair는 항상 줄 단위)")
    p.add_argument("--format", choices=("md", "json"), default="md")
    args = p.parse_args(argv)
    terms = tuple(v.strip() for v in args.terms.read_text(encoding="utf-8").splitlines() if v.strip() and not v.startswith("#")) if args.terms else ()
    counter = SuppressedCounter()
    kiwi = get_kiwi(tuple(sorted(terms)))
    exts = {"." + v.strip() for v in args.ext.split(",")}
    inputs = [("-", args.text)] if args.text is not None else [(str(f), None) for f in
              (sorted(f for f in args.dir.rglob("*") if f.is_file() and f.suffix in exts) if args.dir else [args.file])]
    report = dict(modules=["spacing"], spacing=args.spacing, quiet=args.quiet, sparse_lines=0,
                  items=[], diagnostics=[], suppressed={})
    for source, inline in inputs:
        if inline is None:
            with Path(source).open(encoding="utf-8", newline="") as stream:
                text = stream.read()
        else:
            text = inline
        findings = check(text, find_protected(text, args.fmt, terms), counter=counter, terms=terms,
                         kiwi=kiwi, sentence=args.sentence, spacing=args.spacing)
        item = dict(source=source, findings=[f.to_dict() for f in findings])
        corrected = apply_findings(text, findings)
        if args.spacing == "repair":
            item["line_changes"] = changed_lines(text, corrected)
        else:
            report["sparse_lines"] += sparse_line_count(text)
        if args.write:
            import difflib
            item["diff"] = "".join(difflib.unified_diff(text.splitlines(True), corrected.splitlines(True),
                                                      fromfile=source, tofile=source + " (교정)"))
            if source != "-" and text != corrected:
                with Path(source).open("w", encoding="utf-8", newline="") as stream:
                    stream.write(corrected)
            else:
                item["corrected_text"] = corrected
        if not args.quiet or findings:
            report["items"].append(item)
    report["suppressed"] = counter.to_dict()
    from kcr.review import markdown_report
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else markdown_report(report)
    print(output, end="")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
