"""Fixed official MC model crouch and right MAIN/OFF progress samples.

Normally constructed ArmorStand inputs; no World, Player, entity tick, renderer,
native gameplay, server or downloads. This is an explicit model-input oracle.
The original standing/look/walk tools and canonical output are preserved.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import zipfile

import build_steve_pose as old

ROOT, assets = old.ROOT, old.assets
DEFAULT_OUTPUT = ROOT / "build/steve-action-pose-1.21.1"
JAVA_SOURCE = ROOT / "tools/SteveActionPoseDump.java"
CLASS_FILE = "helper-classes/local/crimsonmc/assets/SteveActionPoseDump.class"
REPORT_NAME = "steve-action-pose-report.json"
VARIANT = "official-classic-steve-model-crouch-right-main-off-progress"
CLIENT_SHA256 = old.CLIENT_SHA256
POSE_SHA256 = "6c289d5f803f3ceb5a2721cff93077a1a055b612bc2eed55c45ee0f582631c98"
HELPER_CLASS_SHA256 = "127d3fb268e7b148183891d82556c5da9b6f282b64dc4bf9245ae69c2a0126c8"
MAPPINGS = ROOT / "downloads/block-state-models-1.21.1/client-mappings.txt"
MAPPINGS_SHA1 = "2244b6f072256667bcd9a73df124d6c58de77992"
CLASS_PINS = {**old.CLASS_PINS,
    "bua.class": "50ef75592d57a3ead156453504efffedb87dcf7470a84d98df244a71513ea58c",
    "gpo.class": "471736db277d8bafd2977005253f661184a0d6d1ee45322ae9cd3bdc6b902ba6",
    "glk.class": "d8a05e693b4581ad843c955d6839b6d5ce38d67cd7d38ab6c9fae626525cec26",
    "cmx.class": "cf857b1a2a716131f78eadec2ee5be22167e3dcf648ee42e2036edc1935edab5",
    "btp.class": "64df9009f5438ccad2a3fdd4d612b60848cf84b8f05c2a7b5ec0582253439d95",
    "bsa.class": "dad0279df081da30a559e24270315f3be6d88e2685d64b4a0befc5d584cef349",
    "bsb.class": "c51f6132191125053b36356d7bbcefcce5c284f23fbe71efab9efcadc4a10c68",
    "brz.class": "a7453d5f04ab3b6b10d7a524b5f1c9d47a0a76c84a57c79c9b457429339b64bb",
}
LEGACY_PINS = {
    "tools/StevePoseDump.java": "a1e7f63c351a9a4eb21599b97ed5005a685725948e17dee535daac4bef5eac58",
    "tools/build_steve_pose.py": "50160afec76069589723d8235ab6e6e645ba97a89d7a28b30e1dd331e5f52615",
    "tools/check_steve_pose.py": "2ad7752d9d3273fc5cce1a60191b676565d852643f4cdaa835206d2786a4441f",
    "build/steve-pose-1.21.1/poses.json": old.POSE_SHA256,
    "build/steve-pose-1.21.1/" + old.CLASS_FILE: old.HELPER_CLASS_SHA256,
    "build/steve-pose-1.21.1/steve-pose-report.json": "5f1a72721094c10b2b9834528eab03f0c8ff832825db948489e0ab335ecba89b",
}
PARTS, RAW_FIELDS = old.PARTS, old.RAW_FIELDS
PROFILES = ("model_crouch", "right_main_hand_swing", "right_off_hand_swing")
FRAME_COUNT = 43
POSE_LIMIT = old.POSE_LIMIT
digest, report_bytes, input_bytes = old.digest, old.report_bytes, old.input_bytes
verify_snapshot, f32, finite_vector, converted_quaternion = old.verify_snapshot, old.f32, old.finite_vector, old.converted_quaternion
COORDINATES = copy.deepcopy(old.COORDINATES)
PRECONDITIONS = {
    "setSneakingTrueGetter": True, "poseAfterSneakFlag": "STANDING", "setCrouchPoseAccepted": False,
    "setCrouchPoseException": "java.lang.NullPointerException",
    "setCrouchPoseExceptionMessage": 'Cannot read field "B" because "this.r" is null',
    "setCrouchPoseOfficialStack": ["bsr.i_:3064", "ciw.i_:121", "bsr.a:3035", "btn.a:3202", "ciw.a:777", "aka.a:69", "aka.a:61", "bsr.b:422"],
    "failedPoseFixtureReused": False, "playerConstructed": False, "mobConstructed": False,
    "worldConstructed": False, "entityTickCalled": False,
}
FIELD_EVIDENCE = {
    "model.handSwingProgress": {"field": "fvk.c:F", "officialMappingName": "EntityModel.attackTime",
        "consumer": "fvx.animateArms / HumanoidModel.setupAttackAnimation", "rendererMapping": "glk.render @6..15 writes getAttackAnim(entity,tickDelta) to model.c", "rendererExecuted": False},
    "model.sneaking": {"field": "fvx.t:Z", "officialMappingName": "HumanoidModel.crouching",
        "consumer": "fvx.setAngles @610..731", "rendererMapping": "gpo.setModelPose @128..133 reads player.cb to model.t", "rendererExecuted": False},
    "entity.isSneaking": {"getter": "bsr.bW:()Z", "setter": "bsr.g:(Z)V", "means": "shift/sneak flag, not crouching Pose"},
    "entity.isInSneakingPose": {"getter": "bsr.cb:()Z", "setter": "bsr.b:(Lbua;)V", "crouchingEnum": "bua.f=CROUCHING", "fixtureResult": "Pose setter fails on null World; main samples remain STANDING"},
    "entity.preferredHand": {"field": "btn.aK:Lbqq;", "officialSetter": "btn.a:(Lbqq;)V swingHand", "enum": "bqq.a=MAIN_HAND,bqq.b=OFF_HAND"},
    "entity.mainArm": {"getter": "btn.fq:()Lbtg; / ciw.fq", "fixtureResult": "ciw.fq @0..3 constant btg.b=RIGHT"},
    "officialPreferredArm": {"method": "fvx.c:(Lbtn;)Lbtg;", "bytecode": "@0..23 getMainArm; MAIN returns main arm, OFF returns opposite"},
    "entity.activeHand": {"getter": "btn.fs:()Lbqq;", "means": "using-item arm pose input, independent of preferred attack hand"},
    "timeBoundary": {"currentProgress": "btn.aS:F", "lastProgress": "btn.aR:F", "interpolation": "btn.B:(F)F",
        "swingComponent": "btn.eR @0..60 updates ticks/progress without previous-frame copy",
        "previousCopy": "btn.aw @0..5 copies aS to aR; later @55..58 directly accesses World profiler",
        "duration": "btn.C defaults to six with no status effects; actual neutral getter observed, not a timing sweep",
        "fullEntityTickExecuted": False},
    "unavailableNormalFixtures": {"Player": "cmx constructor @105..106 dereferences World.B; not instantiated",
        "Mob": "btp constructor @76..77 and @91..92 dereferences World profiler; not instantiated"},
}
INPUT_CONTRACT = {
    "sampleKind": "specified model inputs, not entity ticks or captured Player state",
    "profiles": {"model_crouch": 1, "right_main_hand_swing": 21, "right_off_hand_swing": 21},
    "progress": "float32(sampleIndex/20), ordered 0..1 inclusive; 21 pose samples, no seconds/tick-cycle claim",
    "modelSneaking": "only model_crouch=true; fixture isInSneakingPose remains false",
    "preferredHand": "official swingHand(MAIN/OFF) on a new normal ArmorStand before each model evaluation",
    "mainArm": "RIGHT for every frame; OFF samples LEFT arm, not a left-main-hand Player",
    "activeHand": "MAIN_HAND for every frame; item use false",
    "otherAngles": "limbAngle=limbDistance=age=headYawDegrees=headPitchDegrees=tickDelta=0; stationary empty-hand adult",
    "freshEntityPerFrame": True, "freshModelPerFrame": True,
    "rendererFieldMappingKnownButNotExecuted": True, "entityTicked": False, "progressIsTickCycle": False,
}


def preflight(output):
    output = assets.output_directory(Path(output))
    protected = [old.DEFAULT_OUTPUT, assets.DEFAULT_OUTPUT, ROOT / "build/steve-action-pose-research-20261008",
                 ROOT / "downloads/steve-1.21.1", JAVA_SOURCE.parent]
    if output != DEFAULT_OUTPUT:
        protected.append(DEFAULT_OUTPUT)
    for directory in protected:
        directory = directory.resolve()
        if output == directory or output.is_relative_to(directory) or directory.is_relative_to(output):
            raise ValueError("Action pose output overlaps protected legacy/source/canonical assets")
    if output.exists():
        raise ValueError("Action pose output already exists; never overwrite it")
    return output


def sources(client=None, java_home=None):
    provenance, snapshot, client, jars, java, javac = old.sources(client, java_home)

    def record(path, expected=None, algorithm="sha256"):
        path = Path(path).resolve()
        raw = input_bytes(path)
        if expected is not None and digest(raw, algorithm) != expected:
            raise ValueError("Action pose source fingerprint differs: " + path.name)
        if path in snapshot and snapshot[path] != raw:
            raise ValueError("Action pose source changed between reads")
        snapshot[path] = raw
        return {"path": str(path), "bytes": len(raw), "sha256": digest(raw)}, raw

    legacy = {relative: record(ROOT / relative, pin)[0] for relative, pin in LEGACY_PINS.items()}
    prior = json.loads(snapshot[(old.DEFAULT_OUTPUT / old.REPORT_NAME).resolve()])["sources"]
    classpath_pins = lambda items: [(item["artifact"], item["sha1"], item["sha256"]) for item in items]
    if (any(provenance[name]["sha256"] != prior[name]["sha256"]
            for name in ("client", "assetConfig", "versionMetadata"))
            or classpath_pins(provenance["externalClasspath"]) != classpath_pins(prior["externalClasspath"])
            or any(provenance["javaTools"][name]["sha256"] != prior["javaTools"][name]["sha256"]
                   for name in ("java", "javac"))):
        raise ValueError("Action pose dependencies differ from the preserved fixed official oracle")
    with zipfile.ZipFile(client) as archive:
        hashes = {name: digest(archive.read(name)) for name in CLASS_PINS}
    if hashes != CLASS_PINS:
        raise ValueError("Action pose/renderer/entity algorithm class differs")
    mapping, mapping_raw = record(MAPPINGS, MAPPINGS_SHA1, "sha1")
    mapping["sha1"] = digest(mapping_raw, "sha1")
    metadata = json.loads(snapshot[Path(provenance["versionMetadata"]["path"])])
    if metadata["downloads"]["client_mappings"]["sha1"] != MAPPINGS_SHA1:
        raise ValueError("Official mappings not tied to the pinned version metadata")
    helper, _ = record(JAVA_SOURCE)
    builder, _ = record(Path(__file__))
    provenance = {**provenance, "helperSource": helper, "builderSource": builder,
                  "algorithmClassSha256": hashes, "officialMappings": mapping,
                  "legacyPreserved": legacy, "matchesPreservedOracleDependencySha256": True}
    return provenance, snapshot, client, jars, java, javac


def fixture_state(hand):
    return {"worldNull": True, "pose": "STANDING", "isSneaking": False, "isInSneakingPose": False,
        "fallFlyingTicks": 0, "swimmingPose": False, "usingItem": False, "mainArm": "RIGHT",
        "activeHand": "MAIN_HAND", "preferredHand": hand, "velocityZero": True,
        "mainHandEmpty": True, "offHandEmpty": True, "chestEmpty": True, "riding": False, "child": False,
        "activeEffectCount": 0, "entitySwinging": True, "entitySwingTicks": -1,
        "entityHandSwingProgress": 0.0, "entityLastHandSwingProgress": 0.0,
        "entityInterpolatedProgressAtZero": 0.0, "leaningPitchAtZero": 0.0, "officialSwingDurationNeutralGetter": 6}


def frame_inputs(profile, index):
    return {"handSwingProgress": f32(index / 20) if profile.endswith("swing") else 0.0,
            "modelSneaking": profile == "model_crouch",
            "preferredHand": "OFF_HAND" if profile == "right_off_hand_swing" else "MAIN_HAND",
            "limbAngle": 0.0, "limbDistance": 0.0, "age": 0.0,
            "headYawDegrees": 0.0, "headPitchDegrees": 0.0, "tickDelta": 0.0}


def validate_parts(parts):
    if not isinstance(parts, dict) or set(parts) != set(PARTS):
        raise ValueError("Action pose requires the exact six base parts")
    for part in parts.values():
        if not isinstance(part, dict) or set(part) != {"rawModelPart", "rawFloatBits", "translationMetres", "rotationQuaternionXYZW", "scale"}:
            raise ValueError("Action pose part field inventory differs")
        raw = part["rawModelPart"]
        if not isinstance(raw, dict) or set(raw) != set(RAW_FIELDS):
            raise ValueError("Action pose raw ModelPart fields differ")
        values = finite_vector([raw[name] for name in RAW_FIELDS], 9)
        bits = [struct.unpack("<i", struct.pack("<f", number))[0] for number in values]
        if part["rawFloatBits"] != bits or any(type(number) is not int for number in part["rawFloatBits"]):
            raise ValueError("Action pose raw float bits differ")
        translation, scale, quaternion = (finite_vector(part[name], length) for name, length in
            (("translationMetres", 3), ("scale", 3), ("rotationQuaternionXYZW", 4)))
        expected_translation = [f32(values[0]/16), f32(1.5-f32(values[1]/16)), f32(-values[2]/16)]
        if (max(abs(a-b) for a,b in zip(translation, expected_translation)) > 1e-7
                or any(f32(a) != f32(b) for a,b in zip(scale, values[6:]))
                or abs(sum(v*v for v in quaternion)-1) > 1e-5
                or max(abs(a-b) for a,b in zip(quaternion, converted_quaternion(*values[3:6]))) > 4e-7):
            raise ValueError("Action pose TRS differs from actual ModelPart fields")


def model_state_matches(actual, expected):
    if not isinstance(actual, dict) or set(actual) != set(expected):
        return False
    progress = actual["handSwingProgress"]
    if type(progress) not in (int, float) or not math.isfinite(progress):
        return False
    normalized = {**actual, "handSwingProgress": f32(progress)}
    return report_bytes(normalized) == report_bytes(expected)


def validate_poses(value):
    expected = {"schemaVersion", "minecraftVersion", "fixtureType", "fixtureIsPlayer", "worldNull", "entityTicked",
        "officialMethodsCalled", "progressIsTickCycle", "leftMainHandPlayerCovered", "rendererSynchronizationApplied",
        "crouchingEntityPoseApplied", "nativeApplied", "animationSystemComplete", "preconditions", "profiles",
        "animateModelCalls", "setAnglesCalls", "swingHandCalls", "preferredArmGetterCalls"}
    if (not isinstance(value, dict) or set(value) != expected or type(value["schemaVersion"]) is not int
            or value["schemaVersion"] != 1 or value["minecraftVersion"] != "1.21.1" or value["fixtureType"] != "ArmorStandEntity"
            or any(value[key] is not False for key in ("fixtureIsPlayer", "entityTicked", "progressIsTickCycle",
                "leftMainHandPlayerCovered", "rendererSynchronizationApplied", "crouchingEntityPoseApplied", "nativeApplied", "animationSystemComplete"))
            or any(value[key] is not True for key in ("worldNull", "officialMethodsCalled"))
            or report_bytes(value["preconditions"]) != report_bytes(PRECONDITIONS)
            or not isinstance(value["profiles"], dict) or set(value["profiles"]) != set(PROFILES)
            or any(type(value[key]) is not int or value[key] != FRAME_COUNT for key in ("animateModelCalls", "setAnglesCalls", "swingHandCalls"))
            or type(value["preferredArmGetterCalls"]) is not int or value["preferredArmGetterCalls"] != 2*FRAME_COUNT):
        raise ValueError("Action pose evaluation/World/hand/timing contract differs")
    for profile, frames in value["profiles"].items():
        if not isinstance(frames, list) or len(frames) != INPUT_CONTRACT["profiles"][profile]:
            raise ValueError("Action pose sample count differs")
        for index, frame in enumerate(frames):
            inputs = frame_inputs(profile, index)
            hand = inputs["preferredHand"]
            model = {"handSwingProgress": inputs["handSwingProgress"], "sneaking": inputs["modelSneaking"],
                     "riding": False, "child": False, "leaningPitch": 0.0, "leftArmPose": "EMPTY", "rightArmPose": "EMPTY"}
            arm = "LEFT" if hand == "OFF_HAND" else "RIGHT"
            if (not isinstance(frame, dict) or set(frame) != {"sampleIndex", "inputs", "fixtureStateBefore", "fixtureStateAfter",
                    "modelStateBefore", "modelStateAfter", "officialPreferredArmBefore", "officialPreferredArmAfter", "parts"}
                    or type(frame["sampleIndex"]) is not int or frame["sampleIndex"] != index
                    or not isinstance(frame["inputs"], dict) or set(frame["inputs"]) != set(inputs)
                    or any(type(frame["inputs"][key]) not in (int, float) or not math.isfinite(frame["inputs"][key])
                           or f32(frame["inputs"][key]) != val for key,val in inputs.items() if type(val) is float)
                    or frame["inputs"]["modelSneaking"] is not inputs["modelSneaking"] or frame["inputs"]["preferredHand"] != hand
                    or any(report_bytes(frame[key]) != report_bytes(fixture_state(hand)) for key in ("fixtureStateBefore", "fixtureStateAfter"))
                    or any(not model_state_matches(frame[key], model) for key in ("modelStateBefore", "modelStateAfter"))
                    or frame["officialPreferredArmBefore"] != arm or frame["officialPreferredArmAfter"] != arm):
                raise ValueError("Action pose same-frame state or complete model input differs")
            validate_parts(frame["parts"])
    return value


def expected_report(provenance, raw_pose, raw_class):
    if digest(raw_pose) != POSE_SHA256:
        raise ValueError("Action pose bytes differ from the reviewed official deterministic oracle")
    if digest(raw_class) != HELPER_CLASS_SHA256:
        raise ValueError("Action pose official-call helper class differs")
    validate_poses(json.loads(raw_pose))
    return {"schemaVersion": 1, "minecraftVersion": "1.21.1", "variant": VARIANT, "sources": provenance,
        "files": {"poses.json": digest(raw_pose), CLASS_FILE: digest(raw_class)},
        "evaluation": {"fixtureType": "ArmorStandEntity", "fixtureIsPlayer": False, "worldNull": True,
            "entityTicked": False, "freshEntityPerFrame": True, "freshModelPerFrame": True,
            "methods": ["LivingEntity.swingHand(Hand)", "BipedEntityModel.animateModel(LivingEntity,FFF)",
                        "PlayerEntityModel.setAngles(LivingEntity,FFFFF)", "BipedEntityModel.getPreferredArm(LivingEntity)"],
            "swingHandCalls": 43, "animateModelCalls": 43, "setAnglesCalls": 43, "preferredArmGetterCalls": 86,
            "modelInputSamples": True, "preconditions": copy.deepcopy(PRECONDITIONS)},
        "inputs": copy.deepcopy(INPUT_CONTRACT), "fieldEvidence": copy.deepcopy(FIELD_EVIDENCE),
        "coordinates": copy.deepcopy(COORDINATES),
        "integration": {"nativeApplied": False, "animationSystemComplete": False, "playerStateCaptured": False,
            "combatApplied": False, "nativeRetargeted": False, "entityTimingVerified": False,
            "crouchingEntityPoseApplied": False, "leftMainHandPlayerCaptured": False, "rendererSynchronizationApplied": False},
        "limitations": ["model_crouch is the official model.sneaking=true branch; the normal entity remains STANDING/isInSneakingPose=false.",
            "All frames use a fixed right-main-arm ArmorStand, not Player: MAIN swings RIGHT, OFF swings LEFT. Left-main-hand Player not covered.",
            "Uniform specified progress 0..1 is not a tick cycle or observed gameplay duration; entity progress remains zero and entity tick is not called.",
            "Official renderer field mappings are bytecode evidence, not an executed renderer/Player lifecycle.",
            "Real crouch Pose and normal Player/Mob construction require a valid World; no substitute World or uninitialized entity was used.",
            "No damage, target, cooldown, sprint, movement crouch, held item, or native pose/controller integration."]}


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
        raise ValueError("Action pose report differs from complete canonical source/input contract")
    verify_snapshot(snapshot)
    return report, json.loads(raw_pose), snapshot


def build(output=DEFAULT_OUTPUT, client=None, java_home=None):
    output = preflight(output)
    provenance, snapshot, client, jars, java, javac = sources(client, java_home)
    environment = dict(os.environ)
    for key in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
        environment.pop(key, None)
    with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="steve-action-pose-stage-") as temporary:
        stage = assets.output_directory(Path(temporary))
        classes = stage / "helper-classes"
        classes.mkdir()
        staged_source = stage / JAVA_SOURCE.name
        staged_source.write_bytes(snapshot[JAVA_SOURCE.resolve()])
        staged_classpath = []
        for index, path in enumerate([client, *jars]):
            raw = snapshot[Path(path).resolve()]
            target = stage / "classpath" / str(index) / Path(path).name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            if input_bytes(target) != raw:
                raise ValueError("Action pose staged fixed classpath differs")
            staged_classpath.append(target)
        commands = ([str(javac), "--release", "21", "-d", str(classes), str(staged_source)],
            [str(java), "-Djava.awt.headless=true", "-Djava.io.tmpdir="+str(stage), "-cp",
             os.pathsep.join(map(str, [classes, *staged_classpath])), "local.crimsonmc.assets.SteveActionPoseDump", str(stage / "poses.json")])
        for command in commands:
            result = subprocess.run(command, cwd=stage, env=environment, capture_output=True, text=True, timeout=45)
            if result.returncode:
                raise RuntimeError("Official action pose call failed; no synthetic fallback:\n" + result.stderr[-6000:])
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
    print(json.dumps({"output": str(assets.output_directory(args.output)), "profiles": list(PROFILES), "samples": FRAME_COUNT,
                     "posesSha256": report["files"]["poses.json"], **report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
