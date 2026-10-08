#!/usr/bin/env python3
"""공개 금지 문자열을 검사한다. 값은 출력하지 않고 파일:줄과 유형만 알린다."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys


# 문자열을 나눈 이유: 검사기 소스에도 동일한 금지 패턴 검사를 적용하기 위해서다.
# 추가할 ID도 분할 리터럴로 기록한다. 검출 시에는 합친 전체 값으로 비교한다.
INTERNAL_IDS = ("16fPakOh9CqK92y" "wFrf03BhzPW9jahLg-",)
EXCLUDED_DIRS = {".git", "node_modules", ".cache", "__pycache__", ".pytest_cache"}
# 기본 예외: RFC 2606 예약 예시 도메인, 브라우저 User-Agent 버전(예: Chrome/136.0.0.0)
DEFAULT_ALLOW = (re.compile(r"@example\.(?:org|com|net)$|\.test$"), re.compile(r"^\d{2,3}\.0\.0\.0$"))
PATTERNS = (
    ("user-home", re.compile(r"C:[/\\]Users\b|[/]Users[/]|[/]home[/]|~[/\\]dev\b", re.I)),
    ("local-work", re.compile("scratch" "pad|_work" "trees|ekkorean-ds-" "sync", re.I)),
    ("privileged-role", re.compile("service" "_role", re.I)),
    ("backend-key", re.compile("SUPABASE_" + r"[A-Z_]*" + "KEY")),
    ("api-token", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("email", re.compile(r"(?<![\w.+-])[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
                         r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
                         r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*"
                         r"\.(?:[A-Za-z]{2,63}|xn--[A-Za-z0-9-]{2,})(?![A-Za-z0-9.-])")),
    ("ipv4", re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")),
    ("dotenv-value", re.compile(
        r"^[ \t]*(?:export[ \t]+)?(?:[A-Z][A-Z0-9_]*_)?"
        r"(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?|PRIVATE_KEY|DATABASE_URL)"
        r"[ \t]*=[ \t]*(?![ \t#]*$)[^\r\n]+", re.M)),
    *(('internal-id', re.compile(re.escape(value))) for value in INTERNAL_IDS),
)


def findings(text: str, allow: list[re.Pattern[str]]):
    """일치한 값에만 명시적 예외를 적용하고 줄 번호와 유형을 반환한다."""
    seen = set()
    for kind, pattern in PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0)
            # 브라우저 버전처럼 각 구간이 범위를 벗어나는 수열은 IP가 아니다.
            if kind == "ipv4" and any(int(part) > 255 for part in value.split(".")):
                continue
            if any(rule.search(value) for rule in (*DEFAULT_ALLOW, *allow)):
                continue
            line = text.count("\n", 0, match.start()) + 1
            if (line, kind) not in seen:
                seen.add((line, kind))
                yield line, kind


def scan(root: Path, allow: list[re.Pattern[str]]) -> int:
    total = 0
    scanned = 0
    errors = []

    def onerror(error):
        errors.append(error)

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        dirs[:] = sorted(name for name in dirs if name not in EXCLUDED_DIRS)
        # 외부 경로를 따라가지 않고, 검사할 수 없는 링크는 실패로 보고한다.
        for name in list(dirs):
            candidate = Path(directory, name)
            if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
                print(f"{candidate.relative_to(root).as_posix()}:1 [unscanned-link]")
                total += 1
                dirs.remove(name)
        for name in sorted(files):
            file = Path(directory, name)
            relative = file.relative_to(root).as_posix()
            if file.is_symlink():
                print(f"{relative}:1 [unscanned-link]")
                total += 1
                continue
            # 자격증명 파일은 열지 않는다. 파일 존재 자체를 공개 차단 사유로 삼는다.
            if name == ".env" or name.startswith(".env."):
                print(f"{relative}:1 [dotenv-file: 내용 미열람]")
                total += 1
                continue
            for line, kind in findings(relative, allow):
                print(f"{relative}:{line} [filename:{kind}]")
                total += 1
            try:
                raw = file.read_bytes()
            except OSError:
                print(f"{relative}:1 [read-error]")
                total += 1
                continue
            # UTF-16 문서와 바이너리 안의 경로·메타데이터 문자열도 검사한다.
            if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
                content = raw.decode("utf-16", errors="replace")
            elif b"\x00" in raw:
                content = raw.decode("utf-8", errors="replace")
            else:
                try:
                    content = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    try:
                        content = raw.decode("cp949")
                    except UnicodeDecodeError:
                        content = raw.decode("utf-8", errors="replace")
            scanned += 1
            for line, kind in findings(content, allow):
                print(f"{relative}:{line} [{kind}]")
                total += 1
    for _ in errors:
        print(".:1 [walk-error: 일부 폴더 검사 실패]")
        total += 1
    print(f"비공개 정보 검사: {scanned}파일, 발견 {total}건")
    return 1 if total else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1],
                        help="검사할 폴더(기본: 저장소 전체)")
    parser.add_argument("--allow", action="append", default=[], metavar="정규식",
                        help="일치한 값에 적용할 예외 정규식. 여러 번 지정 가능, 기본 예외 없음")
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        parser.error("검사 폴더가 없습니다")
    try:
        allow = [re.compile(value) for value in args.allow]
    except re.error as error:
        parser.error(f"잘못된 예외 정규식: {error}")
    return scan(args.root.resolve(), allow)


if __name__ == "__main__":
    sys.exit(main())
