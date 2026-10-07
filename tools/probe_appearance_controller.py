"""Observe the controlled actor's fixed appearance-controller chain, read-only.

No native function is called, no HTTP endpoint is contacted and no heap scan is
performed. Unknown types, incomplete reads and unstable links stop interpretation.
Pointer-bearing output is confined to ignored runtime JSON files.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import time

import probe_characters as core
import probe_character_roster as roster

ROOT = Path(__file__).resolve().parents[1]
WORLD_GLOBAL = 0x6D69190
WORLD_ANCHORS = (0x361B87, 0x36256A, 0x36DCEC)
WORLD_PATTERN = "48 8B 05 ?? ?? ?? ?? 48 8B 48 30 48 8B 83 A0 00 00 00 48 39 41 58"
CONTROLLER_VTABLE = 0x559DD98
SCENE_VTABLE = 0x5B409A0
SCENE_GETTER = 0x2D091C0
SCENE_META = 0x6D6C850
SCENE_META_VTABLE = 0x557CFC0
SCENE_META_TYPE = ".?AV?$ReflectMetaObjectBind@VCharacterScene@pa@@$0A@@pa@@"
SCENE_PARAM_VTABLE = 0x5B38478
SKINNED_MESH_VTABLE = 0x5B4C6C0
SKINNED_MESH_GETTER = 0x2D88B10
SKINNED_MESH_META = 0x6D6A160
SKINNED_MESH_META_VTABLE = 0x55739A0
SKINNED_MESH_META_TYPE = ".?AV?$ReflectMetaObjectBind@VSkinnedMeshComponent@pa@@$0A@@pa@@"
ANONYMOUS_RESOURCE_VTABLE = 0x5B3FC58
RENDER_INPUT_PROPERTIES = {"pac": (0xD8, 0x5B37368), "pab": (0xE8, 0x5B43050)}
INITIAL_APPEARANCE_INPUT_OFFSET = 0x168
MAX_RENDER_INPUT_PATH_BYTES = 512
# Constructor/owner/string consumers prove declared inputs only. These are not
# assumed to be the paths consumed by the selected render resource/descriptor.
INPUT_PATH_WINDOWS = {
    0x2D96DD0: bytes.fromhex("ba10000000b93800000041382c377407e8938ca501eb05e8c48ba501488bd84885c0751be8772058fe4533c94533c0ba01000000b9020000a0ff153943450248895c24684885db740a488bcbe80f89edffeb03488bc54889afd80000004885c07407488987d8000000"),
    0x2C6F78D: bytes.fromhex("488d412848894424484889442450488d0d9e61df03488908488d05bc7bec02488903"),
    0x2D96E39: bytes.fromhex("4c8d3500ebcc034c89b7e0000000ba10000000b93800000041803c37007407e81b8ca501eb05e84c8ba501"),
    0x2D96EE0: bytes.fromhex("488d4328488944247048894424784c8930488d0558c1da02488903"),
    0x2D96F04: bytes.fromhex("4889afe80000004885db740748899fe8000000"),
    0x2D97149: bytes.fromhex("488b9fd800000048397b10741e488b07488bcfff908801000084c07406804b1a08eb0848897b1066897318488b9fe800000048397b10741e488b07488bcfff908801000084c07406804b1a08eb0848897b1066897318"),
    0x2D9BBE8: bytes.fromhex("488bb3d8000000488b4628488b084885c974058039007554"),
    0x2D9BC54: bytes.fromhex("488d05ddb2d90248894424204c8d0d45787d024c8d051e102104488b93d8000000488bcbe803390000"),
    0x2D9BC7D: bytes.fromhex("488d05d461da0248894424204c8d0d1c787d024c8d05fd0f2104488b93e8000000488bcbe8da380000"),
    0x2D9F5A3: bytes.fromhex("488b42284c8b104d85d20f842c010000450fb61a4584db0f841f010000498bc248ffc04180fb2e75034c8bd0440fb6184584db75eb488b9424c0000000492bd2410fb60a410fb604122bc8750749ffc285c075ec85c90f8487000000"),
    0x47B6EA: bytes.fromhex("488b39488bd9488b0a488d1546a25e0648890b483bca740b8b411085c07804f0ff4110"),
    0x5B36F38: b"pac\0",
    0x5B41E58: b"pab\0",
    # Initial Appearance loader key: callback output+30 is copied into the
    # newly constructed exact Skinned +168 held string. This is an input key,
    # not a loaded prefab list, selected PAC or rendered descriptor.
    0x2D97018: bytes.fromhex("48c787580100000000803f4889af600100004c89b7680100004889af70010000"),
    0x46B1D3: bytes.fromhex("4885db740a488bcbe870bb9202eb03488bc648894588"),
    0x46B278: bytes.fromhex("498b57384885d274144883c230488b4d884881c168010000e84b040100"),
    0x2439DB6: bytes.fromhex("4c8be9488b71104889b5581e0000488d5918488b412848833800"),
    0x243A340: bytes.fromhex("488d4e30488bd3e8941304fe"),
    0x243A389: bytes.fromhex("4c8d85d0150000488d5580488bcee8a4e6ffff"),
}
# Separate opt-in contract: the constructor and consumers prove only the +68
# held reference, not a complete resource class, descriptor or native ABI.
RESOURCE_LINK_WINDOWS = {
    0x109DB74F: bytes.fromhex("488d05024516f5488901"),
    0x109DB78F: bytes.fromhex("897b6048897b68"),
    0x2CC7E55: bytes.fromhex("498d7668488d7b68483bf77436488b06483907742e488bcfe81e2f6cfd488b0e48890f4885c9741b807914007406f0ff4110eb088b4110ffc0894110488b07c6401601"),
    0x2DEFE18: bytes.fromhex("488b41184889442420488b412048894424280fb64128488b7cc420488b5f684885db7425807b1501741f8b5b38"),
}
CODE_WINDOWS = {
    # Existing native callers, not entry points for this diagnostic to invoke.
    0x6298DD: bytes.fromhex("488b4708488b4868488b4140488b88b8000000488b5920488d542430488bcbe8cf2c1000488d542440488bcbe892271000488bcbe83ad30f00"),
    0x726C7D: bytes.fromhex("488b416033ff4885c075048bcfeb0f488b4008488d48d84885c0480f44cfe800cad4ff4885c00f848a010000"),
    # Exact resource-class writes, name getter, mesh rows and FF consumers.
    0x732B80: bytes.fromhex("488d0549c5e604488906"),
    0x733074: bytes.fromhex("488d0595c0e604488906"),
    0x7349B5: bytes.fromhex("488d0594a7e604488906"),
    0x48D670: bytes.fromhex("488b4120488b00c3"),
    0x72C299: bytes.fromhex("498b81280100004d6bf8584c0378280fb65101440fb6690244886d7f"),
    0x72C2B5: bytes.fromhex("498b89100100004885c9742180791501741b8b414085c07414413bc0760f488b413841803c00ff7404b001eb0232c04180fdff751884c0740b488b4138450fb62c00eb05450fb66f1044886d7f418b4f08410fb6c53bc10f8369020000"),
    0x92ECA42: bytes.fromhex("4c8b89100100004d85c9741f41807915017418413951307612498b41284189d341803c03ff7404b001eb0530c04189d34969d398000000480353484180f8ff751784c0740b498b4128450fb60403eb08440fb68282000000"),
    0x9311225: bytes.fromhex("410fb68080000000440fb6d24c8b5c24284889cb418801410fb69081000000418813"),
    # Scene reflection lookup/getter, constructor writes, owner weak unwrap,
    # owned parameter constructor and the native two-buffer consumer. These
    # bytes were re-read from the pinned EXE, not accepted from research JSON.
    0x4736B1: bytes.fromhex("4883ec20488bf9e8e330ffff488b9f10020000488bf08b8f18020000488d3ccb483bdf744d66660f1f8400000000004c8b33498bce498b06ff5008"),
    0x2D091C0: bytes.fromhex("e9dbd575fd"),
    0x4667EF: bytes.fromhex("488d05ca671105"),
    0x466833: bytes.fromhex("488d0516609006"),
    0x2D0AB12: bytes.fromhex("488d05875ee302488901"),
    0x2D0AB8E: bytes.fromhex("b9000200004738243e7407e8da4eae01eb05e80b4eae01488bd8"),
    0x2D0ABD2: bytes.fromhex("488bd7488bcbe8c326f7ff488bc8eb03498bcc48898fa0000000"),
    0x2D0B807: bytes.fromhex("498b47604885c07505498bcdeb0f488b4008488d48d84885c0490f44cd48894d408b811802000085c00f84520100004d8be5448be80f1f4000488b8110020000"),
    0x2C7D2D8: bytes.fromhex("488d0599b1eb02488901"),
    0x2C7D324: bytes.fromhex("4885ff7425807f3d00751f488d4f28e8387e75fd488943504885c0740d807804007405f0ff00eb02ff00"),
    0x7268A3: bytes.fromhex("488b40784885c07413488b40084885c0740a44386015488d48d87403498bcc488b89a8000000488b4118488945e8488b4120488945f00fb641284c8b6cc5e8"),
    # Actual Scene+78 identity, independently checked against the pinned PE.
    0x2D96D6A: bytes.fromhex("488d054f59db02488901"),
    0x2D88B10: bytes.fromhex("e90b775dfd"),
    0x36026F: bytes.fromhex("488d052a372105"),
    0x3602B3: bytes.fromhex("488d05a69ea006"),
    # Native new-resource primary pointer and old-resource virtual destructor.
    # Identity-only observation below does not follow the consumed +0x68 field.
    0x2DF025A: bytes.fromhex("488b024c8b7068"),
    0x2DF03FF: bytes.fromhex("488b134c8b02ba01000000488bcb41ffd0"),
}
TYPES = {
    "manager": ".?AVClientActorManager@pa@@",
    "user": ".?AVClientUserActor@pa@@",
    "actor": ".?AVClientChildOnlyInGameActor@pa@@",
    "control": ".?AVClientCharacterControlActorComponent@pa@@",
    "controller": ".?AVCharacterCustomizationController@pa@@",
    "owner": ".?AVSceneObjectClient@pa@@",
}
RESOURCE_TYPES = {
    "meshParams": (0x128, 0x58, 0x559F0D0, ".?AVCustomizationMeshParamData@pa@@"),
    "preset": (0x110, 0x70, 0x559F150, ".?AVCharacterCustomizationData@pa@@"),
    "decorationParams": (0x130, 0x98, 0x559F110, ".?AVCustomizationDecorationParamData@pa@@"),
}
MAX_OWNER_COMPONENTS = 256
SAMPLE_GAP_SECONDS = 0.05


class ProbeError(RuntimeError):
    pass


def pointer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or not 0x10000 <= value < 2**47 or value % 8:
        raise ProbeError(f"{name} is null, unaligned or outside the reviewed address bounds")
    return value


def read(reader, address, size, name):
    if not isinstance(size, int) or not 1 <= size <= 4096:
        raise ProbeError(f"{name} read exceeds the fixed diagnostic bound")
    raw = reader.read(address, size)
    if raw is None or len(raw) != size:
        raise ProbeError(f"{name} complete readable span is unavailable")
    return raw


def value(reader, address, name, fmt="<Q"):
    return struct.unpack(fmt, read(reader, address, struct.calcsize(fmt), name))[0]


def typed(reader, address, base, length, name, *, context=None, evidence=None):
    """Keep exact type gates; optional evidence records only existing identity reads.

    A qword at vtable-8 is merely a candidate locator until its header passes.
    In particular, code bytes at that address are not labelled verified RTTI.
    """
    label = context or name
    expected = (SCENE_META_TYPE if name == "sceneMetadata" else SKINNED_MESH_META_TYPE
                if name == "skinnedMeshMetadata" else TYPES[name] if name in TYPES else RESOURCE_TYPES[name][3])
    if evidence is not None:
        evidence.update(pointer=hex(address), context=label, expectedRtti=expected,
            typeGatePassed=False, completePrimaryLocatorVerified=False,
            candidateLocatorFieldsInterpretedAsVerifiedRtti=False, failedChecks=[])

    def record(**fields):
        if evidence is not None:
            evidence.update(fields)

    try:
        pointer(address, label)
        vt = value(reader, address, label + " vtable")
        record(vtablePointer=hex(vt))
        if not base + 8 <= vt <= base + length - 8:
            record(failedChecks=["vtable-main-image-bounds"])
            raise ProbeError(f"{label} vtable escaped the main image")
        record(vtableRva=hex(vt - base))
        col = value(reader, vt - 8, label + " RTTI locator")
        record(candidateLocatorPointer=hex(col))
        if not base <= col <= base + length - 24:
            record(failedChecks=["locator-main-image-bounds"])
            raise ProbeError(f"{label} RTTI locator escaped the main image")
        record(candidateLocatorRva=hex(col - base))
        raw = read(reader, col, 24, label + " RTTI locator")
        sig, offset, ctor, desc, hierarchy, selfrva = struct.unpack("<6I", raw)
        record(candidateLocatorHeaderHex=raw.hex(), candidateLocatorFields={
            "signature": sig, "primaryThisOffset": offset, "constructorDisplacement": ctor,
            "typeDescriptorRva": hex(desc), "classHierarchyRva": hex(hierarchy), "selfRva": hex(selfrva)})
        failed = [key for valid, key in ((sig == 1, "signature-equals-one"),
            (offset == 0, "primary-this-offset-zero"), (col - selfrva == base, "locator-self-rva"),
            (0 < desc <= length - 208, "type-descriptor-main-image-bounds"),
            (0 < hierarchy < length, "class-hierarchy-main-image-bounds")) if not valid]
        record(failedChecks=failed)
        if failed:
            raise ProbeError(f"{label} RTTI does not describe a complete primary object: " + ", ".join(failed))
        record(completePrimaryLocatorVerified=True, candidateLocatorFieldsInterpretedAsVerifiedRtti=True)
        actual = reader.rtti(address, base, length)
        record(observedRtti=actual)
        if actual != expected:
            record(failedChecks=["exact-reviewed-rtti"])
            raise ProbeError(f"{label} RTTI differs from the reviewed type: {actual}")
        if name == "controller" and vt - base != CONTROLLER_VTABLE:
            record(failedChecks=["exact-controller-vtable"])
            raise ProbeError("Controller vtable differs from the fixed EXE layout")
        if name in RESOURCE_TYPES and vt - base != RESOURCE_TYPES[name][2]:
            record(failedChecks=["exact-resource-vtable"])
            raise ProbeError(f"{label} vtable differs from the fixed resource class")
        if name == "sceneMetadata" and vt - base != SCENE_META_VTABLE:
            record(failedChecks=["exact-scene-metadata-vtable"])
            raise ProbeError("Scene reflection metadata vtable differs from the fixed EXE")
        if name == "skinnedMeshMetadata" and vt - base != SKINNED_MESH_META_VTABLE:
            record(failedChecks=["exact-skinned-mesh-metadata-vtable"])
            raise ProbeError("Skinned mesh reflection metadata vtable differs from the fixed EXE")
        record(typeGatePassed=True)
        return {"pointer": hex(address), "rtti": actual, "vtableRva": hex(vt - base)}
    except ProbeError as error:
        record(failureReason=str(error))
        raise


def code_windows(*, render_resource_links=False, render_input_paths=False):
    return {**CODE_WINDOWS, **(RESOURCE_LINK_WINDOWS if render_resource_links else {}),
            **(INPUT_PATH_WINDOWS if render_input_paths else {})}


def validate_code(reader, base, length, *, render_resource_links=False, render_input_paths=False):
    if not 0 < length <= core.MAX_IMAGE_SIZE:
        raise ProbeError("Main image exceeds the reviewed bounds")
    if any(rva > length - size for rva, size in ((WORLD_GLOBAL, 8), (CONTROLLER_VTABLE, 8),
            (SCENE_META, 24), (SCENE_META_VTABLE, 8), (SCENE_VTABLE, 16), (SCENE_PARAM_VTABLE, 8),
            (SKINNED_MESH_META, 24), (SKINNED_MESH_META_VTABLE, 8), (SKINNED_MESH_VTABLE, 16))):
        raise ProbeError("Fixed world global or reviewed vtable/metadata escaped the main image")
    if render_resource_links and ANONYMOUS_RESOURCE_VTABLE > length - 8:
        raise ProbeError("Anonymous constructor vtable escaped the main image")
    if render_input_paths and any(vtable > length - 8 for _, vtable in RENDER_INPUT_PROPERTIES.values()):
        raise ProbeError("Declared input property constructor vtable escaped the main image")
    windows = code_windows(render_resource_links=render_resource_links, render_input_paths=render_input_paths)
    for rva, expected in windows.items():
        if rva > length - len(expected) or read(reader, base + rva, len(expected), "native chain code") != expected:
            raise ProbeError("Native chain code bytes differ from the fixed EXE contract")
    pattern = core.pattern(WORLD_PATTERN)
    size = len(WORLD_PATTERN.split())
    for rva in WORLD_ANCHORS:
        if rva > length - size:
            raise ProbeError("World anchor escaped the main image")
        raw = read(reader, base + rva, size, "world anchor")
        if pattern.fullmatch(raw) is None:
            raise ProbeError("World anchor differs from the fixed source signature")
        if rva + 7 + struct.unpack_from("<i", raw, 3)[0] != WORLD_GLOBAL:
            raise ProbeError("The three fixed world anchors do not agree")


def loaded_options(reader, base, length, controller, controller_raw, selections, observed):
    """Read reviewed resource containers; descriptor names are candidate inputs.

    This does not assert the current render scene consumed these inputs. Decoration
    final bounds depend on native palette data which this diagnostic never follows.
    """
    watched = {}
    resources = {}
    info = {"state": "notReady", "resources": {}, "meshGroups": [], "decorationGroups": [],
            "meshGroupChoiceBoundsVerified": False, "decorationDeclaredBoundsObserved": False,
            "decorationComputedBoundsVerified": False, "renderedDescriptorVerified": False,
            "slotSemanticsVerified": False, "scope": "current selections and declared resource fields only"}
    observed["loadedOptions"] = info

    def get(address, size, name):
        raw = read(reader, address, size, name)
        watched[(address, size, name)] = raw
        return raw

    def name_from_holder(holder, label):
        pointer(holder, label + " string holder")
        chars = struct.unpack("<Q", get(holder, 8, label + " chars pointer"))[0]
        if not 0x10000 <= chars < 2**47:
            raise ProbeError(label + " chars pointer is outside reviewed bounds")
        result = b""
        for at in range(0, 512, 32):
            part = read(reader, chars + at, 32, label + " chars")
            end = part.find(b"\0")
            if end >= 0:
                result += part[:end + 1]
                watched[(chars, len(result), label + " chars reread")] = result
                text = result[:-1].decode("utf-8")
                if any(ord(c) < 32 for c in text):
                    raise ProbeError(label + " contains unreviewed control characters")
                return text
            result += part
        raise ProbeError(label + " has no terminator within the 512-byte bound")

    def vector(raw, offset, maximum, label):
        array, count, capacity = struct.unpack_from("<QII", raw, offset)
        if not 0 <= count <= maximum or not count <= capacity <= 4096:
            raise ProbeError(label + " count/capacity exceeds the diagnostic bounds")
        if count:
            pointer(array, label + " array")
        return array, count, capacity

    for name, (offset, size, _, _) in RESOURCE_TYPES.items():
        address = struct.unpack_from("<Q", controller_raw, offset)[0]
        watched[(controller + offset, 8, name + " link")] = struct.pack("<Q", address)
        if not address:
            info["resources"][name] = {"present": False}
            continue
        entry = typed(reader, address, base, length, name)
        raw = read(reader, address, size, name + " allocation")
        flag = get(address + 0x15, 1, name + " invalidation flag")[0]
        if flag != 0:
            raise ProbeError(name + " is invalidated or has an unknown resource flag")
        holder = struct.unpack("<Q", get(address + 0x20, 8, name + " name holder"))[0]
        entry.update(present=True, resourceName=name_from_holder(holder, name), invalidationFlag=flag)
        info["resources"][name] = entry
        resources[name] = (address, raw)
    preset = {"mesh": b"", "decoration": b""}
    if "preset" in resources:
        address, raw = resources["preset"]
        for name, offset, maximum in (("mesh", 0x38, 16), ("decoration", 0x28, 250)):
            directory = get(address + offset, 16, "preset " + name + " directory")
            array, count, capacity = vector(directory, 0, maximum, "preset " + name)
            preset[name] = get(array, count, "preset " + name + " bytes") if count else b""
            info["resources"]["preset"][name] = {"count": count, "capacity": capacity,
                                                     "selectionBytesHex": preset[name].hex()}
    if "meshParams" in resources:
        address, _ = resources["meshParams"]
        directory = get(address + 0x28, 16, "mesh group directory")
        array, count, capacity = vector(directory, 0, 16, "mesh groups")
        info["meshGroupCount"], info["meshGroupCapacity"] = count, capacity
        current = bytes.fromhex(selections["mesh"]["selectionBytesHex"])
        info["meshSelectionCoverage"] = {"selectionCount": len(current), "groupCount": count,
            "selectionGroupCountsMatch": len(current) == count,
            "unmappedSelectionCount": max(0, len(current) - count),
            "unmappedSelectionBytesHex": current[count:].hex(),
            "missingSelectionCount": max(0, count - len(current))}
        for index in range(count):
            row = array + index * 0x58
            options = get(row, 16, "mesh option directory")
            choices, size, cap = vector(options, 0, 256, "mesh group options")
            default = get(row + 0x10, 1, "mesh group default")[0]
            requested = current[index] if index < len(current) else None
            effective, source = requested, "selection"
            if requested == 0xFF:
                effective, source = default, "groupDefault"
                if index < len(preset["mesh"]) and preset["mesh"][index] != 0xFF:
                    effective, source = preset["mesh"][index], "preset"
            group = {"index": index, "optionCount": size, "optionCapacity": cap,
                     "defaultChoice": default, "rawChoice": requested,
                     "fallbackCandidate": effective, "fallbackSource": source,
                     "currentOptionInBounds": effective is not None and effective < size,
                     "nativeWouldSkipOutOfBoundsCandidate": effective is not None and effective >= size,
                     "prefabNames": [], "renderedDescriptorVerified": False}
            info["meshGroups"].append(group)
            if requested is not None and requested != 0xFF and requested >= size:
                raise ProbeError("Direct mesh choice is outside its real group's option count")
            if group["currentOptionInBounds"]:
                option = choices + effective * 0x120
                paths = get(option, 16, "current mesh prefab directory")
                refs, refs_count, refs_capacity = vector(paths, 0, 32, "current mesh prefab references")
                group["prefabReferenceCount"], group["prefabReferenceCapacity"] = refs_count, refs_capacity
                names = get(refs, refs_count * 8, "current mesh prefab references") if refs_count else b""
                for i in range(refs_count):
                    holder = struct.unpack_from("<Q", names, i * 8)[0]
                    group["prefabNames"].append(name_from_holder(holder, "mesh prefab"))
        info["meshGroupChoiceBoundsVerified"] = bool(count) and all(
            g["currentOptionInBounds"] or (g["optionCount"] == 0 and g["rawChoice"] == 0xFF)
            for g in info["meshGroups"])
    if "decorationParams" in resources:
        address, _ = resources["decorationParams"]
        directory = get(address + 0x48, 16, "decoration group directory")
        array, count, capacity = vector(directory, 0, 250, "decoration groups")
        info["decorationGroupCount"], info["decorationGroupCapacity"] = count, capacity
        current = bytes.fromhex(selections["decoration"]["selectionBytesHex"])
        for index in range(count):
            row = array + index * 0x98
            fields = get(row + 0x7E, 6, "decoration declared mode/range/default")
            category, mode, minimum, maximum, default, palette_index = fields
            mesh_slot = struct.unpack("<i", get(row + 0x3C, 4, "decoration mesh slot reference"))[0]
            requested = current[index] if index < len(current) else None
            fallback, source = requested, "selection"
            if requested == 0xFF:
                fallback, source = default, "groupDefault"
                if index < len(preset["decoration"]) and preset["decoration"][index] != 0xFF:
                    fallback, source = preset["decoration"][index], "preset"
            info["decorationGroups"].append({"index": index, "rawChoice": requested,
                "fallbackCandidate": fallback, "fallbackSource": source, "declaredMin": minimum,
                "declaredMax": maximum, "declaredDefault": default, "categoryByte": category,
                "modeByte": mode, "paletteIndexByte": palette_index, "meshSlotReference": mesh_slot,
                "nativeComputedBoundsVerified": False})
        info["decorationDeclaredBoundsObserved"] = bool(count)
    # These are constant resource inputs, not an atomic scene snapshot. Re-read all
    # interpreted bytes and exact type gates, including name holders and payloads.
    for (address, size, label), expected in watched.items():
        if read(reader, address, size, label + " stability") != expected:
            raise ProbeError("Loaded appearance resource fields changed during reads")
    for name, (address, _) in resources.items():
        expected = {key: info["resources"][name][key] for key in ("pointer", "rtti", "vtableRva")}
        if typed(reader, address, base, length, name) != expected:
            raise ProbeError("Loaded appearance resource type changed during reads")
    selections["mesh"]["loadedOptionBoundsVerified"] = (info["meshGroupChoiceBoundsVerified"] and
        info["meshSelectionCoverage"]["selectionGroupCountsMatch"]) if "meshSelectionCoverage" in info else False
    selections["decoration"]["loadedOptionBoundsVerified"] = False
    info["state"] = "observed" if info.get("meshGroupCount", 0) and info.get("decorationGroupCount", 0) else "notReady"
    info["limitations"] = ["FF fallback candidates are native inputs; currently rendered meshes are not verified.",
        "Decoration declared ranges are not final bounds: native palette and mesh-dependent mapping are not decoded.",
        "Group indices and prefab names do not establish nude/armor/weapon slot semantics.",
        "Mesh group bounds exclude any selection bytes without a corresponding loaded group.",
        "Names require readable 32-byte chunks; a page-end terminator can conservatively reject an otherwise valid name."]


def resource_identity(reader, address, base, length, evidence):
    """Observe only standard primary RTTI; do not admit an unknown resource layout.

    Called only for the two fresh controlled-Scene selector inputs. It deliberately
    does not use Reader.rtti's second pointer walk: every byte and image bound used
    here is retained and re-read, including the bounded, terminated type name.
    """
    evidence.update(pointer=hex(address), identityOnly=True, layoutInterpreted=False,
                    exactResourceClassVerified=False, rttiNameObserved=False, failedChecks=[])
    watched = []

    def get(at, size, label):
        raw = read(reader, at, size, label)
        watched.append((at, size, raw, label))
        return raw

    def require(valid, key):
        if not valid:
            evidence["failedChecks"].append(key)
            raise ProbeError("Render resource identity rejected: " + key)

    try:
        pointer(address, "render resource primary pointer")
        vt = struct.unpack("<Q", get(address, 8, "render resource vtable"))[0]
        evidence["vtablePointer"] = hex(vt)
        require(base + 8 <= vt <= base + length - 8, "vtable-main-image-bounds")
        evidence["vtableRva"] = hex(vt - base)
        col = struct.unpack("<Q", get(vt - 8, 8, "render resource locator"))[0]
        evidence["candidateLocatorPointer"] = hex(col)
        require(base <= col <= base + length - 24, "locator-main-image-bounds")
        raw = get(col, 24, "render resource primary locator")
        sig, offset, ctor, desc, hierarchy, selfrva = struct.unpack("<6I", raw)
        evidence["candidateLocatorHeaderHex"] = raw.hex()
        evidence["candidateLocatorRva"] = hex(col - base)
        evidence["candidateLocatorFields"] = dict(signature=sig, primaryThisOffset=offset,
            constructorDisplacement=ctor, typeDescriptorRva=hex(desc),
            classHierarchyRva=hex(hierarchy), selfRva=hex(selfrva))
        for valid, key in ((sig == 1, "signature-equals-one"), (offset == 0, "primary-this-offset-zero"),
            (col - selfrva == base, "locator-self-rva"),
            (0 < desc <= length - 208, "type-descriptor-main-image-bounds"),
            (0 < hierarchy < length, "class-hierarchy-main-image-bounds")):
            require(valid, key)
        name = get(base + desc + 16, 192, "render resource RTTI name")
        require(b"\0" in name, "bounded-terminated-rtti-name")
        text = name.split(b"\0", 1)[0]
        require(bool(text) and all(32 <= byte < 127 for byte in text), "ascii-rtti-name")
        evidence["rtti"] = text.decode("ascii")
        for at, size, expected, label in watched:
            require(read(reader, at, size, label + " stability") == expected, "stable-identity-bytes")
        evidence["rttiNameObserved"] = True
        return {key: evidence[key] for key in ("pointer", "vtableRva", "rtti", "candidateLocatorRva",
                                               "candidateLocatorHeaderHex")}
    except ProbeError as error:
        evidence["failureReason"] = str(error)
        raise


def linked_resource_header(reader, address, base, length, evidence, *, watch=None):
    """Read one exact anonymous parent's +68 reference and nested vtable only.

    There is no RTTI fallback: this is an independent constructor/consumer field
    contract. A nested vtable in the image is only an observed pointer, never a
    class admission. No nested member, locator, name or descriptor is read.
    """
    evidence.update(pointer=hex(address), state="rejected", anonymousParentVtableVerified=False,
        primaryMsvcRttiVerified=False, nestedClassVerified=False, nestedLayoutInterpreted=False,
        descriptorVerified=False, linkFieldObserved=False, nestedPrimaryHeaderObserved=False,
        identityMode="exact-constructor-vtable/held-reference-consumer-only", failedChecks=[])
    watched = []

    def get(at, label):
        raw = read(reader, at, 8, label)
        watched.append((at, raw, label))
        if watch is not None:
            watch(at, raw, label)
        return struct.unpack("<Q", raw)[0]

    def require(valid, key):
        if not valid:
            evidence["failedChecks"].append(key)
            raise ProbeError("Anonymous render resource link rejected: " + key)

    try:
        pointer(address, "anonymous render resource parent")
        vt = get(address, "anonymous resource parent vtable")
        evidence["parentVtablePointer"] = hex(vt)
        require(vt == base + ANONYMOUS_RESOURCE_VTABLE, "exact-anonymous-constructor-vtable")
        evidence.update(parentVtableRva=hex(vt - base), anonymousParentVtableVerified=True)
        nested = get(address + 0x68, "anonymous resource nested reference")
        evidence.update(nestedPointer=hex(nested), nestedPresent=bool(nested), linkFieldObserved=True)
        if nested:
            pointer(nested, "anonymous resource nested primary")
            nested_vt = get(nested, "anonymous resource nested vtable")
            evidence["nestedVtablePointer"] = hex(nested_vt)
            require(base + 8 <= nested_vt <= base + length - 8, "nested-vtable-main-image-bounds")
            evidence.update(nestedVtableRva=hex(nested_vt - base), nestedPrimaryHeaderObserved=True)
        for at, expected, label in watched:
            require(read(reader, at, 8, label + " stability") == expected, "stable-linked-header-bytes")
        evidence["state"] = "headerObserved" if nested else "emptyNestedReference"
        return {key: evidence[key] for key in ("pointer", "parentVtableRva", "nestedPointer",
                "nestedPresent", "linkFieldObserved", "nestedPrimaryHeaderObserved", "state")} | (
            {"nestedVtableRva": evidence["nestedVtableRva"]} if nested else {})
    except ProbeError as error:
        evidence["state"] = "rejected"
        evidence["failureReason"] = str(error)
        raise


def initial_appearance_input(get, component, evidence):
    """Read the initial Appearance loader key from an already exact Skinned.

    Constructor and producer pins prove a direct held string at +168. No
    property, weak owner, resource members or file-content interpretation is
    applicable to this field. Characters remain byte addresses.
    """
    evidence.update(kind="initialAppearance", componentOffset=hex(INITIAL_APPEARANCE_INPUT_OFFSET),
        state="notReady", initialAppearanceInputObserved=False, nulTerminated=False,
        bytesRead=0, failedChecks=[], maxPathBytes=MAX_RENDER_INPUT_PATH_BYTES,
        identityMode="exact-Skinned/direct-held-string/initial-Appearance-key-producer",
        loadedAppearanceResourceVerified=False, selectedRenderResourceEquivalenceVerified=False,
        renderedDescriptorVerified=False, appearanceApplicationVerified=False,
        scope="initial Appearance loader input key only; not selected PAC or assembled prefab identity")
    text_raw = bytearray()
    label = "Skinned initial Appearance loader input"
    try:
        holder = struct.unpack("<Q", get(component + INITIAL_APPEARANCE_INPUT_OFFSET, 8,
                                         label + " held string"))[0]
        evidence.update(stringHolderPointer=hex(holder), present=bool(holder))
        if not holder:
            evidence["reason"] = "Initial Appearance string holder is absent"
            return None
        pointer(holder, label + " string holder")
        chars = struct.unpack("<Q", get(holder, 8, label + " character pointer"))[0]
        evidence["charactersPointer"] = hex(chars)
        if not chars:
            evidence["reason"] = "Initial Appearance character pointer is absent"
            return None
        if not 0x10000 <= chars < 2**47:
            evidence["failedChecks"] = ["character-byte-address-bounds"]
            raise ProbeError(label + " character pointer escaped the reviewed byte-address bounds")
        for index in range(MAX_RENDER_INPUT_PATH_BYTES):
            if chars + index >= 2**47:
                evidence["failedChecks"] = ["character-byte-address-bounds"]
                raise ProbeError(label + " character span escaped the reviewed address bounds")
            byte = get(chars + index, 1, label + " character byte")[0]
            text_raw.append(byte)
            if byte == 0:
                evidence["nulTerminated"] = True
                break
            if not 0x20 <= byte < 0x7F:
                evidence["failedChecks"] = ["printable-ASCII-initial-Appearance-input"]
                raise ProbeError(label + " is outside the reviewed printable ASCII string contract")
        if not evidence["nulTerminated"]:
            evidence["failedChecks"] = ["bounded-NUL-termination"]
            raise ProbeError(label + " lacks NUL termination within the fixed path bound")
        evidence["path"] = text_raw[:-1].decode("ascii")
        if not evidence["path"]:
            evidence["reason"] = "Initial Appearance loader input string is empty"
            return None
        evidence.update(state="observed", initialAppearanceInputObserved=True)
        return None
    except ProbeError as error:
        evidence.update(state="rejected", failureReason=str(error))
        return error
    finally:
        evidence.update(bytesRead=len(text_raw), pathBytesIncludingNulHex=text_raw.hex())


def declared_render_input_paths(reader, component, base, evidence, *, watch):
    """Read two native file-input properties and the initial Appearance key.

    The parent has already passed the dedicated Skinned reflection gate. Only
    direct property owners are supported; the constructor's weak branch stops
    before +28. Character pointers are byte addresses, unlike aligned holders.
    Every read byte, including NUL, joins the whole Scene stability recheck.
    The separate initial key is a producer-proven held string, not a property.
    """
    evidence.update(state="notReady", inputs=[], maxPathBytes=MAX_RENDER_INPUT_PATH_BYTES,
        stringEncoding="printable-ASCII/NUL", selectedRenderResourceEquivalenceVerified=False,
        renderedDescriptorVerified=False, appearanceApplicationVerified=False,
        identityMode="exact-property-constructor-vtable/direct-Skinned-owner/native-string-consumer")
    errors = []

    def get(address, size, label):
        raw = read(reader, address, size, label)
        watch(address, raw, label)
        return raw

    def qword(address, label):
        return struct.unpack("<Q", get(address, 8, label))[0]

    for kind, (offset, expected_vt) in RENDER_INPUT_PROPERTIES.items():
        label = "Skinned declared " + kind + " input"
        entry = {"kind": kind, "componentOffset": hex(offset), "state": "notReady",
                 "expectedPropertyVtableRva": hex(expected_vt), "propertyIdentityVerified": False,
                 "directOwnerRoundTripObserved": False, "declaredPathObserved": False,
                 "nulTerminated": False, "bytesRead": 0, "failedChecks": []}
        evidence["inputs"].append(entry)
        text_raw = bytearray()
        try:
            prop = qword(component + offset, label + " property")
            entry.update(propertyPointer=hex(prop), present=bool(prop))
            if not prop:
                entry["reason"] = "Declared input property is absent"
                continue
            pointer(prop, label + " property")
            vt = qword(prop, label + " property vtable")
            entry["propertyVtablePointer"] = hex(vt)
            if vt != base + expected_vt:
                entry["failedChecks"] = ["exact-declared-property-constructor-vtable"]
                raise ProbeError(label + " property vtable differs from the fixed constructor")
            entry.update(propertyVtableRva=hex(expected_vt), propertyIdentityVerified=True)
            flag = get(prop + 0x1A, 1, label + " owner flags")[0]
            entry["ownerFlag1A"] = flag
            if flag & 8:
                entry["failedChecks"] = ["direct-property-owner-required"]
                raise ProbeError(label + " uses the unsupported weak property-owner branch")
            parent = qword(prop + 0x10, label + " direct owner")
            entry["ownerPointer"] = hex(parent)
            if parent != component:
                entry["failedChecks"] = ["exact-Skinned-property-owner-backlink"]
                raise ProbeError(label + " property does not refer back to the controlled Skinned component")
            entry["directOwnerRoundTripObserved"] = True
            holder = qword(prop + 0x28, label + " string holder")
            entry["stringHolderPointer"] = hex(holder)
            if not holder:
                entry["reason"] = "Declared input string holder is absent"
                continue
            pointer(holder, label + " string holder")
            chars = qword(holder, label + " character pointer")
            entry["charactersPointer"] = hex(chars)
            if not chars:
                entry["reason"] = "Declared input character pointer is absent"
                continue
            # Native code loads individual characters. Imposing QWORD alignment
            # here would reject valid interned strings sharing a backing buffer.
            if not 0x10000 <= chars < 2**47:
                entry["failedChecks"] = ["character-byte-address-bounds"]
                raise ProbeError(label + " character pointer escaped the reviewed byte-address bounds")
            for index in range(MAX_RENDER_INPUT_PATH_BYTES):
                if chars + index >= 2**47:
                    entry["failedChecks"] = ["character-byte-address-bounds"]
                    raise ProbeError(label + " character span escaped the reviewed address bounds")
                byte = get(chars + index, 1, label + " character byte")[0]
                text_raw.append(byte)
                if byte == 0:
                    entry["nulTerminated"] = True
                    break
                if not 0x20 <= byte < 0x7F:
                    entry["failedChecks"] = ["printable-ASCII-declared-input"]
                    raise ProbeError(label + " is outside the reviewed printable ASCII string contract")
            if not entry["nulTerminated"]:
                entry["failedChecks"] = ["bounded-NUL-termination"]
                raise ProbeError(label + " lacks NUL termination within the fixed path bound")
            path = text_raw[:-1].decode("ascii")
            entry.update(path=path, expectedNativeExtension=kind,
                         extensionMatchesNativeInput=path.rsplit(".", 1)[-1] == kind)
            if not path:
                entry["reason"] = "Declared input string is empty"
                continue
            entry.update(state="observed", declaredPathObserved=True)
        except ProbeError as error:
            entry.update(state="rejected", failureReason=str(error))
            errors.append(error)
        finally:
            entry.update(bytesRead=len(text_raw), pathBytesIncludingNulHex=text_raw.hex())
    evidence["initialAppearanceInput"] = {}
    initial_error = initial_appearance_input(get, component, evidence["initialAppearanceInput"])
    if initial_error:
        errors.append(initial_error)
    evidence["state"] = ("rejected" if errors else "observed" if
                         all(item["declaredPathObserved"] for item in evidence["inputs"])
                         and evidence["initialAppearanceInput"]["initialAppearanceInputObserved"] else "notReady")
    return errors


def character_scene(reader, base, length, owner, members, observed, *, render_resource_identities=False,
                    render_resource_links=False, render_input_paths=False):
    """Follow the exact owner's bounded components and reviewed Scene fields.

    Scene and its owned parameter resource lack a valid primary MSVC RTTI
    locator. Their identity is therefore gated by pinned constructor/getter
    code, exact vtables, typed reflection metadata and weak-owner round trips.
    The render selector container is deliberately opaque. Its three native input
    fields are read; optional resource observation reads standard identity only.
    """
    info = {"state": "notReady", "sceneOccurrences": 0,
            "sceneOwnerRoundTripObserved": False, "parameterOwnerRoundTripObserved": False,
            "renderLinkObserved": False, "renderSelectorFieldsObserved": False,
            "selectedResourceTypeVerified": False, "renderedDescriptorVerified": False,
            "appearanceApplicationVerified": False, "renderResourceIdentitiesObserved": False,
            "renderResourceLinksObserved": False, "renderInputPathsObserved": False,
            "initialAppearanceInputObserved": False}
    observed["characterScene"] = info
    watched = {}
    resource_identities = []
    identity_errors = []
    resource_links = []
    link_errors = []
    input_errors = []

    def get(address, size, label):
        raw = read(reader, address, size, label)
        watched[(address, size, label)] = raw
        return raw

    def qword(address, label):
        return struct.unpack("<Q", get(address, 8, label))[0]

    def watch_link(address, raw, label):
        key = (address, len(raw), label)
        if watched.setdefault(key, raw) != raw:
            raise ProbeError("Anonymous resource link bytes changed during Scene reads")

    def watch_input(address, raw, label):
        key = (address, len(raw), label)
        if watched.setdefault(key, raw) != raw:
            raise ProbeError("Declared render input bytes changed during Scene reads")

    def weak_at(address, label, expected=None):
        holder = qword(address, label + " holder")
        if not holder:
            return None
        pointer(holder, label + " holder")
        target = qword(holder + 8, label + " target")
        if not target:
            return {"holder": hex(holder), "target": "0x0", "present": False}
        pointer(target, label + " target")
        if expected is not None and target != expected + 0x28:
            raise ProbeError(label + " weak target differs from the reviewed primary owner")
        flag = get(target + 0x15, 1, label + " invalidation flag")[0]
        entry = {"holder": hex(holder), "target": hex(target), "targetFlag15": flag, "present": True}
        if flag != 0:
            raise ProbeError(label + " is invalidated or has an unknown flag")
        entry["primaryPointer"] = hex(target - 0x28)
        return entry

    def stable():
        for (address, size, label), expected in watched.items():
            if read(reader, address, size, label + " stability") != expected:
                raise ProbeError("CharacterScene interpreted fields changed during reads")

    def render_identity(primary, evidence=None):
        vt = qword(primary, "render-linked primary vtable")
        if vt != base + SKINNED_MESH_VTABLE:
            # Existing exact SceneObjectClient gate is unchanged for this route;
            # an unknown vtable cannot fall back to reflection or a type name.
            return typed(reader, primary, base, length, "owner",
                         context="render-linked primary object", evidence=evidence)
        identity = evidence if evidence is not None else {}
        identity.update(pointer=hex(primary), context="render-linked SkinnedMeshComponent",
            vtablePointer=hex(vt), vtableRva=hex(SKINNED_MESH_VTABLE),
            identityMode="exact-constructor-vtable/getter/typed-reflection/controlled-Scene-weak-route",
            primaryMsvcRttiVerified=False, typeGatePassed=False, failedChecks=[])
        try:
            if qword(base + SKINNED_MESH_VTABLE + 8, "SkinnedMeshComponent reflection getter") != base + SKINNED_MESH_GETTER:
                identity["failedChecks"] = ["exact-skinned-mesh-reflection-getter"]
                raise ProbeError("SkinnedMeshComponent reflection getter differs from the fixed EXE")
            meta_evidence = {}
            identity["reflectionMetadataIdentity"] = meta_evidence
            meta = typed(reader, base + SKINNED_MESH_META, base, length, "skinnedMeshMetadata",
                         context="SkinnedMeshComponent reflection metadata", evidence=meta_evidence)
            qword(base + SKINNED_MESH_META, "Skinned mesh metadata vtable")
            identity.update(typeGatePassed=True, reflectionType="SkinnedMeshComponent", reflectionMetadata=meta)
            return {"pointer": hex(primary), "vtableRva": hex(SKINNED_MESH_VTABLE),
                "reflectionType": "SkinnedMeshComponent", "reflectionMetadata": meta,
                "primaryMsvcRttiVerified": False, "identityMode": identity["identityMode"]}
        except ProbeError as error:
            identity["failureReason"] = str(error)
            raise

    scenes = []
    # This is the already-proven +210 component array, not a heap/type scan.
    for address in struct.unpack(f"<{len(members) // 8}Q", members):
        pointer(address, "owner component member")
        vt = qword(address, "owner component member vtable")
        if vt == base + SCENE_VTABLE:
            scenes.append(address)
    info["sceneOccurrences"] = len(scenes)
    if not scenes:
        info["reason"] = "No exact CharacterScene vtable in the controlled owner's component array"
        stable()
        return
    if len(scenes) != 1:
        raise ProbeError("CharacterScene is not unique in the controlled owner's component array")
    scene = scenes[0]
    pointer(scene, "CharacterScene")
    info.update(pointer=hex(scene), identityMode="exact-vtable/getter/reflection-metadata/owner-round-trip",
                vtableRva=hex(SCENE_VTABLE), primaryMsvcRttiVerified=False)
    if qword(base + SCENE_VTABLE + 8, "CharacterScene reflection getter") != base + SCENE_GETTER:
        raise ProbeError("CharacterScene reflection getter differs from the fixed EXE")
    metadata = typed(reader, base + SCENE_META, base, length, "sceneMetadata")
    info["reflectionMetadata"] = metadata
    get(base + SCENE_META, 8, "Scene metadata vtable")
    flag = get(scene + 0x3D, 1, "CharacterScene weak invalidation flag")[0]
    if flag != 0:
        raise ProbeError("CharacterScene is invalidated or has an unknown weak flag")
    info["weakOwner"] = weak_at(scene + 0x60, "CharacterScene owner", owner)
    if not info["weakOwner"] or not info["weakOwner"]["present"]:
        raise ProbeError("CharacterScene owner weak link is absent")
    info["sceneOwnerRoundTripObserved"] = True

    parameter = qword(scene + 0xA0, "CharacterScene parameter resource")
    info["parameterResource"] = {"present": bool(parameter)}
    if parameter:
        pointer(parameter, "Scene parameter resource")
        vt = qword(parameter, "Scene parameter resource vtable")
        if vt != base + SCENE_PARAM_VTABLE:
            raise ProbeError("Scene parameter resource vtable differs from its reviewed constructor")
        # Constructor's allocation is 0x200; only its known prefix is read.
        read(reader, parameter, 0x58, "Scene parameter known header")
        parameter_flag = get(parameter + 0x15, 1, "Scene parameter invalidation flag")[0]
        if parameter_flag != 0:
            raise ProbeError("Scene parameter resource is invalidated or has an unknown flag")
        parent = weak_at(parameter + 0x50, "Scene parameter Scene backlink", scene)
        info["parameterResource"].update(pointer=hex(parameter), vtableRva=hex(vt - base),
            identityMode="exact-constructor-vtable/Scene-weak-round-trip", primaryMsvcRttiVerified=False,
            constructorAllocationBytes=0x200, readableKnownHeaderBytes=0x58, weakScene=parent,
            partsOrDescriptorFieldsInterpreted=False)
        if not parent or not parent["present"]:
            raise ProbeError("Scene parameter Scene weak backlink is absent")
        info["parameterOwnerRoundTripObserved"] = True

    render_link = weak_at(scene + 0x78, "CharacterScene render link")
    info["renderWeakLink"] = render_link
    if render_link and render_link["present"]:
        primary = pointer(int(render_link["primaryPointer"], 16), "render-linked primary object")
        identity = {}
        info["renderObjectIdentity"] = identity
        render_type = render_identity(primary, identity)
        get(primary, 8, "render-linked primary vtable")
        info["renderObject"] = {**render_type, "equalsControlledOwner": primary == owner}
        info["renderLinkObserved"] = True
        if render_input_paths:
            info["renderInputPaths"] = {"state": "notReady"}
            if render_type.get("reflectionType") != "SkinnedMeshComponent":
                info["renderInputPaths"].update(state="rejected", failedChecks=["exact-SkinnedMeshComponent-required"])
                raise ProbeError("Declared render inputs require the dedicated exact SkinnedMeshComponent type gate")
            input_errors = declared_render_input_paths(reader, primary, base,
                info["renderInputPaths"], watch=watch_input)
        selector = qword(primary + 0xA8, "render selector container")
        info["renderSelector"] = {"present": bool(selector), "typeInterpreted": False,
            "fieldContract": "native 0x7268C2..0x7268DD only; no constructor/type inferred"}
        if selector:
            pointer(selector, "render selector container")
            fields = get(selector + 0x18, 17, "render selector resource pair/index")
            first, second, index = struct.unpack("<QQB", fields)
            if index not in (0, 1):
                raise ProbeError("Render selector index is outside the native two-entry pair")
            for candidate in (first, second):
                if candidate:
                    pointer(candidate, "render selector resource pointer")
            info["renderSelector"].update(pointer=hex(selector), resourcePointers=[hex(first), hex(second)],
                selectedIndex=index, selectedResourcePointer=hex((first, second)[index]),
                selectedResourceDereferenced=False)
            info["renderSelectorFieldsObserved"] = True
            if render_resource_identities:
                info["renderSelector"]["resourceIdentities"] = []
                info["renderSelector"]["resourceReadsIdentityOnly"] = True
                for slot, candidate in enumerate((first, second)):
                    evidence = {"slot": slot, "present": bool(candidate)}
                    info["renderSelector"]["resourceIdentities"].append(evidence)
                    if candidate:
                        if slot == index:
                            info["renderSelector"]["selectedResourceDereferenced"] = True
                        try:
                            identity = resource_identity(reader, candidate, base, length, evidence)
                            resource_identities.append((candidate, identity))
                        except ProbeError as error:
                            # Each sibling pointer came from the same bounded pair.
                            # Stop interpreting this resource, retain its rejection,
                            # and allow the other identity-only observation. Never
                            # promote a mixed/failed pair to a stable Scene result.
                            identity_errors.append(error)
            if render_resource_links:
                info["renderSelector"].update(resourceLinks=[], nestedResourcesIdentityOnly=True)
                for slot, candidate in enumerate((first, second)):
                    evidence = {"slot": slot, "present": bool(candidate),
                                "nestedPrimaryHeaderObserved": False, "state": "emptyParentReference"}
                    info["renderSelector"]["resourceLinks"].append(evidence)
                    if candidate:
                        if slot == index:
                            info["renderSelector"]["selectedResourceDereferenced"] = True
                        try:
                            header = linked_resource_header(reader, candidate, base, length, evidence, watch=watch_link)
                            resource_links.append((candidate, header))
                        except ProbeError as error:
                            link_errors.append(error)
    stable()
    if typed(reader, base + SCENE_META, base, length, "sceneMetadata") != metadata:
        raise ProbeError("CharacterScene reflection metadata changed during reads")
    if render_link and render_link["present"] and render_identity(primary) != render_type:
        raise ProbeError("CharacterScene render object type changed during reads")
    for candidate, identity in resource_identities:
        if resource_identity(reader, candidate, base, length, {}) != identity:
            raise ProbeError("Render resource identity changed within the controlled Scene observation")
    for candidate, header in resource_links:
        if linked_resource_header(reader, candidate, base, length, {}, watch=watch_link) != header:
            raise ProbeError("Anonymous render resource link changed within the controlled Scene observation")
    # Include a final pair/owner re-read after identity reads, not just before them.
    if render_resource_identities:
        stable()
        if identity_errors:
            raise identity_errors[0]
        info["renderResourceIdentitiesObserved"] = bool(resource_identities)
    if render_resource_links:
        stable()
        if link_errors:
            raise link_errors[0]
        info["renderResourceLinksObserved"] = (len(resource_links) == 2 and
            all(header["nestedPrimaryHeaderObserved"] for _, header in resource_links))
    if render_input_paths:
        stable()
        if input_errors:
            raise input_errors[0]
        info["initialAppearanceInputObserved"] = (info.get("renderInputPaths", {}).get(
            "initialAppearanceInput", {}).get("initialAppearanceInputObserved", False)
            and bool(parameter and info["renderSelectorFieldsObserved"]))
        info["renderInputPathsObserved"] = (info.get("renderInputPaths", {}).get("state") == "observed"
            and bool(parameter and info["renderSelectorFieldsObserved"]))
    info["state"] = "observed" if (parameter and info["renderSelectorFieldsObserved"]) else "notReady"
    info["limitations"] = ["The selected buffer's resource type and descriptor fields are not decoded.",
        "Scene and parameter identity use pinned reflection/constructor evidence; primary MSVC RTTI is unavailable.",
        "The render-linked object must pass exact SceneObjectClient RTTI or the dedicated pinned SkinnedMeshComponent reflection contract.",
        "Declared PAC/PAB property strings do not verify the selected resource's rendered descriptor or grant native application permission.",
        "The initial Appearance loader key does not verify its file content, assembled prefabs or selected head/body PAC.",
        "These observations do not establish appearance application ABI, thread, restore or slot semantics."]


def sample(reader, base, length, observed, *, render_resource_identities=False, render_resource_links=False,
           render_input_paths=False):
    def link(address, name):
        return pointer(value(reader, address, name), name)
    root = link(base + WORLD_GLOBAL, "world root")
    observed["worldRoot"] = hex(root)
    manager = link(root + 0x30, "client manager")
    observed["manager"] = typed(reader, manager, base, length, "manager")
    user = link(manager + 0x58, "client user")
    observed["user"] = typed(reader, user, base, length, "user")
    actor = link(manager + 0x50, "controlled actor")
    observed["actor"] = typed(reader, actor, base, length, "actor")
    if (value(reader, user + 0xD0, "user first child") != actor or
            value(reader, user + 0xD8, "user second child") != actor or
            value(reader, actor + 0xA0, "actor user backlink") != user):
        raise ProbeError("Controlled actor manager/user round trip does not agree")
    observed["controlledActorRoundTripObserved"] = True
    table = link(actor + 0x68, "actor component table")
    observed["componentTable"] = hex(table)
    control = link(table + 0x40, "character control component")
    observed["control"] = typed(reader, control, base, length, "control")
    if value(reader, control + 8, "control actor backlink") != actor:
        raise ProbeError("Character control owner backlink differs from the controlled actor")
    middle = link(control + 0xB8, "opaque controller holder")
    header = read(reader, middle, 0x28, "opaque controller holder")
    observed["opaqueHolder"] = {"pointer": hex(middle), "readableHeaderBytes": 0x28,
                                "typeOrOtherFieldsInterpreted": False}
    controller = pointer(struct.unpack_from("<Q", header, 0x20)[0], "appearance controller")
    observed["controller"] = typed(reader, controller, base, length, "controller")
    raw = read(reader, controller, 0x140, "complete controller allocation")
    owner = pointer(struct.unpack_from("<Q", raw, 0x10)[0], "controller owner")
    observed["owner"] = typed(reader, owner, base, length, "owner")
    weak = pointer(struct.unpack_from("<Q", raw, 0x60)[0], "controller weak owner holder")
    target = pointer(value(reader, weak + 8, "weak owner target"), "weak owner target")
    if target != owner + 0x28:
        raise ProbeError("Controller weak-owner unwrap differs from the primary owner")
    flag = value(reader, target + 0x15, "weak target invalidation flag", "<B")
    observed["weakOwner"] = {"holder": hex(weak), "target": hex(target), "targetFlag15": flag,
                             "unwrapMatchesOwner": True}
    if flag != 0:
        raise ProbeError("Controller weak owner is invalidated or has an unknown flag")
    directory = read(reader, owner + 0x210, 16, "owner component directory")
    owner_array, count, capacity = struct.unpack("<QII", directory)
    if not 1 <= count <= MAX_OWNER_COMPONENTS or not count <= capacity <= 4096:
        raise ProbeError("Owner component count/capacity exceeds the reviewed bounds")
    pointer(owner_array, "owner component array")
    members = read(reader, owner_array, count * 8, "complete owner component array")
    occurrences = list(struct.unpack(f"<{count}Q", members)).count(controller)
    observed["ownerComponents"] = {"array": hex(owner_array), "count": count, "capacity": capacity,
                                   "controllerOccurrences": occurrences}
    if occurrences != 1:
        raise ProbeError("Controller is not present exactly once in its owner's component array")
    observed["controllerOwnerRoundTripObserved"] = True
    selections = {}
    for name, offset, maximum in (("mesh", 0xA0, 16), ("decoration", 0xB0, 250)):
        array, count, capacity = struct.unpack_from("<QII", raw, offset)
        if not 0 <= count <= maximum or not count <= capacity <= 4096:
            raise ProbeError(f"{name} selection count/capacity exceeds the reviewed bounds")
        if count:
            pointer(array, name + " selection array")
            choices = read(reader, array, count, name + " selections")
        else:
            choices = b""
        selections[name] = {"array": hex(array), "count": count, "capacity": capacity,
                            "selectionBytesHex": choices.hex(), "loadedOptionBoundsVerified": False}
    observed["selections"] = selections
    loaded_options(reader, base, length, controller, raw, selections, observed)
    character_scene(reader, base, length, owner, members, observed,
                    render_resource_identities=render_resource_identities,
                    render_resource_links=render_resource_links, render_input_paths=render_input_paths)
    # Re-read only structural bytes that have a known contract, not unknown
    # holder fields or values which may legitimately change while moving.
    expected_links = ((base + WORLD_GLOBAL, root), (root + 0x30, manager), (manager + 0x58, user),
                      (manager + 0x50, actor), (user + 0xD0, actor), (user + 0xD8, actor),
                      (actor + 0xA0, user), (actor + 0x68, table), (table + 0x40, control),
                      (control + 8, actor), (control + 0xB8, middle), (middle + 0x20, controller),
                      (controller + 0x10, owner), (controller + 0x60, weak), (weak + 8, target))
    if any(value(reader, address, "structural link reread") != expected for address, expected in expected_links):
        raise ProbeError("Structural controller links changed during reads")
    if (read(reader, owner + 0x210, 16, "owner directory reread") != directory or
            read(reader, owner_array, len(members), "owner array reread") != members or
            read(reader, controller + 0xA0, 32, "selection directory reread") != raw[0xA0:0xC0] or
            value(reader, target + 0x15, "weak flag reread", "<B") != flag):
        raise ProbeError("Controller owner or selection directory changed during reads")
    for name, entry in selections.items():
        if entry["count"] and read(reader, int(entry["array"], 16), entry["count"], name + " selection reread").hex() != entry["selectionBytesHex"]:
            raise ProbeError("Controller selections changed during reads")
    for name, address in (("manager", manager), ("user", user), ("actor", actor),
                          ("control", control), ("controller", controller), ("owner", owner)):
        if typed(reader, address, base, length, name) != observed[name]:
            raise ProbeError("Typed controller chain changed during reads")
    observed["stableDuringSample"] = True


def collect(reader, base, length, pause=time.sleep, *, render_resource_identities=False, render_resource_links=False,
            render_input_paths=False):
    report = {"schemaVersion": 7 if render_input_paths else 5 if render_resource_links else 4,
              "mode": "external-read-only", "state": "rejected", "samples": [],
              "renderResourceIdentitiesRequested": render_resource_identities,
              "renderResourceIdentitiesObserved": False,
              "renderResourceLinksRequested": render_resource_links,
              "renderResourceLinksObserved": False,
              "renderInputPathsRequested": render_input_paths,
              "renderInputPathsObserved": False,
              "initialAppearanceInputObserved": False,
              "nativeFunctionsInvoked": False, "gameMemoryWritten": False, "heapScanned": False,
              "appearanceApplicationVerified": False, "appearanceRestoreVerified": False,
              "steveModelLoaded": False, "snapshotAtomic": False,
              "controlledControllerChainObserved": False, "stableTwoSamples": False,
              "characterSceneObserved": False, "sceneRenderSelectorObserved": False,
              "renderedDescriptorVerified": False,
              "limitations": ["Stable pointer ownership is an observation, not a native appearance application contract.",
                              "Typed mesh option bounds and prefab names do not verify the currently rendered descriptors or permit writes.",
                              "Decoration final palette/mesh-dependent bounds and slot semantics are not verified.",
                              "The intermediate holder's type and unused fields are not interpreted."]}
    try:
        if sum(bool(mode) for mode in (render_resource_identities, render_resource_links, render_input_paths)) > 1:
            raise ProbeError("Choose exactly one independent render-resource diagnostic mode")
        validate_code(reader, base, length, render_resource_links=render_resource_links,
                      render_input_paths=render_input_paths)
        for index in range(2):
            observed = {}
            report["samples"].append(observed)
            sample(reader, base, length, observed, render_resource_identities=render_resource_identities,
                   render_resource_links=render_resource_links, render_input_paths=render_input_paths)
            if index == 0:
                pause(SAMPLE_GAP_SECONDS)
        validate_code(reader, base, length, render_resource_links=render_resource_links,
                      render_input_paths=render_input_paths)
        if report["samples"][0] != report["samples"][1]:
            report["state"] = "unstable"
            raise ProbeError("The two fixed controller samples do not agree")
        report["stableTwoSamples"] = True
        report["controlledControllerChainObserved"] = True
        selections = report["samples"][0]["selections"]
        report["selectionBuffersPresent"] = all(entry["count"] > 0 for entry in selections.values())
        options = report["samples"][0]["loadedOptions"]
        report["loadedOptionsObserved"] = options["state"] == "observed"
        report["meshGroupChoiceBoundsVerified"] = options["meshGroupChoiceBoundsVerified"]
        report["decorationComputedBoundsVerified"] = False
        scene = report["samples"][0]["characterScene"]
        report["characterSceneObserved"] = scene["sceneOwnerRoundTripObserved"]
        report["sceneRenderSelectorObserved"] = scene["state"] == "observed"
        report["renderResourceIdentitiesObserved"] = scene["renderResourceIdentitiesObserved"]
        report["renderResourceLinksObserved"] = scene["renderResourceLinksObserved"]
        report["renderInputPathsObserved"] = scene["renderInputPathsObserved"]
        report["initialAppearanceInputObserved"] = scene["initialAppearanceInputObserved"]
        report["state"] = "observed" if report["selectionBuffersPresent"] and report["loadedOptionsObserved"] else "notReady"
        if render_resource_links and not report["renderResourceLinksObserved"]:
            report["state"] = "notReady"
            report["reason"] = "The controlled Scene resource pair or a nested reference/header is absent"
        if render_input_paths and not report["renderInputPathsObserved"]:
            report["state"] = "notReady"
            report["reason"] = "A controlled Scene field, declared PAC/PAB input or initial Appearance loader key is absent or empty"
        if report["state"] == "notReady":
            report.setdefault("reason", "Controller ownership was observed but a selection buffer or loaded option table is empty")
    except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
        if len(report["samples"]) > 1 and report["samples"][0].get("stableDuringSample"):
            report["state"] = "unstable"
        report["reason"] = str(error)[:2000]
    return report


def output_path(path):
    path = roster.output_path(path)
    if path.exists():
        raise ProbeError("Appearance evidence output already exists; use a new runtime JSON path")
    return path


def write_report(path, report):
    path = output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output_path(path)
    raw = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > 512 * 1024:
        raise ProbeError("Appearance evidence exceeds the bounded report size")
    with path.open("xb") as stream:
        stream.write(raw)


def summary(report, output):
    return {"output": str(output), **{key: report.get(key) for key in
            ("state", "reason", "stableTwoSamples", "controlledControllerChainObserved", "selectionBuffersPresent",
             "loadedOptionsObserved", "meshGroupChoiceBoundsVerified", "decorationComputedBoundsVerified",
             "characterSceneObserved", "sceneRenderSelectorObserved", "renderResourceIdentitiesObserved", "renderedDescriptorVerified",
             "renderResourceLinksObserved", "renderInputPathsObserved", "initialAppearanceInputObserved",
             "nativeFunctionsInvoked", "gameMemoryWritten", "appearanceApplicationVerified", "steveModelLoaded")}}


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, help="otherwise require exactly one running CrimsonDesert.exe")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--render-resource-identities", action="store_true",
                        help="Read only primary RTTI identities of the two controlled Scene selector resources")
    modes.add_argument("--render-resource-links", action="store_true",
                       help="Read exact anonymous parent +68 references and nested vtables only, without RTTI or descriptor interpretation")
    modes.add_argument("--render-input-paths", action="store_true",
                       help="Read exact controlled Skinned declared PAC/PAB strings and initial Appearance loader key; no selected descriptor equivalence")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/appearance-controller.json")
    args = parser.parse_args()
    output = output_path(args.output)
    pid = args.pid
    if pid is None:
        text = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq CrimsonDesert.exe", "/FO", "CSV"],
                                       text=True, encoding="utf-8", errors="replace")
        matches = re.findall(r'"CrimsonDesert\.exe","(\d+)"', text, re.I)
        if len(matches) != 1:
            raise ProbeError("Require exactly one running game or explicit --pid")
        pid = int(matches[0])
    if pid <= 0:
        raise ProbeError("Invalid process ID")
    profile, _ = core.load_profile()
    reader = core.Reader(pid)
    try:
        base, length, path = reader.module()
        version = subprocess.check_output(["powershell", "-NoProfile", "-Command",
            "(Get-Item -LiteralPath '" + str(path).replace("'", "''") + "').VersionInfo.FileVersion"], text=True).strip()
        digest = file_digest(path)
        roster.validate_layout_build(profile, version, digest)
        report = collect(reader, base, length, render_resource_identities=args.render_resource_identities,
                         render_resource_links=args.render_resource_links, render_input_paths=args.render_input_paths)
        if reader.module() != (base, length, path) or file_digest(path) != digest:
            report.update(state="unstable", stableTwoSamples=False, controlledControllerChainObserved=False,
                          characterSceneObserved=False, sceneRenderSelectorObserved=False,
                          renderResourceIdentitiesObserved=False,
                          renderResourceLinksObserved=False,
                          renderInputPathsObserved=False,
                          initialAppearanceInputObserved=False,
                          renderedDescriptorVerified=False,
                          reason="Game module changed during the read-only observation")
        report.update(timeUtc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      game={"pid": pid, "path": str(path), "version": version, "sha256": digest,
                            "moduleBase": hex(base), "moduleSize": length},
                      source={"worldAnchor": profile["world_root"]["source"], "license": "MIT",
                              "staticChainRvas": [hex(rva) for rva in code_windows(
                                  render_resource_links=args.render_resource_links,
                                  render_input_paths=args.render_input_paths)]})
        write_report(output, report)
        print(json.dumps(summary(report, output), ensure_ascii=False, indent=2))
        return 0 if report["state"] == "observed" else 1
    finally:
        reader.close()


if __name__ == "__main__":
    raise SystemExit(main())
