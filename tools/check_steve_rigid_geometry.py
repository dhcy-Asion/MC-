"""Independently check local rigid PAM/PAMLOD geometry; no game or installation.

The oracle reads original glTF accessors and neutral joints, not the converter's
vertex mapping. Packed donor bytes are preserved, not claimed to be decoded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import unittest

import prepare_native_block as block
import build_steve_rigid_adapter as adapter
import check_steve_asset as asset

ROOT = block.ROOT
DEFAULT_PLAN = ROOT / 'build/steve-rigid-geometry-1.21.1'
DEFAULT_OUTPUT = ROOT / 'build/steve-rigid-geometry-check-20261008'
REPORT = 'steve-rigid-geometry-report.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def independent_meshes():
    folder = ROOT / 'build/steve-1.21.1'
    gltf = json.loads((folder / 'steve.gltf').read_bytes())
    binary = (folder / 'steve.bin').read_bytes()
    result = {}
    for mesh in gltf['meshes']:
        primitive = mesh['primitives'][0]
        attrs = {key: asset.accessor(gltf, binary, ref) for key, ref in primitive['attributes'].items()}
        joint_index = attrs['JOINTS_0'][0][0]
        assert attrs['JOINTS_0'] == [[joint_index, 0, 0, 0]] * 24
        assert attrs['WEIGHTS_0'] == [[1, 0, 0, 0]] * 24
        joint = gltf['nodes'][gltf['skins'][0]['joints'][joint_index]]
        pivot = joint['translation']
        result[mesh['name']] = {
            'joint': joint['name'].removesuffix('_joint'),
            'positions': [[p[a] - pivot[a] for a in range(3)] for p in attrs['POSITION']],
            'normals': attrs['NORMAL'], 'uv': [[u, 1-v] for u, v in attrs['TEXCOORD_0']],
            'indices': [x[0] for x in asset.accessor(gltf, binary, primitive['indices'])],
        }
    assert len(result) == 12
    return result


class GeometryChecks(unittest.TestCase):
    plan = DEFAULT_PLAN
    evidence = DEFAULT_OUTPUT
    metrics = {'layers': 0, 'verticesPerLod': 0, 'trianglesPerLod': 0,
               'maxPositionError': 0.0, 'maxUvError': 0.0}

    @classmethod
    def setUpClass(cls):
        block.native.load_cdmw(ROOT / 'build/cdmw-fixed-source', ROOT / 'build/cdmw-deps')
        from cdmw.modding.mesh_parser import parse_pam, parse_pamlod
        cls.parse_pam, cls.parse_pamlod = staticmethod(parse_pam), staticmethod(parse_pamlod)
        cls.report = json.loads((cls.plan / REPORT).read_bytes())
        cls.payloads = {name: (ROOT / 'build/native-block-declaration-fixed/template' / name).read_bytes()
                        for name in block.TEMPLATE_HASHES}
        cls.pam, cls.lod, cls.layout, cls.lod_layout = block.validate_template(cls.payloads)
        cls.oracle = independent_meshes()
        _, _, cls.snapshot = adapter.load()
        cls.rows = cls.report['parts']
        cls.before = {p: p.read_bytes() for p in (ROOT/'tools/prepare_steve_rigid_geometry.py',
                     ROOT/'tools/check_steve_rigid_geometry.py')}

    def pair(self, row):
        return (self.plan / row['pam']).read_bytes(), (self.plan / row['pamlod']).read_bytes()

    def mapping(self, source, mesh):
        span = [max(p[a] for p in source['positions']) - min(p[a] for p in source['positions']) for a in range(3)]
        tol = max(span) / 65535 + 2e-7
        mapping = []
        for p, n in zip(mesh.vertices, mesh.normals):
            matches = [i for i, (op, on) in enumerate(zip(source['positions'], source['normals']))
                       if max(abs(x-y) for x,y in zip(p,op)) <= tol
                       and max(abs(x-y) for x,y in zip(n,on)) <= 1e-6]
            self.assertEqual(len(matches), 1, (p, n, matches))
            mapping.append(matches[0])
        self.assertEqual(sorted(mapping), list(range(24)))
        return mapping

    def test_01_inputs_inventory_and_unverified_boundaries(self):
        self.assertEqual(len(self.rows), 12)
        self.assertEqual({r['sourceMesh'] for r in self.rows}, set(self.oracle))
        for row in self.rows:
            self.assertIs(row['outerLayer'], row['sourceMesh'] in adapter.assets.OUTER_PARTS)
        self.assertEqual({joint:sum(r['joint']==joint for r in self.rows) for joint in adapter.PARTS},
                         {joint:2 for joint in adapter.PARTS})
        self.assertEqual(len(self.report['files']), 24)
        self.assertEqual({p.relative_to(self.plan).as_posix() for p in self.plan.rglob('*') if p.is_file()},
                         set(self.report['files']) | {REPORT})
        for name, digest in self.report['files'].items():
            self.assertIn(Path(name).suffix, ('.pam', '.pamlod'))
            self.assertEqual(sha((self.plan/name).read_bytes()), digest)
        integration = self.report['integration']
        self.assertTrue(integration['geometryAuthored'])
        for key in ('materialBinding', 'collisionless', 'groupObjects', 'ownerFollow', 'nativeApplied', 'installed'):
            self.assertIs(integration[key], False)
        self.assertIs(self.report['coordinates']['rootScaleBaked'], False)
        self.assertIs(self.report['recordContract']['packedNormalDecoded'], False)
        self.assertIs(self.report['recordContract']['tangentToNewUvVerified'], False)
        for name, value in self.report['sources'].items():
            self.assertEqual(sha((ROOT/name).read_bytes()), value['sha256'])

    def test_02_two_formats_keep_complete_layer_topology(self):
        for row in self.rows:
            pam, lod = self.pair(row)
            for mesh in (self.parse_pam(pam), self.parse_pamlod(lod)):
                self.assertEqual((len(mesh.submeshes), mesh.total_vertices, mesh.total_faces), (1,24,12))
                self.assertFalse(mesh.has_bones)
                self.assertEqual(mesh.submeshes[0].faces, self.pam.submeshes[0].faces)
        self.metrics.update(layers=12, verticesPerLod=288, trianglesPerLod=144)

    def test_03_independent_gltf_pivot_uv_and_raw_quantization(self):
        for row in self.rows:
            source = self.oracle[row['sourceMesh']]
            self.assertEqual(row['joint'], source['joint'])
            for raw, parser, start, bbox_offset in ((self.pair(row)[0], self.parse_pam, 1712, 0x14),
                                                  (self.pair(row)[1], self.parse_pamlod, 736, 0x10)):
                part = parser(raw).submeshes[0]
                mapping = self.mapping(source, part)
                self.assertEqual(row['sourceVertexIndices'], mapping)
                bbox = struct.unpack_from('<6f', raw, bbox_offset)
                for i, si in enumerate(mapping):
                    packed = struct.unpack_from('<3H', raw, start+i*20)
                    pos = [bbox[a] + packed[a]/65535 * (bbox[a+3]-bbox[a]) for a in range(3)]
                    uv = struct.unpack_from('<2e', raw, start+i*20+8)
                    for a in range(3):
                        err = abs(pos[a]-source['positions'][si][a])
                        self.assertLessEqual(err, (bbox[a+3]-bbox[a])/65535+2e-7)
                        self.assertAlmostEqual(pos[a], part.vertices[i][a], places=7)
                        self.metrics['maxPositionError'] = max(self.metrics['maxPositionError'], err)
                    for a in range(2):
                        err = abs(uv[a]-source['uv'][si][a])
                        self.assertLessEqual(err, .0005)
                        self.metrics['maxUvError'] = max(self.metrics['maxUvError'], err)
                for a in range(3):
                    self.assertAlmostEqual(bbox[a], min(p[a] for p in source['positions']), places=7)
                    self.assertAlmostEqual(bbox[a+3], max(p[a] for p in source['positions']), places=7)

    def test_04_every_mc_quad_retains_outward_area_and_uv_corners(self):
        for row in self.rows:
            source = self.oracle[row['sourceMesh']]
            part = self.parse_pam(self.pair(row)[0]).submeshes[0]
            mapping = self.mapping(source, part)
            covered = {q: [] for q in range(6)}
            for face in part.faces:
                ids = [mapping[i] for i in face]
                self.assertEqual(len({i//4 for i in ids}), 1)
                covered[ids[0]//4].append(ids)
            for q, triangles in covered.items():
                self.assertEqual(len(triangles), 2)
                self.assertEqual({i for tri in triangles for i in tri}, set(range(q*4,q*4+4)))
                areas = []
                for tri in triangles:
                    p0,p1,p2 = [source['positions'][i] for i in tri]
                    u,v = ([p1[a]-p0[a] for a in range(3)], [p2[a]-p0[a] for a in range(3)])
                    cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
                    self.assertGreater(sum(cross[a]*source['normals'][tri[0]][a] for a in range(3)), 0)
                    areas.append(math.hypot(*cross)/2)
                quad = source['positions'][q*4:q*4+4]
                spans = sorted(max(p[a] for p in quad)-min(p[a] for p in quad) for a in range(3))
                self.assertAlmostEqual(sum(areas), spans[1]*spans[2], places=7)

    def test_05_all_non_position_uv_vertex_bytes_match_native_donor(self):
        original = self.payloads[block.BASE+'.pam']
        for row in self.rows:
            for raw, start in ((self.pair(row)[0],1712), (self.pair(row)[1],736)):
                for i in range(24):
                    rec = raw[start+i*20:start+(i+1)*20]
                    donor = original[1712+i*20:1712+(i+1)*20]
                    self.assertEqual(rec[6:8]+rec[12:20], donor[6:8]+donor[12:20])

    def test_06_lod_binary_records_and_indices_equal_main(self):
        for row in self.rows:
            pam, lod = self.pair(row)
            self.assertEqual(len(pam), 2276)
            self.assertEqual(len(lod), 1288)
            self.assertEqual(pam[1712:2264], lod[736:1288])
            self.assertEqual(struct.unpack_from('<4I', pam,1040), (24,36,0,0))
            self.assertEqual(struct.unpack_from('<4I', lod,92), (24,36,0,0))

    def test_07_fresh_process_rebuild_and_existing_output_refusal(self):
        rebuilt = self.evidence / 'steve-rigid-geometry-rebuilt'
        command = [sys.executable,'-B',str(ROOT/'tools/prepare_steve_rigid_geometry.py'),'--output',str(rebuilt)]
        result = subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr[-3000:])
        for name in (*self.report['files'], REPORT):
            self.assertEqual((rebuilt/name).read_bytes(),(self.plan/name).read_bytes(),name)
        before = {p:p.read_bytes() for p in rebuilt.rglob('*') if p.is_file()}
        second = subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(second.returncode,0)
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(),raw)

    def test_08_protected_output_and_source_snapshot(self):
        for output in (ROOT/'tools/steve-rigid-geometry-forbidden', ROOT/'build',
                       ROOT/'build/steve-pose-1.21.1/steve-rigid-geometry-forbidden',
                       ROOT/'build/steve-rigid-adapter-1.21.1', self.plan):
            existed = output.exists()
            result = subprocess.run([sys.executable,'-B',str(ROOT/'tools/prepare_steve_rigid_geometry.py'),
                                     '--output',str(output)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(output.exists(),existed)
        nested = ROOT/'build/steve-1.21.1/steve-rigid-geometry-check-forbidden'
        self.assertFalse(nested.exists())
        result = subprocess.run([sys.executable,'-B',str(ROOT/'tools/check_steve_rigid_geometry.py'),
                                 '--plan',str(self.plan),'--output',str(nested)],
                                cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(nested.exists())
        adapter.verify_snapshot(self.snapshot)
        for path, raw in self.before.items():
            self.assertEqual(path.read_bytes(),raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,default=DEFAULT_PLAN)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = adapter.input_path(args.plan)
    evidence = adapter.assets.output_directory(args.output)
    if (evidence.exists() or evidence.parent != ROOT/'build'
            or not evidence.name.startswith('steve-rigid-geometry-check-')):
        raise ValueError('Evidence output must be a new direct build child with the dedicated prefix')
    for path in (plan,ROOT/'tools',ROOT/'runtime',ROOT/'minecraft',ROOT/'downloads'):
        if evidence == path or evidence.is_relative_to(path) or path.is_relative_to(evidence):
            raise ValueError('Evidence output overlaps protected files')
    evidence.mkdir(parents=True)
    GeometryChecks.plan, GeometryChecks.evidence = plan, evidence
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GeometryChecks))
    report = {'testsRun':result.testsRun,'passed':result.wasSuccessful(),'metrics':GeometryChecks.metrics,
              'errors':[{'test':test.id(),'trace':trace} for test,trace in result.errors],
              'failures':[{'test':test.id(),'trace':trace} for test,trace in result.failures],
              'sourceSnapshotItems':len(getattr(GeometryChecks,'snapshot',{})),
              'nativeApplied':False,'collisionlessVerified':False,'installed':False}
    (evidence/'check-results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
