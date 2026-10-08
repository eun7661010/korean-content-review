"""공개 사이트·만료 고전의 실제 비교. 원응답은 무시되는 .cache 안에만 저장한다."""
import argparse
from collections import Counter
from dataclasses import asdict
from difflib import SequenceMatcher
import hashlib
import importlib.util
import json
import os
from os import getenv
from pathlib import Path
import random
import re
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
sys.path.insert(0, str(ROOT / "skills/korean-content-review/scripts"))
from kcr import spacing, spell_nara, style_lint
from kcr.extract import extract_blocks
from kcr.findings import SuppressedCounter, overlaps
from kcr.protect import Span, find_protected
from reporting import write_reports

TERMS = ["지국총", "살어리랏다", "컨텐츠은행", "오픈북", "김은광 수능국어"]


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def category(url):
    path = urlsplit(url).path
    if path.startswith("/columns/"):
        return "칼럼"
    if path.startswith("/guide"):
        return "학습 안내"
    if path.startswith("/books/"):
        return "교재 소개"
    return "랜딩·서비스 소개"


def select_urls(urls, max_pages):
    desired = ["", "/guide", "/guide/prologue", "/guide/chapter-1", "/guide/chapter-2", "/guide/chapter-3",
               "/cognitive-engineering-korean", "/60korean", "/resources", "/suneung-ebs-2026", "/columns"]
    selected = []
    for path in desired:
        match = next((u for u in urls if urlsplit(u).path.rstrip("/") == path), None)
        if match:
            selected.append(match)
    selected += sorted(u for u in urls if urlsplit(u).path.startswith("/columns/"))[:15]
    selected += sorted(u for u in urls if urlsplit(u).path.startswith("/books/") and urlsplit(u).path.count("/") == 2)[:4]
    selected = list(dict.fromkeys(selected))[:min(30, max_pages)]
    for url in selected:
        parsed = urlsplit(url)
        if parsed.netloc != "ekkorean.com" or parsed.scheme != "https" or any(
                parsed.path.startswith(p) for p in EXCLUDED_PATHS):
            raise ValueError("허용 범위 밖 URL입니다.")
    return selected


# 로그인·관리 화면 등 측정에서 뺄 경로. 사이트마다 다르므로 환경변수로 덧붙인다(쉼표 구분).
EXCLUDED_PATHS = tuple(p for p in ("/api,/admin,/login,/class,/learn," + os.environ.get("KCR_BENCH_EXCLUDE_PATHS", "")).split(",") if p)


def collect_pages(max_pages=30):
    CACHE.mkdir(parents=True, exist_ok=True)
    manifest_path = CACHE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else dict(site_gets=0, pages=[])
    opener = build_opener(NoRedirect())
    sitemap = CACHE / "sitemap.xml"
    if not sitemap.exists():
        manifest["site_gets"] += 1
        write_json(manifest_path, manifest)
        with opener.open("https://ekkorean.com/sitemap.xml", timeout=30) as response:
            sitemap.write_bytes(response.read())
    elif not manifest["site_gets"]:
        # 사전에 허용된 단일 sitemap 수집도 전체 요청 수에 포함한다.
        manifest["site_gets"] = 1
    urls = [e.text for e in ET.fromstring(sitemap.read_bytes()).iter() if e.tag.endswith("loc")]
    selected = select_urls(urls, max_pages)
    for url in selected:
        if any(p["url"] == url for p in manifest["pages"]):
            continue
        if manifest["site_gets"] >= 40:
            break
        time.sleep(1.0)
        manifest["site_gets"] += 1
        write_json(manifest_path, manifest)
        entry = dict(url=url, category=category(url), file="page-" + digest(url)[:16] + ".html")
        try:
            with opener.open(Request(url, headers={"User-Agent": "korean-content-review-benchmark/1.0"}), timeout=30) as response:
                raw = response.read()
                (CACHE / entry["file"]).write_bytes(raw)
                entry.update(status=response.status, sha256=digest(raw))
                html = raw.decode("utf-8", "replace")
                entry["login_required"] = bool("로그인이 필요합니다" in html or "로그인이 필요한" in html)
        except HTTPError as exc:
            (CACHE / entry["file"]).write_bytes(exc.read())
            entry["status"] = exc.code
        except OSError as exc:
            entry["status"] = type(exc).__name__
        manifest["pages"].append(entry)
        write_json(manifest_path, manifest)
        print(f"사이트 GET {manifest['site_gets']}: {entry['status']} ({entry['category']})", flush=True)
    return manifest


def load_legacy(names=("spacing", "spell")):
    roots = [Path(v) for v in getenv("KCR_LEGACY_SKILLS_DIR", "").split(os.pathsep) if v]
    loaded = {}
    hashes = {}
    targets = {"spacing": "kiwi-spacing/kiwi_space.py", "spell": "korean-spell-check/scripts/korean_spell_check.py"}
    for name, relative in targets.items():
        if name not in names:
            continue
        path = next((r / relative for r in roots if (r / relative).is_file()), None)
        if path is None:
            raise ValueError("KCR_LEGACY_SKILLS_DIR에 비교할 기존 스킬 경로를 지정하세요.")
        spec = importlib.util.spec_from_file_location("legacy_" + name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = previous
        loaded[name] = module
        hashes[name] = digest(path.read_bytes())
    return loaded, hashes


def corpora(manifest):
    a, b = [], []
    for entry in manifest["pages"]:
        if entry.get("status") != 200 or entry.get("login_required"):
            continue
        html = (CACHE / entry["file"]).read_text(encoding="utf-8")
        if digest((CACHE / entry["file"]).read_bytes()) != entry["sha256"]:
            raise ValueError("사이트 캐시 해시가 맞지 않습니다.")
        for block in extract_blocks(html):
            if not any("가" <= c <= "힣" for c in block.text):
                continue
            spans = [Span(0, len(block.text), block.protection)] if block.protection else find_protected(block.text, terms=TERMS)
            a.append(dict(text=block.text, spans=spans, source=entry["url"], category=entry["category"],
                          selector=block.selector, protection=block.protection, ui=block.ui, table=block.table))
    for name in ("classical.md", "classical_prose.md", "questions.md", "original.html"):
        text = (ROOT / "tests/fixtures" / name).read_text(encoding="utf-8")
        fmt = "html" if name.endswith("html") else "md"
        b.append(dict(text=text, spans=find_protected(text, fmt, TERMS), source=name, category="원문 보호", selector=None))
    return a, b


def spell_inputs(a, b):
    chosen = []
    for source in dict.fromkeys(item["source"] for item in a):
        blocks = [item for item in a if item["source"] == source]
        text = "\n".join(item["text"] for item in blocks if not any(s.kind == "original" for s in item["spans"]))
        if len(text) >= 150:
            offset, chunk = spell_nara.split_chunks(text, 1200)[0]
            chosen.append(dict(text=chunk, source=source, corpus="A"))
        if len(chosen) >= 16:
            break
    for item in b[:3]:
        # 주석도 보호 정보를 가진 입력이다. 같은 입력·같은 응답으로 두 후처리를 비교한다.
        for offset, chunk in spell_nara.split_chunks(item["text"], 1200):
            chosen.append(dict(text=chunk, source=item["source"], corpus="B"))
    return chosen[:23]


def collect_spell(inputs):
    # 추출기를 바꿔도 이미 받은 응답과 같은 입력을 재생할 수 있도록 별도 저장한다.
    write_json(CACHE / "spell-inputs.json", inputs)
    path = CACHE / "spell-manifest.json"
    ledger = json.loads(path.read_text(encoding="utf-8")) if path.exists() else dict(nara_posts=0, responses=[])
    budget = spell_nara.RequestBudget(max_requests=25, requests=ledger["nara_posts"])
    # 고전 입력을 먼저 확인한다. 이미 요청한 청크는 다시 보내지 않는다.
    inputs = sorted(inputs, key=lambda i: i["corpus"] != "B")
    consecutive_failures = 0
    for item in inputs:
        key = digest(item["text"])
        if any(r["input_sha256"] == key for r in ledger["responses"]):
            continue
        entry = dict(input_sha256=key, source=item["source"], corpus=item["corpus"], file="nara-" + key[:16] + ".html")
        # 프로세스 재시작 사이에도 2초를 지킨다. 재시도하지 않는다.
        time.sleep(2.0)
        if budget.requests >= 25:
            break
        budget.requests += 1
        ledger["nara_posts"] = budget.requests
        entry["status"] = "pending"
        ledger["responses"].append(entry)
        write_json(path, ledger)
        try:
            raw = spell_nara.fetch_spell_check_html(item["text"])
            (CACHE / entry["file"]).write_bytes(raw.encode("utf-8"))
            entry.update(status="ok", response_sha256=digest(raw))
        except HTTPError as exc:
            (CACHE / entry["file"]).write_bytes(exc.read())
            entry["status"] = f"HTTP {exc.code}"
        except OSError as exc:
            entry["status"] = type(exc).__name__
        write_json(path, ledger)
        print(f"nara POST {ledger['nara_posts']}: {entry['status']} ({item['corpus']})", flush=True)
        consecutive_failures = consecutive_failures + 1 if entry["status"] != "ok" else 0
        if consecutive_failures >= 3:
            ledger["stopped_reason"] = "연속 실패 3회: 추가 전송 중단"
            write_json(path, ledger)
            break
    return ledger


def diff_edits(text, revised):
    return [(a, b, revised[c:d]) for op, a, b, c, d in SequenceMatcher(None, text, revised, autojunk=False).get_opcodes() if op != "equal"]


def spacing_measure(items, legacy, kiwi, *, sample_path=None):
    stats = dict(chars=0, protected_chars=0, legacy_edits=0, new_suggestions=0,
                 legacy_protected_edits=0, legacy_protected_changed_chars=0, new_protected_edits=0, new_protected_changed_chars=0,
                 legacy_original_edits=0, legacy_original_changed_chars=0, new_original_edits=0, new_original_changed_chars=0,
                 suppressed=0, suppression_kinds={}, examples=[], counts={}, new_all_suggestions=0, insertions=0)
    timing = {"legacy_ms": 0, "new_ms": 0}
    samples = []
    for item in items:
        text, spans = item["text"], item["spans"]
        stats["chars"] += len(text)
        stats["protected_chars"] += sum(s.end - s.start for s in spans)
        start = time.perf_counter()
        revised, changes = legacy.correct_spacing(text, kiwi)
        timing["legacy_ms"] += (time.perf_counter() - start) * 1000
        edits = diff_edits(text, revised)
        stats["legacy_edits"] += len(edits)
        counter = SuppressedCounter()
        start = time.perf_counter()
        findings = spacing.check(text, spans, counter=counter, kiwi=kiwi, terms=TERMS)
        timing["new_ms"] += (time.perf_counter() - start) * 1000
        stats["new_suggestions"] += len(findings)
        stats["new_all_suggestions"] += len(spacing.check(text, spans, kiwi=kiwi, terms=TERMS, spacing="all"))
        stats["suppressed"] += counter.total
        for key, value in counter.to_dict().items():
            kind = key.split(":", 1)[1]
            stats["suppression_kinds"][kind] = stats["suppression_kinds"].get(kind, 0) + value
        for a, b, replacement in edits:
            if any(overlaps(a, b, s) for s in spans):
                stats["legacy_protected_edits"] += 1
                stats["legacy_protected_changed_chars"] += max(b - a, len(replacement))
                original_overlap = any(overlaps(a, b, s) and s.kind in {"original", "old-hangul"} for s in spans)
                if original_overlap:
                    stats["legacy_original_edits"] += 1
                    stats["legacy_original_changed_chars"] += max(b - a, len(replacement))
                if original_overlap and len(stats["examples"]) < 3:
                    # 최대 80자. 행 단위 전후 비교를 보여주되 원문 전체는 내보내지 않는다.
                    line_start = text.rfind("\n", 0, a) + 1
                    line_end = text.find("\n", b)
                    original = text[line_start:line_end if line_end >= 0 else len(text)]
                    corrected, _ = legacy.correct_spacing(original, kiwi)
                    if len(original) <= 80 and len(corrected) <= 80:
                        example = dict(original=original, legacy=corrected, source=item["source"])
                        if example not in stats["examples"]:
                            stats["examples"].append(example)
        for f in findings:
            stats["counts"][f.rule] = stats["counts"].get(f.rule, 0) + 1
            stats["insertions"] += f.start == f.end
            samples.append(dict(source=item["source"], selector=item["selector"],
                                before=text[max(0, f.start - 20):f.start], after=text[f.end:f.end + 20],
                                original=f.original, suggestion=f.suggestion, rule=f.rule, category=f.rule,
                                confidence=f.confidence, precision=None))
            if any(overlaps(f.start, f.end, s) for s in spans):
                stats["new_protected_edits"] += 1
                stats["new_protected_changed_chars"] += max(f.end - f.start, len(f.suggestion))
            if any(overlaps(f.start, f.end, s) and s.kind in {"original", "old-hangul"} for s in spans):
                stats["new_original_edits"] += 1
                stats["new_original_changed_chars"] += max(f.end - f.start, len(f.suggestion))
    stats["protected_ratio"] = round(stats["protected_chars"] / max(1, stats["chars"]), 6)
    stats["counts"] = dict(sorted(stats["counts"].items()))
    if sample_path:
        selected = random.Random(20261008).sample(samples, min(40, len(samples)))
        sample_path.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in selected), encoding="utf-8")
        stats["sample_size"] = len(selected)
        stats["sample_requested"] = 40
        stats["precision"] = None
        stats["sampling_status"] = "검수 표본 생성" if selected else "strict 후보 없음: 표본·정밀도 산출 불가"
    timings = {k.replace("_ms", "_ms_per_1000_chars"): round(v * 1000 / max(1, stats["chars"]), 3) for k, v in timing.items()}
    return stats, timings


def spell_measure(inputs, ledger, legacy):
    stats = {key: dict(chunks=0, parsed=0, failed=0, legacy_suggestions=0, new_suggestions=0,
                      legacy_protected=0, legacy_applied_protected_edits=0, new_protected=0, suppressed=0, kinds={},
                      rejected={}, no_change=0) for key in ("A", "B")}
    timings = dict(legacy_ms=0.0, new_ms=0.0, chars=0)
    for item in inputs:
        record = next((r for r in ledger["responses"] if r["input_sha256"] == digest(item["text"])), None)
        if record is None:
            continue
        stat = stats[item["corpus"]]
        stat["chunks"] += 1
        if record["status"] != "ok":
            stat["failed"] += 1
            continue
        raw = (CACHE / record["file"]).read_bytes().decode("utf-8")
        if digest(raw) != record["response_sha256"]:
            raise ValueError("맞춤법 응답 캐시 해시가 맞지 않습니다.")
        try:
            pages = legacy.extract_result_payload(raw)
        except (ValueError, TypeError):
            stat["failed"] += 1
            continue
        text = item["text"]
        spans = find_protected(text, "md", TERMS)
        stat["parsed"] += 1
        timings["chars"] += len(text)
        start = time.perf_counter()
        corrected = legacy.apply_chunk_corrections(text, pages)
        issues = [legacy.build_issue(0, pi, ei, page, err) for pi, page in enumerate(pages)
                  for ei, err in enumerate(page.get("errInfo", []))]
        timings["legacy_ms"] += (time.perf_counter() - start) * 1000
        stat["legacy_suggestions"] += len(issues)
        stat["legacy_applied_protected_edits"] += sum(any(overlaps(a, b, s) for s in spans) for a, b, _ in diff_edits(text, corrected))
        counter = SuppressedCounter()
        start = time.perf_counter()
        diagnostics = []
        processing_stats = {}
        new = spell_nara.postprocess(text, spans, raw, counter=counter, diagnostics=diagnostics, stats=processing_stats)
        timings["new_ms"] += (time.perf_counter() - start) * 1000
        # 같은 좌표 복원을 보호 없이 실행해 후보 단위의 침범을 센다.
        all_candidates = spell_nara.postprocess(text, [], raw)
        stat["new_suggestions"] += len(new)
        stat["legacy_protected"] += sum(any(overlaps(f.start, f.end, s) for s in spans) for f in all_candidates)
        stat["new_protected"] += sum(any(overlaps(f.start, f.end, s) for s in spans) for f in new)
        for key in ("source_mismatch", "original_mismatch", "invalid_offsets", "no_suggestion"):
            stat["rejected"][key] = stat["rejected"].get(key, 0) + processing_stats.get(key, 0)
        stat["no_change"] += processing_stats.get("no_change", 0)
        stat["suppressed"] += counter.total
        for k, v in counter.to_dict().items():
            kind = k.split(":", 1)[1]
            stat["kinds"][kind] = stat["kinds"].get(kind, 0) + v
    speed = {k + "_per_1000_chars": round(timings[k] * 1000 / max(1, timings["chars"]), 3)
             for k in ("legacy_ms", "new_ms")}
    return stats, speed


def style_measure(items):
    counts = Counter({rule: 0 for rule in sorted({r.id for r in style_lint.RULES} | style_lint.DYNAMIC_RULES)})
    samples = []
    elapsed, chars, suppressed = 0, 0, 0
    for item in items:
        counter = SuppressedCounter()
        start = time.perf_counter()
        findings = style_lint.check(item["text"], item["spans"], counter=counter, profile="article", table=item.get("table", False))
        elapsed += (time.perf_counter() - start) * 1000
        chars += len(item["text"])
        suppressed += counter.total
        for f in findings:
            counts[f.rule] += 1
            left = max(0, f.start - 35)
            context = item["text"][left:left + 120]
            samples.append(dict(source=item["source"], selector=item["selector"], rule=f.rule, severity=f.severity,
                                context=context, suggestion=f.suggestion, precision=None))
    rng = random.Random(20261008)
    samples = rng.sample(samples, min(40, len(samples)))
    path = HERE / "style-sample.jsonl"
    path.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in samples), encoding="utf-8")
    return dict(profile="article", rule_count=len(style_lint.RULES) + len(style_lint.DYNAMIC_RULES), counts=dict(sorted(counts.items())),
                total=sum(counts.values()), suppressed=suppressed, sample_size=len(samples), precision="검수자 판정 대기"), round(elapsed * 1000 / max(1, chars), 3)



def cached_spell_inputs(ledger):
    path = next((p for p in (CACHE / "spell-inputs.json", CACHE / "revision1/spell-inputs.json") if p.exists()), None)
    if path is None:
        raise ValueError("최초 맞춤법 전송 입력 캐시가 없습니다. 변경된 추출 입력으로 대체하지 않습니다.")
    inputs = json.loads(path.read_text(encoding="utf-8"))
    expected = {entry["input_sha256"] for entry in ledger["responses"]}
    actual = {digest(item["text"]) for item in inputs}
    if not expected <= actual:
        raise ValueError("맞춤법 입력 캐시가 응답 기록과 일치하지 않습니다.")
    return inputs


def audit_protection(items, kiwi):
    protected = [item for item in items if item.get("protection") in {"quote", "original"}]
    findings = sum(len(spacing.check(i["text"], i["spans"], kiwi=kiwi, terms=TERMS, spacing="all"))
                   + len(style_lint.check(i["text"], i["spans"], profile="article")) for i in protected)
    compact = lambda text: re.sub(r"\s+", "", text)
    by_source = {}
    for item in protected:
        if item["protection"] == "quote":
            by_source.setdefault(item["source"], []).append(item["text"])
    quote_text = {source: compact("".join(texts)) for source, texts in by_source.items()}
    old_samples = CACHE / "revision1/style-sample.before.jsonl"
    matched = 0
    if old_samples.exists():
        for line in old_samples.read_text(encoding="utf-8").splitlines():
            sample = json.loads(line)
            if compact(sample["context"]) in quote_text.get(sample["source"], ""):
                matched += 1
    passages = [i for i in items if "조성 음악은" in i["text"]]
    if not passages or any(i.get("protection") != "original" for i in passages) or findings:
        raise ValueError("검수자가 지적한 지문 또는 후기 보호 검증에 실패했습니다.")
    return dict(quote_blocks=sum(i["protection"] == "quote" for i in protected),
                original_blocks=sum(i["protection"] == "original" for i in protected),
                findings_in_protected_blocks=findings, reported_passage_blocks=len(passages),
                prior_quote_samples_matched=matched,
                note="1차 표본 문맥을 현재 보호 후기 본문에 공백 정규화 후 대응. 검수자의 판정 행 ID는 미제공.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cached", action="store_true", help="네트워크 요청 없이 동일 캐시를 재검사")
    p.add_argument("--collect-only", action="store_true")
    p.add_argument("--max-pages", type=int, default=30)
    args = p.parse_args()
    if args.cached:
        # 캐시 모드에서는 잘못 추가된 요청도 DNS/TCP/UDP 호출 전에 차단한다.
        def block_network(event, arguments):
            if event in {"socket.getaddrinfo", "socket.connect", "socket.sendto"}:
                raise RuntimeError("--cached에서는 네트워크를 사용할 수 없습니다.")
        sys.addaudithook(block_network)
        manifest = json.loads((CACHE / "manifest.json").read_text(encoding="utf-8"))
    else:
        manifest = collect_pages(args.max_pages)
    a, b = corpora(manifest)
    if args.cached:
        ledger = json.loads((CACHE / "spell-manifest.json").read_text(encoding="utf-8"))
        inputs = cached_spell_inputs(ledger)
    else:
        inputs = spell_inputs(a, b)
        ledger = collect_spell(inputs)
    if args.collect_only:
        return
    legacy, hashes = load_legacy()
    kiwi = spacing.get_kiwi(tuple(sorted(TERMS)))
    # 초기 모델 로드와 첫 분석을 제외한 정상 상태 시간을 측정한다. 두 경로가 같은 Kiwi를 사용한다.
    kiwi.space("다음 문장을 확인하세요.")
    sa, ta = spacing_measure(a, legacy["spacing"], kiwi, sample_path=HERE / "spacing-sample.jsonl")
    sb, tb = spacing_measure(b, legacy["spacing"], kiwi)
    # 공개 예시 한도는 결과 전체 8개. 사이트 예시는 따로 내보내지 않고 고전 예시만 남긴다.
    sa.pop("examples")
    spell, ts = spell_measure(inputs, ledger, legacy["spell"])
    style, tstyle = style_measure(a)
    audit = audit_protection(a, kiwi)
    if any(s["new_protected_edits"] for s in (sa, sb)) or any(s["new_protected"] for s in spell.values()):
        raise ValueError("새 엔진의 보호 구간 침범이 발견됐습니다.")
    import kiwipiepy
    engine_hash = digest("".join(digest(f.read_bytes()) for f in sorted((ROOT / "skills/korean-content-review/scripts").rglob("*.py")))
                         + "".join(digest(f.read_bytes()) for f in sorted(HERE.glob("*.py"))))
    baseline = json.loads((HERE / "baseline-review1.json").read_text(encoding="utf-8"))
    input_hash = digest(json.dumps([manifest, ledger, hashes, [digest(i["text"]) for i in b],
                                   [digest(i["text"]) for i in inputs], baseline], sort_keys=True, ensure_ascii=False))
    results = dict(schema=2, defaults=dict(spacing="strict", profile="article"),
                   before_review1=baseline,
                   reviewer_report=dict(spacing_suggestions=2382, spacing_insertions=2250,
                                        note="검수자 제공 수치. 저장된 1차 2184건과 차이가 있어 별도 보존."),
                   historical_protection=dict(spacing_B_original_legacy=8, spacing_B_original_new=0,
                                              spacing_A_legacy=301, spacing_A_new=0, spell_legacy=57, spell_new=0),
                   protection_audit=audit,
                   corpus=dict(site_pages=sum(p.get("status") == 200 and not p.get("login_required") for p in manifest["pages"]),
                   site_attempted_pages=len(manifest["pages"]), categories=dict(Counter(p["category"] for p in manifest["pages"]
                   if p.get("status") == 200 and not p.get("login_required"))),
                   site_blocks=len(a), original_fixtures=len(b)), spacing=dict(A=sa, B=sb), spell=spell, style=style,
                   external=dict(site_gets=manifest["site_gets"], nara_posts=ledger["nara_posts"],
                                 nara_403=sum(entry["status"] in {403, "403", "HTTP 403"} for entry in ledger["responses"]),
                                 this_run_site_gets=0 if args.cached else manifest["site_gets"],
                                 this_run_nara_posts=0 if args.cached else ledger["nara_posts"]),
                   versions=dict(python=sys.version.split()[0], kiwipiepy=kiwipiepy.__version__),
                   evidence=dict(engine_sha256=engine_hash, input_sha256=input_hash, legacy_sha256=hashes),
                   speed=dict(spacing_A=ta, spacing_B=tb, spell_postprocessing=ts, style_ms_per_1000_chars=tstyle,
                              note="모델 초기화·네트워크 대기 제외. 동일 증거의 캐시 재실행은 최초 실측 시간을 유지한다."))
    result_path = HERE / "results.json"
    if result_path.exists():
        previous = json.loads(result_path.read_text(encoding="utf-8"))
        if previous.get("evidence") == results["evidence"]:
            write_json(CACHE / "replay-timing.json", results["speed"])
            results["speed"] = previous["speed"]
    write_json(result_path, results)
    write_reports(results, HERE, ROOT)
    print(json.dumps({"pages": results["corpus"]["site_pages"], "spacing_A": sa, "spacing_B": sb, "spell": spell,
                      "style": style, "protection_audit": audit, "external": results["external"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
