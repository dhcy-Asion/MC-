"""Prepare pinned MC 1.21.1 type previews locally; never distribute game assets.

Only Python's standard library is required. Every plain item has its own image;
seven component-dependent types use an explicitly listed preview of that SAME
item type. Inventory names/counts/components still come exclusively from MC.
"""
from pathlib import Path
import hashlib
import json
import re
import struct
import urllib.request
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/item-icons.json"
CACHE = ROOT / "downloads/minecraft-icons-1.21.1"
ARCHIVE = ROOT / "downloads/minecraft-icons-1.21.1.zip"
SIMPLE_NAME = re.compile(r"[a-z0-9_]+\.png")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_png(data):
    """Validate PNG framing, all CRCs and a complete RGBA scanline stream."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid PNG signature")
    pos, compressed, dimensions, ended = 8, bytearray(), None, False
    while pos < len(data):
        if pos + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4:pos + 8]
        end = pos + 8 + length
        if end + 4 > len(data) or zlib.crc32(data[pos + 4:end]) != struct.unpack_from(">I", data, end)[0]:
            raise ValueError("PNG chunk length/CRC mismatch")
        chunk = data[pos + 8:end]
        if kind == b"IHDR":
            if dimensions is not None or length != 13 or pos != 8:
                raise ValueError("Invalid PNG header")
            w, h, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunk)
            if not (w == h == 128 and depth == 8 and color == 6 and compression == filtering == interlace == 0):
                raise ValueError("Expected 128x128 non-interlaced RGBA8 PNG")
            dimensions = (w, h)
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            if length or end + 4 != len(data):
                raise ValueError("Invalid PNG end")
            ended = True
        pos = end + 4
    if not dimensions or not ended:
        raise ValueError("Incomplete PNG")
    decoder = zlib.decompressobj()
    expected = dimensions[1] * (dimensions[0] * 4 + 1)
    pixels = decoder.decompress(compressed, expected + 1)
    if len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("Invalid PNG image stream")
    stride = dimensions[0] * 4 + 1
    if any(pixels[i] > 4 for i in range(0, expected, stride)):
        raise ValueError("Invalid PNG scanline filter")
    return dimensions


def prepare():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    if ARCHIVE.exists():
        data = ARCHIVE.read_bytes()
    else:
        print("Downloading pinned Minecraft item previews...", flush=True)
        with urllib.request.urlopen(config["archiveUrl"], timeout=40) as response:
            data = response.read(config["archiveBytes"] + 1)
        if len(data) != config["archiveBytes"] or sha256(data) != config["archiveSha256"]:
            raise ValueError("Downloaded icon archive hash/size mismatch")
        temporary = ARCHIVE.with_suffix(".zip.part")
        temporary.write_bytes(data)
        temporary.replace(ARCHIVE)
    if len(data) != config["archiveBytes"] or sha256(data) != config["archiveSha256"]:
        raise ValueError("Icon archive changed; retained. Inspect before removing/re-downloading.")

    prefix = config["minecraftVersion"] + "/"
    files = {}
    with zipfile.ZipFile(ARCHIVE) as archive:
        manifest = json.loads(archive.read(prefix + "manifest.json"))
        if manifest["version"] != config["minecraftVersion"]:
            raise ValueError("Icon version mismatch")
        names = manifest["images"]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate icon names")
        sources = {name[:-4]: name for name in names if SIMPLE_NAME.fullmatch(name) and "__" not in name and name != "air.png"}
        for item, source in config["typePreviews"].items():
            if item in sources or source not in names or not source.startswith(item + "__"):
                raise ValueError("Invalid component preview mapping: " + item)
            sources[item] = source
        if len(sources) != config["iconCount"]:
            raise ValueError("Unexpected icon coverage")
        # Read and validate the entire plan before writing any extracted images.
        for item, source in sorted(sources.items()):
            if not SIMPLE_NAME.fullmatch(item + ".png"):
                raise ValueError("Invalid item filename")
            png = archive.read(prefix + source)
            validate_png(png)
            files[item + ".png"] = (png, source)

    CACHE.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, (png, source) in files.items():
        target = CACHE / name
        if target.exists() and target.read_bytes() != png:
            raise ValueError("Changed cached image retained: " + str(target))
        if not target.exists():
            target.write_bytes(png)
        entries.append({"id": "minecraft:" + name[:-4], "file": name, "sourceFile": source,
                        "sha256": sha256(png), "typePreview": name[:-4] in config["typePreviews"]})
    result = {"version": config["minecraftVersion"], "source": config["source"],
              "commit": config["commit"], "archiveSha256": config["archiveSha256"], "items": entries}
    (CACHE / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(entries)} validated item images in {CACHE}")
    return result


if __name__ == "__main__":
    prepare()
