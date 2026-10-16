"""Inspect the pinned local blue-cube meshinfo without writing any assets.

Print a diagnostic JSON report. The additional string tables and record
boundaries can be accounted for, but the three string tokens and omitted
defaults are unresolved. A successful inspection is NOT mutation approval.
No game files, process, network service or runtime state are accessed.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import struct

import prepare_native_steve as native

ROOT = native.ROOT
MESHINFO = "build/native-block-declaration-fixed/template/object/bin__/00_common/system/cd_testfield_grid_box_1m.meshinfo"
SOURCE = ROOT / "build/cdmw-fixed-source"
DEPS = ROOT / "build/cdmw-deps"
PINS = {
    MESHINFO: "504b30976d10c67ad5eaa2c51ba8259e5cf5f1995cdbfb35cc2c73410df13caf",
    "tools/prepare_native_steve.py": "f4fab8cafa6bc373ae21f196e9f5c4787c0f26e09a99517a96fdde9b17d8dcf0",
    "build/cdmw-fixed-source/cdmw/core/prefab_binary.py": "00e722d184c4cc9340aae06053900f7837c2c256e93cf1e3d3f9476775cb8f4f",
    "build/cdmw-fixed-source/cdmw/core/prefab_collection_spans.py": "2e08190f27cfbcc343a47ff8ce9d8750867a4405da42be3d23070125cf833fff",
    "build/cdmw-fixed-source/cdmw/core/prefab_blob_tail.py": "3fa125af94e393a2b22c42dd24b16b46c624b0f96ed79b0ac6d2a63a1f2711ab",
    "build/cdmw-fixed-source/cdmw/core/effect_binary.py": "9354a688cd52c64cdd31a8a2695e738470620360b9a44029f80326b0e57d7056",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def plain(value):
    if dataclasses.is_dataclass(value):
        return plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if isinstance(value, bytes):
        return value.hex()
    return value


def inspect():
    snapshot = {}
    for name, pin in {**PINS, "tools/inspect_fixed_meshinfo.py": None}.items():
        path = ROOT / name
        native.check_links(path)
        raw = path.read_bytes()
        require(pin is None or native.sha256(raw) == pin, "Fixed source changed: " + name)
        snapshot[name] = raw
    provenance = native.load_cdmw(SOURCE, DEPS)
    from cdmw.core.prefab_binary import _Reader, _read_types, decode_prefab_binary
    from cdmw.core.effect_binary import _Walker, KIND_STRING

    data = snapshot[MESHINFO]
    require(len(data) == 3754 and struct.unpack_from("<HH", data) == (65535, 4), "Unsupported file")
    require(struct.unpack_from("<IH", data, 14) == (15, 4), "Unsupported revision/types")
    reader = _Reader(data, 20)
    types = _read_types(reader, 4)
    require(reader.pos == 3533, "Type declaration boundary changed")

    # These are only numbered tables. Their semantic categories and the
    # conversion from serialized string tokens to table entries are UNKNOWN.
    tables = []
    for expected in (("node_0",), ("", "normal"), ("node_0",)):
        at = reader.pos
        count = reader.u32()
        require(count == len(expected), "String table count changed")
        strings = tuple(reader.text() for _ in range(count))
        require(strings == expected, "String table contents changed")
        tables.append({"start": at, "end": reader.pos, "strings": strings,
                       "category": None})
    header_at = reader.pos
    header = struct.unpack_from("<IIIQII", data, header_at)
    require(header == (1, len(data), 0, 0xffffffffffffffff, 3607, 147), "Data header changed")
    require(header_at + 28 == header[4] and sum(header[-2:]) == len(data), "Blob size mismatch")

    try:
        decode_prefab_binary(data)
    except ValueError as exc:
        generic_error = str(exc)
    else:
        raise ValueError("The fixed generic parser unexpectedly accepted this meshinfo")

    # Preserve the original decoder's failure rather than modifying the
    # third-party grammar to silently accept our token-width hypothesis.
    original = _Walker(data, 0, types, header[4], header[5])
    try:
        original.read_root()
    except ValueError as exc:
        inline_error = {"cursor": original.pos, "message": str(exc)}
    else:
        raise ValueError("The inline string grammar unexpectedly completed")

    class TokenHypothesisWalker(_Walker):
        def __init__(self):
            super().__init__(data, 0, types, header[4], header[5])
            self.tokens = []
            self.record_lengths = []

        def read_member(self, node, member, path, depth):
            if member.flags != KIND_STRING:
                return super().read_member(node, member, path, depth)
            at = self.pos
            token = self.u32()
            self.tokens.append({"member": path + "." + member.name,
                                "declaredType": member.type_name,
                                "start": at, "end": self.pos,
                                "raw": data[at:self.pos].hex(),
                                "unresolvedU32": token, "decodedString": None})

        def read_length(self, pointee, what):
            at = self.pos
            super().read_length(pointee, what)
            self.record_lengths.append({"path": what, "selfPointerField": pointee - 4,
                                        "pointeeStart": pointee, "footer": at,
                                        "length": at - pointee, "end": self.pos})

    walker = TokenHypothesisWalker()
    root = walker.read_root()
    require(walker.pos == len(data), "Token hypothesis left unaccounted bytes")
    require([(v["start"], v["unresolvedU32"]) for v in walker.tokens] ==
            [(3624, 0), (3675, 1), (3679, 0)], "Token boundaries changed")
    require([(r["pointeeStart"], r["footer"], r["length"]) for r in walker.record_lengths] ==
            [(3671, 3684, 13), (3707, 3712, 5), (3746, 3750, 4)], "Record lengths changed")
    require(root.type_name == "StaticMesh" and root.mask == 0x1000aa000000, "Root mask changed")
    children = root.child("_collisionNodeList")
    require(isinstance(children, tuple) and len(children) == 1, "Collision list changed")
    node = children[0]
    require(node.type_name == "CollisionNodeInfo" and node.mask == 7, "Collision node mask changed")

    omitted = []
    for kind, instance, member_name, bit in (
        (types[0], root, "_isWorldCollidable", 22),
        (types[2], node, "_isNoCollisionLayer", 9),
    ):
        member = kind.members[bit]
        require(member.name == member_name and member.type_name == "bool" and
                member.value_size == 1 and not (instance.mask & (1 << bit)), "Flag declaration changed")
        omitted.append({"type": kind.type_name, "member": member_name, "maskBit": bit,
                        "presentInMask": False, "serializedValueOffset": None,
                        "effectiveValue": None, "engineDefaultKnown": False})

    for name, raw in snapshot.items():
        require((ROOT / name).read_bytes() == raw, "Source changed during inspection: " + name)
    require(native.source_fingerprint(SOURCE) == provenance["pythonSourceTreeSha256"], "CDMW tree changed")
    return {
        "schemaVersion": 1, "scope": "one pinned local meshinfo; read-only partial interpretation",
        "fixedCdmw": provenance,
        "sources": {name: {"sha256": native.sha256(raw), "size": len(raw)}
                    for name, raw in snapshot.items()},
        "version": 4, "revision": 15, "types": plain(types), "schemaEnd": 3533,
        "stringTables": tables,
        "dataHeader": {"start": header_at, "end": header_at + 28, "instances": header[0],
                       "fileSize": header[1], "unknown": header[2], "ownerRaw": header[3],
                       "blobOffset": header[4], "blobLength": header[5]},
        "originalParserFailures": {"genericPrefab": generic_error, "effectInlineString": inline_error},
        "conditionalTokenWalk": {"assumption": "each kind-1 string consumes four uninterpreted bytes",
                                 "tokens": walker.tokens, "recordLengths": walker.record_lengths,
                                 "root": plain(root), "walkEnd": walker.pos,
                                 "boundaryConstraintsClose": True, "uniqueSemanticInterpretation": False},
        "omittedCollisionFlags": omitted,
        "limitations": ["Numbered string table categories and token encoding are unresolved.",
                        "An omitted scalar has no serialized value byte; its engine default is unknown.",
                        "Collision enum raw value 4 has no verified symbolic or behavioral meaning here.",
                        "A conditional complete byte walk does not authorize asset edits or native calls."],
        "fullSemanticDecode": False, "mutationContractVerified": False,
        "collisionless": False, "nativeApplied": False, "candidateEmitted": False,
    }


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(inspect(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
