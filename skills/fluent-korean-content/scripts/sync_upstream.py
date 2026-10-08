#!/usr/bin/env python3
"""fluent-korean 비코딩 지침을 GitHub 원본과 안전하게 동기화한다."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPOSITORY = "snflkd/fluent-korean"
BRANCH = "main"
UPSTREAM_PATH = "plugins/fluent-korean/output-styles/fluent-korean-not-coding.md"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/contents/{UPSTREAM_PATH}?ref={BRANCH}"
SOURCE_URL = f"https://github.com/{REPOSITORY}/blob/{BRANCH}/{UPSTREAM_PATH}"
SKILL_ROOT = Path(__file__).resolve().parents[1]
TARGET_PATH = SKILL_ROOT / "references" / "fluent-korean-not-coding.md"
METADATA_PATH = SKILL_ROOT / "references" / "upstream.json"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
KST = timezone(timedelta(hours=9))
REQUIRED_MARKERS = (
    "name: fluent-korean-not-coding",
    "## 동작 범위",
    "## 문장 단위",
    "## 구 단위",
)


class SyncError(RuntimeError):
    pass


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"


def fetch_upstream() -> tuple[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "fluent-korean-content-sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(API_URL, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SyncError(f"GitHub 원본을 읽지 못했습니다: {exc}") from exc

    try:
        if payload["type"] != "file" or payload["encoding"] != "base64":
            raise SyncError("GitHub 응답이 예상한 단일 base64 파일 형식이 아닙니다.")
        encoded = "".join(payload["content"].split())
        content = base64.b64decode(encoded, validate=True).decode("utf-8")
        blob_sha = payload["sha"]
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise SyncError(f"GitHub 응답을 해석하지 못했습니다: {exc}") from exc

    content = normalize(content)
    missing = [marker for marker in REQUIRED_MARKERS if marker not in content]
    if missing:
        raise SyncError("원본 형식이 바뀌어 필수 표지를 찾지 못했습니다: " + ", ".join(missing))
    return content, blob_sha


def read_local(path: Path) -> str | None:
    if not path.exists():
        return None
    return normalize(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def update_skill_timestamp(timestamp: str) -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    replacement = f'  updated: "{timestamp}"'
    updated, count = re.subn(r'^  updated:\s*.*$', replacement, skill, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SyncError("SKILL.md frontmatter의 metadata에서 updated 항목을 정확히 하나 찾지 못했습니다.")
    atomic_write(SKILL_PATH, normalize(updated))


def metadata(blob_sha: str, timestamp: str) -> str:
    payload = {
        "source": SOURCE_URL,
        "repository": REPOSITORY,
        "branch": BRANCH,
        "path": UPSTREAM_PATH,
        "license": "MIT",
        "upstream_blob_sha": blob_sha,
        "synced_at_kst": timestamp,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def check(content: str, blob_sha: str) -> bool:
    local_content = read_local(TARGET_PATH)
    try:
        local_metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        local_metadata = {}
    return local_content == content and local_metadata.get("upstream_blob_sha") == blob_sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="원본과 차이가 있는지만 확인합니다.")
    mode.add_argument("--write", action="store_true", help="변경된 원본을 로컬 참조 파일에 반영합니다.")
    args = parser.parse_args()

    try:
        content, blob_sha = fetch_upstream()
        current = check(content, blob_sha)
        if args.check:
            print("CURRENT" if current else "OUTDATED")
            return 0 if current else 1

        if current:
            print("UNCHANGED")
            return 0

        timestamp = datetime.now(KST).isoformat(timespec="seconds")
        atomic_write(TARGET_PATH, content)
        atomic_write(METADATA_PATH, metadata(blob_sha, timestamp))
        update_skill_timestamp(timestamp)
        print(f"UPDATED {blob_sha}")
        return 0
    except SyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
