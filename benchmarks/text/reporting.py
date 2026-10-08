"""집계 보고서와 루트 README의 허용된 측정 구간만 갱신한다."""
import json
import re


def write_reports(r, here, root):
    a, b = r["spacing"]["A"], r["spacing"]["B"]
    old = r["before_review1"]
    sa, sb = r["spell"]["A"], r["spell"]["B"]
    audit = r["protection_audit"]
    historical = r["historical_protection"]
    rows = [
        "# 텍스트 검수 재측정", "",
        "동일한 공개 페이지 30개의 캐시 HTML을 새 추출기로 다시 추출했다. 외부 요청은 이번 재측정에서 0회다. "
        "원문 HTML·외부 응답·최초 맞춤법 입력은 `.cache/`에만 저장하며 배포하지 않는다.", "",
        "| 항목 | 개선 전(1차 저장 결과) | 개선 후(strict/article) |", "|---|---:|---:|",
        f"| 사이트 본문 블록 | {old['corpus']['site_blocks']:,} | {r['corpus']['site_blocks']:,} |",
        f"| 사이트 본문 문자 | {old['spacing']['A']['chars']:,} | {a['chars']:,} |",
        f"| A 띄어쓰기 제안 | {old['spacing']['A']['new_suggestions']:,} | {a['new_suggestions']:,} |",
        f"| A 새 엔진 보호 침범 | {old['spacing']['A']['new_protected_edits']} | {a['new_protected_edits']} |",
        f"| A 보호 문자 비율 | {old['spacing']['A']['protected_ratio']:.2%} | {a['protected_ratio']:.2%} |",
        f"| A 문체 검출 | {old['style']['total']} | {r['style']['total']} |",
        f"| A 말투 혼용 | {old['style']['counts']['mixed-register']} | {r['style']['counts']['mixed-register']} |",
        f"| A 긴 문장 | {old['style']['counts']['long-sentence']} | {r['style']['counts']['long-sentence']} |",
        f"| A ~로부터 | {old['style']['counts']['translation-from']} | {r['style']['counts']['translation-from']} |",
        f"| B 새 엔진 원문 편집 | {old['spacing']['B']['new_original_edits']} | {b['new_original_edits']} |",
        f"| 맞춤법 새 엔진 보호 침범 | {sum(v['new_protected'] for v in old['spell'].values())} | {sum(v['new_protected'] for v in r['spell'].values())} |", "",
        "검수자 기록의 개선 전 띄어쓰기 2,382건(공백 삽입 2,250건)과 이 저장소의 1차 results.json 2,184건은 일치하지 않는다. "
        "검수자 수치는 별도 `reviewer_report`에 보존하고 위 표는 사전 사본 `baseline-review1.json` 기준이다. "
        "추출 경계·보호 범위·검사 기본값이 함께 바뀌었으므로 감소율은 정밀도 향상률이 아니다.", "",
        "## 원문·후기 보호", "",
        "| 같은 입력에서 기존 사용자 스킬과 새 엔진 비교 | 기존 | 새 엔진 |", "|---|---:|---:|",
        f"| 고전 원문 편집(공백 포함 문자 수도 동일) | {b['legacy_original_edits']} | {b['new_original_edits']} |",
        f"| 1차 A 보호 구간 침범(역사적 비교) | {historical['spacing_A_legacy']} | {historical['spacing_A_new']} |",
        f"| 재추출 A 보호 구간 침범 | {a['legacy_protected_edits']} | {a['new_protected_edits']} |",
        f"| 고정 맞춤법 입력 보호 침범 후보 | {sum(v['legacy_protected'] for v in r['spell'].values())} | {sum(v['new_protected'] for v in r['spell'].values())} |", "",
        f"A 인용·후기 {audit['quote_blocks']}블록, 원문 {audit['original_blocks']}블록을 보호했다. "
        f"보호 블록의 띄어쓰기(all)·문체(article) Finding은 {audit['findings_in_protected_blocks']}건이다. "
        f"검수자가 지적한 ‘조성 음악은 …’ 지문 보호 확인 {audit['reported_passage_blocks']}블록. "
        f"1차 표본에서 현재 후기 보호 영역으로 대응된 {audit['prior_quote_samples_matched']}건은 모두 제외됐다. "
        "검수자의 판정 행 ID는 전달되지 않아 후기 11건과의 일대일 동일성은 확정하지 않는다.", "",
        f"띄어쓰기 보호 억제는 A {a['suppressed']}건·B {b['suppressed']}건이다. "
        "억제 수는 strict 필터 전 Kiwi 전체 후보 기준이며 오류 수가 아니다. B 보호 비율은 "
        f"{b['protected_ratio']:.2%}다. 원문 표시·옛한글·인용·코드·표지·용어를 포함한다.", "",
        "기존 스킬이 원문을 바꾼 실제 예:", "",
    ]
    for example in b["examples"]:
        rows.append(f"- `{example['original']}` → `{example['legacy']}` (새 엔진은 보존)")
    rows += [
        "", "## 띄어쓰기와 정밀도 표본", "",
        f"기본 strict 범주별 검출: `{json.dumps(a['counts'], ensure_ascii=False)}`. 공백 삽입 {a['insertions']}건. "
        f"같은 재추출 입력의 all 모드는 {a['new_all_suggestions']}건이다. "
        "strict는 두 형태소 분석의 경계 품사가 일치하는 의존명사·한글 수사와 단위·떨어진 조사/어미·확실한 부정 문맥을 보고한다. "
        "보조용언·합성명사·기호·영문/숫자 경계·NBSP와 의미가 모호한 한번/안되다/데/지는 제외한다.", "",
        f"`spacing-sample.jsonl`은 strict 결과 {a['sample_size']}건이다. 시드 20261008로 최대 40건을 뽑되 "
        "실제 후보가 40건 미만이면 전부 기록하며 복제하지 않는다. 앞뒤 각 20자 문맥·원문·제안·범주·확신도와 precision=null을 남긴다.", "",
        "이번 strict 후보는 0건이므로 띄어쓰기 표본 파일은 비어 있고 정밀도를 계산할 수 없다. "
        "40건 표본 요구는 이 캐시의 실제 검출만으로 충족하지 못했다. 오류가 있는 실제 콘텐츠를 추가해 재현율과 정밀도를 함께 평가해야 한다.", "",
        f"article 문체 규칙별 검출: `{json.dumps(r['style']['counts'], ensure_ascii=False)}`. "
        f"`style-sample.jsonl`에는 최대 40건 중 {r['style']['sample_size']}건을 기록했다(문맥 120자 이내). "
        "말투 혼용은 ui에서 화면/문서당 한 번, 긴 문장은 article에서 120자 초과 info로만 보고한다. "
        "시간 기점의 로부터와 짧은 구·대조 표의 에 의해서는 제외한다.", "",
        "정밀도: **검수 판정 후 기입**. 표본의 precision을 검수자가 판정한다. "
        "기존 fluent-korean-content는 자동 검사 수단이 없는 원칙 문서이므로 검출 수를 0→N 효과로 해석하지 않는다.", "",
        "## 선택 맞춤법 모듈", "",
        f"과거 nara POST {r['external']['nara_posts']}회 중 HTTP 403이 {r['external']['nara_403']}회였다. "
        f"A {sa['parsed']}·B {sb['parsed']}청크의 성공 원응답을 각 청크당 한 번 받아 캐시했다. "
        "이번에는 새로 추출한 입력을 과거 응답에 끼워 맞추지 않고 최초 전송 입력과 응답의 해시를 대조해 재생했다. "
        "따라서 맞춤법 수치는 고정된 1차 입력의 후처리 비교이며 새 HTML 추출기의 효과 측정은 아니다.", "",
        f"유효 제안 A {sa['new_suggestions']}·B {sb['new_suggestions']}건, 보호 억제 합계 {sa['suppressed'] + sb['suppressed']}건이다. "
        "침범 후보 57건은 좌표 복원이 가능한 후보에 한정된다. 기존 실제 적용 편집은 "
        f"{sa['legacy_applied_protected_edits'] + sb['legacy_applied_protected_edits']}회로 별도 지표다. "
        "보호 외 제외와 무변경 제안은 results.json에 기록한다. 외부 서비스 의존·실패율 때문에 기본 꺼짐인 선택 모듈이다.", "",
        "## 속도와 재현", "",
        "| 처리 시간(ms/1,000자) | 1차 새 엔진 | 개선 후 새 엔진 |", "|---|---:|---:|",
        f"| A 띄어쓰기 | {old['speed']['spacing_A']['new_ms_per_1000_chars']} | {r['speed']['spacing_A']['new_ms_per_1000_chars']} |",
        f"| B 띄어쓰기 | {old['speed']['spacing_B']['new_ms_per_1000_chars']} | {r['speed']['spacing_B']['new_ms_per_1000_chars']} |",
        f"| 맞춤법 후처리 | {old['speed']['spell_postprocessing']['new_ms_per_1000_chars']} | {r['speed']['spell_postprocessing']['new_ms_per_1000_chars']} |",
        f"| 문체 | {old['speed']['style_ms_per_1000_chars']} | {r['speed']['style_ms_per_1000_chars']} |", "",
        "초기 모델 로드·첫 분석·네트워크 대기를 제외한 최초 실측이다. 코드·입력 해시가 같으면 재실행의 검출·집계를 모두 다시 계산하되 "
        "최초 시간을 유지해 results.json을 바이트 단위로 재현한다. 새 실측은 `.cache/replay-timing.json`에 둔다.", "",
        "```powershell", "$env:KCR_LEGACY_SKILLS_DIR = '<기존 스킬 폴더들: 운영체제 PATH 구분자로 연결>'",
        "python -B benchmarks/text/run_bench.py --cached", "python -B -m pytest -q tests",
        "python -B tools/scan_private.py", "```", "",
        "캐시에는 manifest.json, 페이지 HTML, spell-manifest.json, 최초 spell-inputs.json이 필요하다. "
        "1차 마이그레이션 입력은 `.cache/revision1/spell-inputs.json`에서도 읽는다. 캐시가 없거나 해시가 다르면 중단하며 네트워크로 대체하지 않는다. "
        f"누적 요청은 사이트 GET {r['external']['site_gets']}·nara POST {r['external']['nara_posts']}회, 이번 실행 요청은 각각 0회다.",
    ]
    (here / "README.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

    examples = b["examples"][:2]
    section = [
        "", "같은 입력에서 기존 사용자 스킬과 비교한 보호 결과: 고전 원문 편집 **8 → 0**, "
        "1차 사이트 보호 구간 침범 **301 → 0**, 맞춤법 보호 침범 후보 **57 → 0**입니다. "
        "사이트 301건은 1차 추출 기준이며 재추출 측정과 구분합니다.", "",
    ]
    section += [f"- `{e['original']}` → 기존 `{e['legacy']}`; 새 엔진은 원문 보존." for e in examples]
    section += ["", "| 기본 검사 | 개선 후 검출 | 정밀도: 검수 판정 후 기입 |", "|---|---:|---|",
                f"| 띄어쓰기(strict) | {a['new_suggestions']}건 | PRECISION_SPACING |",
                f"| 문체(article) | {r['style']['total']}건 | PRECISION_STYLE |", "",
                "검출 수 감소가 정밀도 향상을 증명하지는 않습니다. 학생 후기·인용·지문을 보호하고 판정용 표본을 다시 만들었습니다. "
                "맞춤법은 **선택 모듈**입니다. 외부 서비스가 과거 19회 요청 중 13회 HTTP 403을 반환했습니다. "
                "이번 재측정은 캐시만 사용했으며 외부 요청은 0회입니다. [상세 비교·표본·재현 방법](benchmarks/text/README.md)을 참고하세요.", ""]
    path = root / "README.md"
    data = path.read_bytes()
    start, end = b"<!-- TEXT-BENCH:START -->", b"<!-- TEXT-BENCH:END -->"
    if data.count(start) != 1 or data.count(end) != 1:
        raise ValueError("README 측정 구간 표지가 유일하지 않습니다.")
    a_start, a_end = data.index(start) + len(start), data.index(end)
    if a_end < a_start:
        raise ValueError("README 측정 구간 표지 순서가 잘못됐습니다.")
    newline = "\r\n" if b"\r\n" in data else "\n"
    path.write_bytes(data[:a_start] + newline.join(section).encode("utf-8") + data[a_end:])
    injected = here / "injection-results.json"
    if injected.exists():
        write_injection_report(json.loads(injected.read_text(encoding="utf-8")), here, root)


def percentage(value):
    return "—" if value is None else f"{value:.1%}"


def write_injection_report(result, here, root):
    names = {"legacy-spacing": "기존 Kiwi", "spacing-strict": "새 strict", "spacing-all": "새 all",
             "style-article": "새 문체(article)", "combined-default": "통합 기본값"}
    kinds = list(result["injection_counts"])
    rows = ["", "## 실제 문장 오류 주입 실험", "",
            f"시드 {result['seed']}. 보호되지 않은 실제 문장 후보 {result['eligible_sentence_pool']:,}개에서 "
            f"15~90자 문장 {result['clean_sentences']}개를 중복 없이 균일 무작위 선택했다. "
            f"선택 후 가능한 유형 하나를 넣은 오염 문장은 {result['corrupted_sentences']}개이며, "
            f"적용 가능한 오류가 없던 {result['skipped_no_applicable_error']}개는 깨끗한 집합 평가에만 포함한다. "
            "깨끗한 문장의 기존 내용은 손대지 않았고, 오류 주입 위치와 모든 문장은 `.cache/injection/`에만 둔다.", "",
            "유형 선택은 누적 주입 수가 적은 유형을 우선하고 동률·위치는 고정 시드로 고른다. "
            "희소 유형을 만들려고 문장이나 어휘를 추가하지 않는다. 한 번/한번처럼 의미에 따라 둘 다 허용될 수 있는 대안은 "
            "알려진 단위 오류로 주입하지 않는다. 검출 결과는 문장·유형 선택에 사용하지 않았다.", "",
            "| 주입 유형 | 선택 300문장 중 가능 문장 | 실제 주입 수 |", "|---|---:|---:|"]
    rows += [f"| {kind} | {result['available_sentence_counts'][kind]} | {result['injection_counts'][kind]} |" for kind in kinds]
    rows += ["", "| 도구 | 재현율(전체 주입) | 정밀도(오염 Finding) | 깨끗한 300문장 헛지적 | 문장당 평균 | 오염 위치 밖 Finding |",
             "|---|---:|---:|---:|---:|---:|"]
    for name, stat in result["tools"].items():
        rows.append(f"| {names[name]} | {percentage(stat['recall'])} ({stat['detected_sentences_near']}/{stat['injected_sentences']}) "
                    f"| {percentage(stat['precision'])} ({stat['true_positive_findings']}/{stat['corrupted_findings']}) "
                    f"| {stat['clean_findings']} | {stat['clean_findings_per_sentence']:.3f} | {stat['off_target_findings']} |")
    rows += ["", "| 유형별 재현율(±2자) | " + " | ".join(names.values()) + " |", "|---|" + "---:|" * len(names)]
    for kind in kinds:
        rows.append(f"| {kind} | " + " | ".join(percentage(result['by_type'][kind][name]['recall']) for name in names) + " |")
    rows += ["", "유형별 정밀도·깨끗한 대응 문장의 헛지적·오염 위치 밖 Finding도 `injection-results.json`의 "
             "`by_type`에 기록했다. 재현율은 주입 위치 ±2자와 겹치는 Finding으로 판정하지만 정밀도는 정확한 주입 위치만 인정한다. "
             "0길이 공백 삭제/삽입 좌표를 포함하며, 분모가 0이면 —(null)이다. 모든 등급을 포함한다. "
             "오염 위치 밖은 정확한 위치 기준이고 ±2자 밖 건수도 JSON에 별도로 기록한다.", "",
             "도구별 전체 재현율은 다섯 유형 전체가 분모다. 따라서 띄어쓰기 도구가 표기·이중 피동을 놓친 것과 "
             "문체 도구가 공백 오류를 놓친 것은 담당 범위 차이도 포함한다. 유형별 표를 함께 읽는다. "
             "이는 알려진 주입 위치를 기준으로 한 정밀도이며 실제 윤문 가치에 대한 검수자 판정을 대신하지 않는다.", "",
             "strict/통합 기본값은 헛지적을 줄이는 대신 일부 조사·의존명사 오류를 놓쳤다. all은 이번 실험에서 기존 Kiwi보다 "
             "깨끗한 문장의 지적이 더 많고 정밀도가 낮았다. 표기 사전 주입은 1건뿐이며 이중 피동은 0건이므로 "
             "문체 모듈 전체의 정밀도·재현율을 일반화하지 않는다.", "",
             "주입 조각 예시(전후 각각 20자 이하):", ""]
    rows += [f"- {example['type']}: `{example['before']}` → `{example['after']}`" for example in result["examples"]]
    rows += ["", "맞춤법(nara)은 네트워크 금지로 비교에서 제외했다. 사이트 GET·nara POST 모두 0회이며 DNS·연결 호출도 차단한다. "
             "기존 Kiwi에는 새 도구와 같은 모델·용어 사전을 넣고, 줄 변경 수 대신 문자 diff 편집을 Finding으로 변환했다.", "",
             "```powershell", "$env:KCR_LEGACY_SKILLS_DIR = '<기존 kiwi-spacing을 포함한 스킬 폴더>'",
             "python -B benchmarks/text/injection.py --cached", "```", "",
             "캐시가 없으면 종료 코드 2로 실패하고 네트워크로 수집하지 않는다. "
             "깨끗한/오염 문장·좌표·원문/치환 문자열은 `.cache/injection/dataset.json`, 두 집합의 Finding은 `.cache/injection/findings.json`에 있다. "
             "공개 결과에는 집계·해시와 20자 이하 조각만 남긴다.", ""]
    start, end = "<!-- TEXT-INJECTION:START -->", "<!-- TEXT-INJECTION:END -->"
    report = here / "README.md"
    text = report.read_text(encoding="utf-8")
    section = start + "\n" + "\n".join(rows) + end
    if start in text or end in text:
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError("오류 주입 보고서 구간 표지가 유일하지 않습니다.")
        a, b = text.index(start), text.index(end) + len(end)
        text = text[:a] + section + text[b:]
    else:
        text = text.rstrip() + "\n\n" + section + "\n"
    report.write_text(text, encoding="utf-8")

    path = root / "README.md"
    data = path.read_bytes()
    root_start, root_end = b"<!-- TEXT-BENCH:START -->", b"<!-- TEXT-BENCH:END -->"
    if data.count(root_start) != 1 or data.count(root_end) != 1:
        raise ValueError("README 측정 구간 표지가 유일하지 않습니다.")
    a, b = data.index(root_start) + len(root_start), data.index(root_end)
    inner = data[a:b].decode("utf-8")
    inner = inner.replace("정밀도: 검수 판정 후 기입", "오류 주입: 정밀도·재현율·헛지적")
    for label, name in (("띄어쓰기(strict)", "spacing-strict"), ("문체(article)", "style-article")):
        stat = result["tools"][name]
        value = (f"정밀도 {percentage(stat['precision'])} · 재현율 {percentage(stat['recall'])} "
                 f"· 깨끗한 300문장 {stat['clean_findings']}건(평균 {stat['clean_findings_per_sentence']:.3f})")
        inner, count = re.subn(r"(?m)^(\| " + re.escape(label) + r" \| [^|\r\n]*\|)[^\r\n]*",
                              lambda m: m.group(1) + " " + value + " |", inner)
        if count != 1:
            raise ValueError("README 기본 검사 행을 찾을 수 없습니다.")
    note_start, note_end = "<!-- INJECTION-SUMMARY:START -->", "<!-- INJECTION-SUMMARY:END -->"
    stat = result["tools"]["combined-default"]
    summary = (f"{note_start}\n실제 문장 300개 중 {result['corrupted_sentences']}개에 오류 하나씩을 주입했습니다. "
               f"통합 기본값: 정밀도 {percentage(stat['precision'])}, 재현율 {percentage(stat['recall'])}, "
               f"깨끗한 문장 헛지적 {stat['clean_findings']}건. 재현율은 주입 위치 ±2자, 정밀도는 정확한 위치 기준이며 "
               "실제 주입된 유형을 합산했습니다. 표기 주입은 1건, 이중 피동은 0건이어서 문체 전체의 효과로 일반화할 수 없습니다. "
               "실사용 문구의 윤문 가치에 대한 정밀도 판정과 구분합니다. "
               f"nara는 제외했고 외부 요청은 0회입니다.\n{note_end}")
    if note_start in inner:
        x, y = inner.index(note_start), inner.index(note_end) + len(note_end)
        inner = inner[:x] + summary + inner[y:]
    else:
        inner = inner.rstrip() + "\n\n" + summary + "\n"
    newline = "\r\n" if b"\r\n" in data else "\n"
    inner = inner.replace("\r\n", "\n").replace("\n", newline)
    path.write_bytes(data[:a] + inner.encode("utf-8") + data[b:])
