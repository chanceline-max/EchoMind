"""Build and inspect ephemeral backend release artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.1.0"
EXPECTED_LICENSE = "Apache-2.0"
EXPECTED_AUTHOR = "杨锦辰"


def inspect_wheel(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = BytesParser(policy=policy.default).parsebytes(archive.read(metadata_name))
        license_files = sorted(name for name in names if ".dist-info/licenses/" in name)

    assert metadata["Version"] == EXPECTED_VERSION
    assert metadata["License-Expression"] == EXPECTED_LICENSE
    assert metadata["Author"] == EXPECTED_AUTHOR
    expected_license_root = f"echomind-{EXPECTED_VERSION}.dist-info/licenses"
    assert license_files == [
        f"{expected_license_root}/LICENSE",
        f"{expected_license_root}/NOTICE",
    ]
    return {
        "filename": path.name,
        "file_count": len(names),
        "license_expression": metadata["License-Expression"],
        "author": metadata["Author"],
        "license_files": license_files,
    }


def inspect_sdist(path: Path) -> dict[str, Any]:
    with tarfile.open(path, mode="r:gz") as archive:
        names = archive.getnames()
    license_files = sorted(
        name for name in names if name.endswith("/LICENSE") or name.endswith("/NOTICE")
    )
    assert any(name.endswith("/LICENSE") for name in license_files)
    assert any(name.endswith("/NOTICE") for name in license_files)
    return {"filename": path.name, "file_count": len(names), "license_files": license_files}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="echomind-stage12-build-") as directory:
        output_directory = Path(directory) / "from-sdist"
        direct_wheel_directory = Path(directory) / "direct-wheel"
        output_directory.mkdir()
        direct_wheel_directory.mkdir()
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "backend",
                "--outdir",
                str(output_directory),
            ],
            cwd=REPOSITORY_ROOT,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "backend",
                "--outdir",
                str(direct_wheel_directory),
            ],
            cwd=REPOSITORY_ROOT,
            check=True,
        )
        wheels = list(output_directory.glob("*.whl"))
        sdists = list(output_directory.glob("*.tar.gz"))
        direct_wheels = list(direct_wheel_directory.glob("*.whl"))
        assert len(wheels) == len(sdists) == len(direct_wheels) == 1
        report = {
            "result": "pass",
            "wheel_from_sdist": inspect_wheel(wheels[0]),
            "wheel_direct": inspect_wheel(direct_wheels[0]),
            "sdist": inspect_sdist(sdists[0]),
        }
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
