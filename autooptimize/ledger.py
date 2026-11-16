"""Append-only JSONL ledger. Each record is flushed and fsynced before the call returns."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class Ledger:
    def __init__(self, path, run_id, contract_hash):
        self.path = Path(path)
        self.run_id = run_id
        self.contract_hash = contract_hash
        self.lines = len(read(self.path)) if self.path.exists() else 0

    def append(self, kind, **fields):
        """Write one record and return its line number (1-based)."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "run": self.run_id,
            "contract": self.contract_hash,
            "kind": kind,
            **fields,
        }
        line = json.dumps(record, sort_keys=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.lines += 1
        return self.lines


def read(path):
    """Return [(line_number, record)]. A broken line raises, it is never skipped."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if line.strip():
                rows.append((number, json.loads(line)))
    return rows
