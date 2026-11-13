"""Check the untouched v1 starter files against their recorded original hashes."""
import hashlib
import json
from pathlib import Path

def check() -> None:
    root = Path(__file__).resolve().parents[1]
    hashes = json.loads((root / "docs/ORIGINAL_FILE_HASHES.json").read_text(encoding="utf-8"))
    mismatches = [rel for rel, digest in hashes.items()
                  if not (root / rel).exists()
                  or hashlib.sha256((root / rel).read_bytes()).hexdigest() != digest]
    if mismatches:
        raise SystemExit("Changed/missing v1 files: " + ", ".join(mismatches))
    print(f"{len(hashes)} original starter files preserved byte-for-byte.")

if __name__ == "__main__":
    check()
