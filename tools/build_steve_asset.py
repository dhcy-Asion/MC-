"""Export the actual classic Minecraft 1.21.1 Steve model to an ignored glTF package.

Uses a separate, offline Java process with the verified official client; never starts
Minecraft or reads/writes Crimson Desert. No native asset import or installation.
Run tools/prepare_environment.ps1 -SourceBuild and the MC build first for cached
dependencies, or pass --download to fetch hash-pinned official dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "steve-asset-1.21.1.json"
DEFAULT_OUTPUT = ROOT / "build" / "steve-1.21.1"
BASE_PARTS = ("head", "body", "right_arm", "left_arm", "right_leg", "left_leg")
OUTER_PARTS = {
    "hat": "head", "jacket": "body", "right_sleeve": "right_arm",
    "left_sleeve": "left_arm", "right_pants": "right_leg", "left_pants": "left_leg",
}


def digest(data: bytes, algorithm: str = "sha256") -> str:
    return hashlib.new(algorithm, data).hexdigest()


def canonical_digest(value: object) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def read_config() -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["schemaVersion"] != 1 or config["minecraftVersion"] != "1.21.1":
        raise ValueError("Unsupported Steve asset configuration")
    return config


def output_directory(path: Path) -> Path:
    # Check lexical containment before resolving: a linked build root must never
    # turn a public directory into an accepted asset output location.
    lexical = Path(os.path.abspath(path))
    build_root = Path(os.path.abspath(ROOT)) / "build"
    if not lexical.is_relative_to(build_root) or lexical == build_root:
        raise ValueError("Official/derived assets must stay in an ignored build subdirectory")
    # Do not follow an existing output junction/symlink into a different location.
    current = lexical
    while current != ROOT and current != current.parent:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("Asset output cannot contain symlinks or junctions")
        current = current.parent
    return lexical.resolve()


def checked_bytes(path: Path, expected: str, algorithm: str = "sha1") -> bytes:
    data = path.read_bytes()
    if digest(data, algorithm) != expected:
        raise ValueError(f"Checksum mismatch; existing file retained: {path}")
    return data


def obtain(cache: Path, source: dict, candidates: list[Path], download: bool) -> Path:
    if cache.exists():
        checked_bytes(cache, source["sha1"])
        return cache
    for candidate in candidates:
        if candidate.is_file() and digest(candidate.read_bytes(), "sha1") == source["sha1"]:
            return candidate
    if not download:
        raise FileNotFoundError(f"Missing verified dependency {cache.name}; prepare MC dependencies or use --download")
    url = source["url"]
    if not url.startswith(("https://piston-data.mojang.com/", "https://piston-meta.mojang.com/", "https://libraries.minecraft.net/")):
        raise ValueError("Dependency URL must be the fixed official Minecraft source")
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    if digest(data, "sha1") != source["sha1"] or ("size" in source and len(data) != source["size"]):
        raise ValueError(f"Downloaded dependency failed checksum: {cache.name}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    temp = cache.with_suffix(cache.suffix + ".tmp")
    temp.write_bytes(data)
    temp.replace(cache)
    return cache


def java_tools(java_home: Path | None) -> tuple[Path, Path]:
    suffix = ".exe" if os.name == "nt" else ""
    homes = [java_home] if java_home else sorted((ROOT / "downloads" / "jdk21").glob("*"))
    for home in homes:
        if home and (home / "bin" / f"javac{suffix}").is_file():
            return home / "bin" / f"java{suffix}", home / "bin" / f"javac{suffix}"
    javac = shutil.which("javac")
    java = shutil.which("java")
    if java_home or not java or not javac:
        raise FileNotFoundError("Java 21 JDK required; run tools/prepare_environment.ps1")
    return Path(java), Path(javac)


def dependencies(config: dict, client: Path | None, download: bool) -> tuple[Path, list[Path]]:
    cache = ROOT / "downloads" / "steve-1.21.1"
    gradle = Path(os.environ.get("GRADLE_USER_HOME", str(Path.home() / ".gradle-crimsonmc"))) / "caches"
    metadata_path = obtain(cache / "version.json", config["versionMetadata"], [], download)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata["id"] != "1.21.1" or metadata["downloads"]["client"] != {
        key: config["client"][key] for key in ("sha1", "size", "url")
    }:
        raise ValueError("Pinned version metadata does not describe the pinned client")
    if client:
        checked_bytes(client, config["client"]["sha1"])
    else:
        client = obtain(cache / "client.jar", config["client"],
                        [gradle / "fabric-loom" / "1.21.1" / "minecraft-client.jar"], download)
    checked_bytes(client, config["client"]["sha256"], "sha256")
    jars = []
    cached_jars = list((gradle / "modules-2" / "files-2.1").glob("*/*/*/*/*.jar"))
    # The model constructors need several codec dependencies. Read their fixed versions
    # from the official metadata; native libraries and platform-only launchers are unused.
    for library in metadata["libraries"]:
        source = library.get("downloads", {}).get("artifact")
        if not source or "natives-" in source["path"] or library.get("rules"):
            continue
        name = Path(source["path"]).name
        jars.append(obtain(cache / "libraries" / name, source,
                           [path for path in cached_jars if path.name == name], download))
    return client, jars


def verify_client(client: Path, config: dict) -> bytes:
    checked_bytes(client, config["client"]["sha256"], "sha256")
    with zipfile.ZipFile(client) as archive:
        for name, expected in config["sourceClasses"].items():
            if digest(archive.read(name)) != expected:
                raise ValueError(f"Minecraft class hash mismatch: {name}")
        skin = archive.read(config["skin"]["entry"])
    if digest(skin) != config["skin"]["sha256"]:
        raise ValueError("The official wide Steve skin failed verification")
    if skin[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", skin[16:24]) != (64, 64):
        raise ValueError("Unexpected official skin dimensions")
    return skin


def read_engine_geometry(output: Path, client: Path, jars: list[Path], java_home: Path | None, config: dict) -> dict:
    java, javac = java_tools(java_home)
    classes = output / "helper-classes"
    classes.mkdir(exist_ok=True)
    subprocess.run([str(javac), "--release", "21", "-d", str(classes), str(ROOT / "tools" / "SteveModelDump.java")], check=True,
                   capture_output=True, text=True)
    raw_path = output / "minecraft-model.json"
    classpath = os.pathsep.join(str(path) for path in [classes, client, *jars])
    subprocess.run([str(java), "-Djava.awt.headless=true", "-cp", classpath,
                    "local.crimsonmc.assets.SteveModelDump", str(raw_path)], check=True, capture_output=True, text=True)
    geometry = json.loads(raw_path.read_text(encoding="utf-8"))
    if canonical_digest(geometry) != config["geometryCanonicalSha256"]:
        raise ValueError("Engine geometry no longer matches the reviewed Minecraft model contract")
    return geometry


def convert_vector(vector: list[float], factor: float = 1 / 16) -> list[float]:
    # MC front = -Z and down = +Y. glTF here uses front = +Z and up = +Y.
    # Flipping two axes preserves handedness and quad winding. UVs remain top-origin.
    return [vector[0] * factor, -vector[1] * factor, -vector[2] * factor]


def export_gltf(geometry: dict, config: dict) -> tuple[dict, bytes]:
    by_name = {part["name"]: part for part in geometry["parts"]}
    if set(by_name) != set(BASE_PARTS) | set(OUTER_PARTS) | {"ear", "cloak"}:
        raise ValueError("Unexpected engine model parts")
    binary = bytearray()
    gltf = {
        "asset": {"version": "2.0", "generator": "CrimsonMC offline Steve asset exporter"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "SteveModel", "scale": [config["model"]["playerRendererScale"]] * 3, "children": []}],
        "meshes": [], "bufferViews": [], "accessors": [],
        "buffers": [{"uri": "steve.bin", "byteLength": 0}],
        "images": [{"uri": "steve.png"}], "textures": [{"source": 0, "sampler": 0}],
        "samplers": [{"magFilter": 9728, "minFilter": 9728, "wrapS": 33071, "wrapT": 33071}],
        "materials": [
            {"name": "Steve base skin", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0, "roughnessFactor": 1}},
            {"name": "Steve outer skin layer", "alphaMode": "MASK", "alphaCutoff": 0.1,
             "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0, "roughnessFactor": 1}},
        ],
        "extras": {"minecraftVersion": "1.21.1", "thinArms": False, "nativeGameIntegration": False,
                   "excludedMinecraftParts": ["cloak", "ear"], "coordinateSystem": "Y up, Steve faces +Z; feet at Y=0 in bind pose",
                   "baseHeightBeforeRendererScale": 2.0, "baseHeightAfterRendererScale": 1.875},
    }

    def accessor(values: list, components: int, code: str, kind: str, target: int | None = None) -> int:
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        flat = [element for row in values for element in row] if components > 1 else values
        binary.extend(struct.pack("<" + code * len(flat), *flat))
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset}
        if target:
            view["target"] = target
        gltf["bufferViews"].append(view)
        value = {"bufferView": len(gltf["bufferViews"]) - 1, "componentType": {"f": 5126, "H": 5123}[code],
                 "count": len(values), "type": kind}
        if kind == "VEC3" and target == 34962:
            value["min"] = [min(row[axis] for row in values) for axis in range(3)]
            value["max"] = [max(row[axis] for row in values) for axis in range(3)]
        gltf["accessors"].append(value)
        return len(gltf["accessors"]) - 1

    joints, bind_matrices = [], []
    feet = config["model"]["feetPixelY"] / config["model"]["pixelsPerModelMeter"]
    for name in BASE_PARTS:
        part = by_name[name]
        if part["rotation"] != [0, 0, 0] or part["scale"] != [1, 1, 1]:
            raise ValueError("Unexpected rest-pose model transform")
        pivot = convert_vector(part["pivot"])
        pivot[1] += feet
        joints.append(len(gltf["nodes"]))
        gltf["nodes"].append({"name": name + "_joint", "translation": pivot})
        bind_matrices.append([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -pivot[0], -pivot[1], -pivot[2], 1])
    gltf["skins"] = [{"name": "Minecraft classic rigid body parts", "skeleton": 0, "joints": joints,
                       "inverseBindMatrices": accessor(bind_matrices, 16, "f", "MAT4")}]
    for name in (*BASE_PARTS, *OUTER_PARTS):
        part = by_name[name]
        joint_name = OUTER_PARTS.get(name, name)
        if part["pivot"] != by_name[joint_name]["pivot"]:
            raise ValueError("Outer layer does not match its body-part pivot")
        joint = BASE_PARTS.index(joint_name)
        positions, normals, uvs, indices = [], [], [], []
        for cuboid in part["cuboids"]:
            for quad in cuboid["quads"]:
                start = len(positions)
                for vertex in quad["vertices"]:
                    position = convert_vector([vertex[axis] + part["pivot"][axis] for axis in range(3)])
                    position[1] += feet
                    positions.append(position)
                    normals.append(convert_vector(quad["normal"], 1))
                    uvs.append(vertex[3:5])
                indices.extend([start, start + 1, start + 2, start, start + 2, start + 3])
        attributes = {
            "POSITION": accessor(positions, 3, "f", "VEC3", 34962),
            "NORMAL": accessor(normals, 3, "f", "VEC3", 34962),
            "TEXCOORD_0": accessor(uvs, 2, "f", "VEC2", 34962),
            "JOINTS_0": accessor([[joint, 0, 0, 0]] * len(positions), 4, "H", "VEC4", 34962),
            "WEIGHTS_0": accessor([[1, 0, 0, 0]] * len(positions), 4, "f", "VEC4", 34962),
        }
        gltf["meshes"].append({"name": name, "primitives": [{"attributes": attributes,
            "indices": accessor(indices, 1, "H", "SCALAR", 34963), "material": int(name in OUTER_PARTS), "mode": 4}]})
        mesh_node = len(gltf["nodes"])
        gltf["nodes"].append({"name": name, "mesh": len(gltf["meshes"]) - 1, "skin": 0})
        # glTF ignores a skinned mesh node's transforms. Keep meshes at scene root;
        # the shared skeleton root carries the verified MC player-renderer scale.
        gltf["scenes"][0]["nodes"].append(mesh_node)
    gltf["nodes"][0]["children"] = joints
    gltf["buffers"][0]["byteLength"] = len(binary)
    return gltf, bytes(binary)


def build(output: Path, client: Path | None = None, download: bool = False, java_home: Path | None = None) -> dict:
    config = read_config()
    output = output_directory(output)
    client, jars = dependencies(config, client, download)
    skin = verify_client(client, config)
    output.mkdir(parents=True, exist_ok=True)
    geometry = read_engine_geometry(output, client, jars, java_home, config)
    gltf, binary = export_gltf(geometry, config)
    files = {"steve.gltf": (json.dumps(gltf, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
             "steve.bin": binary, "steve.png": skin}
    for name, data in files.items():
        temp = output / (name + ".tmp")
        temp.write_bytes(data)
        temp.replace(output / name)
    manifest = {
        "schemaVersion": 1, "minecraftVersion": "1.21.1", "clientSha256": config["client"]["sha256"],
        "geometryCanonicalSha256": canonical_digest(geometry), "configurationSha256": digest(CONFIG.read_bytes()),
        "exporterSha256": digest(Path(__file__).read_bytes()),
        "readerSha256": digest((ROOT / "tools" / "SteveModelDump.java").read_bytes()),
        "files": {name: digest(data) for name, data in files.items()}, "model": config["model"],
        "integration": config["integration"],
        "limitations": ["Six Minecraft rigid joints are not a Crimson Desert bone palette or retargeted animation.",
                        "Neutral bind pose only; no game/player pose, equipment, hand sockets, physics or native asset.",
                        "Cape and deadmau5 ears are not part of default Steve rendering and are excluded.",
                        "The MC renderer 0.9375 scale is applied; world-render offsets/lighting and collision are not exported.",
                        "Official client/skin and derived asset package remain local and ignored; Minecraft EULA applies."],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--client", type=Path, help="Local official client JAR; exact pinned checksums required")
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--download", action="store_true", help="Download missing fixed official dependencies to ignored downloads")
    args = parser.parse_args()
    try:
        manifest = build(args.output, args.client, args.download, args.java_home)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Offline model reader failed: {error.stderr or error.stdout}") from error
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps({"output": str(output_directory(args.output)), "files": manifest["files"], "nativeIntegrated": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
