"""Check local rigid Standard bindings without claiming shader alpha or loading."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

import prepare_native_block as block
import prepare_steve_material as skin
import build_steve_rigid_adapter as adapter

ROOT = block.ROOT
DEFAULT_PLAN = ROOT/'build/steve-rigid-material-1.21.1'
DEFAULT_EVIDENCE = ROOT/'build/steve-rigid-material-check-20261008'
REPORT_NAME = 'steve-rigid-material-report.json'
GEOMETRY = ROOT/'build/steve-rigid-geometry-1.21.1'
GEOMETRY_REPORT_SHA = '40407ce6766dcb3efad97e87c0dacb9ffdaa67f8cb128ef0c61adc5d4b97f8f7'
TEXTURES = {
    '': '653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a',
    '_n': '3555d0a27af8de753c2368e8878a995469577ff40515d9467e4540ff2feebc33',
    '_sp': '047babdb8e93774756a770cdd4387e091fe21527dfb4dca9ad2c8e6f6e29f2db',
}
TEXTURE_BASE = 'character/texture/crimsonmc_steve_1_21_1'
OLD_NAME, NEW_NAME = 'cd_testfield_grid_03.dds', 'crimsonmc_steve_1_21_1.dds'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def field(name):
    raw = name.encode('ascii')
    assert len(raw) < 256
    return raw + bytes(256-len(raw))


def xml_shape(element):
    """Preserve all attributes, non-whitespace text, order and child multiplicity."""
    return [element.tag, dict(element.attrib), (element.text or '').strip(),
            (element.tail or '').strip(), [xml_shape(child) for child in element]]


class MaterialChecks(unittest.TestCase):
    plan, evidence = DEFAULT_PLAN, DEFAULT_EVIDENCE
    metrics = {}

    @classmethod
    def setUpClass(cls):
        cls.report = read_json(cls.plan/REPORT_NAME)
        geometry_raw = (GEOMETRY/'steve-rigid-geometry-report.json').read_bytes()
        assert sha(geometry_raw) == GEOMETRY_REPORT_SHA
        cls.geometry_report = json.loads(geometry_raw)
        cls.geometry_rows = {row['sourceMesh']:row for row in cls.geometry_report['parts']}
        cls.rows = cls.report['parts']
        cls.template = (ROOT/'build/native-block-declaration-fixed/template'/ (block.BASE+'.pami')).read_bytes()
        assert sha(cls.template) == block.TEMPLATE_HASHES[block.BASE+'.pami']
        cls.original_xml = ET.fromstring(cls.template)
        cls.before = {p:p.read_bytes() for p in (ROOT/'tools/prepare_steve_rigid_material.py',
                      ROOT/'tools/check_steve_rigid_material.py')}
        cls.source_before = {name:sha((ROOT/name).read_bytes()) for name in cls.report['sources']}

    def test_01_complete_inventory_and_explicit_runtime_limits(self):
        self.assertEqual(len(self.rows),12)
        self.assertEqual(len(self.report['files']),39)
        self.assertEqual({r['sourceMesh'] for r in self.rows},set(self.geometry_rows))
        actual = {p.relative_to(self.plan).as_posix() for p in self.plan.rglob('*') if p.is_file()}
        self.assertEqual(actual,set(self.report['files'])|{REPORT_NAME})
        for name,pin in self.report['files'].items():
            path = PurePosixPath(name)
            self.assertFalse(path.is_absolute())
            self.assertNotIn('..',path.parts)
            self.assertEqual(path.parts[0],'resources')
            self.assertIn(path.suffix,('.pam','.pamlod','.pami','.dds'))
            self.assertEqual(sha((self.plan/name).read_bytes()),pin)
        integration = self.report['integration']
        self.assertIs(integration['materialBindingsAuthored'],True)
        for key in ('alphaBehaviorVerified','nativeMaterialLoaded','collisionless','nativeApplied','installed','installableResourcePackage'):
            self.assertIs(integration[key],False)
        self.metrics.update(layers=12,resources=39,geometryFiles=24,materialFiles=12,textures=3)

    def test_02_geometry_exact_inverse_outside_four_name_fields(self):
        names_changed = 0
        for row in self.rows:
            original_row = self.geometry_rows[row['sourceMesh']]
            self.assertEqual(row['joint'],original_row['joint'])
            self.assertEqual(row['outerLayer'],original_row['outerLayer'])
            for key, offsets in (('pam',(0x420,0x520)),('pamlod',(108,364))):
                before = (GEOMETRY/original_row[key]).read_bytes()
                self.assertEqual(sha(before),self.geometry_report['files'][original_row[key]])
                after = bytearray((self.plan/row[key]).read_bytes())
                self.assertEqual(len(after),len(before))
                for offset in offsets:
                    self.assertEqual(before[offset:offset+256].split(b'\0',1)[0],OLD_NAME.encode('ascii'))
                    self.assertEqual(after[offset:offset+256],field(NEW_NAME))
                    after[offset:offset+256] = before[offset:offset+256]
                    names_changed += 1
                self.assertEqual(bytes(after),before)
        self.assertEqual(names_changed,48)

    def test_03_pami_preserves_full_standard_contract(self):
        for row in self.rows:
            raw = (self.plan/row['pami']).read_bytes()
            self.assertTrue(raw.startswith(b'<StaticMeshInstance'))
            self.assertNotIn(b'<?xml',raw)
            self.assertNotIn(b'<!',raw)
            doc = ET.fromstring(raw)
            self.assertEqual(doc.find('StaticMesh').get('Path'),row['virtualStem']+'.pam')
            material = doc.find('MaterialData/Material')
            self.assertEqual(material.get('PrimitiveName'),NEW_NAME)
            textures = material.findall('Parameters/MaterialParameterTexture')
            self.assertEqual(len(textures),3)
            expected = {'_baseColorTexture':TEXTURE_BASE+'.dds','_normalTexture':TEXTURE_BASE+'_n.dds',
                        '_materialTexture':TEXTURE_BASE+'_sp.dds'}
            self.assertEqual({node.get('Name'):node.get('Value') for node in textures},expected)
            # Undo precisely the five changed values, then compare the whole tree.
            doc.find('StaticMesh').set('Path',block.BASE+'.pam')
            material.set('PrimitiveName',OLD_NAME)
            old = {node.get('Name'):node.get('Value') for node in self.original_xml.findall('MaterialData/Material/Parameters/MaterialParameterTexture')}
            for node in textures:
                node.set('Value',old[node.get('Name')])
            self.assertEqual(xml_shape(doc),xml_shape(self.original_xml))

    def test_04_all_material_dependencies_resolve_inside_output(self):
        used = set()
        for row in self.rows:
            expected_stem = 'object/00_common/system/crimsonmc_steve_rigid_'+row['sourceMesh']
            self.assertEqual(row['virtualStem'],expected_stem)
            for key in ('pam','pamlod','pami'):
                self.assertEqual(row[key],'resources/'+expected_stem+'.'+key)
            doc = ET.fromstring((self.plan/row['pami']).read_bytes())
            dependencies = [doc.find('StaticMesh').get('Path')]
            dependencies += [node.get('Value') for node in doc.findall('MaterialData/Material/Parameters/MaterialParameterTexture')]
            self.assertEqual(len(dependencies),4)
            for virtual in dependencies:
                self.assertIn('resources/'+virtual,self.report['files'])
                used.add(virtual)
            self.assertIn('resources/'+expected_stem+'.pamlod',self.report['files'])
            for path,offsets in ((row['pam'],(0x420,0x520)),(row['pamlod'],(108,364))):
                raw = (self.plan/path).read_bytes()
                for offset in offsets:
                    self.assertEqual(raw[offset:offset+256].split(b'\0',1)[0].decode('ascii'),
                                     doc.find('MaterialData/Material').get('PrimitiveName'))
        self.assertEqual(len(used),15)

    def test_05_texture_bytes_classification_and_official_skin(self):
        for suffix,pin in TEXTURES.items():
            name = 'resources/'+TEXTURE_BASE+suffix+'.dds'
            raw = (self.plan/name).read_bytes()
            self.assertEqual(sha(raw),pin)
            self.assertEqual(raw,(ROOT/'build/steve-material'/name).read_bytes())
            self.assertEqual(raw[:4],b'DDS ')
            self.assertEqual(struct.unpack_from('<2I',raw,12),(256,256))
            self.assertEqual(struct.unpack_from('<I',raw,28)[0],9)
            self.assertEqual(raw[84:88],{'':b'DXT5','_n':b'BC5U','_sp':b'DXT1'}[suffix])
        png = (ROOT/'build/steve-1.21.1/steve.png').read_bytes()
        self.assertEqual(sha(png),'d876e0c88f4b3de71040966ed94a614f315b888592b520b993399fd2738418d0')
        base = (self.plan/('resources/'+TEXTURE_BASE+'.dds')).read_bytes()
        decoder, images = skin.independent_decode([png,base],Path(shutil.which('python') or 'python'))
        (w,h,source),(dw,dh,decoded) = images
        self.assertEqual((w,h,dw,dh),(64,64,256,256))
        maximum = 0
        for y in range(256):
            for x in range(256):
                original, pixel = source[(y//4)*64+x//4],decoded[y*256+x]
                self.assertEqual(original[3],pixel[3])
                maximum = max(maximum,max(abs(original[a]-pixel[a]) for a in range(3)))
        self.assertLessEqual(maximum,4)
        self.metrics.update(baseMipMaxRgbError=maximum,baseMipAlphaError=0,independentDecoder=decoder)

    def test_06_fixed_sources_and_original_geometry_preserved(self):
        for name,row in self.report['sources'].items():
            self.assertEqual(self.source_before[name],row['sha256'])
            self.assertEqual(sha((ROOT/name).read_bytes()),row['sha256'])
        for name,pin in self.geometry_report['files'].items():
            self.assertEqual(sha((GEOMETRY/name).read_bytes()),pin)
        for path,raw in self.before.items():
            self.assertEqual(path.read_bytes(),raw)
        self.metrics['watchedSources'] = len(self.report['sources'])

    def test_07_fresh_rebuild_is_identical_and_cannot_overwrite(self):
        output = self.evidence/'steve-rigid-material-rebuilt'
        cmd = [sys.executable,'-B',str(ROOT/'tools/prepare_steve_rigid_material.py'),'--output',str(output)]
        result = subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr[-3000:])
        for name in (*self.report['files'],REPORT_NAME):
            self.assertEqual((output/name).read_bytes(),(self.plan/name).read_bytes())
        result = subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(result.returncode,0)
        for name in (*self.report['files'],REPORT_NAME):
            self.assertEqual((output/name).read_bytes(),(self.plan/name).read_bytes())

    def test_08_source_and_evidence_output_gates(self):
        for output in (ROOT/'tools/steve-rigid-material-forbidden',GEOMETRY/'steve-rigid-material-forbidden',
                       ROOT/'build/steve-pose-1.21.1/steve-rigid-material-forbidden',self.plan):
            existed = output.exists()
            result = subprocess.run([sys.executable,'-B',str(ROOT/'tools/prepare_steve_rigid_material.py'),
                                     '--output',str(output)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(output.exists(),existed)
        nested = GEOMETRY/'steve-rigid-material-check-forbidden'
        self.assertFalse(nested.exists())
        result = subprocess.run([sys.executable,'-B',str(Path(__file__)), '--plan',str(self.plan),'--output',str(nested)],
                                cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(nested.exists())
        self.test_06_fixed_sources_and_original_geometry_preserved()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,default=DEFAULT_PLAN)
    parser.add_argument('--output',type=Path,default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    plan = adapter.input_path(args.plan)
    evidence = adapter.assets.output_directory(args.output)
    if evidence.exists() or evidence.parent != ROOT/'build' or not evidence.name.startswith('steve-rigid-material-check-'):
        raise ValueError('Evidence output must be a new direct build child with the dedicated prefix')
    for protected in (plan,ROOT/'tools',ROOT/'runtime',ROOT/'minecraft',ROOT/'downloads'):
        if evidence == protected or evidence.is_relative_to(protected) or protected.is_relative_to(evidence):
            raise ValueError('Evidence output overlaps a protected source')
    evidence.mkdir(parents=True)
    MaterialChecks.plan, MaterialChecks.evidence = plan, evidence
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MaterialChecks))
    report = {'testsRun':result.testsRun,'passed':result.wasSuccessful(),'metrics':MaterialChecks.metrics,
              'errors':[{'test':test.id(),'trace':trace} for test,trace in result.errors],
              'failures':[{'test':test.id(),'trace':trace} for test,trace in result.failures],
              'alphaBehaviorVerified':False,'nativeMaterialLoaded':False,'nativeApplied':False,'installed':False}
    (evidence/'check-results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
