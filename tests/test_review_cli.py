import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/korean-content-review/scripts"))
import pytest
from kcr.review import main, review_text, markdown_report
from kcr.findings import overlaps
from kcr.protect import find_protected

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/korean-content-review/scripts/review.py"
KIWI_CLI = ROOT / "skills/kiwi-spacing/kiwi_space.py"
OCR = "논증은크게연역과귀납으로나뉜다전제가참이면결론이참이다"
RESTORED = "논증은 크게 연역과 귀납으로 나뉜다 전제가 참이면 결론이 참이다"


def run(*args, input=None):
    return subprocess.run([sys.executable, str(CLI), *map(str, args)], input=input,
                          capture_output=True, text=True, encoding="utf-8")


def test_default_modes_and_explicit_all_ui():
    source = "회원가입을 해보다. 할수 있어요. 확인합니다."
    strict = run("text", "-", "--format", "json", input=source)
    broad = run("text", "-", "--spacing", "all", "--profile", "ui", "--format", "json", input=source)
    assert strict.returncode == broad.returncode == 0
    a, b = json.loads(strict.stdout), json.loads(broad.stdout)
    assert (a["spacing"], a["profile"]) == ("strict", "article")
    assert not any(f["rule"] == "mixed-register" for f in a["items"][0]["findings"])
    assert sum(f["rule"] == "mixed-register" for f in b["items"][0]["findings"]) == 1
    assert any(f["rule"] == "spacing-optional" for f in b["items"][0]["findings"])


def test_site_ui_register_once_and_reviews_excluded(monkeypatch, capsys):
    import io
    import kcr.review as module
    html = '<button>시작해요.</button><button>확인합니다.</button><a>다시 해요.</a><a>계속합니다.</a><section id="reviews"><p>컨텐츠를 보여줘요. 할수 있다.</p></section><div class="exam-box">역활</div>'
    monkeypatch.setattr(module, "urlopen", lambda *a, **kw: io.BytesIO(html.encode()))
    assert main(["site", "https://example.org", "--profile", "ui", "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    findings = [f for item in report["items"] for f in item["findings"]]
    assert sum(f["rule"] == "mixed-register" for f in findings) == 1
    protected = [item for item in report["items"] if item.get("protection")]
    assert {item["protection"] for item in protected} == {"quote", "original"}
    assert all(not item["findings"] for item in protected)


def test_json_original_fixture():
    done = run("text", ROOT / "tests/fixtures/classical.md", "--fmt", "md", "--format", "json")
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    text = (ROOT / "tests/fixtures/classical.md").read_text(encoding="utf-8")
    spans = find_protected(text, "md")
    assert all(not overlaps(f["start"], f["end"], s) for f in report["items"][0]["findings"] for s in spans)
    assert sum(report["suppressed"].values()) > 0
    assert report["external"]["nara_posts"] == 0


def test_stdin_markdown_default():
    done = run("text", "-", "--modules", "style", input="컨텐츠 역활")
    assert done.returncode == 0
    assert "| style | 2 |" in done.stdout and "컨텐츠" in done.stdout


def test_apply_is_explicit_conservative_and_preserves_bytes(tmp_path):
    file = tmp_path / "input.md"
    source = ":::original\r\n컨텐츠 역활\r\n:::\r\n컨텐츠 역활 되어지는 일\r\n"
    file.write_bytes(source.encode())
    before = file.read_bytes()
    check = run("text", file, "--fmt", "md", "--modules", "style", "--format", "json")
    assert check.returncode == 0 and file.read_bytes() == before
    done = run("text", file, "--fmt", "md", "--modules", "style", "--apply", "--format", "json")
    assert done.returncode == 0, done.stderr
    assert file.read_bytes().decode() == source.replace("컨텐츠 역활 되어지는", "콘텐츠 역할 되어지는")
    report = json.loads(done.stdout)
    assert report["items"][0]["applied"] == 2 and report["items"][0]["diff"]


def test_output_and_bad_module(tmp_path):
    out = tmp_path / "report.json"
    done = run("text", "-", "--modules", "style", "--format", "json", "--out", out, input="메세지")
    assert done.returncode == 0 and json.loads(out.read_text(encoding="utf-8"))["items"]
    assert run("text", "-", "--modules", "unknown", input="텍스트").returncode == 2


def test_standalone_spacing_wrapper():
    helper = ROOT / "skills/kiwi-spacing/kiwi_space.py"
    done = subprocess.run([sys.executable, str(helper), "--file", str(ROOT / "tests/fixtures/questions.md"),
                           "--check", "--format", "json"], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert sum(report["suppressed"].values()) > 0
    text = (ROOT / "tests/fixtures/questions.md").read_text(encoding="utf-8")
    spans = find_protected(text, "md")
    assert all(not overlaps(f["start"], f["end"], s) for f in report["items"][0]["findings"] for s in spans)


def test_site_offline_and_linebreak_ignore(monkeypatch, capsys):
    import kcr.review as review
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return '<p>메세지</p><p class="poem">컨텐츠</p>'.encode()
    monkeypatch.setattr(review, "urlopen", lambda *args, **kwargs: FakeResponse())
    commands = []
    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, '{"issues":[]}', '')
    monkeypatch.setattr(review.subprocess, "run", fake_run)
    assert main(["site", "https://example.org", "--modules", "style", "--linebreak", "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["items"][0]["findings"]) == 1
    assert not report["items"][1]["findings"]
    assert "--ignore" in commands[0] and "[data-original-text]" in commands[0][-1]
    assert commands[0][1].endswith("korean-line-break\\scripts\\ko-wrap-check.mjs") or commands[0][1].endswith("korean-line-break/scripts/ko-wrap-check.mjs")


def run_kiwi(*args):
    return subprocess.run([sys.executable, "-B", "-X", "utf8", str(KIWI_CLI), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8")


@pytest.mark.parametrize("wrapper", ["kiwi", "review"])
def test_repair_cli_before_after_and_json(wrapper):
    if wrapper == "kiwi":
        done = run_kiwi("--text", OCR, "--spacing", "repair")
        structured = run_kiwi("--text", OCR, "--spacing", "repair", "--format", "json")
    else:
        done = run("text", "-", "--spacing", "repair", input=OCR)
        structured = run("text", "-", "--spacing", "repair", "--format", "json", input=OCR)
    assert done.returncode == structured.returncode == 0, done.stderr + structured.stderr
    assert "[line 1]" in done.stdout and "전: " + OCR in done.stdout and "후: " + RESTORED in done.stdout
    assert "공백이 거의 없는 줄" not in done.stdout
    report = json.loads(structured.stdout)
    assert report["items"][0]["line_changes"] == [{"line": 1, "original": OCR, "corrected": RESTORED}]
    assert all("⟦" in f["context_before"] and "⟦ ⟧" in f["context_after"]
               for f in report["items"][0]["findings"])


@pytest.mark.parametrize("wrapper", ["kiwi", "review"])
def test_default_sparse_advisory_once_and_strict_kept(wrapper):
    done = run_kiwi("--text", OCR) if wrapper == "kiwi" else run("text", "-", input=OCR)
    assert done.returncode == 0, done.stderr
    assert done.stdout.count("공백이 거의 없는 줄 1개 — OCR 복원은 `--spacing repair`") == 1
    assert "후: " not in done.stdout
    assert "| spacing | 0 | 0 | 0 |" in done.stdout


@pytest.mark.parametrize("write", [False, True])
def test_repair_quiet_batch_and_explicit_write(tmp_path, write):
    changed = tmp_path / "changed.md"
    unchanged = tmp_path / "unchanged.md"
    source = ":::original\r\n" + OCR + "\r\n:::\r\n" + OCR + "\r\n"
    changed.write_bytes(source.encode())
    unchanged.write_text(RESTORED, encoding="utf-8")
    done = run_kiwi("--dir", tmp_path, "--spacing", "repair", "--quiet", "--write" if write else "--check")
    assert done.returncode == 0, done.stderr
    assert "changed.md" in done.stdout and "unchanged.md" not in done.stdout
    assert "[line 4]" in done.stdout and "[line 2]" not in done.stdout
    expected = source.replace(":::\r\n" + OCR, ":::\r\n" + RESTORED) if write else source
    assert changed.read_bytes().decode() == expected
    assert unchanged.read_text(encoding="utf-8") == RESTORED


@pytest.mark.parametrize("wrapper", ["kiwi", "review"])
def test_quiet_unchanged_file_is_silent(tmp_path, wrapper):
    file = tmp_path / "clean.txt"
    file.write_text(RESTORED, encoding="utf-8")
    done = (run_kiwi("--file", file, "--spacing", "repair", "--quiet") if wrapper == "kiwi"
            else run("text", file, "--spacing", "repair", "--quiet"))
    assert done.returncode == 0, done.stderr
    assert done.stdout == ""


@pytest.mark.parametrize("apply_flag", ["--apply", "--write"])
def test_review_repair_apply_and_protection(tmp_path, apply_flag):
    file = tmp_path / "ocr.md"
    source = ":::original\r\n" + OCR + "\r\n:::\r\n" + OCR + "\r\n"
    file.write_bytes(source.encode())
    preview = run("text", file, "--fmt", "md", "--spacing", "repair")
    assert preview.returncode == 0 and file.read_bytes().decode() == source
    applied = run("text", file, "--fmt", "md", "--spacing", "repair", apply_flag)
    assert applied.returncode == 0, applied.stderr
    assert file.read_bytes().decode() == source.replace(":::\r\n" + OCR, ":::\r\n" + RESTORED)
    assert "[line 4]" in applied.stdout and "[line 2]" not in applied.stdout
    assert "```diff" in applied.stdout


def test_all_markdown_and_json_retain_context():
    done = run_kiwi("--text", OCR, "--spacing", "all")
    assert done.returncode == 0, done.stderr
    assert "크게⟦⟧연역과" in done.stdout and "크게⟦ ⟧연역과" in done.stdout
    structured = run("text", "-", "--modules", "style", "--format", "json", input="컨텐츠 안내")
    data = json.loads(structured.stdout)["items"][0]["findings"][0]
    assert data["original"] == "컨텐츠" and data["suggestion"] == "콘텐츠"
    assert data["context_before"] == "⟦컨텐츠⟧ 안내" and data["context_after"] == "⟦콘텐츠⟧ 안내"
