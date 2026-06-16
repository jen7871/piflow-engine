from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from cn.piflow.core.artifact import FileArtifact
from cn.piflow.core.runtime_context import JobContext, ProcessContext
from cn.piflow.core.runtime_keys import RUN_CONTEXT_FINAL_OUTPUT_PATH
from cn.piflow.core.stop import ConfigurableStop
from cn.piflow.core.stream import DEFAULT_PORT, JobInputStream, JobOutputStream
from cn.piflow.engine.local.constants import RUNNER_CONTEXT_WORKSPACE_ROOT


class FileSaveStop(ConfigurableStop):
    author_email = ""
    description = "Save one input file to an absolute path."
    inport_list = [DEFAULT_PORT]
    outport_list = [DEFAULT_PORT]

    def __init__(self) -> None:
        super().__init__()
        self.absolute_path = ""
        self.overwrite = False
        self._workspace_root: Path | None = None

    def set_properties(self, properties: dict[str, Any]) -> None:
        raw_path = (
            properties.get("absolute_path")
            or properties.get("path")
            or properties.get("output_path")
            or ""
        )
        if not isinstance(raw_path, str):
            raise TypeError("file save absolute_path must be a string")

        self.absolute_path = raw_path
        self.overwrite = _parse_bool(properties.get("overwrite", False))

    def initialize(self, ctx: ProcessContext) -> None:
        if not self.absolute_path:
            raise ValueError("file save absolute_path must not be empty")
        workspace_root = ctx.get(RUNNER_CONTEXT_WORKSPACE_ROOT, None)
        if workspace_root:
            self._workspace_root = Path(str(workspace_root)).expanduser().resolve()
        destination = self._resolve_destination()
        if not destination.is_absolute():
            raise ValueError(f"file save path must be absolute: {self.absolute_path}")

    def perform(
        self,
        inputs: JobInputStream,
        outputs: JobOutputStream,
        ctx: JobContext,
    ) -> None:
        source_path = self._read_input_file(inputs)
        destination = self._resolve_destination()

        if destination.exists() and not self.overwrite:
            raise FileExistsError(f"target file already exists: {destination}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)

        ctx.put(RUN_CONTEXT_FINAL_OUTPUT_PATH, str(destination))
        saved_artifact = FileArtifact(path=str(destination))
        outputs.write(saved_artifact)

    def _read_input_file(self, inputs: JobInputStream) -> Path:
        if inputs.contains():
            artifact = inputs.read()
        else:
            ports = inputs.ports()
            if len(ports) != 1:
                raise ValueError(
                    f"file save stop requires exactly one input, got ports={ports}"
                )
            artifact = inputs.read(ports[0])

        path = getattr(artifact, "path", "") or str(getattr(artifact, "value", ""))
        if not path:
            raise ValueError("file save input artifact has no file path")

        source_path = Path(path).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"file save input file not found: {source_path}")
        if not source_path.is_file():
            raise ValueError(f"file save input path is not a file: {source_path}")

        return source_path

    def _resolve_destination(self) -> Path:
        raw_path = self.absolute_path
        if self._workspace_root is not None and (
            raw_path == "/workspace" or raw_path.startswith("/workspace/")
        ):
            relative_path = raw_path.removeprefix("/workspace").lstrip("/")
            return (self._workspace_root / relative_path).resolve()
        return Path(raw_path).expanduser().resolve()


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n", ""}:
            return False
    raise TypeError("overwrite must be a boolean or boolean-like string")
