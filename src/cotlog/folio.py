"""FOLIO dataset loader."""

import json
from dataclasses import dataclass
from pathlib import Path

FOLIO_VALIDATION = Path(__file__).parent.parent.parent / "data" / "folio" / "data" / "v0.0" / "folio-validation.jsonl"
FOLIO_V2_VALIDATION = Path(__file__).parent.parent.parent / "data" / "folio" / "data" / "v2" / "folio_v2_validation.jsonl"


def _to_list(val: str | list[str]) -> list[str]:
    """Normalize a field that may be a newline-delimited string or a list."""
    if isinstance(val, list):
        return val
    return [s for s in val.split("\n") if s.strip()]


@dataclass
class FolioExample:
    premises: list[str]
    premises_fol: list[str]
    conclusion: str
    conclusion_fol: str
    label: str  # "True", "False", or "Uncertain"


def load_folio(path: Path = FOLIO_VALIDATION) -> list[FolioExample]:
    """Load FOLIO JSONL file into typed dataclass instances."""
    examples = []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            examples.append(FolioExample(
                premises=_to_list(d["premises"]),
                premises_fol=_to_list(d["premises-FOL"]),
                conclusion=d["conclusion"],
                conclusion_fol=d["conclusion-FOL"],
                label=d["label"],
            ))
    return examples
