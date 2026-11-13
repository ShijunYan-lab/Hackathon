"""Zero-dependency PNG dimension/layout check for A & D sprite sheets.

Run from repository root: python game/tests/check_spritesheets.py
This checks dimensions, not animation appearance or Godot parser validity.
"""
from pathlib import Path
import json
import struct

SPRITES = Path(__file__).resolve().parents[1] / "actors" / "assets" / "sprites"
MANIFEST = SPRITES.parent / "sprite_sheet_layouts.json"
ACTIONS = ("idle", "run", "attack", "hurt", "death", "dodge", "sprint")


def frame_size_for_dimensions(width: int, height: int, override=None):
    if override:
        return tuple(override)
    if width % 48 == 0 and height % 64 == 0:
        return (48, 64)
    if width % 32 == 0 and height % 32 == 0:
        return (32, 32)
    return None


def png_dimensions(path: Path):
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"Bad PNG header: {path}")
    return struct.unpack(">II", data[16:24])


def check_sheet(width: int, height: int, framesize, defaults, skin_rules):
    fw, fh = framesize
    assert fw > 0 and fh > 0 and width % fw == 0 and height % fh == 0
    cols, rows = width // fw, height // fh
    result = {}
    for name in ACTIONS:
        rule = dict(defaults.get(name, {}))
        rule.update(skin_rules.get(name, {}))
        row = int(rule.get("row", 0))
        if row < 0 or row >= rows:
            row = 1 if name in ("dodge", "sprint") and rows > 1 else 0
        count = max(1, min(cols, int(rule.get("frames", 4))))
        assert count * fw <= width and (row + 1) * fh <= height
        result[name] = (row, count)
    return result


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    defaults = manifest["animations"]
    skins = manifest.get("skins", {})
    count = 0
    for image in sorted(SPRITES.glob("*.png")):
        width, height = png_dimensions(image)
        config = skins.get(image.stem, {})
        framesize = frame_size_for_dimensions(width, height, config.get("frame_size"))
        if framesize is None:
            raise ValueError(f"{image.name}: sheet not divisible by 48x64 or 32x32: {width}x{height}")
        actions = check_sheet(width, height, framesize, defaults, config.get("animations", {}))
        print(f"OK {image.name:<20} {width}x{height}, frame {framesize[0]}x{framesize[1]}, {len(actions)} actions")
        count += 1
    target = check_sheet(192, 448, (48, 64), defaults, {})
    assert target["sprint"] == (6, 4)
    assert target["dodge"] == (5, 4)
    print(f"PASS: {count} existing sprites plus synthetic 192x448 layout validated")


if __name__ == "__main__":
    main()
