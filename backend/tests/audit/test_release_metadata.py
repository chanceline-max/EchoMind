"""Stage 12 release metadata and licensing contract checks."""

import hashlib
import json
import tomllib
from pathlib import Path

from echomind import __version__
from echomind.core.config import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RELEASE_VERSION = "0.1.0"
APACHE_2_CANONICAL_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"


def read_text(path: str) -> str:
    return (REPOSITORY_ROOT / path).read_text(encoding="utf-8")


def test_license_and_notice_are_complete_lf_text_files() -> None:
    license_bytes = (REPOSITORY_ROOT / "LICENSE").read_bytes()
    notice_bytes = (REPOSITORY_ROOT / "NOTICE").read_bytes()

    assert len(license_bytes) == 11_358
    assert hashlib.sha256(license_bytes).hexdigest() == APACHE_2_CANONICAL_SHA256
    assert b"Apache License\n                           Version 2.0, January 2004" in license_bytes
    assert b"END OF TERMS AND CONDITIONS" in license_bytes
    assert b"Copyright [yyyy] [name of copyright owner]" in license_bytes
    assert "杨锦辰".encode() not in license_bytes
    assert b"\r" not in license_bytes
    assert license_bytes.endswith(b"\n") and not license_bytes.endswith(b"\n\n")

    notice = notice_bytes.decode("utf-8")
    assert "EchoMind" in notice
    assert "Copyright 2026 杨锦辰" in notice
    assert "Apache License, Version 2.0" in notice
    assert b"\r" not in notice_bytes


def test_backend_and_frontend_publish_apache_metadata() -> None:
    pyproject = tomllib.loads(read_text("backend/pyproject.toml"))["project"]
    frontend = json.loads(read_text("frontend/package.json"))

    assert pyproject["name"] == "echomind"
    assert pyproject["version"] == RELEASE_VERSION
    assert pyproject["license"] == "Apache-2.0"
    assert pyproject["authors"] == [{"name": "杨锦辰"}]
    assert pyproject["readme"] == "README.md"
    assert pyproject["requires-python"] == ">=3.12,<3.13"
    assert frontend["name"] == "echomind-frontend"
    assert frontend["version"] == RELEASE_VERSION
    assert frontend["license"] == "Apache-2.0"
    assert frontend["author"] == "杨锦辰"


def test_release_version_is_consistent_across_runtime_and_documents() -> None:
    settings_default = Settings.model_fields["app_version"].default
    assert __version__ == settings_default == RELEASE_VERSION
    assert f"EchoMind {RELEASE_VERSION}" in read_text("README.md")
    assert f"## [{RELEASE_VERSION}] - 2026-07-18" in read_text("CHANGELOG.md")
    assert read_text("docs/RELEASE_NOTES_0.1.0.md").startswith(
        f"# EchoMind {RELEASE_VERSION} 发布说明\n"
    )


def test_release_community_files_exist_and_no_license_decision_is_pending() -> None:
    required = [
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "CHANGELOG.md",
        "docs/RELEASE_CHECKLIST.md",
        "docs/RELEASE_NOTES_0.1.0.md",
        "docs/THIRD_PARTY_LICENSES.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
    ]
    assert all((REPOSITORY_ROOT / item).is_file() for item in required)

    documentation = "\n".join(
        read_text(item)
        for item in ["README.md", "docs/DECISIONS.md", "docs/ROADMAP.md", "docs/MVP_AUDIT.md"]
    )
    forbidden_pending_statements = [
        "仓库尚未选择开源许可证",
        "项目开源许可证。",
        "OWNER_DECISION_REQUIRED：1（开源许可证）",
        "下一步：项目所有者选择许可证",
    ]
    assert all(statement not in documentation for statement in forbidden_pending_statements)
    assert "Apache-2.0" in documentation
    assert "Copyright 2026 杨锦辰" in documentation
