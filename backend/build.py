"""Hatch build hook for repository-root release notices."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.config import BuilderConfig
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface[BuilderConfig]):
    """Include the canonical root LICENSE and NOTICE in both distribution types."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        del version
        project_root = Path(self.root)
        force_include = build_data.setdefault("force_include", {})
        distribution_name = self.metadata.name.replace("-", "_")
        if self.target_name == "wheel":
            destination_root = f"{distribution_name}-{self.metadata.version}.dist-info/licenses"
        else:
            destination_root = ""

        for filename in ("LICENSE", "NOTICE"):
            packaged_source = project_root / filename
            if self.target_name == "wheel" and packaged_source.is_file():
                # Hatch automatically places license files found beside pyproject.toml.
                continue
            candidates = (packaged_source, project_root.parent / filename)
            source = next((path for path in candidates if path.is_file()), None)
            if source is None:
                raise FileNotFoundError(f"Required release file is missing: {filename}")
            destination = f"{destination_root}/{filename}" if destination_root else filename
            force_include[str(source)] = destination
