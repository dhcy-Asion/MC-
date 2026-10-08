"""Build a limited MC 1.21.1 pose oracle using the official model methods.

Only standing/look/walk on an explicit ArmorStandEntity fixture are admitted.
No world/client main or Crimson Desert access is involved; all outputs are local
ignored build files. Cached official dependencies are required; no download route.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import zipfile

import build_steve_asset as assets

ROOT = assets.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-pose-1.21.1"
JAVA_SOURCE = ROOT / "tools/StevePoseDump.java"
CLASS_FILE = "helper-classes/local/crimsonmc/assets/StevePoseDump.class"
REPORT_NAME = "steve-pose-report.json"
CLIENT_SHA256 = "499f6897d1837516680f3114072d8106e11c9adcd933fe5cf051b551089b0c99"
POSE_SHA256 = "0302fd9021bc0bd31eb5b51478cb6512f8fcb7b053ed32458ed0fe6c6d8b0855"
HELPER_CLASS_SHA256 = "c04f419012b4d6045b7d33254ebd976777c594ccd66ef30851089e41a6a3f7cc"
CLASS_PINS = {
    "fwp.class": "4d75b4c7930a104fc47f7cbb4caa28953c801a11e39eacda1b45d54eb6926ff9",
    "fvx.class": "ff2bed3d05ca29da524fddba8d2ac8b654427587e5568e7dc6ae89cfa6902a20",
    "fvx$a.class": "e38a9d180d54e91c929a5b74d072c270c44e6e1a54a6c4bc856269dd95eac05d",
    "fuf.class": "f657b43e19f6c88d8c29430f1c6a583b10b7d3577b7b19e4ba1464491bdb3560",
    "fvk.class": "8633dd53a8da2ed9257192ff99c54657816f132e1de02b6697ac810500e48ee5",
    "fyk.class": "b6f1eea56136a1e5b78ea6dda7200bbfada8aa45a3116b1e82a7c40e3dae4c67",
    "fyo.class": "4f90c1853385b9c8b5c31c071c91faeb09bb6d91eafed4e772b72c987f999d0c",
    "fys.class": "c32b828f0a202093fbd594933c79535d2cb21dd37de5d0f3067577115f272786",
    "fuh.class": "5d982bcced033bbdf54fea6f7478aefc3d524c3fcb513ce4f69d3a2ad2712e27",
    "ayo.class": "f9417695604144fcb88ae34ce68c47743f169cbbd72a3fccad94cdb5ea305ab1",
    "ciw.class": "10c0677335bc874720115aa5598cf4aec7b5787e90b365e9d980875f39a65bd0",
    "btn.class": "a729393b3a7d636dc60a0f34e743ed48c951bef7ca75509ec7316dad0d39d0f4",
    "bsr.class": "de2b58e3d3e9976c2ca74c7142f8ff27ef613cbfda9010df36606555e374fee5",
    "bsx.class": "0178475b8600aae5067425f54cd27d46bb56404299f40caa2f31cc32ca114e93",
    "akt.class": "c4b3b83dc839ac5cbcb1916c7e5c3583235a3542d7522256292f1683e9e80e4c",
    "ab.class": "c90fc49d47bb3018cad99303e5874e49e0ff24e70125d0a9aadf654ade670ea7",
    "btg.class": "c5f2b6f5377017207b37b78f6693b3f02d04cdf95afaf4eeb509011ec3f92a4e",
    "bqq.class": "fba09d7b13f4381652f1d8dd43068e9ad02bc5024dad898633b814962dabe248",
    "bsy.class": "c5ff6667243fe29238a20afdcb2c6d32cfdb0b9e9db34ec3697bd0882c7886ca",
    "cuq.class": "a34b9141828bd62fa74ad6a5d3b9b47a81df18b4a86866827c8f73d3ab97f901",
    "exc.class": "93fe7ebf605ba92ee6bfcff46a48fc6e217ff458ca0f78723774421951fc2d2b",
}
PARTS = assets.BASE_PARTS
RAW_FIELDS = ("pivotX", "pivotY", "pivotZ", "pitch", "yaw", "roll", "scaleX", "scaleY", "scaleZ")
FIXTURE_STATE = {"fallFlyingTicks": 0, "swimmingPose": False, "usingItem": False,
                 "sneaking": False, "mainArmRight": True, "activeHandMain": True,
                 "velocityZero": True, "chestEmpty": True}
INPUT_CONTRACT = {
    "ticksPerSecond": 20, "cycleTicks": 40, "endpointIncluded": True, "samplesPerProfile": 41,
    "limbAngle": "official setAngles limb angle argument, radians / float32(0.6662)",
    "limbDistance": "dimensionless model amplitude; standing/look=0, walk=float32(0.6)",
    "phaseRadians": "float32(2*pi*tick/40), ticks 0..40 inclusive; one locomotion cycle",
    "age": "tick count 0..40, also drives official idle arm bob; not a loop closure claim",
    "headAngles": "degrees; look yaw=30 pitch=15, other profiles=0",
    "tickDelta": 0.0, "entityTicked": False,
    "modelState": {"handSwingProgress": 0.0, "riding": False, "child": False,
                   "sneaking": False, "leaningPitch": 0.0, "leftArmPose": "EMPTY", "rightArmPose": "EMPTY"},
}
COORDINATES = {
    "raw": "MC ModelPart pivot in pixels, Euler pitch/yaw/roll in radians, scale dimensionless",
    "rotationOrder": "official ModelPart/JOML ZYX: Rz(roll)*Ry(yaw)*Rx(pitch)",
    "basis": "C=diag(1,-1,-1): MC +Y down/-Z front to exported +Y up/+Z front",
    "translationMetres": "[pivotX/16, 1.5-pivotY/16, -pivotZ/16]; feet offset is common root translation",
    "rotationQuaternionXYZW": "q from JOML rotationZYX(roll,yaw,pitch); [q.x,-q.y,-q.z,q.w]",
    "scale": "raw ModelPart scale; separate renderer root scale=0.9375",
    "rendererRootScale": 0.9375, "pixelsPerModelMetre": 16, "feetOffsetMetres": 1.5,
    "partParents": "all six MC base parts are root children; no native bone retargeting",
}
SOURCE_LIMIT = 64 * 1024 * 1024
POSE_LIMIT = 2 * 1024 * 1024


def digest(raw, algorithm="sha256"):
    return hashlib.new(algorithm, raw).hexdigest()


def report_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def input_bytes(path, limit=SOURCE_LIMIT):
    path = Path(os.path.abspath(path))
    current = path
    while current != current.parent:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("Pose input/output must not contain links")
        current = current.parent
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Pose source missing or outside its read bound")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("Pose source exceeded its read bound")
    return raw


def preflight(output):
    output = assets.output_directory(Path(output))
    protected = [assets.DEFAULT_OUTPUT, JAVA_SOURCE.parent, ROOT / "downloads/steve-1.21.1"]
    if output != DEFAULT_OUTPUT:
        protected.append(DEFAULT_OUTPUT)
    for directory in protected:
        directory = directory.resolve()
        if output == directory or output.is_relative_to(directory) or directory.is_relative_to(output):
            raise ValueError("Pose output overlaps a protected input or canonical output")
    if output.exists():
        raise ValueError("Pose output already exists; never overwrite it")
    return output


def sources(client=None, java_home=None):
    config = assets.read_config()
    if config["client"]["sha256"] != CLIENT_SHA256:
        raise ValueError("Pose oracle requires the fixed official client")
    client, jars = assets.dependencies(config, client, False)
    java, javac = assets.java_tools(java_home)
    snapshot = {}

    def record(path, expected=None, algorithm="sha256"):
        path = Path(path).resolve()
        raw = input_bytes(path)
        if expected is not None and digest(raw, algorithm) != expected:
            raise ValueError("Pose source fingerprint differs: " + path.name)
        if path in snapshot and snapshot[path] != raw:
            raise ValueError("Pose input changed between admitted reads")
        snapshot[path] = raw
        return {"path": str(path), "bytes": len(raw), "sha256": digest(raw)}, raw

    client_info, raw_client = record(client, CLIENT_SHA256)
    client_info["sha1"] = digest(raw_client, "sha1")
    if client_info["sha1"] != config["client"]["sha1"]:
        raise ValueError("Official client SHA-1 differs")
    with zipfile.ZipFile(client) as archive:
        class_hashes = {name: digest(archive.read(name)) for name in CLASS_PINS}
    if class_hashes != CLASS_PINS:
        raise ValueError("Official pose/fixture algorithm class fingerprint differs")
    meta_info, meta_raw = record(ROOT / "downloads/steve-1.21.1/version.json", config["versionMetadata"]["sha1"], "sha1")
    meta_info["sha1"] = digest(meta_raw, "sha1")
    metadata = json.loads(meta_raw)
    artifacts = [item["downloads"]["artifact"] for item in metadata["libraries"]
                 if item.get("downloads", {}).get("artifact")
                 and "natives-" not in item["downloads"]["artifact"]["path"] and not item.get("rules")]
    if len(artifacts) != len(jars):
        raise ValueError("Fixed classpath dependency inventory differs")
    libraries = []
    for jar, artifact in zip(jars, artifacts):
        if jar.name != Path(artifact["path"]).name:
            raise ValueError("Classpath order or artifact name differs")
        item, raw = record(jar, artifact["sha1"], "sha1")
        item.update({"artifact": artifact["path"], "sha1": artifact["sha1"]})
        libraries.append(item)
    helper, _ = record(JAVA_SOURCE)
    builder, _ = record(Path(__file__))
    cfg, _ = record(assets.CONFIG)
    java_info, _ = record(java)
    javac_info, _ = record(javac)
    provenance = {"client": client_info, "versionMetadata": meta_info, "algorithmClassSha256": class_hashes,
                  "allMinecraftClassesPinnedByClientSha256": True, "externalClasspath": libraries,
                  "helperSource": helper, "builderSource": builder, "assetConfig": cfg,
                  "javaTools": {"java": java_info, "javac": javac_info}}
    return provenance, snapshot, client, jars, java, javac


def verify_snapshot(snapshot):
    for path, admitted in snapshot.items():
        if input_bytes(path) != admitted:
            raise ValueError("Pose source changed before publication/admission")


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def finite_vector(value, length):
    if (not isinstance(value, list) or len(value) != length
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("Pose vector is not finite or has the wrong dimension")
    return value


def converted_quaternion(pitch, yaw, roll):
    # Independent coordinate conversion, never a pose/animation approximation.
    sx, sy, sz = (math.sin(v / 2) for v in (pitch, yaw, roll))
    cx, cy, cz = (math.cos(v / 2) for v in (pitch, yaw, roll))
    return [cz * cy * sx - sz * sy * cx, -(cz * sy * cx + sz * cy * sx),
            -(sz * cy * cx - cz * sy * sx), cz * cy * cx + sz * sy * sx]


def validate_poses(value):
    expected_keys = {"schemaVersion", "minecraftVersion", "fixtureType", "fixtureIsPlayer", "worldNull", "entityTicked",
                     "officialMethodsCalled", "cycleTicks", "endpointIncluded", "nativeApplied", "animationSystemComplete",
                     "fixtureState", "profiles", "animateModelCalls", "setAnglesCalls"}
    if (not isinstance(value, dict) or set(value) != expected_keys or value["schemaVersion"] != 1
            or value["minecraftVersion"] != "1.21.1" or value["fixtureType"] != "ArmorStandEntity"
            or any(value[k] is not False for k in ("fixtureIsPlayer", "entityTicked", "nativeApplied", "animationSystemComplete"))
            or any(value[k] is not True for k in ("worldNull", "officialMethodsCalled", "endpointIncluded"))
            or type(value["cycleTicks"]) is not int or value["cycleTicks"] != 40
            or report_bytes(value["fixtureState"]) != report_bytes(FIXTURE_STATE)
            or set(value["profiles"]) != {"standing", "look", "walk"}
            or any(type(value[k]) is not int or value[k] != 123 for k in ("animateModelCalls", "setAnglesCalls"))):
        raise ValueError("Pose fixture/evaluation contract differs")
    for profile, frames in value["profiles"].items():
        if not isinstance(frames, list) or len(frames) != 41:
            raise ValueError("Pose profile needs all 40 ticks and the endpoint")
        for tick, frame in enumerate(frames):
            phase = f32(2 * math.pi * tick / 40)
            inputs = {"phaseRadians": phase, "limbAngle": f32(phase / f32(.6662)) if profile == "walk" else 0.,
                      "limbDistance": f32(.6) if profile == "walk" else 0., "age": float(tick),
                      "headYawDegrees": 30. if profile == "look" else 0.,
                      "headPitchDegrees": 15. if profile == "look" else 0., "tickDelta": 0.}
            if (set(frame) != {"tick", "inputs", "fixtureStateBefore", "fixtureStateAfter", "parts"}
                    or type(frame["tick"]) is not int or frame["tick"] != tick or set(frame["inputs"]) != set(inputs)
                    or any(type(frame["inputs"][k]) not in (int, float) or f32(frame["inputs"][k]) != f32(v)
                           for k, v in inputs.items())
                    or report_bytes(frame["fixtureStateBefore"]) != report_bytes(FIXTURE_STATE)
                    or report_bytes(frame["fixtureStateAfter"]) != report_bytes(FIXTURE_STATE)
                    or set(frame["parts"]) != set(PARTS)):
                raise ValueError("Pose frame input, fixture state or six-part inventory differs")
            for part in frame["parts"].values():
                if set(part) != {"rawModelPart", "rawFloatBits", "translationMetres", "rotationQuaternionXYZW", "scale"}:
                    raise ValueError("Pose part field inventory differs")
                raw = part["rawModelPart"]
                if set(raw) != set(RAW_FIELDS):
                    raise ValueError("ModelPart raw field inventory differs")
                numbers = finite_vector([raw[k] for k in RAW_FIELDS], 9)
                bits = [struct.unpack("<i", struct.pack("<f", n))[0] for n in numbers]
                if (part["rawFloatBits"] != bits or any(type(v) is not int for v in part["rawFloatBits"])):
                    raise ValueError("Raw ModelPart float bits differ")
                translation = finite_vector(part["translationMetres"], 3)
                scale = finite_vector(part["scale"], 3)
                q = finite_vector(part["rotationQuaternionXYZW"], 4)
                expected_translation = [f32(numbers[0] / 16), f32(1.5 - f32(numbers[1] / 16)), f32(-numbers[2] / 16)]
                if (any(abs(a - b) > 1e-7 for a, b in zip(translation, expected_translation))
                        or any(f32(a) != f32(b) for a, b in zip(scale, numbers[6:]))
                        or abs(sum(v * v for v in q) - 1) > 1e-5
                        or max(abs(a - b) for a, b in zip(q, converted_quaternion(*numbers[3:6]))) > 4e-7):
                    raise ValueError("Pose coordinate TRS differs from raw ModelPart fields")
    return value


def expected_report(provenance, raw_pose, raw_class):
    if digest(raw_pose) != POSE_SHA256:
        raise ValueError("Official limited pose bytes differ from the reviewed deterministic oracle")
    if digest(raw_class) != HELPER_CLASS_SHA256:
        raise ValueError("Compiled official-call helper differs from the reviewed class")
    poses = validate_poses(json.loads(raw_pose))
    return {"schemaVersion": 1, "minecraftVersion": "1.21.1", "variant": "official-classic-steve-standing-look-walk",
            "sources": provenance, "files": {"poses.json": digest(raw_pose), CLASS_FILE: digest(raw_class)},
            "evaluation": {"fixtureType": "ArmorStandEntity", "fixtureIsPlayer": False,
                           "fixtureState": copy.deepcopy(poses["fixtureState"]), "worldNull": True, "entityTicked": False,
                           "methods": ["BipedEntityModel.animateModel(LivingEntity,FFF)", "PlayerEntityModel.setAngles(LivingEntity,FFFFF)"],
                           "animateModelCalls": 123, "setAnglesCalls": 123, "freshModelPerFrame": True},
            "inputs": copy.deepcopy(INPUT_CONTRACT), "coordinates": copy.deepcopy(COORDINATES),
            "integration": {"nativeApplied": False, "animationSystemComplete": False, "playerStateCaptured": False,
                            "combatApplied": False, "nativeRetargeted": False},
            "limitations": ["ArmorStandEntity is an explicit offline non-player input fixture; no World or entity tick.",
                            "Only ordinary empty-hand adult standing/look/walk input profiles are admitted.",
                            "One locomotion phase cycle plus endpoint; age-driven idle bob is not looped.",
                            "Attack, crouch, sprint state, jump/fall, riding, swim, flight and item-use states are not covered.",
                            "No native pose/controller ABI, native bone retargeting, gameplay timing or live player state."]}


def load(output=DEFAULT_OUTPUT):
    output = assets.output_directory(Path(output))
    raw_report = input_bytes(output / REPORT_NAME, POSE_LIMIT)
    report = json.loads(raw_report)
    provenance, snapshot, *_ = sources(Path(report["sources"]["client"]["path"]),
                                     Path(report["sources"]["javaTools"]["java"]["path"]).parent.parent)
    raw_pose = input_bytes(output / "poses.json", POSE_LIMIT)
    raw_class = input_bytes(output / CLASS_FILE, POSE_LIMIT)
    expected = expected_report(provenance, raw_pose, raw_class)
    if report != expected or raw_report != report_bytes(expected):
        raise ValueError("Pose report is not the complete canonical source/evaluation contract")
    verify_snapshot(snapshot)
    return report, json.loads(raw_pose), snapshot


def build(output=DEFAULT_OUTPUT, client=None, java_home=None):
    output = preflight(output)
    provenance, snapshot, client, jars, java, javac = sources(client, java_home)
    environment = dict(os.environ)
    for key in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
        environment.pop(key, None)
    with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="steve-pose-stage-") as temporary:
        stage = assets.output_directory(Path(temporary))
        classes = stage / "helper-classes"
        classes.mkdir()
        staged_source = stage / "StevePoseDump.java"
        staged_source.write_bytes(snapshot[JAVA_SOURCE.resolve()])
        staged_classpath = []
        for i, path in enumerate([client, *jars]):
            admitted = snapshot[Path(path).resolve()]
            staged_jar = stage / "classpath" / str(i) / Path(path).name
            staged_jar.parent.mkdir(parents=True, exist_ok=True)
            staged_jar.write_bytes(admitted)
            if input_bytes(staged_jar) != admitted:
                raise ValueError("Staged fixed classpath bytes differ")
            staged_classpath.append(staged_jar)
        commands = (
            [str(javac), "--release", "21", "-d", str(classes), str(staged_source)],
            [str(java), "-Djava.awt.headless=true", "-Djava.io.tmpdir=" + str(stage), "-cp",
             os.pathsep.join(map(str, [classes, *staged_classpath])), "local.crimsonmc.assets.StevePoseDump", str(stage / "poses.json")],
        )
        for command in commands:
            result = subprocess.run(command, cwd=stage, env=environment, capture_output=True, text=True, timeout=45)
            if result.returncode:
                raise RuntimeError("Official offline pose call failed; no synthetic fallback:\n" + result.stderr[-6000:])
        raw_pose, raw_class = input_bytes(stage / "poses.json", POSE_LIMIT), input_bytes(stage / CLASS_FILE, POSE_LIMIT)
        report = expected_report(provenance, raw_pose, raw_class)
        verify_snapshot(snapshot)
        output = preflight(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir()
        for relative, raw in {"poses.json": raw_pose, CLASS_FILE: raw_class, REPORT_NAME: report_bytes(report)}.items():
            path = output / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
        verify_snapshot(snapshot)
    load(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--client", type=Path)
    parser.add_argument("--java-home", type=Path)
    args = parser.parse_args()
    report = build(args.output, args.client, args.java_home)
    print(json.dumps({"output": str(assets.output_directory(args.output)), "profiles": ["standing", "look", "walk"],
                      "samples": 123, "posesSha256": report["files"]["poses.json"], **report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
