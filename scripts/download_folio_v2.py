"""Download FOLIO v2 dataset from HuggingFace to data/folio/data/v2/."""

from pathlib import Path

from datasets import load_dataset

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "folio" / "data" / "v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ds = load_dataset("yale-nlp/FOLIO")

for split in ds:
    out = OUT_DIR / f"folio_v2_{split}.jsonl"
    ds[split].to_json(out)
    print(f"{split}: {len(ds[split])} examples -> {out}")
