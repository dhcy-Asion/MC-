"""Export the actual vanilla 1.21.1 block registry and legal states locally.

Runs the pinned client's data-report entry point in an isolated build directory.
It does not start a client/server world or contact the running authority service.
Registry coverage is not native rendering, collision or item-use coverage.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

import build_steve_asset as assets

ROOT = assets.ROOT
MAIN_CLASS = "net/minecraft/data/Main.class"
MAIN_SHA256 = "86a127ec5dc73de209b18c7dd8eec46041e5c9a9ab0f088b100950ea25544bf7"
BLOCKS_SHA256 = "0dde7f869588905763ea6ff2e7e01bec1db740a58d27477fd27c2f07fb029f73"
DEFAULT_OUTPUT = ROOT / "build/block-registry-1.21.1"
OUTPUT_NAMES = ("reports/blocks.json", "reports/registries.json", "generator.log", "block-registry.json")


def strict_json(data: bytes) -> dict:
    if not data or len(data) > 16 * 1024 * 1024:
        raise ValueError("Registry report exceeds bounded size")
    def pairs(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise ValueError("Duplicate registry JSON key")
            out[key] = value
        return out
    value = json.loads(data, object_pairs_hook=pairs,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if not isinstance(value, dict):
        raise ValueError("Registry report must be an object")
    return value


def audit_registry(blocks: dict, registries: dict, archive: zipfile.ZipFile) -> dict:
    entries = registries.get("minecraft:block", {}).get("entries", {})
    if not blocks or len(blocks) > 4096 or set(entries) != set(blocks):
        raise ValueError("Block report and actual registry IDs disagree")
    prefix = "assets/minecraft/blockstates/"
    names = [name for name in archive.namelist() if name.startswith(prefix) and name.endswith(".json")]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate blockstate resource entries")
    resource_ids = {"minecraft:" + name[len(prefix):-5]: name for name in names}
    missing = sorted(set(blocks) - resource_ids.keys())
    if missing:
        raise ValueError("Registered blocks lack client resources: " + ", ".join(missing))
    protocol_ids, state_ids, rows = set(), set(), []
    for block_id in sorted(blocks):
        block = blocks[block_id]
        protocol = entries[block_id].get("protocol_id")
        if type(protocol) is not int or protocol < 0 or protocol in protocol_ids:
            raise ValueError("Invalid or duplicate block protocol ID")
        protocol_ids.add(protocol)
        properties = block.get("properties", {})
        if not isinstance(properties, dict) or len(properties) > 32:
            raise ValueError("Invalid block property domains")
        for key, values in properties.items():
            if (not isinstance(key, str) or not key or not isinstance(values, list) or not values
                    or any(not isinstance(v, str) or not v for v in values)
                    or len(values) != len(set(values))):
                raise ValueError("Invalid or duplicate property values")
        states = block.get("states")
        expected = math.prod(len(values) for values in properties.values())
        if not isinstance(states, list) or not 1 <= len(states) <= 65536 or len(states) != expected:
            raise ValueError("State enumeration does not cover the property product")
        signatures, defaults = set(), []
        for state in states:
            state_id, values = state.get("id"), state.get("properties", {})
            if type(state_id) is not int or state_id < 0 or state_id in state_ids:
                raise ValueError("Invalid or duplicate global block-state ID")
            state_ids.add(state_id)
            if (not isinstance(values, dict) or set(values) != set(properties)
                    or any(value not in properties[key] for key, value in values.items())):
                raise ValueError("State uses an undeclared property or value")
            signature = tuple(sorted(values.items()))
            if signature in signatures:
                raise ValueError("Duplicate block-state property tuple")
            signatures.add(signature)
            if type(state.get("default", False)) is not bool:
                raise ValueError("Default-state marker must be boolean")
            if state.get("default", False):
                defaults.append(state_id)
        if len(defaults) != 1:
            raise ValueError("Block needs exactly one default state")
        resource = resource_ids[block_id]
        rows.append({"id": block_id, "registryId": protocol, "defaultStateId": defaults[0],
                     "properties": properties, "states": states,
                     "blockstateResource": resource,
                     "blockstateResourceSha256": assets.digest(archive.read(resource))})
    if protocol_ids != set(range(len(blocks))) or state_ids != set(range(len(state_ids))):
        raise ValueError("Vanilla registry IDs are not contiguous from zero")
    return {"registeredBlockCount": len(blocks), "legalStateCount": len(state_ids),
            "resourceFileCount": len(resource_ids), "unregisteredResourceIds": sorted(resource_ids.keys() - blocks.keys()),
            "missingResourceIds": missing, "blocks": rows}


def preflight(output: Path, names: list[str] | tuple[str, ...], inputs: tuple[Path, ...] = ()) -> Path:
    output = assets.output_directory(output)
    sources = tuple(source.resolve() for source in inputs)
    for name in names:
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Output path escapes registry directory")
        for path in (output / name, output / (name + ".tmp")):
            assets.output_directory(path)
            for source in sources:
                if (path.resolve() == source or path.exists() and source.exists() and path.samefile(source)):
                    raise ValueError("Registry output or temporary path conflicts with a generator input")
            if path.exists() and (not path.is_file() or str(path).endswith(".tmp")):
                raise ValueError("Registry output or temporary path is occupied")
    return output


def publish(output: Path, files: dict[str, bytes], inputs: tuple[Path, ...] = ()) -> None:
    output = preflight(output, list(files), inputs)
    for name, data in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = output / (name + ".tmp")
        assets.output_directory(target)
        assets.output_directory(temporary)
        created = False
        try:
            with temporary.open("xb") as stream:
                created = True
                stream.write(data)
            temporary.replace(target)
        finally:
            if created and temporary.exists():
                temporary.unlink()


def build(output: Path, client: Path | None = None, download: bool = False,
          java_home: Path | None = None) -> dict:
    output = preflight(output, OUTPUT_NAMES)
    config = assets.read_config()
    client, jars = assets.dependencies(config, client, download)
    # The isolated generator uses a different cwd; preserve the caller's
    # interpretation of --client, dependencies and --java-home before launch.
    client, jars = client.resolve(), [path.resolve() for path in jars]
    java, _ = assets.java_tools(java_home.resolve() if java_home else None)
    java = java.resolve()
    inputs = (client, *jars, java)
    preflight(output, OUTPUT_NAMES, inputs)
    assets.checked_bytes(client, config["client"]["sha256"], "sha256")
    with zipfile.ZipFile(client) as archive:
        if assets.digest(archive.read(MAIN_CLASS)) != MAIN_SHA256:
            raise ValueError("Vanilla data generator fingerprint mismatch")
    snapshots = {path: assets.digest(path.read_bytes()) for path in [client, *jars]}
    with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="block-registry-generator-") as temp:
        stage = assets.output_directory(Path(temp))
        result = subprocess.run([str(java), "-Djava.awt.headless=true", "-cp",
            os.pathsep.join(str(path) for path in [client, *jars]), "net.minecraft.data.Main",
            "--reports", "--output", str(stage / "generated")], cwd=stage,
            capture_output=True, text=True, timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise ValueError("Vanilla report generator failed: " + (result.stdout + result.stderr)[-4000:])
        raw = {name: (stage / "generated/reports" / name).read_bytes()
               for name in ("blocks.json", "registries.json")}
        if assets.digest(raw["blocks.json"]) != BLOCKS_SHA256:
            raise ValueError("Vanilla 1.21.1 block report differs from the reviewed generator output")
        with zipfile.ZipFile(client) as archive:
            coverage = audit_registry(strict_json(raw["blocks.json"]), strict_json(raw["registries.json"]), archive)
    if any(assets.digest(path.read_bytes()) != digest for path, digest in snapshots.items()):
        raise ValueError("Generator inputs changed during export")
    report = {"schemaVersion": 1, "minecraftVersion": config["minecraftVersion"],
        "clientSha256": snapshots[client], "generatorClassSha256": MAIN_SHA256,
        "generator": "net.minecraft.data.Main --reports", "libraries": {p.name: snapshots[p] for p in jars},
        "sourceReports": {name: assets.digest(data) for name, data in raw.items()}, **coverage,
        "integration": {"nativeModelsMapped": False, "nativeRenderingVerified": False,
                        "nativeCollisionVerified": False, "allItemUsesImplemented": False},
        "limitations": ["Vanilla registry and legal states only; this is not the Fabric authority's runtime registry.",
                        "Client resource presence does not prove model selection, special rendering, transparency, animation or collision.",
                        "Generated reports and game-derived state data remain in ignored build; no world is started or changed."]}
    files = {"reports/" + name: data for name, data in raw.items()}
    files["generator.log"] = (result.stdout + result.stderr).encode("utf-8")
    files["block-registry.json"] = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    publish(output, files, inputs)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--client", type=Path)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--java-home", type=Path)
    args = parser.parse_args()
    try:
        report = build(args.output, args.client, args.download, args.java_home)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"Block registry export stopped: {error}") from error
    print(json.dumps({key: report[key] for key in ("registeredBlockCount", "legalStateCount", "resourceFileCount",
                     "unregisteredResourceIds", "missingResourceIds", "integration")}, indent=2))


if __name__ == "__main__":
    main()
