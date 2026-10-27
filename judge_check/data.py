"""Loading cases and rubrics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


def load_cases(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    ids = [c["id"] for c in data["items"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids in dataset")
    return data


def load_rubric(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        rubric = yaml.safe_load(f)
    rubric["by_id"] = {c["id"]: c for c in rubric["criteria"]}
    return rubric


def fingerprint(obj) -> str:
    """Short stable hash, used to version prompts, rubrics and datasets in run records."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:12]
