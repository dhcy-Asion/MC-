"""Read-only check: pinned images cover the real MC catalog one-to-one."""
import argparse
import json
import urllib.request
from prepare_item_icons import CACHE, CONFIG, ROOT, sha256, validate_png


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", default="http://127.0.0.1:8766")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    manifest = json.loads((CACHE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == config["minecraftVersion"]
    assert manifest["commit"] == config["commit"]
    assert manifest["archiveSha256"] == config["archiveSha256"]
    with urllib.request.urlopen(args.authority + "/api/catalog", timeout=10) as response:
        catalog = json.load(response)
    rows = manifest["items"]
    by_id = {row["id"]: row for row in rows}
    assert len(rows) == len(by_id) == len(catalog["items"]) == config["iconCount"]
    assert set(by_id) == {item["id"] for item in catalog["items"]}
    assert len({row["file"] for row in rows}) == len(rows)
    for item in catalog["items"]:
        row = by_id[item["id"]]
        name = item["id"].removeprefix("minecraft:")
        assert row["file"] == name + ".png"
        assert row["sourceFile"] == config["typePreviews"].get(name, name + ".png")
        assert row["typePreview"] == (name in config["typePreviews"])
        png = (CACHE / row["file"]).read_bytes()
        assert sha256(png) == row["sha256"]
        assert validate_png(png) == (128, 128)
    # Detect damaged/truncated images before they reach the native loader.
    sample = (CACHE / "oak_log.png").read_bytes()
    for damaged in (sample[:-1], b"not png", sample[:32] + bytes([sample[32] ^ 1]) + sample[33:]):
        try:
            validate_png(damaged)
        except ValueError:
            pass
        else:
            raise AssertionError("A damaged PNG was accepted")
    report = {"passed": True, "minecraftVersion": config["minecraftVersion"],
              "catalogItems": len(rows), "exactIdFiles": len(rows),
              "directRenders": len(rows) - len(config["typePreviews"]),
              "componentTypePreviews": config["typePreviews"],
              "archiveSha256": config["archiveSha256"],
              "sourceCommit": config["commit"], "dimensions": [128, 128],
              "pngValidation": "CRC, complete RGBA stream, rejected corruption/truncation",
              "inventoryMutations": 0, "gameRendering": "not verified by this check"}
    (ROOT / "runtime/item-icons-check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
