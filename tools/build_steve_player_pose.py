"""Replay one frozen successful owned Player capture through official MC models.

--source accepts only runtime/mc-player-tick-4tm1bcz6, not arbitrary fresh runs.
No server, game directory, process API, downloads or native renderer is used.
The producer is a real ServerPlayer; the model fixture remains an ArmorStand.
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

import build_steve_action_pose as action
import check_steve_player_context as context

ROOT, assets = action.ROOT, action.assets
DEFAULT_OUTPUT = ROOT / "build/steve-player-pose-1.21.1"
SOURCE_DIRECTORY = ROOT / "runtime/mc-player-tick-4tm1bcz6"
JAVA_SOURCE = ROOT / "tools/StevePlayerPoseDump.java"
CHECKER_SOURCE = ROOT / "tools/check_steve_player_pose.py"
CLASS_FILE = "helper-classes/local/crimsonmc/assets/StevePlayerPoseDump.class"
REPORT_NAME = "steve-player-pose-report.json"
VARIANT = "official-classic-steve-real-player-tick-state-six-joint-replay"
TICKET = "109f43d3-d1e1-49d3-99eb-dee4ec87bbfc"
SOURCE_FILE_PINS = {
    "player-tick-fixture.json": "035855694c825e1c4f02a1481fb7c466c562b38780d9e2f4a1255186bd2f12b2",
    "runner-result.json": "b8ae0a4c127f279a5d4a1eef90c5ee0f0312aa011a407975db7a741e898e2619",
}
PRODUCER_PINS = {
    "build/mc-player-tick-20261008/harness/src/main/java/local/crimsonmc/fixture/OwnedPlayerTickFixture.java": "ad4a3cbf8484ae393f2c915e8aea56e72c533bba9038cef2bcd20b11a5482fd3",
    "build/mc-player-tick-20261008/harness/owned-run.gradle": "58167f36841f5551d59de80f7b64b281a64bc82d0c9ba2546183eb4f84d5563f",
    "build/mc-player-tick-20261008/harness/run_fixture.py": "138502924fcb7993f83c2083dee3432d4ca0ead655ded969c5c6667a8ea6ff31",
    "tools/check_inventory.py": "5c217c867f39f457a06f71af2473f4d8ee1b32fb05800c7f3ed92195a2f59ffd",
    "tools/check_steve_player_context.py": "71bf898b8cb220c09c38805d35886aa0d98e9acb3f469b895934d98fd092f599",
    "minecraft/build.gradle": "df06c94ddafd8920e2c171feaf34b2a9add841ea344e2d89ce63a760ce4833fa",
}
PRESERVED_PINS = {**action.LEGACY_PINS,
    "tools/SteveActionPoseDump.java": "2d1184fc10de008f1f5f8bdb15138d202fb2ef0c915af7805c5fe782f9a1bc43",
    "tools/build_steve_action_pose.py": "e9c21321fd353047faa279d145308503585cd9c1041969ed2c412201fa322665",
    "tools/check_steve_action_pose.py": "2c36693e0ce0fac12de0f62656aa55bd7c35f0bd8a9ea6da03f49c468cfa45a1",
    "build/steve-action-pose-1.21.1/poses.json": action.POSE_SHA256,
    "build/steve-action-pose-1.21.1/" + action.CLASS_FILE: action.HELPER_CLASS_SHA256,
    "build/steve-action-pose-1.21.1/" + action.REPORT_NAME: "d6cb722878db506cba84506392c15f0f7262eda1365f3f6f4ab1bc4406866523",
}
# Filled from independent official JVM evaluation before canonical publication.
POSE_SHA256 = "9bf389fdb3eb34dfcee9b558df55138fbcf7d037b4d5287b8ae819c718d8a3a0"
HELPER_CLASS_SHA256 = "2ba8d8524a78e794d52bea4750b06f12a50492019e62f566baa66241137cce0d"
FRAME_COUNT, SAMPLE_COUNT = 32, 96
PROFILES = ("standing_main", "standing_off", "crouching_main", "crouching_off")
ENTRY_ORDER = "ServerWorld.tickEntity(player) -> ServerPlayerEntity.playerTick()"
ENTRY_POINT = "ServerWorld.tickEntity(player) then ServerPlayerEntity.playerTick()"
SCHEDULER = "Fabric START_SERVER_TICK; exactly one call to each full official entry in fixed world-before-player order per observed distinct server tick"
MISSING_LIFECYCLE = "Player is absent from world/entity and connection lists; ServerPlayNetworkHandler.tick and connected/registered scheduling are not requested"
POSE_LIMIT = 4 * 1024 * 1024
digest, report_bytes, input_bytes = action.digest, action.report_bytes, action.input_bytes
verify_snapshot, f32 = action.verify_snapshot, action.f32
FLOAT_KEYS = {"lastHandSwingProgress", "handSwingProgress", "scale", "bodyYaw", "prevBodyYaw",
    "headYaw", "prevHeadYaw", "yaw", "prevYaw", "pitch", "prevPitch", "health"}
BOOL_KEYS = {"handSwinging", "isSneaking", "isInSneakingPose", "onGround", "mainHandEmpty",
    "offHandEmpty", "chestEmpty", "usingItem", "baby", "riding", "fallFlying", "inSwimmingPose",
    "swimming", "alive", "spectator", "statusEffectsEmpty", "sleeping", "hasCustomName"}
INT_KEYS = {"age", "handSwingTicks", "fallFlyingTicks", "queuedConnectionTasks"}
STRING_KEYS = {"mainArm", "preferredHand", "activeHand", "pose", "playerName"}
STATE_KEYS = FLOAT_KEYS | BOOL_KEYS | INT_KEYS | STRING_KEYS | {"position", "previousPosition", "velocity", "interpolation"}
POINT_KEYS = {"tickDelta", "handSwingProgress", "leaningPitch", "limbSpeed", "limbPosition"}
FIXTURE_KEYS = {"schemaVersion", "runTicket", "checks", "warmup", "frames", "scope", "tickEntryPoint",
    "scheduler", "normalLifecycleMissing", "worldPath", "playerEntityId", "constructedState",
    "serverPlayerClassCodeSource", "ownedFloor", "placedState", "settledState", "playerTickCalls",
    "warmupPlayerTickCalls", "samplePlayerTickCalls", "oncePerDistinctServerTickObserved",
    "worldTickEntityCalls", "completePlayerTickMethodExecuted", "terminalState", "result"}
SCOPE_TRUE = {"fixtureConnectionNormallyConstructed", "fixtureNetworkHandlerNormallyConstructed",
    "fullServerPlayerTickCalled", "worldTickEntityCalled", "worldAgeLifecycleVerified",
    "privateQueueFieldReadOnly", "ownedWorldFloorBlocksWritten"}
SCOPE_FALSE = {"fixtureClientConnected", "registeredWithPlayerManager", "spawnedInWorld",
    "fullConnectedLifecycleVerified", "twentyHzLifecycleVerified", "privateFieldsWritten", "attackOrDamageCalled",
    "nativeApplied", "clientModelOrGameRendererVerified", "animationSystemComplete"}
RUNNER_KEYS = {"schemaVersion", "runTicket", "runtimeDirectory", "inputs", "ownedLaunchPid", "ownedProcessExitCode",
    "normalConsoleShutdown", "forcedOwnedPidStop", "productionDirectoriesUnchanged", "sourcesAndPinnedJarUnchanged",
    "production8766Or8765Requested", "runnerHttpPort", "gamePort", "nativeApplied", "failure"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def input_path(path):
    """Validate fixed input paths without treating them as build outputs."""
    path = Path(os.path.abspath(path))
    current = path
    while current != current.parent:
        require(not current.is_symlink() and not (hasattr(current, "is_junction") and current.is_junction()),
                "Player replay inputs/protected paths must not contain reparse links")
        current = current.parent
    return path.resolve()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON constant")))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid bounded JSON") from error


def keys(value, expected, name):
    require(type(value) is dict and set(value) == set(expected), name + " field inventory differs")


def integer(value, name, minimum=None):
    require(type(value) is int and (minimum is None or value >= minimum), name + " integer type/range differs")


def float_record(value):
    keys(value, {"value", "rawBits"}, "Observed float")
    number, bits = value["value"], value["rawBits"]
    require(type(number) in (int, float) and math.isfinite(number), "Observed float must be finite numeric")
    require(type(bits) is int and -(1 << 31) <= bits < (1 << 31), "Observed float rawBits must be int32")
    try:
        actual = struct.unpack("<i", struct.pack("<f", number))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError("Observed float32 overflow") from error
    require(actual == bits, "Observed float value/rawBits differs")
    return struct.unpack("<f", struct.pack("<i", bits))[0]


def vector(value):
    keys(value, {"x", "y", "z", "xRawBitsHex", "yRawBitsHex", "zRawBitsHex"}, "Observed double vector")
    for axis in "xyz":
        number, bits = value[axis], value[axis + "RawBitsHex"]
        require(type(number) in (int, float) and math.isfinite(number), "Observed vector must be finite numeric")
        require(type(bits) is str and bits == format(struct.unpack("<Q", struct.pack("<d", number))[0], "x"),
                "Observed double value/bits differs")


def validate_state(state, profile=None):
    keys(state, STATE_KEYS, "Captured Player state")
    for name in FLOAT_KEYS:
        float_record(state[name])
    for name in BOOL_KEYS:
        require(type(state[name]) is bool, "Captured boolean type differs: " + name)
    for name in INT_KEYS:
        integer(state[name], name, -1 if name == "handSwingTicks" else 0)
    for name in STRING_KEYS:
        require(type(state[name]) is str, "Captured string type differs")
    require(state["mainArm"] == "RIGHT" and state["activeHand"] in ("MAIN_HAND", "OFF_HAND")
            and state["preferredHand"] in ("MAIN_HAND", "OFF_HAND", "null"), "Captured arm/hand enum differs")
    require(state["pose"] in ("STANDING", "CROUCHING") and state["playerName"] == "CMCTickContext"
            and not state["hasCustomName"], "Captured Player pose/name outside scope")
    for name in ("position", "previousPosition", "velocity"):
        vector(state[name])
    require(type(state["interpolation"]) is list and len(state["interpolation"]) == 3, "Captured delta count differs")
    for index, point in enumerate(state["interpolation"]):
        keys(point, POINT_KEYS, "Captured interpolation")
        values = {name: float_record(point[name]) for name in POINT_KEYS}
        require(point["tickDelta"]["rawBits"] == struct.unpack("<i", struct.pack("<f", index / 2))[0],
                "Captured delta order/bits differs")
        require(0 <= values["handSwingProgress"] <= 1, "Captured progress range differs")
        require(values["leaningPitch"] == 0 and values["limbSpeed"] == 0, "Captured leaning/locomotion outside stationary scope")
    for name in ("mainHandEmpty", "offHandEmpty", "chestEmpty", "alive", "statusEffectsEmpty"):
        require(state[name] is True, "Required captured state differs: " + name)
    for name in ("usingItem", "baby", "riding", "fallFlying", "inSwimmingPose", "swimming", "spectator", "sleeping"):
        require(state[name] is False, "Unsupported captured state: " + name)
    require(state["fallFlyingTicks"] == 0, "Captured flight ticks outside scope")
    if profile is not None:
        crouch = profile.startswith("crouching_")
        hand = "OFF_HAND" if profile.endswith("_off") else "MAIN_HAND"
        require(state["preferredHand"] == hand and state["isSneaking"] is crouch
                and state["isInSneakingPose"] is crouch
                and state["pose"] == ("CROUCHING" if crouch else "STANDING"), "Captured profile/hand/Pose mismatch")
        require(state["onGround"] is True and state["queuedConnectionTasks"] == 4, "Captured sampled floor/queue evidence differs")
    return state


def validate_runner(runner):
    keys(runner, RUNNER_KEYS, "Runner")
    integer(runner["schemaVersion"], "Runner schema")
    require(runner["schemaVersion"] == 1 and runner["runTicket"] == TICKET
            and runner["runtimeDirectory"] == str(SOURCE_DIRECTORY.resolve()), "Runner identity/ticket differs")
    integer(runner["ownedLaunchPid"], "Owned launch PID", 1)
    integer(runner["ownedProcessExitCode"], "Owned exitcode")
    require(runner["ownedProcessExitCode"] == 0 and runner["failure"] is None, "Runner did not finish successfully")
    for name in ("normalConsoleShutdown", "sourcesAndPinnedJarUnchanged"):
        require(runner[name] is True, "Runner successful isolation/normal close missing")
    for name in ("forcedOwnedPidStop", "production8766Or8765Requested", "nativeApplied"):
        require(runner[name] is False, "Runner forbidden activity claim")
    keys(runner["productionDirectoriesUnchanged"], {"minecraft/src", "minecraft/build"}, "Production isolation")
    require(all(v is True for v in runner["productionDirectoriesUnchanged"].values()), "Production isolation failed")
    for name, expected in (("runnerHttpPort", 8768), ("gamePort", 25580)):
        integer(runner[name], name)
        require(runner[name] == expected, "Runner ports differ")
    keys(runner["inputs"], {"namedMergedJarRelativePath", "namedMergedJarSha256", "sourceSha256"}, "Runner inputs")
    require(runner["inputs"] == {"namedMergedJarRelativePath": context.NAMED_JAR_RELATIVE.as_posix(),
        "namedMergedJarSha256": context.JAR_SHA256, "sourceSha256": PRODUCER_PINS}, "Runner fixed source inventory differs")


def validate_player_report(value):
    keys(value, FIXTURE_KEYS, "Player fixture")
    integer(value["schemaVersion"], "Player fixture schema")
    require(value["schemaVersion"] == 1 and value["runTicket"] == TICKET and value["result"] == "pass",
            "Player fixture success/ticket differs")
    keys(value["scope"], SCOPE_TRUE | SCOPE_FALSE, "Player fixture scope")
    require(all(value["scope"][name] is True for name in SCOPE_TRUE)
            and all(value["scope"][name] is False for name in SCOPE_FALSE), "Player fixture entry/lifecycle scope differs")
    require(value["tickEntryPoint"] == ENTRY_POINT and value["scheduler"] == SCHEDULER
            and value["normalLifecycleMissing"] == MISSING_LIFECYCLE, "Player fixture official entry boundary differs")
    require(value["worldPath"] == ".\\crimsonmc-lab\\." and value["serverPlayerClassCodeSource"] ==
            "file:/" + (ROOT / context.NAMED_JAR_RELATIVE).resolve().as_posix(), "Player world/codeSource differs")
    integer(value["playerEntityId"], "Player entity ID", 1)
    require(type(value["checks"]) is list and len(value["checks"]) == 9, "Player fixture checks differ")
    names = set()
    for row in value["checks"]:
        keys(row, {"name", "passed"}, "Fixture check")
        require(type(row["name"]) is str and row["name"] not in names and row["passed"] is True, "Fixture check failed/duplicated")
        names.add(row["name"])
    require(type(value["frames"]) is list and len(value["frames"]) == FRAME_COUNT
            and type(value["warmup"]) is list and len(value["warmup"]) == 11, "Frozen real frame/warmup count differs")
    for name, expected in (("worldTickEntityCalls", 43), ("playerTickCalls", 43),
                           ("warmupPlayerTickCalls", 11), ("samplePlayerTickCalls", 32)):
        integer(value[name], name)
        require(value[name] == expected, "Actual entry call counts differ")
    require(value["oncePerDistinctServerTickObserved"] is True and value["completePlayerTickMethodExecuted"] is True,
            "Actual entry once/success evidence missing")
    prior_tick = prior_age = prior_nanos = None
    for index, frame in enumerate(value["warmup"] + value["frames"]):
        keys(frame, {"serverTick", "monotonicNanos", "profile", "profileFrame", "entryPointOrder", "before", "afterWorldTickEntity", "after"}, "Player frame")
        integer(frame["serverTick"], "Server tick", 1)
        integer(frame["profileFrame"], "Profile frame", 0)
        require(type(frame["monotonicNanos"]) is str and frame["monotonicNanos"].isdecimal(), "Monotonic clock inventory differs")
        nanos = int(frame["monotonicNanos"])
        require(frame["entryPointOrder"] == ENTRY_ORDER, "Official entry order differs")
        if prior_tick is not None:
            require(frame["serverTick"] == prior_tick + 1 and nanos > prior_nanos, "Repeated/skipped/out-of-order actual tick")
        before, middle, after = (validate_state(frame[key]) for key in ("before", "afterWorldTickEntity", "after"))
        require(middle["age"] == before["age"] + 1 and after["age"] == middle["age"]
                and (prior_age is None or before["age"] == prior_age), "Natural age entry/continuity differs")
        require(middle["previousPosition"] == before["position"], "World entry did not preserve actual prior xyz")
        require(after["lastHandSwingProgress"]["rawBits"] == before["handSwingProgress"]["rawBits"], "Actual previous swing copy differs")
        if index < 11:
            require(frame["profile"] == "natural_floor_warmup" and frame["profileFrame"] == index, "Warmup ordering differs")
        else:
            sample = index - 11
            require(frame["profile"] == PROFILES[sample // 8] and frame["profileFrame"] == sample % 8, "Sample profile ordering differs")
            validate_state(after, frame["profile"])
        prior_tick, prior_age, prior_nanos = frame["serverTick"], after["age"], nanos
    for name in ("constructedState", "placedState", "settledState", "terminalState"):
        validate_state(value[name])
    require(value["terminalState"] == value["frames"][-1]["after"]
            and value["frames"][0]["after"]["age"] == 12 and value["frames"][-1]["after"]["age"] == 43,
            "Frozen natural age/terminal state differs")
    return value


def preflight(output, source=SOURCE_DIRECTORY):
    output = assets.output_directory(Path(output))
    protected = [ROOT / "runtime", ROOT / "minecraft", ROOT / "downloads", ROOT / "tools", Path.home() / ".gradle-crimsonmc",
                 ROOT / "build/mc-player-tick-20261008", ROOT / "build/mc-player-context-20261008",
                 ROOT / "build/steve-player-model-contract-20261008", action.DEFAULT_OUTPUT,
                 action.old.DEFAULT_OUTPUT, assets.DEFAULT_OUTPUT, Path(source)]
    if output != DEFAULT_OUTPUT:
        protected.append(DEFAULT_OUTPUT)
    for path in protected:
        path = input_path(path)
        require(not (output == path or output.is_relative_to(path) or path.is_relative_to(output)), "Player pose output overlaps source/protected canonical")
    require(not output.exists(), "Player pose output already exists; never overwrite it")
    return output


def merge_snapshot(target, incoming):
    for path, raw in incoming.items():
        require(path not in target or target[path] == raw, "Player replay source snapshot conflict")
        target[path] = raw


def sources(source=SOURCE_DIRECTORY):
    source = input_path(source)
    require(source == SOURCE_DIRECTORY.resolve(), "--source accepts only the frozen successful capture, not arbitrary fresh runs")
    old_report, _, snapshot = action.load()

    def record(path, pin=None):
        path = input_path(path)
        raw = input_bytes(path, max(action.old.SOURCE_LIMIT, 128 * 1024 * 1024))
        require(pin is None or digest(raw) == pin, "Frozen player replay source fingerprint differs: " + path.name)
        merge_snapshot(snapshot, {path: raw})
        return {"path": str(path), "bytes": len(raw), "sha256": digest(raw)}, raw

    preserved = {relative: record(ROOT / relative, pin)[0] for relative, pin in PRESERVED_PINS.items()}
    capture_files = {name: record(source / name, pin)[0] for name, pin in SOURCE_FILE_PINS.items()}
    player = validate_player_report(strict_json(snapshot[(source / "player-tick-fixture.json").resolve()]))
    runner = strict_json(snapshot[(source / "runner-result.json").resolve()])
    validate_runner(runner)
    producer = {name: record(ROOT / name, pin)[0] for name, pin in PRODUCER_PINS.items()}
    named, _ = record(ROOT / context.NAMED_JAR_RELATIVE, context.JAR_SHA256)
    provenance = {"officialClientOracle": old_report["sources"], "preservedFixedFiles": preserved,
        "capture": {"runtimeDirectory": str(source), "runTicket": TICKET, "files": capture_files,
                    "producerSourceFiles": producer, "namedMergedJar": named, "entryPointOrder": ENTRY_ORDER,
                    "playerFrames": FRAME_COUNT, "interpolationDeltas": [0.0, 0.5, 1.0], "sourceAfterAges": [12, 43]},
        "helperSource": record(JAVA_SOURCE)[0], "builderSource": record(Path(__file__))[0],
        "checkerSource": record(CHECKER_SOURCE)[0]}
    verify_snapshot(snapshot)
    return provenance, player, snapshot


def validate_poses(value, player):
    expected_keys = {"schemaVersion", "minecraftVersion", "sourceType", "sourcePlayerStateCaptured", "sourceFrameCount",
        "sampleCount", "fixtureType", "fixtureIsPlayer", "worldNull", "fixtureEntityTicked", "officialMethodsCalled",
        "rendererExecuted", "nativeApplied", "animationSystemComplete", "sourceRunTicket", "samples",
        "animateModelCalls", "setAnglesCalls", "swingHandCalls", "preferredArmGetterCalls", "officialMathHelperCalls"}
    keys(value, expected_keys, "Player replay")
    require(type(value["schemaVersion"]) is int and value["schemaVersion"] == 1 and value["minecraftVersion"] == "1.21.1"
            and value["sourceType"] == "ServerPlayerEntity" and value["fixtureType"] == "ArmorStandEntity"
            and value["sourceRunTicket"] == TICKET, "Replay source/model identity differs")
    for name in ("sourcePlayerStateCaptured", "worldNull", "officialMethodsCalled"):
        require(value[name] is True, "Replay official/input evidence missing")
    for name in ("fixtureIsPlayer", "fixtureEntityTicked", "rendererExecuted", "nativeApplied", "animationSystemComplete"):
        require(value[name] is False, "Replay unsupported integration claim")
    for name, expected in (("sourceFrameCount", 32), ("sampleCount", 96), ("animateModelCalls", 96),
                           ("setAnglesCalls", 96), ("swingHandCalls", 96), ("preferredArmGetterCalls", 192), ("officialMathHelperCalls", 384)):
        integer(value[name], name)
        require(value[name] == expected, "Official replay method/sample count differs")
    require(type(value["samples"]) is list and len(value["samples"]) == SAMPLE_COUNT, "Replay sample inventory differs")
    for index, sample in enumerate(value["samples"]):
        keys(sample, {"sampleIndex", "sourceFrameIndex", "sourceDeltaIndex", "sourceServerTick", "sourceProfile", "sourceProfileFrame", "sourceAge", "inputs",
            "fixtureStateBefore", "fixtureStateAfter", "modelStateBefore", "modelStateAfter", "officialPreferredArmBefore", "officialPreferredArmAfter", "parts"}, "Replay sample")
        frame, j = player["frames"][index // 3], index % 3
        state, point = frame["after"], frame["after"]["interpolation"][j]
        for name, expected in (("sampleIndex", index), ("sourceFrameIndex", index // 3), ("sourceDeltaIndex", j),
                               ("sourceServerTick", frame["serverTick"]), ("sourceProfileFrame", frame["profileFrame"]), ("sourceAge", state["age"])):
            integer(sample[name], name)
            require(sample[name] == expected, "Replay source frame/delta reference differs")
        require(sample["sourceProfile"] == frame["profile"], "Replay profile binding differs")
        inputs = sample["inputs"]
        keys(inputs, {"handSwingProgress", "modelSneaking", "preferredHand", "limbAngle", "limbDistance", "age", "headYawDegrees", "headPitchDegrees", "tickDelta", "rawFloatBits"}, "Replay inputs")
        numeric = {"handSwingProgress": float_record(point["handSwingProgress"]), "limbAngle": float_record(point["limbPosition"]),
            "limbDistance": float_record(point["limbSpeed"]), "age": f32(f32(state["age"]) + float_record(point["tickDelta"])), "tickDelta": float_record(point["tickDelta"])}
        # This exact fixed capture has zero head/body/pitch inputs. General angle
        # conversion is deliberately done by the official MathHelper in Java.
        require(all(float_record(state[name]) == 0 for name in ("prevBodyYaw", "bodyYaw", "prevHeadYaw", "headYaw", "prevPitch", "pitch")), "Frozen capture angle scope differs")
        numeric.update({"headYawDegrees": 0.0, "headPitchDegrees": 0.0})
        keys(inputs["rawFloatBits"], numeric, "Replay input float bits")
        for name, expected in numeric.items():
            actual = float_record({"value": inputs[name], "rawBits": inputs["rawFloatBits"][name]})
            require(struct.pack("<f", actual) == struct.pack("<f", expected), "Replay input differs from actual same-frame getter/official renderer argument")
        hand = state["preferredHand"]
        require(inputs["modelSneaking"] is state["isInSneakingPose"] and inputs["preferredHand"] == hand, "Replay actual Player pose/hand mapping differs")
        model = {"handSwingProgress": numeric["handSwingProgress"], "sneaking": state["isInSneakingPose"], "riding": False, "child": False,
                 "leaningPitch": 0.0, "leftArmPose": "EMPTY", "rightArmPose": "EMPTY"}
        arm = "LEFT" if hand == "OFF_HAND" else "RIGHT"
        require(all(report_bytes(sample[name]) == report_bytes(action.fixture_state(hand)) for name in ("fixtureStateBefore", "fixtureStateAfter")), "Normal ArmorStand same-frame state differs")
        require(all(action.model_state_matches(sample[name], model) for name in ("modelStateBefore", "modelStateAfter"))
                and sample["officialPreferredArmBefore"] == arm and sample["officialPreferredArmAfter"] == arm, "Model input/preferred arm changed")
        action.validate_parts(sample["parts"])
    return value


def expected_report(provenance, player, raw_pose, raw_class):
    require(POSE_SHA256 is not None and HELPER_CLASS_SHA256 is not None, "Official replay byte pins not frozen; canonical publication unavailable")
    require(digest(raw_pose) == POSE_SHA256 and digest(raw_class) == HELPER_CLASS_SHA256, "Player pose/helper differs from frozen complete official evaluation")
    validate_poses(strict_json(raw_pose), player)
    return {"schemaVersion": 1, "minecraftVersion": "1.21.1", "variant": VARIANT, "sources": provenance,
        "files": {"poses.json": digest(raw_pose), CLASS_FILE: digest(raw_class)},
        "evaluation": {"sourceType": "ServerPlayerEntity", "sourceFrameCount": 32, "samples": 96,
            "sourceEntries": ENTRY_ORDER, "sourceAges": [12, 43], "modelFixtureType": "ArmorStandEntity", "modelFixturePose": "STANDING",
            "modelWorldNull": True, "freshModelAndFixturePerSample": True, "fixtureEntityTicked": False,
            "animateModelCalls": 96, "setAnglesCalls": 96, "swingHandCalls": 96, "preferredArmGetterCalls": 192,
            "officialMathHelperCalls": 384, "sourceStage": "frames[i].after", "frameInterpolationDeltas": [0.0, 0.5, 1.0],
            "sourceProgressFromActualGetter": True, "sourceSneakingFromActualPoseGetter": True,
            "sourceAgeNotReset": True, "sourceNaturalVelocityNotReset": True, "sixBaseJointOutputOnly": True},
        "coordinates": copy.deepcopy(action.COORDINATES),
        "integration": {"playerStateCaptured": True, "officialModelReplayedFromPlayerState": True,
            "nativeApplied": False, "animationSystemComplete": False, "rendererExecuted": False,
            "clientPlayerConstructed": False, "connectedPlayerLifecycleVerified": False, "twentyHzLifecycleVerified": False,
            "combatApplied": False, "nativeRetargeted": False, "leftMainHandPlayerCovered": False},
        "limitations": ["Only the fixed successful capture/ticket/source pins are admitted, not arbitrary fresh runs.",
            "The real unconnected/unregistered/unspawned ServerPlayer source used world.tickEntity then playerTick; connected handler tick/lifecycle not covered.",
            "Model fixture remains a fresh normal null-World ArmorStand STANDING; source real sneaking Pose maps to model.sneaking for the six base joints.",
            "Empty hands, RIGHT main arm, stationary, standing/crouching, MAIN/OFF only; nonzero leaning/locomotion and special states reject.",
            "Source actual getter progress at delta0/0.5/1 and natural age are retained; these interpolation samples do not prove a client render clock or 20Hz scheduler.",
            "Official renderer input mappings and MathHelper are used, but renderer/client entities, cloak, visibility, root matrices/scales and network interpolation are not executed.",
            "No held items, damage/knockback, native pose/controller/rig application or full animation-system acceptance."]}


def evaluate(source=SOURCE_DIRECTORY):
    """Actual offline JVM evaluation; no publication, server or synthetic fallback."""
    provenance, player, snapshot = sources(source)
    oracle = provenance["officialClientOracle"]
    client = Path(oracle["client"]["path"])
    jars = [Path(item["path"]) for item in oracle["externalClasspath"]]
    java, javac = (Path(oracle["javaTools"][name]["path"]) for name in ("java", "javac"))
    environment = dict(os.environ)
    for name in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
        environment.pop(name, None)
    with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="steve-player-pose-stage-") as temporary:
        stage = assets.output_directory(Path(temporary)); classes = stage / "helper-classes"; classes.mkdir()
        staged_source = stage / JAVA_SOURCE.name; staged_source.write_bytes(snapshot[JAVA_SOURCE.resolve()])
        staged_player = stage / "player-tick-fixture.json"; staged_player.write_bytes(snapshot[(SOURCE_DIRECTORY / staged_player.name).resolve()])
        classpath = []
        for index, path in enumerate([client, *jars]):
            target = stage / "classpath" / str(index) / path.name; target.parent.mkdir(parents=True)
            raw = snapshot[path.resolve()]; target.write_bytes(raw)
            require(input_bytes(target) == raw, "Staged fixed classpath differs")
            classpath.append(target)
        verify_snapshot(snapshot)
        commands = ([str(javac), "--release", "21", "-cp", os.pathsep.join(map(str, classpath)), "-d", str(classes), str(staged_source)],
            [str(java), "-Djava.awt.headless=true", "-Djava.io.tmpdir=" + str(stage), "-cp", os.pathsep.join(map(str, [classes, *classpath])),
             "local.crimsonmc.assets.StevePlayerPoseDump", str(staged_player), str(stage / "poses.json")])
        for command in commands:
            result = subprocess.run(command, cwd=stage, env=environment, capture_output=True, text=True, timeout=45)
            if result.returncode:
                raise RuntimeError("Actual official Player replay failed; no synthetic fallback:\n" + result.stderr[-6000:])
        raw_pose, raw_class = input_bytes(stage / "poses.json", POSE_LIMIT), input_bytes(stage / CLASS_FILE, POSE_LIMIT)
        validate_poses(strict_json(raw_pose), player)
        verify_snapshot(snapshot)
    return provenance, player, snapshot, raw_pose, raw_class


def build(output=DEFAULT_OUTPUT, source=SOURCE_DIRECTORY):
    output = preflight(output, source)
    provenance, player, snapshot, raw_pose, raw_class = evaluate(source)
    report = expected_report(provenance, player, raw_pose, raw_class)
    verify_snapshot(snapshot)
    output = preflight(output, source); output.parent.mkdir(parents=True, exist_ok=True); output.mkdir()
    for relative, raw in {"poses.json": raw_pose, CLASS_FILE: raw_class, REPORT_NAME: report_bytes(report)}.items():
        path = output / relative; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    verify_snapshot(snapshot)
    load(output)
    return report


def load(output=DEFAULT_OUTPUT):
    output = assets.output_directory(Path(output))
    provenance, player, snapshot = sources()
    files = {name: input_bytes(output / name, POSE_LIMIT) for name in (REPORT_NAME, "poses.json", CLASS_FILE)}
    merge_snapshot(snapshot, {(output / name).resolve(): raw for name, raw in files.items()})
    report = strict_json(files[REPORT_NAME])
    expected = expected_report(provenance, player, files["poses.json"], files[CLASS_FILE])
    require(report == expected and files[REPORT_NAME] == report_bytes(expected), "Player replay complete canonical report differs")
    verify_snapshot(snapshot)
    return report, strict_json(files["poses.json"]), snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Only the frozen successful runtime/mc-player-tick-4tm1bcz6 capture")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build(args.output, args.source)
    print(json.dumps({"output": str(assets.output_directory(args.output)), "source": str(SOURCE_DIRECTORY.resolve()),
                      "samples": SAMPLE_COUNT, "posesSha256": report["files"]["poses.json"], **report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
