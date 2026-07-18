"""Audit the frontend distribution and a simulated source archive."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = REPOSITORY_ROOT / "frontend" / "dist"
REQUIRED_SOURCE_FILES = {
    "LICENSE",
    "NOTICE",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/RELEASE_NOTES_0.1.0.md",
    "docs/THIRD_PARTY_LICENSES.md",
}
FORBIDDEN_DIRECTORY_NAMES = {
    ".venv",
    "node_modules",
    "test-results",
    "playwright-report",
    "exports",
    "uploads",
}
SENSITIVE_PATTERNS = {
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai_style_key": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "windows_user_path": re.compile(rb"[A-Za-z]:\\Users\\(?!Synthetic\\)[^\\\s]+\\"),
    "unix_user_path": re.compile(rb"/(?:home|Users)/(?!synthetic/)[^/\s]+/", re.IGNORECASE),
}


def source_candidates() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    return sorted(name for name in completed.stdout.decode("utf-8").split("\0") if name)


def assert_safe_source_name(name: str) -> None:
    path = PurePosixPath(name)
    lowered_parts = {part.casefold() for part in path.parts}
    assert not (lowered_parts & FORBIDDEN_DIRECTORY_NAMES), name
    assert "dist" not in lowered_parts, name
    assert path.suffix.casefold() not in {".db", ".sqlite", ".sqlite3"}, name
    assert not name.casefold().endswith(("-wal", "-shm")), name
    basename = path.name.casefold()
    assert not (basename == ".env" or (basename.startswith(".env.") and basename != ".env.example"))
    assert basename not in {"echoprofile.md", "echoprofile.json"}, name


def scan_bytes(data: bytes, location: str) -> None:
    for label, pattern in SENSITIVE_PATTERNS.items():
        assert pattern.search(data) is None, f"{label} found in {location}"


def inspect_frontend_dist() -> dict[str, int]:
    assert FRONTEND_DIST.is_dir(), "frontend/dist does not exist; run npm run build first"
    files = sorted(path for path in FRONTEND_DIST.rglob("*") if path.is_file())
    assert files
    for path in files:
        relative = path.relative_to(FRONTEND_DIST).as_posix()
        assert ".env" not in relative.casefold()
        assert path.suffix.casefold() not in {".db", ".sqlite", ".sqlite3"}
        scan_bytes(path.read_bytes(), f"frontend/dist/{relative}")
    return {
        "file_count": len(files),
        "byte_count": sum(path.stat().st_size for path in files),
        "source_map_count": sum(path.suffix.casefold() == ".map" for path in files),
    }


def inspect_source_archive() -> dict[str, int]:
    candidates = source_candidates()
    candidate_set = set(candidates)
    assert REQUIRED_SOURCE_FILES <= candidate_set
    for name in candidates:
        assert_safe_source_name(name)
        scan_bytes((REPOSITORY_ROOT / name).read_bytes(), name)

    with tempfile.TemporaryDirectory(prefix="echomind-stage12-source-") as directory:
        archive_path = Path(directory) / "echomind-0.1.0-source.zip"
        with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in candidates:
                archive.write(REPOSITORY_ROOT / name, arcname=f"EchoMind-0.1.0/{name}")
        with zipfile.ZipFile(archive_path) as archive:
            archived_names = archive.namelist()
        assert len(archived_names) == len(candidates)
        archive_bytes = archive_path.stat().st_size

    return {
        "file_count": len(candidates),
        "archive_byte_count": archive_bytes,
    }


def main() -> None:
    report = {
        "result": "pass",
        "frontend_dist": inspect_frontend_dist(),
        "source_archive": inspect_source_archive(),
    }
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
