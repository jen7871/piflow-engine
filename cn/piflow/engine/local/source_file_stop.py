from __future__ import annotations

from pathlib import Path
from typing import Any

from cn.piflow.core.artifact import FileArtifact
from cn.piflow.core.runtime_context import JobContext, ProcessContext
from cn.piflow.core.stop import ConfigurableStop
from cn.piflow.core.stream import JobInputStream, JobOutputStream
from cn.piflow.engine.local.constants import RUNNER_CONTEXT_WORKSPACE_ROOT


OUTPUT_PORT = "output"


class SourceFileStop(ConfigurableStop):
    author_email = ""
    description = "Local file source stop."
    inport_list: list[str] = []
    outport_list = [OUTPUT_PORT]
    is_data_source = True

    def __init__(self) -> None:
        super().__init__()
        self.file_path = ""
        self._workspace_root: Path | None = None

    def set_properties(self, properties: dict[str, Any]) -> None:
        raw_path = properties.get("file_path", "")
        if not isinstance(raw_path, str):
            raise TypeError("source file property 'file_path' must be a string path")
        self.file_path = raw_path

    def initialize(self, ctx: ProcessContext) -> None:
        if not self.file_path:
            raise ValueError("source file stop requires property 'file_path'")
        workspace_root = ctx.get(RUNNER_CONTEXT_WORKSPACE_ROOT, None)
        if workspace_root:
            self._workspace_root = Path(str(workspace_root)).expanduser().resolve()
        path = self._resolve_source_path()
        if not path.exists():
            raise FileNotFoundError(f"source file not found: {path}")
        if not path.is_file():
            raise ValueError(f"source path is not a file: {path}")
        self.file_path = str(path)

    def perform(
        self,
        inputs: JobInputStream,
        outputs: JobOutputStream,
        ctx: JobContext,
    ) -> None:
        outputs.write(FileArtifact(path=self.file_path), OUTPUT_PORT)

    def _resolve_source_path(self) -> Path:
        raw_path = self.file_path.strip()
        if self._workspace_root is not None:
            relative_path = raw_path.lstrip("/")
            return (self._workspace_root / relative_path).resolve()
        return Path(raw_path).expanduser().resolve()
