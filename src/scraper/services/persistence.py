from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class PersistenceService:
    """
    Run-scoped persistence layer.

    Default behavior:
    - each invocation writes into a new run directory
    - JSONL appends only within that run
    - CSV files are written inside that run directory

    Heavy raw payloads should only be written through the optional debug helpers.
    """

    def __init__(
        self,
        data_dir: str | Path = "data",
        run_id: str | None = None,
        save_debug_payloads: bool = False,
        base_dir: str | Path | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.save_debug_payloads = save_debug_payloads

        self.run_id = run_id or self._generate_run_id()

        if base_dir is None:
            self.run_dir = self.data_dir / "runs" / self.run_id
        else:
            self.run_dir = Path(base_dir) / self.run_id

        self.raw_dir = self.run_dir / "raw"
        self.normalized_dir = self.run_dir / "normalized"
        self.analysis_dir = self.run_dir / "analysis"
        self.debug_dir = self.run_dir / "debug_payloads"

        self._ensure_directories()

    @property
    def output_dir(self) -> Path:
        """Convenience alias for the run directory."""
        return self.run_dir

    def _generate_run_id(self) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        short_uuid = uuid4().hex[:8]
        return f"{timestamp}_{short_uuid}"

    def _ensure_directories(self) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

        if self.save_debug_payloads:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

    def append_jsonl_record(self, path: str | Path, record: Any) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        serializable = self._to_serializable(record)

        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(serializable, ensure_ascii=False) + "\n")

    def write_csv_rows(
        self,
        path: str | Path,
        rows: list[Any],
        fieldnames: list[str] | None = None,
    ) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not rows:
            if fieldnames is None:
                raise ValueError("Cannot write empty CSV without fieldnames.")
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            return

        dict_rows = [self._to_flat_dict(row) for row in rows]

        if fieldnames is None:
            fieldnames = list(dict_rows[0].keys())

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(dict_rows)

    def persist_sampling_run(self, record: Any) -> None:
        self.append_jsonl_record(self.raw_dir / "sampling_runs.jsonl", record)

    def persist_processed_household(self, record: Any) -> None:
        self.append_jsonl_record(self.raw_dir / "processed_households.jsonl", record)

    def persist_participant_collection(self, record: Any) -> None:
        self.append_jsonl_record(self.raw_dir / "participant_collection.jsonl", record)

    def persist_normalized_participant(self, record: Any) -> None:
        self.append_jsonl_record(self.normalized_dir / "participants.jsonl", record)

    def write_analysis_rows_csv(self, rows: list[Any]) -> None:
        self.write_csv_rows(self.analysis_dir / "analysis_rows.csv", rows)

    def append_analysis_row_jsonl(self, record: Any) -> None:
        self.append_jsonl_record(self.analysis_dir / "analysis_rows.jsonl", record)

    def maybe_write_debug_text(
        self,
        relative_name: str,
        text: str,
    ) -> None:
        if not self.save_debug_payloads:
            return

        path = self.debug_dir / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _to_serializable(self, obj: Any) -> Any:
        if is_dataclass(obj):
            return self._to_serializable(asdict(obj))

        if isinstance(obj, dict):
            return {str(k): self._to_serializable(v) for k, v in obj.items()}

        if isinstance(obj, list):
            return [self._to_serializable(v) for v in obj]

        if isinstance(obj, tuple):
            return [self._to_serializable(v) for v in obj]

        if isinstance(obj, Path):
            return str(obj)

        return obj

    def _to_flat_dict(self, obj: Any) -> dict[str, Any]:
        base = self._to_serializable(obj)

        if not isinstance(base, dict):
            raise TypeError("CSV rows must serialize to dictionaries.")

        flat: dict[str, Any] = {}
        for key, value in base.items():
            if isinstance(value, (dict, list)):
                flat[key] = json.dumps(value, ensure_ascii=False)
            else:
                flat[key] = value

        return flat