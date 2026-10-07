"""Clone only the fixed Macduff CD_Nude/CD_Head components, offline.

The fixed decoder's element spans end BEFORE their name-pointee footer. Keep
the first complete component including that proven footer; never reuse the last
removed component's footer. New PAC paths are references, not bundled meshes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import prepare_native_steve as native
import prepare_steve_orientation as orientation

ROOT = native.ROOT
DEFAULT_INPUT = ROOT / "build/steve-appearance-research-20261007/observed-native-resources"
DEFAULT_DESCRIPTOR = ROOT / "build/steve-fullbody-review-20261007/cd_phm_00_nude_01_0002_macduff.prefabdata_xml"
DEFAULT_OUTPUT = ROOT / "build/steve-parts-prefab"
REPORT_NAME = "steve-parts-prefab-report.json"
INDEX_SHA256 = "c561ae348ba6dea65b0460686dec089b65291bbbeec439643d42bc5f4ead05b9"
DESCRIPTOR_SHA256 = "e4f831a4b7680dd0dbc7e0547b04347711ceff0d8427ccd5e0f58e611684e1f5"
DESCRIPTOR_TEMPLATE = "character/prefab/1_pc/01_phm/nude/cd_phm_00_nude_01_0002_macduff.prefabdata_xml"
DESCRIPTOR_PATH = "character/prefab/1_pc/01_phm/nude/crimsonmc_steve_body_1_21_1.prefabdata_xml"
PARTS = {
    "body": {
        "local": "03-cd_phm_00_nude_01_0002_macduff.prefab",
        "template": "character/bin__/prefab/1_pc/01_phm/nude/cd_phm_00_nude_01_0002_macduff.prefab",
        "sha256": "0184309bae4ded9d51e07269ddebea8ed6f6b08701c59a077f9d866d6002e757",
        "names": ("CD_Nude", "CD_Underwear"),
        "sourceMesh": "character/model/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pac",
        "targetMesh": "character/model/1_pc/1_phm/nude/crimsonmc_steve_body_1_21_1.pac",
        "target": "character/bin__/prefab/1_pc/01_phm/nude/crimsonmc_steve_body_1_21_1.prefab",
    },
    "head": {
        "local": "04-cd_phm_00_head_00_0001_macduff.prefab",
        "template": "character/bin__/prefab/1_pc/01_phm/head/head/cd_phm_00_head_00_0001_macduff.prefab",
        "sha256": "b8bde25e8781391f281d09b8e2bfce17bf99c91325a4215eee1e6df469b1c26e",
        "names": ("CD_Head", "CD_EyeLeft", "CD_EyeRight", "CD_Eyebrows", "CD_Eyelashes", "CD_Tooth", "CD_Nude_Hair"),
        "sourceMesh": "character/model/1_pc/1_phm/head/head/cd_phm_00_head_00_0001_macduff.pac",
        "targetMesh": "character/model/1_pc/1_phm/head/head/crimsonmc_steve_head_1_21_1.pac",
        "target": "character/bin__/prefab/1_pc/01_phm/head/head/crimsonmc_steve_head_1_21_1.prefab",
    },
}


def read_native_templates(game):
    """Read exactly three SHA-pinned original payloads from the supported index."""
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    native.check_links(game)
    exe, index = game / "bin64/CrimsonDesert.exe", game / "0009/0.pamt"
    for path in (exe, index):
        native.check_links(path)
    def gate():
        if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != INDEX_SHA256:
            raise ValueError("Unsupported EXE or source archive index fingerprint")
    gate()
    hashes = {s["template"]: s["sha256"] for s in PARTS.values()}
    hashes[DESCRIPTOR_TEMPLATE] = DESCRIPTOR_SHA256
    entries = native.select_unique_entries(parse_archive_pamt(index), tuple(hashes))
    payloads = {}
    for path, entry in entries.items():
        native.check_links(Path(entry.paz_file))
        data = _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
        if not 0 < len(data) <= 16384 or native.sha256(data) != hashes[path]:
            raise ValueError("Native template payload fingerprint mismatch: " + path)
        payloads[path] = data
    gate()
    return payloads


def installed_game():
    path = ROOT / "runtime/installation.json"
    native.check_links(path)
    return Path(json.loads(path.read_text(encoding="utf-8-sig"))["gameRoot"])


def read_fixed(path, digest, snapshot):
    path = native.output_directory(path)
    data = path.read_bytes()
    if native.sha256(data) != digest:
        raise ValueError("Fixed prefab input fingerprint mismatch: " + str(path))
    snapshot[path] = data
    return data


def contract(obj):
    return {"name": obj.name, "componentType": obj.component_type,
            "members": list(obj.member_names), "resources": [x.text for x in obj.resources],
            "values": [(key, value.text) for key, value in obj.values],
            "numbers": [(x.name, x.type_name, x.raw.hex()) for x in obj.numbers],
            "opaqueOwnerToken": f"0x{obj.parent:016x}", "typeSource": obj.type_source}


def strict_layout(data):
    """Require actual closure, including name footers the CDMW walk tolerates."""
    from cdmw.core.prefab_binary import decode_prefab_binary, walk_is_determined
    d = decode_prefab_binary(data)
    if (not d.walk_complete or not walk_is_determined(data) or d.root_type != "SceneObject"
            or d.root_members != ("_components",) or len(d.collections) != 1
            or d.root_resources or d.root_texts or d.root_numbers):
        raise ValueError("Prefab is not a determined flat component collection")
    c = d.collections[0]
    if (c.owner_type != "SceneObject" or c.member_name != "_components" or c.header_width != 5
            or c.count != len(c.elements) or c.count != len(d.objects) or not c.count):
        raise ValueError("Prefab collection count or extent differs")
    if (d.blob_offset + d.blob_length != len(data)
            or struct.unpack_from("<I", data, d.blob_offset - 24)[0] != len(data)
            or c.elements[-1][1] + 5 != len(data) or data[-1:] != b"\x01"):
        raise ValueError("Prefab data header or exact terminator differs")
    footers = []
    for index, ((start, end), obj) in enumerate(zip(c.elements, d.objects)):
        if obj.offset != start or obj.component_type != "SkinnedMeshComponent" or obj.type_source != "stated":
            raise ValueError("Prefab component type/span was not explicitly stated")
        sites = [p for p in d.pointers if start <= p.site < end]
        if len(sites) != 3 or any(p.owner != 2**64-1 for p in sites[1:]):
            raise ValueError("Component does not have the fixed name/mesh/empty-skeleton pointer records")
        name = sites[0]
        encoded = obj.name.encode("ascii")
        if (name.owner != obj.parent or data[name.target:name.target+6] != b"\0\0\1\0\0\0"
                or struct.unpack_from("<I", data, name.target + 6)[0] != len(encoded)
                or data[name.target+10:name.target+10+len(encoded)] != encoded):
            raise ValueError("Component name pointer does not match the exact decoded name")
        if struct.unpack_from("<I", data, end)[0] != end - name.target:
            raise ValueError("Component name-pointee footer is stale or missing")
        skeleton = sites[2]
        if data[skeleton.target:skeleton.target+8] != struct.pack("<II", 0, 4):
            raise ValueError("Component skeleton reference is not the original empty pointee")
        if index and start != c.elements[index-1][1]:
            raise ValueError("Component spans are not contiguous")
        footers.append({"name": obj.name, "nameTarget": name.target, "fieldOffset": end,
                        "length": end-name.target})
    return d, footers


def keep_first(data):
    """A fixed-prefix operation: no remaining pointer moves or owner is guessed."""
    d, footers = strict_layout(data)
    c = d.collections[0]
    end = c.elements[0][1]
    # The footer at end belongs to the retained first name pointee. The later
    # components include one another's previous footer in CDMW's element spans.
    result = bytearray(data[:end+4] + data[-1:])
    for offset, value in ((d.blob_offset-24, len(result)),
                          (d.blob_offset-4, len(result)-d.blob_offset), (c.count_offset, 1)):
        struct.pack_into("<I", result, offset, value)
    single = bytes(result)
    after, _ = strict_layout(single)
    if len(after.objects) != 1 or contract(after.objects[0]) != contract(d.objects[0]):
        raise ValueError("Single component lost original semantic fields")
    # Invert this exact tail deletion using only the immutable source tail.
    restored = bytearray(single[:end+4] + data[end+4:-1] + single[-1:])
    for offset in (d.blob_offset-24, d.blob_offset-4, c.count_offset):
        restored[offset:offset+4] = data[offset:offset+4]
    if bytes(restored) != data:
        raise ValueError("Component extraction did not invert to the exact template")
    return single, {"removedComponents": [o.name for o in d.objects[1:]],
                    "originalComponentCount": c.count, "keptComponentCount": 1,
                    "verifiedNameFooters": footers, "retainedPrefixEnd": end+4,
                    "removedTailBytes": len(data)-len(single), "remainingPointersRelocated": 0,
                    "onlyCountAndDataSizesChangedOutsideRemovedTail": True,
                    "exactTemplateRestorationWithSavedTail": True}


def build_part(data, kind):
    from cdmw.core.prefab_binary_edit import rewrite_prefab_paths
    if kind not in PARTS:
        raise ValueError("Only fixed body/head templates are supported")
    spec = PARTS[kind]
    if native.sha256(data) != spec["sha256"]:
        raise ValueError("Prefab template fingerprint mismatch")
    d, _ = strict_layout(data)
    if tuple(o.name for o in d.objects) != spec["names"]:
        raise ValueError("Prefab component names differ from fixed template")
    expected_values = [("_skinnedMeshFile", spec["sourceMesh"]), ("_shrinkTag", "Nude")]
    if kind == "head":
        expected_values.append(("_modelBoneAnimationScriptKey", "breath_effect_basic"))
    original = contract(d.objects[0])
    if (original["values"] != expected_values
            or original["numbers"] != [("_shrinkMaskDistance", "float", "cdcc4c3d")]):
        raise ValueError("Retained component fields differ from reviewed template")
    single, audit = keep_first(data)
    if rewrite_prefab_paths(single, {}).data != single:
        raise ValueError("No-edit prefab rewrite changed source bytes")
    result = rewrite_prefab_paths(single, {spec["sourceMesh"]: spec["targetMesh"]})
    if len(result.edits) != 1 or result.byte_delta != len(spec["targetMesh"])-len(spec["sourceMesh"]):
        raise ValueError("Prefab path rewrite changed more than the single target")
    final, _ = strict_layout(result.data)
    wanted = dict(original, resources=[spec["targetMesh"]],
                  values=[(key, spec["targetMesh"] if key == "_skinnedMeshFile" else val) for key, val in expected_values])
    if len(final.objects) != 1 or contract(final.objects[0]) != wanted:
        raise ValueError("Private prefab changed retained component semantics")
    if rewrite_prefab_paths(result.data, {spec["targetMesh"]: spec["sourceMesh"]}).data != single:
        raise ValueError("Variable-length path inverse did not restore the single component")
    audit.update({"component": wanted, "walkCompleteAndDetermined": True,
                  "strictNameFootersVerified": True, "pathByteDelta": result.byte_delta,
                  "pathRelocatedPointers": result.relocated_pointers,
                  "noEditRewriteByteIdentical": True, "inversePathRewriteByteIdentical": True,
                  "emptySkeletonReferencePreserved": True, "nativeOwnerIdentitySemanticsVerified": False})
    return result.data, audit


def descriptor_audit(data):
    if native.sha256(data) != DESCRIPTOR_SHA256:
        raise ValueError("Current Macduff descriptor fingerprint mismatch")
    root = ET.fromstring(data.decode("utf-8-sig"))
    fields = [(x.tag, dict(x.attrib)) for x in root]
    expected = [("BaseCharacterScale", {"Value": "1.02571"}),
                ("SkeletonName", {"FileName": "1_pc/1_phm/phm_01.pab"}),
                ("SkeletonVariationName", {"FileName": "1_pc/1_phm/nude/cd_phm_00_nude_01_0002.pabc"}),
                ("RagdollName", {"FileName": "1_pc/1_phm/macduff.hkt"}),
                ("AnimationConstraintName", {"FileName": "1_pc/1_phm/phm_01.papr"})]
    if root.tag != "NudePrefabData" or root.attrib or fields != expected:
        raise ValueError("Current Macduff descriptor fields differ")
    return {"byteIdenticalCopy": True, "fields": fields, "candidateMeshFitVerified": False,
            "currentVariationDeformationVerified": False}


def prepare(inputs, descriptor, output, source, deps, game=None):
    if game is not None:
        if inputs is not None or descriptor is not None:
            raise ValueError("Choose game extraction or explicit local inputs, not both")
        dirs = [game, source, deps]
    else:
        if inputs is None or descriptor is None:
            raise ValueError("Local mode requires both inputs and descriptor")
        dirs = [inputs, descriptor.parent, source, deps]
    output = orientation.preflight(output, dirs)
    provenance = native.load_cdmw(source, deps)
    snapshot, files, resources, audits = {}, {}, [], {}
    if game is not None:
        templates = read_native_templates(game)
    else:
        templates = {s["template"]: read_fixed(inputs / s["local"], s["sha256"], snapshot) for s in PARTS.values()}
        templates[DESCRIPTOR_TEMPLATE] = read_fixed(descriptor, DESCRIPTOR_SHA256, snapshot)
    for kind, spec in PARTS.items():
        data = templates[spec["template"]]
        candidate, audits[kind] = build_part(data, kind)
        files["template/"+spec["template"]] = data
        files["resources/"+spec["target"]] = candidate
        resources.append({"kind": "prefab", "virtualPath": spec["target"],
                          "localFile": "resources/"+spec["target"], "sha256": native.sha256(candidate),
                          "templatePath": spec["template"], "templateSha256": spec["sha256"]})
    data = templates[DESCRIPTOR_TEMPLATE]
    audits["bodyDescriptor"] = descriptor_audit(data)
    files["template/"+DESCRIPTOR_TEMPLATE] = data
    files["resources/"+DESCRIPTOR_PATH] = data
    resources.append({"kind": "prefabDescriptor", "virtualPath": DESCRIPTOR_PATH,
                      "localFile": "resources/"+DESCRIPTOR_PATH, "sha256": DESCRIPTOR_SHA256,
                      "templatePath": DESCRIPTOR_TEMPLATE, "templateSha256": DESCRIPTOR_SHA256})
    report = {"schemaVersion": 1, "variant": "private-steve-body-head-components",
              "supportedExeSha256": native.EXE_SHA256, "archiveIndexSha256": INDEX_SHA256,
              "cdmw": provenance, "candidateResources": resources, "audits": audits,
              "requiredExternalMeshes": [x["targetMesh"] for x in PARTS.values()],
              "logicalPrefabs": {key: "/"+s["target"].replace("/bin__/", "/") for key, s in PARTS.items()},
              "files": {key: native.sha256(value) for key, value in files.items()},
              "integration": {key: False for key in ("archiveRegistered", "prefabLoadVerified", "nativeRenderable",
                  "privateAppearanceConfigured", "controlledAppearanceBound", "animationVerified", "equipmentBound",
                  "originalHairBeardSuppressed", "restorationVerified", "installed")},
              "limitations": [
                  "Offline fixed-template clones only; referenced PACs are not bundled or validated by this tool.",
                  "Only CD_Nude and CD_Head remain in these separate candidates; original hair/beard prefabs require a private appearance configuration.",
                  "CD_Nude/CD_Head, Nude shrink tag, 0.05 shrink distance, empty skeleton references and head breath_effect_basic key are preserved byte-for-byte apart from PAC references.",
                  "The original component owner tokens are preserved opaque bytes; their runtime uniqueness or binding semantics are unverified.",
                  "The current Macduff 01_0002 body descriptor is copied unchanged, including scale and ragdoll. This does not prove the new PAC fits that variation or head scaling.",
                  "No head companion descriptor is synthesized; only the observed body descriptor is copied.",
                  "Component collection counts and exact name-pointee footers are validated beyond CDMW's permissive five-byte tail closure.",
                  "Appearance selection, part-shrink behaviour, original/MC equipment, load/unload and restoration remain unverified. No game files or process are touched.",
                  "All native payloads remain in ignored build; no redistribution authorization is claimed."]}
    orientation.verify_snapshot(snapshot)
    native.verify_source(source)
    if game is not None and read_native_templates(game) != templates:
        raise ValueError("Native source templates changed before publication")
    output = orientation.preflight(output, dirs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for relative, payload in {**files, REPORT_NAME: (json.dumps(report, indent=2, allow_nan=False)+"\n").encode()}.items():
        path = output / relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(payload)
    orientation.verify_snapshot(snapshot)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--game-root", type=Path, help="Read the three fixed native templates; default is runtime/installation.json")
    p.add_argument("--inputs", type=Path, help="Explicit local mode: directory containing the two fixed original prefabs")
    p.add_argument("--descriptor", type=Path, help="Explicit local mode: fixed current Macduff body descriptor")
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    p.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    a = p.parse_args()
    if (a.inputs is None) != (a.descriptor is None) or (a.game_root is not None and a.inputs is not None):
        p.error("Use --inputs and --descriptor together, or --game-root/default extraction")
    game = (a.game_root or installed_game()) if a.inputs is None else None
    r = prepare(a.inputs, a.descriptor, a.output, a.cdmw_source, a.deps, game=game)
    print(json.dumps({"output": str(a.output), "resources": r["candidateResources"], "integration": r["integration"]}, indent=2))


if __name__ == "__main__":
    main()
