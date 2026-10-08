"""캐시의 실제 문장에 오류 하나를 주입해 검출 위치를 비교한다. 네트워크는 사용하지 않는다."""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import random
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "skills/korean-content-review/scripts"))
from kcr import spacing, style_lint
from kcr.extract import extract_blocks
from kcr.findings import Finding, overlaps
from kcr.protect import find_protected
from kcr.review import review_text
from run_bench import TERMS, diff_edits, load_legacy
from reporting import write_injection_report

SEED = 20261008
TYPES = ("bound-noun-join", "unit-join", "particle-split", "misspelling", "double-passive")
TOOLS = ("legacy-spacing", "spacing-strict", "spacing-all", "style-article", "combined-default")
BOUND = {"것", "수", "때문", "줄", "데", "만큼", "뿐", "지"}
MISSPELLINGS = {"됐": "됬", "며칠": "몇일", "금세": "금새", "역할": "역활", "콘텐츠": "컨텐츠", "메시지": "메세지", "리더십": "리더쉽"}
PASSIVES = {"되었": "되어졌", "보였": "보여졌", "쓰였": "쓰여졌", "읽혔": "읽혀졌", "잊혔": "잊혀졌"}


@dataclass(frozen=True)
class Mutation:
    kind: str
    start: int
    end: int
    replacement: str


@dataclass(frozen=True)
class Injected:
    kind: str
    text: str
    start: int
    end: int
    clean_start: int
    clean_end: int
    original: str
    replacement: str


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def apply_mutation(text, mutation):
    if not 0 <= mutation.start <= mutation.end <= len(text):
        raise ValueError("주입 위치가 문장 범위를 벗어났습니다.")
    original = text[mutation.start:mutation.end]
    if original == mutation.replacement:
        raise ValueError("변경 없는 주입은 허용하지 않습니다.")
    revised = text[:mutation.start] + mutation.replacement + text[mutation.end:]
    return Injected(mutation.kind, revised, mutation.start, mutation.start + len(mutation.replacement),
                    mutation.start, mutation.end, original, mutation.replacement)


def candidates(text, kiwi):
    """깨끗한 입력의 품사·실제 표면 문자열만 쓴다. 검출 결과로 주입 대상을 고르지 않는다."""
    result = []
    tokens = kiwi.analyze(text, top_n=1)[0][0]
    for index, token in enumerate(tokens):
        a = token.start
        if not 0 < a < len(text) or text[a:a + token.len] != token.form:
            continue
        if token.tag in {"JKS", "JKO", "JKB"} and "가" <= text[a - 1] <= "힣":
            result.append(Mutation("particle-split", a, a, " "))
        gap = re.search(r" +$", text[:a])
        if not gap or not gap.start() or not ("가" <= text[gap.start() - 1] <= "힣"):
            continue
        left = next((t for t in reversed(tokens[:index]) if t.start + t.len <= gap.start()), None)
        if token.tag == "NNB" and token.form in BOUND:
            # 뿐/만큼의 조사 분석은 제외한다. 시간 지는 관형형 뒤 시간 경과 문맥만 사용한다.
            temporal = token.form != "지" or (left and left.tag == "ETM" and left.form != "는"
                and re.match(r"(?:[가를는도만]|\s+(?:오래|지나|\d+\s*(?:일|년|달|시간)|[한두세네]\s*(?:해|달|시간)))", text[a + token.len:]))
            if temporal:
                result.append(Mutation("bound-noun-join", gap.start(), a, ""))
        if (left and left.tag in {"MM", "NR"} and left.form in spacing.NUMERALS
                and token.form in spacing.UNITS and token.tag in {"NNB", "NNG"}):
            # 단위의 경계만 없앤다. 문장에 없던 수사나 단위는 추가하지 않는다.
            # 한 번/한번은 의미에 따라 둘 다 가능한 경우가 있어 알려진 오류로 쓰지 않는다.
            if (left.form, token.form) != ("한", "번"):
                result.append(Mutation("unit-join", gap.start(), a, ""))
    for kind, pairs in (("misspelling", MISSPELLINGS), ("double-passive", PASSIVES)):
        for correct, wrong in pairs.items():
            result.extend(Mutation(kind, m.start(), m.end(), wrong) for m in re.finditer(re.escape(correct), text))
    return sorted(set(result), key=lambda m: (TYPES.index(m.kind), m.start, m.end, m.replacement))


def read_blocks(cache):
    manifest_path = cache / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("사이트 캐시 manifest.json이 없습니다. 네트워크로 대체 수집하지 않습니다.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    blocks, evidence = [], []
    for page in manifest["pages"]:
        if page.get("status") != 200 or page.get("login_required"):
            continue
        name = page["file"]
        if Path(name).name != name or not name.endswith(".html"):
            raise ValueError("사이트 캐시 파일명이 올바르지 않습니다.")
        path = cache / name
        if not path.is_file():
            raise FileNotFoundError("사이트 페이지 HTML 캐시가 없습니다.")
        raw = path.read_bytes()
        if digest(raw) != page["sha256"]:
            raise ValueError("사이트 페이지 캐시 해시가 맞지 않습니다.")
        evidence.append(dict(source=page["url"], sha256=page["sha256"]))
        for block in extract_blocks(raw.decode("utf-8")):
            if block.protection is None:
                blocks.append(dict(text=block.text, table=block.table, source=page["url"], selector=block.selector))
    return blocks, evidence


def select_clean(blocks, kiwi, count=300, seed=SEED):
    pool = {}
    for block in blocks:
        protected = find_protected(block["text"], terms=TERMS)
        for sentence in kiwi.split_into_sents(block["text"]):
            text = sentence.text.strip(" \t\r\n")
            if not 15 <= len(text) <= 90 or not re.search(r"[가-힣]", text):
                continue
            if any(overlaps(sentence.start, sentence.end, span) for span in protected):
                continue
            # 중복 키만 공백을 통일한다. 원문 문장과 NBSP는 바꾸지 않는다.
            key = re.sub(r"\s+", " ", text)
            pool.setdefault(key, dict(text=text, source=block["source"], selector=block["selector"], table=block["table"]))
    ordered = [pool[key] for key in sorted(pool)]
    if len(ordered) < count:
        raise ValueError(f"조건에 맞는 중복 제거 문장이 {len(ordered)}개여서 {count}개를 선택할 수 없습니다.")
    return random.Random(seed).sample(ordered, count), len(ordered)


def inject_dataset(clean, kiwi, seed=SEED):
    rng = random.Random(seed)
    usage, available = Counter(), Counter()
    contaminated, skipped = [], []
    for index, item in enumerate(clean):
        by_type = {}
        for mutation in candidates(item["text"], kiwi):
            by_type.setdefault(mutation.kind, []).append(mutation)
        available.update(by_type.keys())
        if not by_type:
            skipped.append(index)
            continue
        # 적은 유형을 우선하되 가능한 유형 사이에서만 선택한다. 수량을 맞추려고 문장을 만들지 않는다.
        least = min(usage[kind] for kind in by_type)
        kinds = sorted(kind for kind in by_type if usage[kind] == least)
        kind = rng.choice(kinds)
        injected = apply_mutation(item["text"], rng.choice(by_type[kind]))
        usage[kind] += 1
        contaminated.append(dict(clean_index=index, **asdict(injected), source=item["source"],
                                 selector=item["selector"], table=item["table"]))
    return contaminated, dict(usage), dict(available), skipped


def tool_findings(text, table, legacy, kiwi):
    spans = find_protected(text, terms=TERMS)
    revised, _ = legacy.correct_spacing(text, kiwi)
    legacy_findings = [Finding("spacing", "legacy-spacing", "warn", a, b, text.count("\n", 0, a) + 1,
                               text[a:b], replacement, "기존 Kiwi 공백 diff", 0.0)
                       for a, b, replacement in diff_edits(text, revised)]
    return {
        "legacy-spacing": legacy_findings,
        "spacing-strict": spacing.check(text, spans, kiwi=kiwi, terms=TERMS, spacing="strict"),
        "spacing-all": spacing.check(text, spans, kiwi=kiwi, terms=TERMS, spacing="all"),
        "style-article": style_lint.check(text, spans, profile="article", table=table),
        "combined-default": review_text(text, modules=("spacing", "style"), terms=TERMS,
                                       kiwi=kiwi, spacing="strict", profile="article", table=table)["findings"],
    }


def hits(finding, start, end, tolerance=0):
    """공백 삭제 주입/공백 삽입 Finding의 0길이 좌표도 포함해 경계 거리로 판정한다."""
    left, right = start - tolerance, end + tolerance
    if start == end:
        return (left <= finding.start <= right if finding.start == finding.end
                else finding.start <= right and left < finding.end)
    return (left <= finding.start < right if finding.start == finding.end
            else finding.start < right and left < finding.end)


def rates(stat):
    stat["recall"] = round(stat["detected_sentences_near"] / stat["injected_sentences"], 6) if stat["injected_sentences"] else None
    stat["precision"] = round(stat["true_positive_findings"] / stat["corrupted_findings"], 6) if stat["corrupted_findings"] else None
    stat["clean_findings_per_sentence"] = round(stat["clean_findings"] / stat["clean_sentences"], 6) if stat["clean_sentences"] else None
    return stat


def empty_stat():
    return dict(clean_sentences=0, clean_findings=0, injected_sentences=0, detected_sentences_near=0,
                corrupted_findings=0, true_positive_findings=0, off_target_findings=0, off_target_findings_near=0)


def measure(clean, contaminated, legacy, kiwi):
    clean_outputs = [tool_findings(item["text"], item["table"], legacy, kiwi) for item in clean]
    overall = {name: empty_stat() for name in TOOLS}
    by_type = {kind: {name: empty_stat() for name in TOOLS} for kind in TYPES}
    for name in TOOLS:
        overall[name]["clean_sentences"] = len(clean)
        overall[name]["clean_findings"] = sum(len(outputs[name]) for outputs in clean_outputs)
    raw_outputs = dict(clean=[dict(clean_index=index, findings={name: [f.to_dict() for f in fs] for name, fs in outputs.items()})
                              for index, outputs in enumerate(clean_outputs)], corrupted=[])
    for item in contaminated:
        outputs = tool_findings(item["text"], item["table"], legacy, kiwi)
        raw_outputs["corrupted"].append(dict(clean_index=item["clean_index"], findings={name: [f.to_dict() for f in fs] for name, fs in outputs.items()}))
        for name, findings in outputs.items():
            stat = by_type[item["kind"]][name]
            stat["clean_sentences"] += 1
            stat["clean_findings"] += len(clean_outputs[item["clean_index"]][name])
            exact = sum(hits(f, item["start"], item["end"]) for f in findings)
            near = sum(hits(f, item["start"], item["end"], 2) for f in findings)
            increments = dict(injected_sentences=1, detected_sentences_near=int(near > 0),
                              corrupted_findings=len(findings), true_positive_findings=exact,
                              off_target_findings=len(findings) - exact, off_target_findings_near=len(findings) - near)
            for key, value in increments.items():
                stat[key] += value
                overall[name][key] += value
    return {name: rates(stat) for name, stat in overall.items()}, {
        kind: {name: rates(stat) for name, stat in stats.items()} for kind, stats in by_type.items()}, raw_outputs


def fragment(text, start, end, width=20):
    left = max(0, start - max(0, width - (end - start)) // 2)
    left = min(left, max(0, len(text) - width))
    return text[left:left + width]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached", action="store_true", help="필수: 저장된 사이트 HTML만 사용")
    parser.add_argument("--cache-dir", type=Path, default=HERE / ".cache")
    args = parser.parse_args(argv)
    if not args.cached:
        parser.error("이 실험은 네트워크 없이 --cached로만 실행합니다.")
    def block_network(event, arguments):
        if event in {"socket.getaddrinfo", "socket.connect", "socket.sendto"}:
            raise RuntimeError("오류 주입 실험에서는 네트워크를 사용할 수 없습니다.")
    sys.addaudithook(block_network)
    try:
        blocks, pages = read_blocks(args.cache_dir)
        legacy, legacy_hashes = load_legacy(("spacing",))
        kiwi = spacing.get_kiwi(tuple(sorted(TERMS)))
        clean, pool_size = select_clean(blocks, kiwi)
        contaminated, counts, available, skipped = inject_dataset(clean, kiwi)
        overall, by_type, raw_outputs = measure(clean, contaminated, legacy["spacing"], kiwi)
        dataset = dict(seed=SEED, clean=clean, contaminated=contaminated, skipped_clean_indices=skipped)
        dataset_raw = json.dumps(dataset, ensure_ascii=False, indent=2) + "\n"
        cache = args.cache_dir / "injection"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "dataset.json").write_text(dataset_raw, encoding="utf-8")
        (cache / "findings.json").write_text(json.dumps(raw_outputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        examples = []
        for kind in TYPES:
            item = next((i for i in contaminated if i["kind"] == kind), None)
            if item:
                original = clean[item["clean_index"]]["text"]
                examples.append(dict(type=kind, before=fragment(original, item["clean_start"], item["clean_end"]),
                                     after=fragment(item["text"], item["start"], item["end"])))
        files = sorted((ROOT / "skills/korean-content-review/scripts/kcr").glob("*.py")) + [Path(__file__), HERE / "run_bench.py", HERE / "reporting.py"]
        import kiwipiepy
        results = dict(schema=1, seed=SEED, clean_sentences=len(clean), eligible_sentence_pool=pool_size,
                       corrupted_sentences=len(contaminated), skipped_no_applicable_error=len(skipped),
                       injection_counts={kind: counts.get(kind, 0) for kind in TYPES},
                       available_sentence_counts={kind: available.get(kind, 0) for kind in TYPES},
                       selection="300문장 균일 무작위 선택 후 가능한 유형 중 누적 주입 수가 적은 유형 우선, 동률·위치는 고정 시드로 선택",
                       definitions=dict(recall="오염 문장 중 주입 위치와 ±2자 이내 Finding이 있는 비율",
                                        precision="오염 Finding 중 주입 위치와 정확히 겹치는 비율(0길이 경계 포함)",
                                        clean_false_alarms="검수자가 깨끗한 집합으로 간주한 실제 300문장의 Finding 수; 문맥 정밀도 판정 아님"),
                       tools=overall, by_type=by_type, examples=examples,
                       evidence=dict(dataset_sha256=digest(dataset_raw), engine_sha256=digest("".join(digest(p.read_bytes()) for p in files)),
                                     pages=pages, legacy_sha256=legacy_hashes),
                       versions=dict(python=sys.version.split()[0], kiwipiepy=kiwipiepy.__version__),
                       external=dict(site_gets=0, nara_posts=0, nara_excluded=True),
                       limitations=["주입 위치 검출은 올바른 교정 제안·자동 수정 성공을 의미하지 않는다.",
                                    "표기 사전·과거형 이중 피동 등 제한된 오류 유형의 실험이며 실제 오류 분포를 대표하지 않는다.",
                                    "한 번/한번처럼 의미에 따라 허용되는 대안은 단위 오류 주입에서 제외한다.",
                                    "적용 가능한 오류가 없는 선택 문장은 깨끗한 평가에만 포함한다."])
        (HERE / "injection-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_injection_report(results, HERE, ROOT)
        print(json.dumps({key: results[key] for key in ("clean_sentences", "corrupted_sentences", "skipped_no_applicable_error", "injection_counts", "tools", "external")}, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"오류 주입 실험 실패: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
