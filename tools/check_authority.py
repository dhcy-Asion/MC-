"""Validate installed MC using reads and rejected requests only.
Positive mutations are covered by check_inventory.py in an isolated world.
"""
from pathlib import Path
import hashlib
import json
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def call(path="state", body=None):
    req = Request("http://127.0.0.1:8766/api/" + path,
                  data=None if body is None else json.dumps(body).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=8) as response:
        return json.load(response)


def main():
    initial = call()
    assert initial["engine"] == "Minecraft Java 1.21.1"
    catalog = call("catalog")["items"]
    by_id = {row["id"]: row for row in catalog}
    assert len(by_id) == len(catalog) == 1332
    language = ROOT / "downloads/minecraft-lang-1.21.1-zh_cn.json"
    assert hashlib.sha1(language.read_bytes()).hexdigest() == "f87510f4509890eaf176e0de1430f6bb326a6800"
    translations = json.loads(language.read_text(encoding="utf-8"))
    assert all(row["name"] == translations[row["translationKey"]] for row in catalog)
    assert len(initial["slots"]) == 36
    assert by_id["minecraft:raw_copper"]["name"] == "粗铜"
    requests = [
        ("craft", {"recipe": "minecraft:oak_planks"}),
        ("add-item", {"item": "minecraft:does_not_exist", "count": 1}),
        ("add-item", {"item": "minecraft:air", "count": 1}),
        ("add-item", {"item": "minecraft:dirt", "count": 0}),
        ("add-item", {"item": "minecraft:dirt", "count": 1.5}),
        ("add-item", {"item": "minecraft:dirt", "count": 1, "player": "unknown"}),
        ("add-item", {"item": "音乐唱片", "count": 1}),
    ]
    for path, body in requests:
        try:
            call(path, {"operationId": str(uuid.uuid4()), **body})
        except HTTPError as error:
            assert error.code == 400, (path, error.code)
        else:
            raise AssertionError(f"Invalid {path} was accepted")
        assert call() == initial, "Rejected request changed user state"
    evidence = {"result": "passed", "mode": "production reads and rejected requests only",
                "catalogCount": len(catalog), "officialNameMatches": len(catalog),
                "rejections": len(requests), "userStateUnchanged": call() == initial}
    (ROOT / "runtime/authority-checks.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
