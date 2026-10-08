"""Offline six-part feet-frame adapter; no game, native call or owner transform.

Only the fixed admitted Player replay and official neutral Steve asset are used.
One model metre is declared as one native world unit, not calibrated in game.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import struct

import build_steve_player_pose as player
import check_steve_asset as asset_check

ROOT, assets = player.ROOT, player.assets
DEFAULT_OUTPUT = ROOT / "build/steve-rigid-adapter-1.21.1"
REPORT_NAME = "steve-rigid-adapter-report.json"
DATA_NAME = "adapter.json"
VARIANT = "official-player-96-six-rigid-pivot-local-feet-frame-yxz"
ROOT_SCALE = 0.9375
PARTS = assets.BASE_PARTS
LIMIT = 8 * 1024 * 1024
SOURCE_PINS = {
    "build/steve-player-pose-1.21.1/steve-player-pose-report.json": "77dc04a8dd90b23765485298e4430ec2513d6c94c1212fb252314e555ffdb9c7",
    "build/steve-1.21.1/manifest.json": "50b84703cf45455438b29497c6b016967625f0c912a803de87fed88aa58605a3",
    "build/steve-1.21.1/minecraft-model.json": "a738088223b0d109119459ef508dd91560bac836a2e3db3484433a1f5dad9971",
    "build/steve-1.21.1/steve.gltf": "bc9cd38b3ebcab9702def27a425208bbfb2f6a1093012976d95f0c4d165e81b8",
    "build/steve-1.21.1/steve.bin": "d03b7e6354652c7872b14b89d9d56861a23d2e910b52349f0e1da4c3101942a0",
    "build/steve-1.21.1/steve.png": "d876e0c88f4b3de71040966ed94a614f315b888592b520b993399fd2738418d0",
    "config/steve-asset-1.21.1.json": "1cc61e1018feaed90ef5287b4df0e2dabb9848e78fe14c8a572d6b3c7a4ad4d7",
    "tools/build_steve_asset.py": "c71f7319e0417affb5fa28b200d5a360b7f3c264b0d8d28b8fb8345a6f343fa8",
    "tools/SteveModelDump.java": "d13773b511b1f8edd00883a8960aedee8432612d84b17b03afcd73f15814c217",
    "vendor/world-builder/asi/cdmodkit/cdmodkit.cpp": "2772d033f35b019147f331d951297d6fc6c5666dd7fef2d7ee218237f704f1d4",
    "vendor/world-builder/asi/cdmodkit/core.h": "a7da49963177bb026b3e85c9dcb68c2564f6603000c8936872bc0fe9d1db507f",
    "build/steve-rigid-render-contract-20261008/report.json": "9cd69f4015cb737e1f7f1582ecd696c7eeff7c4322c96fdb8354194225dd6f5e",
}
require, digest = player.require, player.digest
report_bytes, verify_snapshot = player.report_bytes, player.verify_snapshot
merge_snapshot = player.merge_snapshot
input_path, input_bytes = player.input_path, player.input_bytes


def finite_vector(value, length, name):
    require(type(value) is list and len(value) == length, name + " length differs")
    require(all(type(x) in (int, float) and math.isfinite(x) for x in value), name + " must be finite numeric")
    return [float(x) for x in value]


def f32(value):
    require(type(value) in (int, float) and math.isfinite(value), "Native input must be finite numeric")
    try:
        result = struct.unpack("<f", struct.pack("<f", value))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError("Native float32 overflow") from error
    require(math.isfinite(result), "Native float32 overflow")
    return result


def uniform_scale(value):
    scale = finite_vector(value, 3, "Part scale")
    require(scale[0] == scale[1] == scale[2] and scale[0] > 0,
            "Native scalar scale cannot represent nonuniform/nonpositive part scale")
    return scale[0]


def quaternion_to_native_rot(value):
    """Hamilton XYZW -> Ry(yaw) Rx(pitch) Rz(roll), in float32 degrees.

    The singular choice roll=0 is only orientation equivalence; no continuity
    or runtime interpolation guarantee is inferred from these Euler values.
    """
    q = finite_vector(value, 4, "Official quaternion")
    norm = math.hypot(*q)
    require(norm > 1e-12 and abs(norm - 1) < 1e-5, "Official quaternion must be unit length")
    x, y, z, w = [number / norm for number in q]
    sin_pitch = max(-1.0, min(1.0, 2 * (x * w - y * z)))
    if abs(sin_pitch) >= 1 - 1e-12:
        pitch = math.copysign(math.pi / 2, sin_pitch)
        yaw = math.atan2(2 * (y * w - x * z), 1 - 2 * (y * y + z * z))
        roll = 0.0
    else:
        pitch = math.asin(sin_pitch)
        yaw = math.atan2(2 * (x * z + y * w), 1 - 2 * (x * x + y * y))
        roll = math.atan2(2 * (x * y + z * w), 1 - 2 * (x * x + z * z))
    return {"yaw": f32(math.degrees(yaw)), "pitch": f32(math.degrees(pitch)), "roll": f32(math.degrees(roll))}


def preflight(output):
    output = assets.output_directory(Path(output))
    require(output.name.startswith("steve-rigid-adapter-"), "Rigid output must use its owned build prefix")
    protected = [ROOT / "runtime", ROOT / "minecraft", ROOT / "downloads", ROOT / "tools",
                 assets.DEFAULT_OUTPUT, player.DEFAULT_OUTPUT, ROOT / "build/steve-rigid-render-contract-20261008"]
    protected.extend(ROOT / relative for relative in SOURCE_PINS)
    if output != DEFAULT_OUTPUT:
        protected.append(DEFAULT_OUTPUT)
    for path in protected:
        path = input_path(path)
        require(not (output == path or output.is_relative_to(path) or path.is_relative_to(output)),
                "Rigid output overlaps a protected source/canonical")
    require(not output.exists(), "Rigid output already exists; never overwrite")
    return output


def load_sources():
    snapshot, summary = {}, {}
    for relative, pin in SOURCE_PINS.items():
        path = input_path(ROOT / relative)
        raw = input_bytes(path, LIMIT)
        require(digest(raw) == pin, "Fixed rigid source fingerprint differs: " + relative)
        merge_snapshot(snapshot, {path: raw})
        summary[relative] = {"sha256": pin, "bytes": len(raw)}
    upstream, poses, upstream_snapshot = player.load()
    merge_snapshot(snapshot, upstream_snapshot)
    for relative in ("tools/build_steve_rigid_adapter.py", "tools/check_steve_rigid_adapter.py", "tools/check_steve_asset.py"):
        path = input_path(ROOT / relative)
        raw = input_bytes(path, LIMIT)
        merge_snapshot(snapshot, {path: raw})
        summary[relative] = {"sha256": digest(raw), "bytes": len(raw)}
    value = lambda relative: player.strict_json(snapshot[input_path(ROOT / relative)])
    config = value("config/steve-asset-1.21.1.json")
    manifest = value("build/steve-1.21.1/manifest.json")
    geometry = value("build/steve-1.21.1/minecraft-model.json")
    gltf = value("build/steve-1.21.1/steve.gltf")
    binary = snapshot[input_path(ROOT / "build/steve-1.21.1/steve.bin")]
    require(assets.canonical_digest(geometry) == config["geometryCanonicalSha256"] == manifest["geometryCanonicalSha256"],
            "Official static geometry differs")
    require(config["model"] == manifest["model"] and config["model"]["playerRendererScale"] == ROOT_SCALE
            and config["model"]["pixelsPerModelMeter"] == 16 and config["model"]["feetPixelY"] == 24,
            "Fixed feet-frame/renderer-scale contract differs")
    require(upstream["files"]["poses.json"] == player.POSE_SHA256, "Official fixed Player pose differs")
    verify_snapshot(snapshot)
    return poses, geometry, gltf, binary, summary, snapshot


def rigid_geometry(geometry, gltf, binary):
    by_name = {part["name"]: part for part in geometry["parts"]}
    skin = gltf["skins"][0]
    require(gltf["nodes"][0]["scale"] == [ROOT_SCALE] * 3 and gltf["nodes"][0]["children"] == skin["joints"]
            and len(skin["joints"]) == 6, "Static shared root/scale differs")
    require([mesh["name"] for mesh in gltf["meshes"]] == [*PARTS, *assets.OUTER_PARTS], "Static mesh inventory/order differs")
    groups = {}
    for index, name in enumerate(PARTS):
        joint = gltf["nodes"][skin["joints"][index]]
        require(joint["name"] == name + "_joint", "Static joint order differs")
        pivot = finite_vector(joint["translation"], 3, "Neutral pivot")
        neutral = by_name[name]["pivot"]
        require(pivot == [neutral[0]/16, 1.5-neutral[1]/16, -neutral[2]/16], "Static neutral pivot differs")
        meshes = []
        for mesh in gltf["meshes"]:
            mesh_name = mesh["name"]
            if assets.OUTER_PARTS.get(mesh_name, mesh_name) != name:
                continue
            part, primitive = by_name[mesh_name], mesh["primitives"][0]
            require(part["pivot"] == by_name[name]["pivot"] and part["rotation"] == [0, 0, 0]
                    and part["scale"] == [1, 1, 1], "Rigid rest geometry transform differs")
            attrs = {key: asset_check.accessor(gltf, binary, ref) for key, ref in primitive["attributes"].items()}
            require(attrs["JOINTS_0"] == [[index, 0, 0, 0]] * 24 and attrs["WEIGHTS_0"] == [[1, 0, 0, 0]] * 24,
                    "Static mesh is not rigid to its one expected joint")
            positions = [[v[axis] - pivot[axis] for axis in range(3)] for v in attrs["POSITION"]]
            # POSITION already contains bind-pivot + feet shift. This subtraction
            # removes both; do not flip axes, add feet or apply .9375 again here.
            require(len(positions) == 24, "Rigid static vertex count differs")
            meshes.append({"name": mesh_name, "outerLayer": mesh_name in assets.OUTER_PARTS,
                           "positionsPivotLocalModelMetres": positions, "normals": attrs["NORMAL"],
                           "uv": attrs["TEXCOORD_0"], "indices": [x[0] for x in asset_check.accessor(gltf, binary, primitive["indices"])],
                           "material": copy.deepcopy(gltf["materials"][primitive["material"]])})
        groups[name] = {"neutralPivotFeetFrameModelMetres": pivot, "meshes": meshes}
    return groups


def convert(poses, geometry, gltf, binary):
    require(type(poses["samples"]) is list and len(poses["samples"]) == 96, "Only fixed 96-sample replay is supported")
    groups = rigid_geometry(geometry, gltf, binary)
    frames = []
    for index, sample in enumerate(poses["samples"]):
        require(sample["sampleIndex"] == index and set(sample["parts"]) == set(PARTS), "Sample/joint inventory differs")
        parts = {}
        for name in PARTS:
            part = sample["parts"][name]
            pos = finite_vector(part["translationMetres"], 3, "Official translation")
            scale = uniform_scale(part["scale"])
            native_scale = f32(ROOT_SCALE * scale)
            require(native_scale > 0, "Native uniform scale underflows to zero")
            parts[name] = {"positionFeetFrameWorldUnits": [f32(ROOT_SCALE * x) for x in pos],
                           "rotYXZDegrees": quaternion_to_native_rot(part["rotationQuaternionXYZW"]),
                           "uniformScale": native_scale}
        frames.append({"sampleIndex": index, "sourceFrameIndex": sample["sourceFrameIndex"],
                       "sourceDeltaIndex": sample["sourceDeltaIndex"], "sourceServerTick": sample["sourceServerTick"],
                       "sourceProfile": sample["sourceProfile"], "sourceAge": sample["sourceAge"],
                       "tickDelta": sample["inputs"]["tickDelta"], "parts": parts})
    return {"schemaVersion": 1, "minecraftVersion": "1.21.1", "variant": VARIANT,
            "frameCount": 96, "jointTransformCount": 576, "geometry": groups, "frames": frames}


def expected_report(summary, data):
    return {"schemaVersion": 1, "variant": VARIANT, "sources": summary,
            "files": {DATA_NAME: digest(report_bytes(data))},
            "evaluation": {"sourceFrameCount": 32, "interpolationSamples": 96, "sixJointTransforms": 576,
                           "staticMeshes": 12, "staticVertices": 288, "sourceMethod": "official PlayerEntityModel evaluation already fixed upstream"},
            "coordinates": {"frame": "declared feet frame; +Y up,+Z Steve front; identity root orientation and zero root position",
                            "geometry": "static glTF POSITION minus matching neutral joint translation; unscaled pivot-local model metres",
                            "position": "0.9375 * official converted animated pivot in feet frame",
                            "scale": "0.9375 * supported positive uniform ModelPart scale, once",
                            "rotation": "Hamilton XYZW official q normalized then decomposed into native Ry(yaw)*Rx(pitch)*Rz(roll), float32 degrees",
                            "nativeWorldUnitsPerModelMetre": 1, "nativeUnitsCalibratedInGame": False,
                            "nativeSource": "core.h:19..20;cdmodkit.cpp:700..714", "singularEulerContinuous": False},
            "integration": {"officialPlayerPoseSource": True, "nativeApplied": False, "animationSystemComplete": False,
                            "nativeOwnerOrientationVerified": False, "nativeOwnerPositionSampled": False,
                            "rendererRootReplayed": False, "runtimeLayerVisibilityVerified": False,
                            "nativeCollisionAbsent": False, "nativeResourcesAuthored": False, "installed": False},
            "limitations": ["Offline coordinates only; no owner/UID, prefab, MoveMany call or native renderer execution.",
                            "Declared feet frame includes the existing 1.5 feet shift and .9375 scale; full renderer body yaw, entity scale, crouch/world offsets and 1.501 translation are not composed.",
                            "One model metre equals one world unit only by declaration; actual game unit calibration remains unverified.",
                            "Twelve static base/outer meshes share six rigid joints; layer visibility is not a captured Player skin-option contract.",
                            "Scalar native scale rejects nonuniform/nonpositive scales. Euler singular solutions prove orientation only, not angle continuity.",
                            "Fresh owner binding, original body/input suppression, collision absence, frame coherence and reload cleanup remain separate runtime requirements."]}


def build(output=DEFAULT_OUTPUT):
    output = preflight(output)
    poses, geometry, gltf, binary, summary, snapshot = load_sources()
    data = convert(poses, geometry, gltf, binary)
    report = expected_report(summary, data)
    verify_snapshot(snapshot)
    output = preflight(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for name, value in ((DATA_NAME, data), (REPORT_NAME, report)):
        with (output / name).open("xb") as stream:
            stream.write(report_bytes(value))
    verify_snapshot(snapshot)
    return report


def load(output=DEFAULT_OUTPUT):
    output = assets.output_directory(Path(output))
    poses, geometry, gltf, binary, summary, snapshot = load_sources()
    data = convert(poses, geometry, gltf, binary)
    report = expected_report(summary, data)
    for name, expected in ((DATA_NAME, data), (REPORT_NAME, report)):
        path = input_path(output / name)
        raw = input_bytes(path, LIMIT)
        require(raw == report_bytes(expected), "Rigid complete canonical " + name + " differs")
        merge_snapshot(snapshot, {path: raw})
    verify_snapshot(snapshot)
    return report, data, snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build(args.output)
    print(json.dumps({"output": str(assets.output_directory(args.output)), "files": report["files"], **report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
