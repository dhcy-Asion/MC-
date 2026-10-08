"""Independent raw-MC matrix/vertex checks and actual fixed MakeTransform C++.

No MC/JVM/server/game/native function is launched. The isolated executable only
evaluates the two extracted arithmetic functions; it has no engine interfaces.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import build_steve_rigid_adapter as adapter

ROOT = adapter.ROOT
DEFAULT_EVIDENCE = ROOT / "build/steve-rigid-adapter-check-20261008"
COMPILER = Path("C:/msys64/ucrt64/bin/g++.exe")
COMPILER_SHA256 = "08c11faa4f15a460af8d90a2fd90f658658938c94051bde8babfbecce3304c6c"
MATRIX_TOLERANCE = 3e-6
VERTEX_TOLERANCE = 3e-6
BUILD_FLAGS = ["-std=c++17", "-O0", "-fno-fast-math", "-ffp-contract=off", "-static-libgcc", "-static-libstdc++"]


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mv(matrix, vector):
    return [sum(matrix[i][j] * vector[j] for j in range(3)) for i in range(3)]


def axis(axis_name, angle):
    c, s = math.cos(angle), math.sin(angle)
    if axis_name == "x":
        return [[1, 0, 0], [0, c, -s], [0, s, c]]
    if axis_name == "y":
        return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def raw_mc_matrix(raw):
    # Independently use official ModelPart raw radians in its documented ZYX
    # matrix order, not the adapter's exported quaternion or inverse formulas.
    official = mul(mul(axis("z", raw["roll"]), axis("y", raw["yaw"])), axis("x", raw["pitch"]))
    c = [[1, 0, 0], [0, -1, 0], [0, 0, -1]]
    return mul(mul(c, official), c)


def quaternion_matrix(q):
    x, y, z, w = q
    return [[1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
            [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
            [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)]]


def matrix_quaternion(m):
    # Test-only independent matrix -> Hamilton quaternion via dominant diagonal.
    trace = sum(m[i][i] for i in range(3))
    if trace > 0:
        s = math.sqrt(trace + 1) * 2
        q = [(m[2][1]-m[1][2])/s, (m[0][2]-m[2][0])/s, (m[1][0]-m[0][1])/s, s/4]
    else:
        i = max(range(3), key=lambda k: m[k][k]); j, k = (i+1) % 3, (i+2) % 3
        s = math.sqrt(1 + m[i][i] - m[j][j] - m[k][k]) * 2
        q = [0.0] * 4; q[i] = s/4; q[j] = (m[j][i]+m[i][j])/s; q[k] = (m[k][i]+m[i][k])/s
        q[3] = (m[k][j]-m[j][k])/s
    return [x / math.hypot(*q) for x in q]


def matrix_error(a, b):
    return max(abs(a[i][j] - b[i][j]) for i in range(3) for j in range(3))


def edge_cases():
    cases = []
    for index, angles in enumerate(((.71, .53, -.89), (-1.13, .94, .36), (.48, -1.29, .77))):
        wanted = raw_mc_matrix(dict(zip(("pitch", "yaw", "roll"), angles)))
        q = matrix_quaternion(wanted)
        for sign in (1, -1):
            cases.append({"name": f"rawZYX_composite_{index}_sign{sign}", "quaternion": [sign*x for x in q], "matrix": wanted})
    for index, pitch in enumerate((math.pi/2, -math.pi/2, math.pi/2-1e-7, -math.pi/2+1e-7)):
        wanted = mul(mul(axis("y", .7), axis("x", pitch)), axis("z", -.4))
        cases.append({"name": f"YXZ_singular_or_near_{index}", "quaternion": matrix_quaternion(wanted), "matrix": wanted})
    for index, yaw in enumerate((0, math.pi)):
        wanted = axis("y", yaw)
        cases.append({"name": f"identity_or_halfturn_{index}", "quaternion": matrix_quaternion(wanted), "matrix": wanted})
    return cases


def cpp_oracle(stage, data, cases, snapshot):
    native_path = adapter.input_path(ROOT / "vendor/world-builder/asi/cdmodkit/cdmodkit.cpp")
    header_path = adapter.input_path(ROOT / "vendor/world-builder/asi/cdmodkit/core.h")
    source, header = snapshot[native_path].decode("utf-8"), snapshot[header_path].decode("utf-8")
    functions = re.search(r"static void QMul\(.*?\r?\n}\r?\nstatic void MakeTransform\(.*?\r?\n}", source, re.S)
    vec = re.search(r"^struct Vec3 \{.*?};", header, re.M)
    rot = re.search(r"^struct Rot \{.*?};", header, re.M)
    adapter.require(functions is not None and vec is not None and rot is not None, "Fixed arithmetic source window unavailable")
    extracted = (vec.group() + "\n" + rot.group() + "\n" + functions.group()).encode()
    # Only these exact declarations/functions are included. No game headers,
    # engine pointers, loaders, native function addresses or plugin code.
    harness = b"#include <cmath>\n#include <cstdint>\n#include <cstring>\n#include <cstdio>\n" + extracted + b'''
int main(int argc, char** argv) {
    if (argc != 3) return 2;
    FILE* in = fopen(argv[1], "rb"); if (!in) return 3;
    FILE* out = fopen(argv[2], "wb"); if (!out) { fclose(in); return 4; }
    uint32_t count=0; if (fread(&count,4,1,in)!=1 || count>1024) return 5;
    for (uint32_t i=0;i<count;++i) {
        float v[7], xf[12]; uint32_t tiled;
        if(fread(v,4,7,in)!=7 || fread(&tiled,4,1,in)!=1 || tiled>1) return 6;
        Rot r{v[0],v[1],v[2]}; Vec3 p{v[3],v[4],v[5]};
        MakeTransform(xf,p,r,v[6],tiled!=0);
        if(fwrite(xf,4,12,out)!=12) return 7;
    }
    if(fgetc(in)!=EOF) return 8;
    fclose(in); return fclose(out)==0 ? 0 : 9;
}
'''
    compiler = adapter.input_path(COMPILER)
    compiler_raw = adapter.input_bytes(compiler, 16 * 1024 * 1024)
    adapter.require(adapter.digest(compiler_raw) == COMPILER_SHA256, "Fixed available C++ compiler differs")
    adapter.merge_snapshot(snapshot, {compiler: compiler_raw})
    environment = dict(os.environ)
    environment["PATH"] = str(compiler.parent) + os.pathsep + environment.get("PATH", "")
    cpp, executable = stage / "fixed-make-transform.cpp", stage / "fixed-make-transform.exe"
    cpp.write_bytes(harness)
    commands = [[str(compiler), *BUILD_FLAGS, str(cpp), "-o", str(executable)]]
    result = subprocess.run(commands[0], cwd=stage, env=environment, capture_output=True, text=True, timeout=60)
    adapter.require(result.returncode == 0, "Actual isolated C++ compilation failed: " + result.stderr[-4000:])
    rows = []
    for frame in data["frames"]:
        for name in adapter.PARTS:
            part = frame["parts"][name]; r = part["rotYXZDegrees"]
            rows.append((r["yaw"], r["pitch"], r["roll"], *part["positionFeetFrameWorldUnits"], part["uniformScale"], 0))
    for case in cases:
        r = adapter.quaternion_to_native_rot(case["quaternion"])
        rows.append((r["yaw"], r["pitch"], r["roll"], 0, 0, 0, .9375, 0))
    for x, z in ((1234.5, -2345.25), (-1234.5, 2345.25)):
        rows.append((31, -23, 17, x, .5, z, .9375, 1))
    raw = struct.pack("<I", len(rows)) + b"".join(struct.pack("<7fI", *row) for row in rows)
    input_file, output_file = stage / "inputs.bin", stage / "outputs.bin"
    input_file.write_bytes(raw)
    adapter.verify_snapshot(snapshot)
    commands.append([str(executable), str(input_file), str(output_file)])
    result = subprocess.run(commands[-1], cwd=stage, env=environment, capture_output=True, timeout=15)
    adapter.require(result.returncode == 0, "Actual isolated fixed arithmetic evaluation failed")
    output = output_file.read_bytes()
    adapter.require(len(output) == 48 * len(rows), "C++ output count/stride differs")
    transforms = [struct.unpack_from("<12f", output, 48*i) for i in range(len(rows))]
    for xf in transforms:
        adapter.require(all(math.isfinite(v) for v in xf[:10]) and xf[11] == 0, "C++ bounded output has nonfinite transform")
    adapter.verify_snapshot(snapshot)
    version = subprocess.run([str(compiler), "--version"], cwd=stage, env=environment, capture_output=True, text=True, timeout=10)
    adapter.require(version.returncode == 0, "Compiler identity command failed")
    evidence = {"compilerPath": str(compiler), "compilerSha256": COMPILER_SHA256,
                "compilerVersion": version.stdout.splitlines()[0], "flags": BUILD_FLAGS,
                "extractedSourceSha256": adapter.digest(extracted), "harnessSourceSha256": adapter.digest(harness),
                "executableSha256": adapter.digest(executable.read_bytes()), "inputSha256": adapter.digest(raw),
                "outputSha256": adapter.digest(output), "records": len(rows), "commands": commands,
                "nativeArithmeticCalled": True, "gameNativeFunctionCalled": False}
    # The tile slot is int16 bits, not a float. Preserve its original bytes;
    # decoding/repacking a NaN float could quiet it and corrupt a tile pair.
    evidence["tilePairs"] = [list(struct.unpack_from("<hh", output, 48*i+40)) for i in range(len(rows)-2, len(rows))]
    return transforms, evidence


class RigidChecks(unittest.TestCase):
    plan = adapter.DEFAULT_OUTPUT
    evidence = DEFAULT_EVIDENCE
    metrics = {}

    @classmethod
    def setUpClass(cls):
        cls.report, cls.data, cls.snapshot = adapter.load(cls.plan)
        cls.poses = adapter.player.strict_json(cls.snapshot[adapter.player.DEFAULT_OUTPUT.resolve() / "poses.json"])
        cls.geometry = adapter.player.strict_json(cls.snapshot[adapter.assets.DEFAULT_OUTPUT.resolve() / "minecraft-model.json"])
        cls.gltf = adapter.player.strict_json(cls.snapshot[adapter.assets.DEFAULT_OUTPUT.resolve() / "steve.gltf"])
        cls.binary = cls.snapshot[adapter.assets.DEFAULT_OUTPUT.resolve() / "steve.bin"]
        cls.raw_parts = {part["name"]: part for part in cls.geometry["parts"]}
        cls.cases = edge_cases()
        stage = cls.evidence / "oracle"; stage.mkdir()
        cls.transforms, cls.cpp = cpp_oracle(stage, cls.data, cls.cases, cls.snapshot)

    @classmethod
    def tearDownClass(cls):
        adapter.verify_snapshot(cls.snapshot)

    def test_01_fixed_sources_real_96_and_scope(self):
        self.assertEqual(len(self.data["frames"]), 96)
        self.assertEqual(sum(len(frame["parts"]) for frame in self.data["frames"]), 576)
        self.assertEqual(self.report["sources"]["build/steve-player-pose-1.21.1/steve-player-pose-report.json"]["sha256"], adapter.SOURCE_PINS["build/steve-player-pose-1.21.1/steve-player-pose-report.json"])
        for key, value in self.report["integration"].items():
            self.assertIs(value, key == "officialPlayerPoseSource")
        self.assertIs(self.report["coordinates"]["nativeUnitsCalibratedInGame"], False)
        for source, frame in zip(self.poses["samples"], self.data["frames"]):
            for key in ("sampleIndex", "sourceFrameIndex", "sourceDeltaIndex", "sourceServerTick", "sourceProfile", "sourceAge"):
                self.assertEqual(frame[key], source[key])
            self.assertEqual(frame["tickDelta"], source["inputs"]["tickDelta"])
        self.assertEqual({frame["sourceAge"] for frame in self.data["frames"]}, set(range(12, 44)))

    def test_02_static_pivot_geometry_normals_uv_and_indices(self):
        count = 0
        for index, name in enumerate(adapter.PARTS):
            group = self.data["geometry"][name]
            p = self.raw_parts[name]["pivot"]
            pivot = [p[0]/16, 1.5-p[1]/16, -p[2]/16]
            self.assertEqual(group["neutralPivotFeetFrameModelMetres"], pivot)
            self.assertEqual(len(group["meshes"]), 2)
            ibm = adapter.asset_check.accessor(self.gltf, self.binary, self.gltf["skins"][0]["inverseBindMatrices"])[index]
            for a, b in zip(ibm[12:15], [-x for x in pivot]):
                self.assertAlmostEqual(a, b, delta=1e-7)
            for mesh in group["meshes"]:
                part = self.raw_parts[mesh["name"]]
                vertices = [(v, quad["normal"]) for cuboid in part["cuboids"] for quad in cuboid["quads"] for v in quad["vertices"]]
                self.assertEqual(mesh["indices"], [q+j for q in range(0, 24, 4) for j in (0,1,2,0,2,3)])
                for (v, normal), local, uv, n in zip(vertices, mesh["positionsPivotLocalModelMetres"], mesh["uv"], mesh["normals"]):
                    wanted = [v[0]/16, -v[1]/16, -v[2]/16]
                    for actual, expected in zip(local, wanted):
                        self.assertAlmostEqual(actual, expected, delta=1e-7)
                    self.assertEqual(uv, v[3:5]); self.assertEqual(n, [normal[0], -normal[1], -normal[2]])
                    count += 1
        self.assertEqual(count, 288)

    def test_03_actual_cpp_all576_against_raw_euler_and_vertices(self):
        max_matrix = max_vertex = max_source_matrix = max_norm = 0.0
        vertex_count = 0
        for frame_index, sample in enumerate(self.poses["samples"]):
            for part_index, name in enumerate(adapter.PARTS):
                xf = self.transforms[frame_index*6 + part_index]
                raw = sample["parts"][name]["rawModelPart"]
                expected_matrix = raw_mc_matrix(raw)
                native_matrix = quaternion_matrix(xf[3:7])
                max_matrix = max(max_matrix, matrix_error(expected_matrix, native_matrix))
                max_source_matrix = max(max_source_matrix, matrix_error(expected_matrix, quaternion_matrix(sample["parts"][name]["rotationQuaternionXYZW"])))
                max_norm = max(max_norm, abs(math.hypot(*xf[3:7])-1))
                self.assertEqual(xf[:3], (0.9375,)*3)
                self.assertEqual(xf[10], 0)
                pivot = [raw["pivotX"]/16, 1.5-raw["pivotY"]/16, -raw["pivotZ"]/16]
                for mesh in self.data["geometry"][name]["meshes"]:
                    vertices = [v for c in self.raw_parts[mesh["name"]]["cuboids"] for q in c["quads"] for v in q["vertices"]]
                    for local, v in zip(mesh["positionsPivotLocalModelMetres"], vertices):
                        actual = [xf[7+i] + xf[i]*x for i, x in enumerate(mv(native_matrix, local))]
                        oracle = mv(expected_matrix, [v[0]/16, -v[1]/16, -v[2]/16])
                        expected = [.9375*(pivot[i]+oracle[i]) for i in range(3)]
                        max_vertex = max(max_vertex, max(abs(a-b) for a, b in zip(actual, expected)))
                        vertex_count += 1
        self.assertLess(max_source_matrix, MATRIX_TOLERANCE)
        self.assertLess(max_matrix, MATRIX_TOLERANCE); self.assertLess(max_vertex, VERTEX_TOLERANCE)
        self.assertLess(max_norm, MATRIX_TOLERANCE); self.assertEqual(vertex_count, 27648)
        self.metrics.update(realJointMatrixMaxAbsError=max_matrix, officialQuaternionVsRawEulerMaxAbsError=max_source_matrix,
                            realVertexMaxAbsErrorWorldUnits=max_vertex, nativeQuaternionNormMaxError=max_norm,
                            realVerticesChecked=vertex_count)

    def test_04_noncommuting_antipodes_and_singular_actual_cpp(self):
        max_error = 0.0
        for index, case in enumerate(self.cases):
            actual = quaternion_matrix(self.transforms[576+index][3:7])
            max_error = max(max_error, matrix_error(actual, case["matrix"]))
        self.assertEqual(len(self.cases), 12); self.assertLess(max_error, MATRIX_TOLERANCE)
        # A direct raw Euler copy is demonstrably wrong for compound rotations.
        raw = {"pitch": .71, "yaw": .53, "roll": -.89}
        wrong = mul(mul(axis("y", -.53), axis("x", .71)), axis("z", .89))
        self.assertGreater(matrix_error(raw_mc_matrix(raw), wrong), .1)
        self.metrics["edgeCaseMatrixMaxAbsError"] = max_error

    def test_05_compiled_position_tile_layout(self):
        for i, (x, z) in enumerate(((1234.5, -2345.25), (-1234.5, 2345.25))):
            xf = self.transforms[588+i]
            tile = tuple(self.cpp["tilePairs"][i])
            self.assertEqual(tile, (int(x*.001), int(z*.001)))
            self.assertEqual(xf[7], x-tile[0]*1000); self.assertEqual(xf[8], .5); self.assertEqual(xf[9], z-tile[1]*1000)
            self.assertEqual(xf[11], 0)

    def test_06_nonfinite_invalid_quaternion_and_scale_reject(self):
        for value in ([math.nan,0,0,1], [0,math.inf,0,1], [0,0,0,0], [0,0,0,2], [True,0,0,1]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                adapter.quaternion_to_native_rot(value)
        for value in ([1,2,1], [0,0,0], [-1,-1,-1], [1,1,math.nan], [1,1,math.inf]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                adapter.uniform_scale(value)
        for field, value in (("translationMetres", [0,math.inf,0]), ("scale", [1,2,1]),
                             ("scale", [1e-100]*3), ("rotationQuaternionXYZW", [0,0,0,0])):
            altered = copy.deepcopy(self.poses); altered["samples"][0]["parts"]["head"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                adapter.convert(altered, self.geometry, self.gltf, self.binary)
        with self.assertRaises(ValueError):
            adapter.f32(1e100)

    def test_07_output_protection_before_sources_no_overwrite(self):
        for path in (adapter.DEFAULT_OUTPUT, adapter.DEFAULT_OUTPUT/"steve-rigid-adapter-child", ROOT/"build",
                     adapter.assets.DEFAULT_OUTPUT, adapter.player.DEFAULT_OUTPUT, ROOT/"runtime", ROOT/"tools",
                     ROOT/"build/steve-rigid-render-contract-20261008"):
            with self.subTest(path=path), patch.object(adapter, "load_sources") as loader, self.assertRaises(ValueError):
                adapter.build(path)
            loader.assert_not_called()
        with self.assertRaises(ValueError):
            adapter.preflight(ROOT.parent/"steve-rigid-adapter-outside")

    def test_08_source_race_conflict_and_pin_reject(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"build", prefix="steve-rigid-adapter-fixture-") as temporary:
            stage = adapter.assets.output_directory(Path(temporary)); source = stage/"source.bin"
            source.write_bytes(b"before"); snapshot = {source.resolve(): b"before"}
            with self.assertRaises(ValueError):
                adapter.merge_snapshot(snapshot, {source.resolve(): b"other"})
            source.write_bytes(b"after")
            with self.assertRaises(ValueError):
                adapter.verify_snapshot(snapshot)
            output = stage/"steve-rigid-adapter-rejected"
            summary = self.report["sources"]
            with patch.object(adapter, "load_sources", return_value=(self.poses,self.geometry,self.gltf,self.binary,summary,snapshot)), self.assertRaises(ValueError):
                adapter.build(output)
            self.assertFalse(output.exists())
        with patch.object(adapter, "input_bytes", return_value=b"wrong fixed source"), patch.object(adapter.player, "load") as upstream, self.assertRaises(ValueError):
            adapter.load_sources()
        upstream.assert_not_called()

    def test_09_independent_rebuild_canonical_tamper_and_final_snapshot(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"build", prefix="steve-rigid-adapter-rebuild-") as temporary:
            output = adapter.assets.output_directory(Path(temporary))/"steve-rigid-adapter-copy"
            report = adapter.build(output)
            for name in (adapter.DATA_NAME, adapter.REPORT_NAME):
                self.assertEqual((output/name).read_bytes(), (self.plan/name).read_bytes())
            self.assertEqual(report, self.report)
            changed = copy.deepcopy(self.data)
            changed["frames"][0]["parts"]["head"]["uniformScale"] = .9375*.9375
            raw = adapter.report_bytes(changed); (output/adapter.DATA_NAME).write_bytes(raw)
            edited = copy.deepcopy(report); edited["files"][adapter.DATA_NAME] = adapter.digest(raw)
            (output/adapter.REPORT_NAME).write_bytes(adapter.report_bytes(edited))
            with self.assertRaises(ValueError):
                adapter.load(output)
        adapter.verify_snapshot(self.snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=adapter.DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--rebuild", action="store_true", help="Build missing canonical adapter; test also rebuilds independently without MC/JVM")
    args = parser.parse_args()
    evidence = adapter.preflight(args.output)
    plan = adapter.assets.output_directory(args.plan)
    if args.rebuild and not plan.exists():
        adapter.build(plan)
    evidence.parent.mkdir(parents=True, exist_ok=True); evidence.mkdir()
    RigidChecks.plan, RigidChecks.evidence = plan, evidence
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RigidChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {"schemaVersion": 1, "command": ["py", "-3.12", "-B", "tools/check_steve_rigid_adapter.py", *os.sys.argv[1:]],
               "checks": result.testsRun, "passed": result.wasSuccessful(), "errors": result.errors, "failures": result.failures,
               "cpp": getattr(RigidChecks, "cpp", None), "metrics": RigidChecks.metrics,
               "tolerances": {"matrixMaxAbs": MATRIX_TOLERANCE, "vertexMaxAbsWorldUnits": VERTEX_TOLERANCE},
               "artifactSha256": {name: adapter.digest((plan/name).read_bytes()) for name in (adapter.DATA_NAME, adapter.REPORT_NAME) if (plan/name).is_file()},
               "sourceSha256": {name: adapter.digest((ROOT/"tools"/name).read_bytes()) for name in ("build_steve_rigid_adapter.py", "check_steve_rigid_adapter.py")},
               "nativeWorldUnitsPerModelMetre": 1, "nativeUnitsCalibratedInGame": False,
               "rendererRootReplayed": False, "nativeOwnerOrientationVerified": False,
               "nativeApplied": False, "animationSystemComplete": False}
    # unittest error entries contain TestCase objects; persist explicit names.
    for name in ("errors", "failures"):
        summary[name] = [{"test": test.id(), "trace": trace} for test, trace in summary[name]]
    (evidence/"check-results.json").write_bytes(adapter.report_bytes(summary))
    print(json.dumps({"checks": result.testsRun, "passed": result.wasSuccessful(), "evidence": str(evidence),
                      "metrics": RigidChecks.metrics, "nativeApplied": False, "animationSystemComplete": False}, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
