"""Check full offline block model faces, raw source coverage and independent PNGs.

--rebuild repeats all original Java geometry in a new ignored directory and
checks a synthetic full-cube UV-lock matrix. No game/world/service is used.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import build_block_model_geometry as asset


def resource(value: str) -> str:
    return value if ":" in value else "minecraft:" + value


def resolve(archive, name):
    """Independent parent walk/overlay; does not call exporter Resources."""
    chain, builtins, documents = {}, [], []
    while name:
        name = resource(name)
        namespace, suffix = name.split(":", 1)
        if suffix.startswith("builtin/"):
            builtins.append(name)
            break
        path = f"assets/{namespace}/models/{suffix}.json"
        if path in chain:
            raise ValueError("Source cycle")
        data = archive.read(path)
        chain[path] = asset.steve.digest(data)
        document = json.loads(data)
        documents.append(document)
        name = document.get("parent")
    merged = {"textures": {}}
    for document in reversed(documents):
        merged["textures"].update(document.get("textures", {}))
        for key in ("elements", "ambientocclusion"):
            if key in document:
                merged[key] = document[key]
    return merged, chain, builtins


def face_texture(face, textures):
    name = face[1:] if face.startswith("#") else face
    value = textures[name]
    seen = set()
    while value.startswith("#"):
        if value in seen:
            raise ValueError("Alias cycle")
        seen.add(value)
        value = textures[value[1:]]
    return resource(value)


CORNERS = {
    "down": ((0,0,1),(0,0,0),(1,0,0),(1,0,1)),
    "up": ((0,1,0),(0,1,1),(1,1,1),(1,1,0)),
    "north": ((1,1,0),(1,0,0),(0,0,0),(0,1,0)),
    "south": ((0,1,1),(0,0,1),(1,0,1),(1,1,1)),
    "west": ((0,1,0),(0,0,0),(0,0,1),(0,1,1)),
    "east": ((1,1,1),(1,0,1),(1,0,0),(1,1,0)),
}
DIRECTIONS = {"down": (0,-1,0), "up": (0,1,0), "north": (0,0,-1), "south": (0,0,1), "west": (-1,0,0), "east": (1,0,0)}


def rotate(point, axis, degrees):
    x,y,z = point
    c,s = math.cos(math.radians(degrees)),math.sin(math.radians(degrees))
    return {"x": [x,y*c-z*s,y*s+z*c], "y": [x*c+z*s,y,-x*s+z*c], "z": [x*c-y*s,x*s+y*c,z]}[axis]


def reference_points(q):
    points = [[q["to" if high else "from"][axis] / 16 for axis,high in enumerate(corner)] for corner in CORNERS[q["face"]]]
    for index,p in enumerate(points):
        if "elementRotation" in q:
            r = q["elementRotation"]
            center = [n/16 for n in r["origin"]]
            p = rotate([p[i]-center[i] for i in range(3)], r["axis"], r["angle"])
            if r.get("rescale", False):
                # Vanilla explicitly selects 22.5 degrees or the 45-degree factor.
                factor = 1/math.cos(math.radians(22.5 if abs(r["angle"]) == 22.5 else 45))
                p = [n if i == "xyz".index(r["axis"]) else n*factor for i,n in enumerate(p)]
            p = [p[i]+center[i] for i in range(3)]
        p = [n-.5 for n in p]
        p = rotate(rotate(p,"x",-q["x"]),"y",-q["y"])
        points[index] = [n+.5 for n in p]
    return points


def reference_uvs(q):
    x0,y0,z0 = q["from"]
    x1,y1,z1 = q["to"]
    rect = q.get("uv", {"down": [x0,16-z1,x1,16-z0], "up": [x0,z0,x1,z1],
        "north": [16-x1,16-y1,16-x0,16-y0], "south": [x0,16-y1,x1,16-y0],
        "west": [z0,16-y1,z1,16-y0], "east": [16-z1,16-y1,16-z0,16-y0]}[q["face"]])
    original = [(rect[0]/16,rect[1]/16), (rect[0]/16,rect[3]/16), (rect[2]/16,rect[3]/16), (rect[2]/16,rect[1]/16)]
    return [original[(i+q["uvRotation"]//90)%4] for i in range(4)]


def pixel_uv(point, face):
    x,y,z = point
    return {"down": [x,1-z], "up": [x,z], "north": [1-x,1-y],
            "south": [x,1-y], "west": [z,1-y], "east": [1-z,1-y]}[face]


class GeometryChecks(unittest.TestCase):
    output = asset.DEFAULT_OUTPUT
    rebuild = False
    decoder = Path(shutil.which("python") or "python")

    @classmethod
    def setUpClass(cls):
        cls.config = asset.steve.read_config()
        cls.client, cls.jars = asset.steve.dependencies(cls.config,None,False)
        asset.steve.verify_client(cls.client,cls.config)
        cls.archive = zipfile.ZipFile(cls.client)
        cls.report = json.loads((cls.output/"manifest.json").read_bytes())
        cls.document = json.loads((cls.output/"geometry.json").read_bytes())
        cls.quads = cls.document["quads"]
        cls.variants = {v["key"]:v for v in cls.document["variants"]}
        cls.raw = json.loads((cls.output/"quad-input.json").read_bytes())["quads"]
        cls.engine = json.loads((cls.output/"engine-quads.json").read_bytes())
        cls.sources = json.loads((cls.output/"resource-models.json").read_bytes())
        cls.textures = json.loads((cls.output/"textures.json").read_bytes())
        cls.dependencies = json.loads((cls.output/"model-dependencies.json").read_bytes())
        cls.models = {name:resolve(cls.archive,name) for name in cls.dependencies}

    @classmethod
    def tearDownClass(cls):
        cls.archive.close()

    def near(self, actual, expected, label="", tolerance=3e-6):
        self.assertEqual(len(actual),len(expected),label)
        self.assertLessEqual(max(abs(a-b) for a,b in zip(actual,expected)),tolerance,label)

    def test_01_provenance_integrity_and_no_native_claims(self):
        self.assertEqual(self.report["clientSha256"],self.config["client"]["sha256"])
        for field,path in (("sourceConfigSha256",asset.steve.CONFIG),("exporterSha256",Path(asset.__file__)),("resourceResolverSha256",Path(asset.base.__file__))):
            self.assertEqual(self.report[field],asset.steve.digest(path.read_bytes()))
        self.assertEqual(self.report["readerSha256"],asset.steve.digest(asset.JAVA_READER.encode()))
        self.assertEqual(self.report["engineClassSha256"],asset.ENGINE_CLASSES)
        for name,sha in asset.ENGINE_CLASSES.items():
            self.assertEqual(asset.steve.digest(self.archive.read(name)),sha)
        for name,sha in self.report["files"].items():
            self.assertEqual(asset.steve.digest((self.output/name).read_bytes()),sha,name)
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        self.assertFalse(self.document["nativeIntegrated"])
        self.assertFalse(self.sources["registryComplete"])
        self.assertFalse(self.sources["randomChoiceApplied"])

    def test_02_all_raw_resource_groups_weights_and_variants(self):
        paths = sorted(n for n in self.archive.namelist() if n.startswith("assets/minecraft/blockstates/") and n.endswith(".json"))
        self.assertEqual([r["file"] for r in self.sources["entries"]],paths)
        keys, count = set(),0
        for row in self.sources["entries"]:
            raw = self.archive.read(row["file"])
            self.assertEqual(row["sha256"],asset.steve.digest(raw))
            state = json.loads(raw)
            groups = [(selector,None,choices) for selector,choices in state.get("variants",{}).items()]
            groups += [(f"part:{i}",part.get("when"),part["apply"]) for i,part in enumerate(state.get("multipart",[]))]
            expected = []
            for selector,when,choices in groups:
                for index,choice in enumerate(choices if isinstance(choices,list) else [choices]):
                    item = {"selector":selector,"when":when,"choice":index,"model":resource(choice["model"]),
                        "x":choice.get("x",0),"y":choice.get("y",0),"uvlock":choice.get("uvlock",False),"weight":choice.get("weight",1)}
                    expected.append(item)
            self.assertEqual([{k:v for k,v in c.items() if k != "geometryKey"} for c in row["choices"]],expected)
            for choice in row["choices"]:
                variant = self.variants[choice["geometryKey"]]
                self.assertEqual(tuple(variant[k] for k in ("model","x","y","uvlock")),tuple(choice[k] for k in ("model","x","y","uvlock")))
                keys.add(variant["key"])
            count += len(expected)
        self.assertEqual(keys,set(self.variants))
        self.assertEqual((len(paths),count,len(keys)),(1062,6766,5163))

    def test_03_every_original_element_face_and_dependency_preserved(self):
        ids=[]
        for v in self.variants.values():
            model,chain,builtins = self.models[v["model"]]
            dep = self.dependencies[v["model"]]
            self.assertEqual(dep["modelFiles"],chain)
            self.assertEqual(dep["builtins"],builtins)
            self.assertEqual(v["ambientOcclusion"],model.get("ambientocclusion",True))
            expected = [(i,e,f,d) for i,e in enumerate(model.get("elements",[])) for f,d in e.get("faces",{}).items()]
            actual = self.quads[v["firstQuad"]:v["firstQuad"]+v["quadCount"]]
            self.assertEqual(len(actual),len(expected),v["key"])
            for q,(i,e,f,d) in zip(actual,expected):
                self.assertEqual((q["element"],q["from"],q["to"],q["face"]),(i,e["from"],e["to"],f))
                self.assertEqual(q.get("elementRotation"),e.get("rotation"))
                self.assertEqual(q.get("uv"),d.get("uv"))
                self.assertEqual(q.get("cullface"),d.get("cullface"))
                self.assertEqual(q["uvRotation"],d.get("rotation",0))
                self.assertEqual(q["tintIndex"],d.get("tintindex",-1))
                self.assertEqual(q["shade"],e.get("shade",True))
                self.assertEqual(q["texture"],face_texture(d["texture"],model["textures"]))
                ids.append(q["quadId"])
        self.assertEqual(ids,list(range(51059)))

    def test_04_all_vertex_sets_against_independent_rotation_rescale_math(self):
        worst=0
        for q in self.quads:
            candidates=reference_points(q)
            for point in q["positions"]:
                distances=[max(abs(a-b) for a,b in zip(point,p)) for p in candidates]
                index=min(range(len(distances)),key=distances.__getitem__)
                worst=max(worst,distances[index])
                self.assertLess(distances[index],3e-6,str(q["quadId"]))
                candidates.pop(index)
        self.assertLess(worst,3e-6)

    def test_05_unlocked_uvs_preserve_vertex_association(self):
        checked=0
        for q in self.quads:
            if q["uvlock"] or q["degenerateTriangles"]:
                continue
            candidates=list(zip(reference_points(q),reference_uvs(q)))
            for point,uv in zip(q["positions"],q["uvs"]):
                distances=[max(abs(a-b) for a,b in zip(point,p)) for p,_ in candidates]
                index=min(range(len(distances)),key=distances.__getitem__)
                self.near(uv,candidates[index][1],str(q["quadId"]))
                candidates.pop(index)
            checked+=1
        self.assertGreater(checked,20000)

    def test_06_normals_collapsed_faces_and_engine_payload(self):
        degenerate=0
        for q,source,original in zip(self.quads,self.raw,self.engine["quads"]):
            for key,value in source.items():
                self.assertEqual(q[key],value)
            for key,value in original.items():
                self.assertEqual(q[key],value)
            zero=0
            for tri,n in zip(self.document["triangles"],q["triangleNormals"]):
                a,b,c=(q["positions"][i] for i in tri)
                u,v=([b[i]-a[i] for i in range(3)],[c[i]-a[i] for i in range(3)])
                cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
                length=math.sqrt(sum(t*t for t in cross))
                if length <= 1e-12:
                    self.assertIsNone(n)
                    zero+=1
                else:
                    self.near(n,[t/length for t in cross])
            self.assertEqual(q["degenerateTriangles"],zero)
            degenerate += zero>0
            self.assertEqual(q["windingRecalculated"],"elementRotation" not in q)
        self.assertEqual(degenerate,160)

    def test_07_original_cullface_rotation_and_unknown_name_null(self):
        invalid=[]
        for q in self.quads:
            if "cullface" not in q:
                self.assertNotIn("transformedCullface",q)
                continue
            if q["cullface"] not in DIRECTIONS:
                invalid.append(q)
                self.assertIsNone(q["transformedCullface"])
            else:
                direction=rotate(rotate(DIRECTIONS[q["cullface"]],"x",-q["x"]),"y",-q["y"])
                self.near(DIRECTIONS[q["transformedCullface"]],direction)
        self.assertEqual(len(invalid),4)
        self.assertTrue(all(q["cullface"]=="bottom" and "scaffolding_unstable" in q["geometryKey"] for q in invalid))

    def test_08_textures_animation_bytes_and_independent_pillow_alpha(self):
        for texture,row in self.textures.items():
            raw=self.archive.read(row["entry"])
            self.assertEqual((self.output/row["file"]).read_bytes(),raw)
            self.assertEqual(row["sha256"],asset.steve.digest(raw))
            if "metadata" in row:
                meta=self.archive.read(row["entry"]+".mcmeta")
                self.assertEqual((self.output/(row["file"]+".mcmeta")).read_bytes(),meta)
                self.assertEqual(row["metadata"],json.loads(meta))
                self.assertEqual(row["mcmetaSha256"],asset.steve.digest(meta))
            self.assertEqual(row["animated"],"animation" in row.get("metadata",{}))
        script=r'''import json,sys,pathlib,PIL
from PIL import Image
root=pathlib.Path(sys.argv[1]);rows=json.loads((root/'textures.json').read_bytes());result={}
for key,row in rows.items():
 with Image.open(root/row['file']) as img:
  hist=img.convert('RGBA').getchannel('A').histogram()
  result[key]={'width':img.width,'height':img.height,'transparentPixels':hist[0],'partialAlphaPixels':sum(hist[1:255]),'opaquePixels':hist[255]}
print(json.dumps({'decoder':'Pillow '+PIL.__version__,'textures':result}))
'''
        process=subprocess.run([str(self.decoder),"-c",script,str(self.output)],check=True,capture_output=True,text=True,timeout=60)
        decoded=json.loads(process.stdout)
        self.assertEqual(set(decoded["textures"]),set(self.textures))
        for name,values in decoded["textures"].items():
            self.assertEqual({k:self.textures[name][k] for k in values},values,name)
        self.assertEqual(sum(t["animated"] for t in self.textures.values()),47)

    def test_09_empty_special_models_and_complete_state_mapping_join(self):
        empty=[v for v in self.variants.values() if v["quadCount"]==0]
        self.assertEqual(len(empty),72)
        for name in ("air","water","lava","chest","bed","oak_sign"):
            matches=[v for v in self.variants.values() if v["model"]=="minecraft:block/"+name]
            self.assertTrue(matches,name)
            self.assertTrue(all(v["quadCount"]==0 for v in matches),name)
        selection_path=asset.steve.ROOT/"build/block-state-models-1.21.1/block-state-models.json"
        selection=json.loads(selection_path.read_bytes())
        choices=0
        lookup={tuple(v[k] for k in ("model","x","y","uvlock")) for v in self.variants.values()}
        for block in selection["blocks"]:
            for group in block["groups"]:
                for choice in group["choices"]:
                    self.assertIn(tuple(choice[k] for k in ("model","x","y","uvlock")),lookup)
                    choices+=1
        self.assertEqual(choices,6762)
        self.assertEqual(sum(len(b["states"]) for b in selection["blocks"]),26684)

    def test_10_unsafe_and_existing_outputs_rejected_before_java(self):
        with patch.object(asset,"engine_geometry") as engine:
            for path in (asset.steve.ROOT,asset.steve.ROOT/"build",asset.steve.ROOT/"runtime/not-an-asset",self.output):
                with self.assertRaises(ValueError):
                    asset.build(path)
            engine.assert_not_called()
        for file in ("../escape.json","C:/escape.json"):
            with self.assertRaises(ValueError):
                asset.base.checked_target(self.output,file)

    def test_11_corrupt_engine_geometry_rejected(self):
        request=[self.raw[0]]
        for change in ({"quadId":123},{"positions":[[float("nan"),0,0]]*4},{"uvs":[[0,0]]*3},{"windingRecalculated":False},{"calculatedFacing":"made-up"}):
            bad=[{**self.engine["quads"][0],**change}]
            with self.assertRaises(ValueError):
                asset.validate_geometry(request,bad)
        with self.assertRaises(ValueError):
            asset.validate_geometry(request,[])

    def test_12_rebuild_real_java_and_uvlock_world_projection(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild to repeat original Java methods and synthetic UV-lock contract")
        with tempfile.TemporaryDirectory(prefix="check-full-geometry-",dir=asset.steve.ROOT/"build") as temporary:
            output=Path(temporary)/"package"
            java,_=asset.steve.java_tools(None)
            rebuilt=asset.build(output,Path(asset.steve.os.path.relpath(self.client)),
                                Path(asset.steve.os.path.relpath(java.parent.parent)))
            self.assertEqual(rebuilt,self.report)
            for file in self.report["files"]:
                self.assertEqual((output/file).read_bytes(),(self.output/file).read_bytes(),file)
            quads=[]
            for x in (0,90,180,270):
                for y in (0,90,180,270):
                    for face in CORNERS:
                        quads.append({"quadId":len(quads),"from":[0,0,0],"to":[16,16,16],"face":face,"uvRotation":0,"x":x,"y":y,"uvlock":True,"cullface":face})
            stage=Path(temporary)/"uvlock"
            stage.mkdir()
            result=asset.engine_geometry(stage,self.client,self.jars,{"quads":quads,"textures":[]},None)
            asset.validate_geometry(quads,result["quads"])
            for quad in result["quads"]:
                for point,uv in zip(quad["positions"],quad["uvs"]):
                    self.near(uv,pixel_uv(point,quad["calculatedFacing"]),str(quad["quadId"]))

    def test_13_first_export_creates_ignored_build_root(self):
        class ReachedJava(Exception):
            pass
        def reached(stage,*args):
            self.assertTrue(stage.is_dir())
            self.assertEqual(stage.parent,root/"build")
            raise ReachedJava()
        with tempfile.TemporaryDirectory(prefix="fresh-geometry-root-",dir=asset.steve.ROOT/"build") as temporary:
            root=Path(temporary)/"checkout"
            root.mkdir()
            with patch.object(asset.steve,"ROOT",root),patch.object(asset.steve,"dependencies",return_value=(self.client,self.jars)),patch.object(asset,"engine_geometry",side_effect=reached):
                with self.assertRaises(ReachedJava):
                    asset.build(root/"build/output",self.client)
            self.assertTrue((root/"build").is_dir())
            self.assertFalse((root/"build/output").exists())

    def test_14_no_empty_child_list_overrides_nonempty_parent_in_pinned_sources(self):
        # Vanilla getElements inherits if a local list is empty. The shared baseline
        # resolver is safe for this pinned corpus only if this edge does not occur.
        checked=set()
        for _,chain,_ in self.models.values():
            for path in chain:
                if path in checked:
                    continue
                checked.add(path)
                doc=json.loads(self.archive.read(path))
                if doc.get("elements")==[] and "parent" in doc:
                    parent,_,_=resolve(self.archive,doc["parent"])
                    self.assertFalse(parent.get("elements"),path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=GeometryChecks.output)
    parser.add_argument("--decoder-python",type=Path,default=GeometryChecks.decoder)
    parser.add_argument("--rebuild",action="store_true")
    args=parser.parse_args()
    GeometryChecks.output=asset.steve.output_directory(args.output)
    GeometryChecks.rebuild=args.rebuild
    GeometryChecks.decoder=args.decoder_python
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GeometryChecks))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=="__main__":
    main()
