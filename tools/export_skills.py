#!/usr/bin/env python3
"""정본 스킬을 공개 폴더에 복사하고 공개 금지 정보 검사를 실행한다."""

from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS = "korean-content-review,korean-line-break,kiwi-spacing,fluent-korean-content"


def excluded(relative: Path) -> bool:
    parts = relative.parts
    return (
        "__pycache__" in parts
        or any(fnmatch.fnmatch(part, "*.pyc") or part == ".DS_Store" for part in parts)
        or (len(parts) >= 2 and parts[0] == "references" and parts[1].startswith("local-"))
    )


def source_files(source: Path):
    def onerror(error):
        raise error

    for directory, dirs, files in os.walk(source, followlinks=False, onerror=onerror):
        base = Path(directory)
        dirs[:] = sorted(name for name in dirs if not excluded((base / name).relative_to(source)))
        for name in dirs:
            candidate = base / name
            if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
                raise ValueError("정본의 폴더 링크는 내보내지 않습니다")
        for name in sorted(files):
            file = base / name
            relative = file.relative_to(source)
            if excluded(relative):
                continue
            if file.is_symlink():
                raise ValueError("정본의 파일 링크는 내보내지 않습니다")
            if name == ".env" or name.startswith(".env."):
                raise ValueError("자격증명 파일이 포함되어 내보내기를 중단합니다(내용 미열람)")
            yield file, relative


def plan(source_root: Path, skills: list[str]):
    operations = []
    for skill in skills:
        source = source_root / skill
        destination = REPOSITORY / "skills" / skill
        if not source.is_dir() or not (source / "SKILL.md").is_file():
            raise ValueError(f"{skill}: 정본 폴더 또는 SKILL.md가 없습니다")
        if source.is_symlink() or getattr(source, "is_junction", lambda: False)():
            raise ValueError(f"{skill}: 정본 폴더 링크는 허용하지 않습니다")
        # 목적지의 기존 링크를 따라 공개 폴더 밖에 쓰는 것을 막는다.
        destination.resolve().relative_to(REPOSITORY.resolve())
        if destination.resolve() == source.resolve():
            raise ValueError(f"{skill}: 정본과 목적지가 같습니다")
        for file, relative in source_files(source):
            target = destination / relative
            target.resolve().relative_to(REPOSITORY.resolve())
            if target.is_symlink():
                raise ValueError(f"{skill}: 목적지 파일 링크는 허용하지 않습니다")
            changed = not target.is_file() or file.read_bytes() != target.read_bytes()
            if changed:
                operations.append(("수정" if target.exists() else "추가", file, target))
    return operations


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="source", type=Path, default=Path.home() / ".claude" / "skills",
                        help="정본 스킬 폴더(기본: ~/.claude/skills)")
    parser.add_argument("--skills", default=DEFAULT_SKILLS, help="쉼표로 나눈 스킬 이름")
    parser.add_argument("--dry-run", action="store_true", help="바뀔 파일 목록만 출력하고 쓰지 않는다")
    args = parser.parse_args(argv)
    skills = list(dict.fromkeys(value.strip() for value in args.skills.split(",") if value.strip()))
    if not skills or any(not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) for value in skills):
        parser.error("스킬 이름은 소문자·숫자·하이픈으로 지정하세요")
    try:
        operations = plan(args.source.expanduser().resolve(), skills)
    except (OSError, ValueError):
        print("내보내기 실패: 정본·목적지 폴더, SKILL.md, 링크 및 자격증명 파일 여부를 확인하세요.", file=sys.stderr)
        return 1
    try:
        for action, source, target in operations:
            print(f"{action}: {target.relative_to(REPOSITORY).as_posix()}")
            if not args.dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    except OSError:
        print("복사 실패: 목적지 쓰기 권한과 정본 파일 상태를 확인하세요.", file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"미리보기: 변경 예정 {len(operations)}파일, 실제 복사 없음")
        return 0
    print(f"복사 완료: {len(operations)}파일. 저장소 전체를 검사합니다.")
    return subprocess.run([sys.executable, str(REPOSITORY / "tools" / "scan_private.py")],
                          cwd=REPOSITORY, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
