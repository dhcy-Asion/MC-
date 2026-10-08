"""Author twelve local, single-draw rigid PAM/PAMLOD pairs, without installation.

The admitted official Steve geometry is pivot-local and unscaled. Only XYZ and
UV record fields are authored; packed donor fields are preserved, not decoded.
Run in a fresh Python process with the existing fixed local CDMW dependencies.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import struct

import build_steve_rigid_adapter as adapter
import prepare_native_block as block

ROOT = adapter.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-rigid-geometry-1.21.1"
REPORT_NAME = "steve-rigid-geometry-report.json"
VARIANT = "official-steve-twelve-single-draw-pivot-local-static-geometries"
SOURCE = ROOT / "build/cdmw-fixed-source"
DEPS = ROOT / "build/cdmw-deps"
TEMPLATE = block.DEFAULT_OUTPUT / "template"
LIMIT = 32 * 1024 * 1024
TREE_LIMIT = 64 * 1024 * 1024
PAM_START, LOD_START, STRIDE = 1712, 736, 20
GEOMETRY_SIZE = 24 * STRIDE + 36 * 2
SOURCE_PINS = {
    "tools/build_steve_rigid_adapter.py": "245a043479f8e15dac633de21045fc87691831bf6f1d5ee9d3ad18c4822786af",
    "tools/check_steve_rigid_adapter.py": "ca4669629c5fac1f0f2bc8f27e93829bba524c4e627ee10e8c3f134457ae2278",
    "build/steve-rigid-adapter-1.21.1/adapter.json": "916abf94581380f347519210b1bc404a3f0f8b673cf59d34f9282dc35a970875",
    "build/steve-rigid-adapter-1.21.1/steve-rigid-adapter-report.json": "b28a10722be57215b28ed6f916076ab0495be6d841aba2e31c44b96bad6b3086",
    "tools/prepare_native_block.py": "e252b529f1afb8fbd308b6201adaf7fd6e14add1de3d99d4a45b7c1457bfffc2",
    "tools/prepare_native_steve.py": "f4fab8cafa6bc373ae21f196e9f5c4787c0f26e09a99517a96fdde9b17d8dcf0",
}
require, digest = adapter.require, adapter.digest
report_bytes, input_path, input_bytes = adapter.report_bytes, adapter.input_path, adapter.input_bytes
merge_snapshot, verify_snapshot = adapter.merge_snapshot, adapter.verify_snapshot


def preflight(output):
    output = adapter.assets.output_directory(Path(output))
    require(output.name.startswith("steve-rigid-geometry-"), "Geometry output must use its owned build prefix")
    protected = [ROOT / name for name in ("tools", "runtime", "minecraft", "downloads",
                 "build/steve-1.21.1", "build/steve-player-pose-1.21.1",
                 "build/steve-rigid-render-contract-20261008")]
    protected += [SOURCE, DEPS, block.DEFAULT_OUTPUT, adapter.DEFAULT_OUTPUT]
    if output != DEFAULT_OUTPUT:
        protected.append(DEFAULT_OUTPUT)
    for path in protected:
        path = input_path(path)
        require(not (output == path or output.is_relative_to(path) or path.is_relative_to(output)),
                "Geometry output overlaps a protected source/canonical")
    require(not output.exists(), "Geometry output already exists; never overwrite")
    return output


def tree_members(root, source_only=False):
    """Inspect links before descending; record the bounded source/dependency set."""
    root = input_path(root)
    require(root.is_dir(), "Fixed local source/dependency directory is absent")
    files, pending = [], [root]
    while pending:
        folder = pending.pop()
        for path in sorted(folder.iterdir()):
            path = input_path(path)
            if path.is_dir():
                pending.append(path)
            elif path.is_file() and (not source_only or path.suffix in (".py", ".pyc")):
                files.append(path)
            require(len(files) + len(pending) <= 4096, "Source/dependency inventory exceeds its bound")
    return tuple(sorted(files))


def tree_bytes(path):
    """Dependency metadata may legitimately be an empty marker file."""
    path = input_path(path)
    require(path.is_file() and 0 <= path.stat().st_size <= LIMIT, "Source/dependency read bound differs")
    raw = path.read_bytes()
    require(len(raw) <= LIMIT, "Source/dependency bytes exceed their bound")
    return raw


def load_inputs():
    """Return fully watched fixed inputs; imports CDMW only in a fresh process."""
    snapshot = {}
    for name, pin in SOURCE_PINS.items():
        path = input_path(ROOT / name)
        raw = input_bytes(path, LIMIT)
        require(digest(raw) == pin, "Fixed geometry source differs: " + name)
        merge_snapshot(snapshot, {path: raw})
    reviewed, data, upstream = adapter.load()
    merge_snapshot(snapshot, upstream)
    require(data["frameCount"] == 96 and data["jointTransformCount"] == 576,
            "Admitted rigid pose inventory differs")
    own = input_path(Path(__file__))
    merge_snapshot(snapshot, {own: input_bytes(own, LIMIT)})
    trees = {"cdmw": tree_members(SOURCE / "cdmw", True), "dependencies": tree_members(DEPS)}
    watched = (*trees["cdmw"], input_path(SOURCE / "LICENSE"), *trees["dependencies"])
    total = 0
    for path in watched:
        raw = tree_bytes(path)
        total += len(raw)
        require(total <= TREE_LIMIT, "Source/dependency bytes exceed their bound")
        merge_snapshot(snapshot, {path: raw})
    provenance = block.native.load_cdmw(SOURCE, DEPS)
    templates = {}
    for name, pin in block.TEMPLATE_HASHES.items():
        path = input_path(TEMPLATE / name)
        raw = input_bytes(path, LIMIT)
        require(digest(raw) == pin, "Fixed blue-cube template differs: " + name)
        templates[name] = raw
        merge_snapshot(snapshot, {path: raw})
    pam, lod, layout, lod_layout = block.validate_template(templates)
    require(layout["old_geom_end"] == PAM_START + GEOMETRY_SIZE
            and len(templates[block.BASE + ".pam"]) == 2276
            and len(templates[block.BASE + ".pamlod"]) == 1032,
            "Fixed template extent differs")
    require(set(data["geometry"]) == set(adapter.PARTS), "Admitted geometry keys differ")
    sources = {}
    for path, raw in sorted(snapshot.items()):
        # Upstream's fixed official jars live in the sibling .gradle cache. Keep
        # their full watched provenance as ROOT-relative paths, including '..'.
        relative = os.path.relpath(path, ROOT).replace("\\", "/")
        require(not Path(relative).is_absolute() and input_path(ROOT / relative) == path,
                "Geometry provenance cannot be represented relative to ROOT")
        sources[relative] = {"sha256": digest(raw), "bytes": len(raw)}
    result = {"adapterReport": reviewed, "adapter": data, "templates": templates,
              "pam": pam, "pamlod": lod, "pamLayout": layout, "pamlodLayout": lod_layout,
              "snapshot": snapshot, "sources": sources, "trees": trees, "cdmw": provenance}
    verify_inputs(result)
    return result


def protect_snapshot(output, snapshot):
    for path in snapshot:
        source_parent = input_path(path.parent)
        require(not (output == source_parent or output.is_relative_to(source_parent)
                    or source_parent.is_relative_to(output)),
                "Geometry output overlaps a watched source parent")


def verify_inputs(inputs):
    require(tree_members(SOURCE / "cdmw", True) == inputs["trees"]["cdmw"]
            and tree_members(DEPS) == inputs["trees"]["dependencies"],
            "Source/dependency inventory changed during geometry preparation")
    require(block.native.source_fingerprint(SOURCE) == block.native.CDMW_SOURCE_SHA256,
            "Fixed CDMW source tree changed")
    verify_snapshot({path: raw for path, raw in inputs["snapshot"].items() if raw})
    for path, raw in inputs["snapshot"].items():
        if not raw:
            require(tree_bytes(path) == raw, "Empty source/dependency marker changed")


def source_mapping(pam, source):
    positions = source["positionsPivotLocalModelMetres"]
    normals, uv, indices = source["normals"], source["uv"], source["indices"]
    require(len(positions) == len(normals) == len(uv) == 24 and len(indices) == 36,
            "Only complete split-corner MC cuboids are supported")
    positions = [adapter.finite_vector(row, 3, "MC position") for row in positions]
    normals = [adapter.finite_vector(row, 3, "MC normal") for row in normals]
    uv = [adapter.finite_vector(row, 2, "MC UV") for row in uv]
    require(all(0 <= x <= 1 for row in uv for x in row), "MC UV is outside its fixed atlas")
    require(all(type(x) is int and 0 <= x < 24 for x in indices), "MC index boundary differs")
    bmin = tuple(min(p[a] for p in positions) for a in range(3))
    bmax = tuple(max(p[a] for p in positions) for a in range(3))
    span = [bmax[a] - bmin[a] for a in range(3)]
    require(all(math.isfinite(x) and x > 0 for x in span), "MC cuboid has unsupported extent")
    unit = [[(p[a] - bmin[a]) / span[a] for a in range(3)] for p in positions]
    require(all(min(abs(x), abs(x - 1)) < 1e-6 for p in unit for x in p),
            "MC source is not a cuboid corner set")
    require(all(sum(abs(x) > 1e-6 for x in n) == 1 and abs(sum(x*x for x in n) - 1) < 1e-6
                for n in normals), "MC cuboid normals are not unit axis normals")
    native = pam.submeshes[0]
    mapping = []
    for pos, normal in zip(native.vertices, native.normals):
        matches = [i for i, (p, n) in enumerate(zip(unit, normals))
                   if max(abs(x-y) for x, y in zip(pos, p)) <= 1 / 65535 + 1e-7
                   and max(abs(x-y) for x, y in zip(normal, n)) < 1e-6]
        require(len(matches) == 1, "Native/MC split corner mapping is missing or ambiguous")
        mapping.append(matches[0])
    require(sorted(mapping) == list(range(24)), "Native/MC corner mapping is not bijective")
    covered = {q: [] for q in range(6)}
    for face in native.faces:
        ids = [mapping[i] for i in face]
        require(len({i // 4 for i in ids}) == 1, "Native triangle crosses MC source faces")
        covered[ids[0] // 4].append(ids)
        p0, p1, p2 = (positions[i] for i in ids)
        a, b = [p1[i]-p0[i] for i in range(3)], [p2[i]-p0[i] for i in range(3)]
        cross = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
        require(sum(cross[i] * normals[ids[0]][i] for i in range(3)) > 0,
                "Native triangle winding disagrees with MC face normal")
    require(all(len(tris) == 2 and {v for tri in tris for v in tri} == set(range(q*4, q*4+4))
                for q, tris in covered.items()), "Native faces do not cover all MC quads")
    return mapping, positions, uv, bmin, bmax


def geometry_pair(inputs, source):
    from cdmw.modding.mesh_pam_builder import _serialize_pam_local_layout
    from cdmw.modding.mesh_pamlod_builder import _serialize_pamlod_lod0_full_rebuild
    from cdmw.modding.mesh_parser import parse_pam, parse_pamlod
    mapping, positions, uv, bmin, bmax = source_mapping(inputs["pam"], source)
    original = inputs["templates"][block.BASE + ".pam"]
    original_lod = inputs["templates"][block.BASE + ".pamlod"]
    edited = copy.deepcopy(inputs["pam"])
    part = edited.submeshes[0]
    part.vertices = [tuple(positions[i]) for i in mapping]
    part.uvs = [(uv[i][0], 1 - uv[i][1]) for i in mapping]
    edited.bbox_min, edited.bbox_max = bmin, bmax
    main = bytearray(_serialize_pam_local_layout(edited, inputs["pam"], original,
                                                inputs["pamLayout"], bmin, bmax))
    require(len(main) == 2276, "PAM writer changed the fixed layout extent")
    # The writer may select a nearby donor after pivot/extent changes. Restore
    # the exact native split-corner donor selected by our position/normal match.
    for i in range(24):
        offset = PAM_START + i * STRIDE
        main[offset+6:offset+8] = original[offset+6:offset+8]
        main[offset+12:offset+20] = original[offset+12:offset+20]
    main = bytes(main)
    parsed = parse_pam(main, source["name"] + ".pam")
    far = bytearray(_serialize_pamlod_lod0_full_rebuild(parsed.submeshes, inputs["pamlod"],
                                                      original_lod, source["name"] + ".pamlod"))
    require(len(far) == LOD_START + GEOMETRY_SIZE, "PAMLOD writer changed the fixed layout extent")
    # The fixed LOD writer expands bounds by epsilon; its identical u16 records
    # must instead use precisely the serialized main-PAM float32 bounds.
    far[0x10:0x1C] = main[0x14:0x20]
    far[0x1C:0x28] = main[0x20:0x2C]
    # Existing block contract: all 24 complete records and the unchanged native
    # indices replace the original 13-corner LOD tail, not just its XYZ/UV fields.
    far[LOD_START:] = main[PAM_START:PAM_START+GEOMETRY_SIZE]
    far = bytes(far)
    indices_raw = original[PAM_START + 24*STRIDE:PAM_START + GEOMETRY_SIZE]
    require(main[PAM_START + 24*STRIDE:PAM_START + GEOMETRY_SIZE] == indices_raw
            and far[LOD_START:] == main[PAM_START:PAM_START+GEOMETRY_SIZE],
            "Native indices or complete LOD geometry changed")
    for raw, parser, start in ((main, parse_pam, PAM_START), (far, parse_pamlod, LOD_START)):
        mesh = parser(raw)
        require((len(mesh.submeshes), mesh.total_vertices, mesh.total_faces, mesh.has_bones) == (1, 24, 12, False),
                "Rigid candidate topology is unsupported")
        require(mesh.submeshes[0].faces == inputs["pam"].submeshes[0].faces,
                "Rigid candidate changed native face order")
        for i, si in enumerate(mapping):
            rec, donor = raw[start+i*STRIDE:start+(i+1)*STRIDE], original[PAM_START+i*STRIDE:PAM_START+(i+1)*STRIDE]
            require(rec[6:8] + rec[12:20] == donor[6:8] + donor[12:20], "Packed native donor fields changed")
            require(max(abs(mesh.submeshes[0].vertices[i][a]-positions[si][a])
                        for a in range(3)) <= max(bmax[a]-bmin[a] for a in range(3))/65535 + 2e-7,
                    "Rigid candidate position quantization differs")
            packed_uv = struct.unpack_from("<2e", rec, 8)
            require(max(abs(packed_uv[a] - part.uvs[i][a]) for a in range(2)) <= .0005,
                    "Rigid candidate UV quantization differs")
    return main, far, mapping, bmin, bmax


def prepare(output=DEFAULT_OUTPUT):
    output = preflight(output)
    inputs = load_inputs()
    protect_snapshot(output, inputs["snapshot"])
    files, parts = {}, []
    outer_names = {joint: outer for outer, joint in adapter.assets.OUTER_PARTS.items()}
    for joint in adapter.PARTS:
        group = inputs["adapter"]["geometry"][joint]
        require([m["name"] for m in group["meshes"]] == [joint, outer_names[joint]],
                "Rigid joint base/outer inventory differs")
        for layer, source in enumerate(group["meshes"]):
            require(source["outerLayer"] is bool(layer), "Rigid layer identity differs")
            main, far, mapping, bmin, bmax = geometry_pair(inputs, source)
            stem = f"geometry/{joint}/{source['name']}"
            files[stem + ".pam"], files[stem + ".pamlod"] = main, far
            parts.append({"joint": joint, "sourceMesh": source["name"], "outerLayer": bool(layer),
                          "pam": stem + ".pam", "pamlod": stem + ".pamlod",
                          "sourceVertexIndices": mapping, "neutralPivot": group["neutralPivotFeetFrameModelMetres"],
                          "bboxMin": list(bmin), "bboxMax": list(bmax), "vertices": 24, "triangles": 12,
                          "sourceGeometry": {"sha256": digest(report_bytes(source)),
                                             "positionsSha256": digest(report_bytes(source["positionsPivotLocalModelMetres"])),
                                             "uvSha256": digest(report_bytes(source["uv"])),
                                             "indicesSha256": digest(report_bytes(source["indices"]))}})
    require(len(parts) == 12 and len(files) == 24, "Rigid geometry inventory differs")
    report = {"schemaVersion": 1, "minecraftVersion": "1.21.1", "variant": VARIANT,
              "sources": inputs["sources"], "files": {name: digest(raw) for name, raw in files.items()},
              "parts": parts, "cdmw": inputs["cdmw"],
              "geometry": {"joints": 6, "layers": 12, "verticesPerLod": 288, "trianglesPerLod": 144,
                           "drawsPerFile": 1, "pamBytes": 2276, "pamlodBytes": 1288},
              "coordinates": {"geometry": "unscaled pivot-local model metres; static POSITION minus neutral joint translation",
                              "rootScaleBaked": False, "rendererRootScale": adapter.ROOT_SCALE,
                              "uv": "original MC atlas U, 1-V; half floats", "nativeWorldUnitsPerModelMetre": 1,
                              "nativeUnitsCalibratedInGame": False},
              "recordContract": {"stride": STRIDE, "pamVertexOffset": PAM_START, "pamlodVertexOffset": LOD_START,
                                 "authoredRanges": [[0, 6], [8, 12]], "donorPreservedRanges": [[6, 8], [12, 20]],
                                 "nativeFaceOrderPreserved": True, "lodCompleteRecordsEqualMain": True,
                                 "packedNormalDecoded": False, "tangentToNewUvVerified": False,
                                 "parserNormals": "geometric normals derived from native indices"},
              "integration": {"geometryAuthored": True, "materialBinding": False, "collisionless": False,
                              "groupObjects": False, "ownerFollow": False, "nativeApplied": False, "installed": False,
                              "animationSystemComplete": False, "installableResourcePackage": False},
              "limitations": ["Geometry only: no material, texture, prefab, HKX or installation manifest is emitted.",
                              "Base and outer layers remain separate. Skin-option visibility and sleeve opacity are not discarded.",
                              "Packed native normal/tangent fields retain their corresponding axis-face donors; tangent consistency with new UV is unverified.",
                              "The .9375 renderer scale is not baked; the admitted rigid transform applies it once. Full renderer root/world offsets and owner orientation remain unverified.",
                              "No collision-only control, group creation, runtime following, input suppression or combat is implemented."]}
    encoded = report_bytes(report)
    require(len(encoded) <= LIMIT, "Geometry report exceeds its bound")
    verify_inputs(inputs)
    output = preflight(output)
    protect_snapshot(output, inputs["snapshot"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for name, raw in (*files.items(), (REPORT_NAME, encoded)):
        path = output / name
        block.native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    verify_inputs(inputs)
    require({p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
            == set(files) | {REPORT_NAME}, "Geometry output inventory differs")
    for name, raw in (*files.items(), (REPORT_NAME, encoded)):
        require(input_bytes(output / name, LIMIT) == raw, "Geometry output changed during publication")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = prepare(args.output)
    print(json.dumps({"output": str(adapter.assets.output_directory(args.output)),
                      "files": len(report["files"]), "parts": len(report["parts"]),
                      **report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
