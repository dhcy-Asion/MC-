"""Prepare local Minecraft 1.21.1 block dependencies and six baseline glTF assets.

This inventories client blockstate RESOURCE FILES, not Registries.BLOCK or all
legal states. No game/world is started or changed. Official and derived assets
stay under ignored build/. Geometry/UVs use the verified original Java classes;
there is no native asset import, random-model selection, collision or renderer.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import zipfile
import zlib

import build_steve_asset as steve

DEFAULT_OUTPUT = steve.ROOT / "build" / "block-assets-1.21.1"
BASELINE = ("oak_log", "oak_planks", "cobblestone", "dirt", "stone", "crafting_table")
FACES = ("down", "up", "north", "south", "west", "east")
RESOURCE = re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+")
# These names are valid ONLY for the client already pinned by steve-asset config.
ENGINE_CLASSES = {
    "ggd.class": "03bc6cb343e1d12613f115ff65a213a8dd894aee4a806d4e3b0af74c028c6593",
    "geq.class": "3bb6eeefff1fd948b4d01d52784c815c13f3427b6a73de0d85f675547e94e48c",
    "geq$b.class": "f3a40f768078a62e16ef47bebeed1930262715c8848828d80b0629e27eb6a28f",
    "gfx.class": "1e8950d0da1166f10c1302636432cb91b1f92322392e266f42f976070f4df6e2",
    "gga.class": "b8fa097537ff1b42bf02f37fe2931f5d532b98f4e5bd15e22d1726593f542306",
    "gsn.class": "9a6447bcfbc76169baceebe3c15495b5cfc08da65441a659bc56170b4c6326d1",
    "ji.class": "f7dda28326b73e7f84552b57b84e76e8bbf5acf6348e6bbc6906441d737532c5",
    "j.class": "f567944769a6fa7dea3b9a7ee83ca1c1a52cc20a239531fb0514ba488614ff2f",
    "ggb.class": "e773c015760009011ed2144d97bca68eb0a56476a966b6a18be4850eda55946a",
}

JAVA_READER = r'''package local.crimsonmc.assets;
import com.google.gson.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.Map;

/** Original-class calls only: no main/client, graphics, native image or atlas. */
public final class BlockQuadDump {
    static Class<?> v, d, t, rotation, transformation, baker, cube, corner, element;
    static Object instance;
    static Method position, transform, defaultUv, faceFor, cornerFor, getRotation, getTransform;
    static Object vector(JsonArray a) throws Exception {
        return v.getConstructor(float.class,float.class,float.class).newInstance(
            a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());
    }
    static JsonArray numbers(float... values) {
        JsonArray a = new JsonArray();
        for (float n: values) {
            if (!Float.isFinite(n)) throw new IllegalStateException("Nonfinite engine output");
            a.add(n);
        }
        return a;
    }
    public static void main(String[] args) throws Exception {
        v=Class.forName("org.joml.Vector3f"); d=Class.forName("ji"); t=Class.forName("gga");
        rotation=Class.forName("gsn"); transformation=Class.forName("j"); baker=Class.forName("ggd");
        cube=Class.forName("geq"); corner=Class.forName("geq$b"); element=Class.forName("gfx");
        instance=baker.getConstructor().newInstance();
        position=baker.getDeclaredMethod("a",v,v); position.setAccessible(true);
        transform=baker.getMethod("a",v,transformation);
        defaultUv=element.getDeclaredMethod("a",d); defaultUv.setAccessible(true);
        faceFor=cube.getMethod("a",d); cornerFor=cube.getMethod("a",int.class);
        getRotation=rotation.getMethod("a",int.class,int.class); getTransform=rotation.getMethod("b");
        JsonArray input=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray();
        JsonArray output=new JsonArray();
        for (JsonElement value: input) {
            JsonObject q=value.getAsJsonObject(); Object from=vector(q.getAsJsonArray("from"));
            Object to=vector(q.getAsJsonArray("to")); Object dir=d.getMethod("a",String.class).invoke(null,q.get("face").getAsString());
            float[] pos=(float[])position.invoke(instance,from,to);
            float[] uv;
            if (!q.has("uv")) {
                Object el=element.getConstructor(v,v,Map.class,Class.forName("gfz"),boolean.class)
                    .newInstance(from,to,Map.of(),null,true);
                uv=(float[])defaultUv.invoke(el,dir);
            } else {
                uv=new float[4]; for(int i=0;i<4;i++) uv[i]=q.getAsJsonArray("uv").get(i).getAsFloat();
            }
            Object tex=t.getConstructor(float[].class,int.class).newInstance(uv,q.get("uvRotation").getAsInt());
            Object rot=getRotation.invoke(null,q.get("x").getAsInt(),q.get("y").getAsInt());
            if(rot==null) throw new IllegalStateException("Unsupported blockstate rotation");
            Object tr=getTransform.invoke(rot);
            if(q.get("uvlock").getAsBoolean()) tex=baker.getMethod("a",t,d,transformation).invoke(null,tex,dir,tr);
            Object cf=faceFor.invoke(null,dir); JsonArray points=new JsonArray(), uvs=new JsonArray();
            for(int i=0;i<4;i++) {
                Object c=cornerFor.invoke(cf,i);
                Object point=v.getConstructor(float.class,float.class,float.class).newInstance(
                    pos[corner.getField("a").getInt(c)],pos[corner.getField("b").getInt(c)],pos[corner.getField("c").getInt(c)]);
                transform.invoke(instance,point,tr);
                points.add(numbers((float)v.getMethod("x").invoke(point),(float)v.getMethod("y").invoke(point),(float)v.getMethod("z").invoke(point)));
                uvs.add(numbers((float)t.getMethod("a",int.class).invoke(tex,i)/16f,(float)t.getMethod("b",int.class).invoke(tex,i)/16f));
            }
            JsonObject result=new JsonObject(); result.addProperty("quadId",q.get("quadId").getAsInt());
            result.add("positions",points); result.add("uvs",uvs); output.add(result);
        }
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(output)+"\n");
    }
}
'''


def resource_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Resource ID is not text")
    value = value if ":" in value else "minecraft:" + value
    if not RESOURCE.fullmatch(value) or any(part in {"", ".", ".."} for part in value.split(":", 1)[1].split("/")):
        raise ValueError("Invalid resource ID: " + value)
    return value


def entry_path(value: str, kind: str, extension: str) -> str:
    namespace, path = resource_id(value).split(":", 1)
    return f"assets/{namespace}/{kind}/{path}.{extension}"


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def choices(state: dict) -> list[dict]:
    """Retain every model choice and condition, without choosing a random model."""
    result = []
    if ("variants" in state) == ("multipart" in state):
        raise ValueError("Expected exactly variants or multipart")
    groups = ((key, None, value) for key, value in state["variants"].items()) if "variants" in state else (
        (f"part:{index}", part.get("when"), part["apply"]) for index, part in enumerate(state["multipart"]))
    for selector, condition, models in groups:
        for index, model in enumerate(models if isinstance(models, list) else [models]):
            if not isinstance(model, dict) or "model" not in model:
                raise ValueError("Missing blockstate model")
            result.append({"selector": selector, "when": condition, "choice": index,
                           "model": resource_id(model["model"]), "x": model.get("x", 0), "y": model.get("y", 0),
                           "uvlock": model.get("uvlock", False), "weight": model.get("weight", 1)})
    return result


class Resources:
    def __init__(self, archive: zipfile.ZipFile):
        self.archive = archive
        self.names = set(archive.namelist())
        self.models: dict[str, dict] = {}

    def read_json(self, path: str) -> dict:
        value = json.loads(self.archive.read(path))
        if not isinstance(value, dict):
            raise ValueError("Expected resource object: " + path)
        return value

    def model(self, name: str, parents: tuple[str, ...] = ()) -> dict:
        name = resource_id(name)
        if name in parents:
            raise ValueError("Model parent cycle: " + name)
        if name in self.models:
            return self.models[name]
        path = entry_path(name, "models", "json")
        if name.startswith("minecraft:builtin/"):
            return {"textures": {}, "modelFiles": {}, "builtins": [name]}
        if path not in self.names:
            raise ValueError("Missing model: " + path)
        data = self.read_json(path)
        result = self.model(data["parent"], (*parents, name)) if "parent" in data else {"textures": {}, "modelFiles": {}, "builtins": []}
        result = copy.deepcopy(result)
        result["textures"].update(data.get("textures", {}))
        for key in ("elements", "ambientocclusion", "gui_light"):
            if key in data:
                result[key] = data[key]
        result["modelFiles"][path] = steve.digest(self.archive.read(path))
        self.models[name] = result
        return result

    @staticmethod
    def texture(value: str, mapping: dict) -> str:
        seen = set()
        while isinstance(value, str) and value.startswith("#"):
            if value in seen:
                raise ValueError("Texture alias cycle: " + value)
            seen.add(value)
            if value[1:] not in mapping:
                raise ValueError("Missing texture alias: " + value)
            value = mapping[value[1:]]
        return resource_id(value)

    def dependencies(self, name: str) -> dict:
        resolved = self.model(name)
        texture_ids = {self.texture(value, resolved["textures"]) for value in resolved["textures"].values()}
        for element in resolved.get("elements", []):
            for face in element.get("faces", {}).values():
                texture_ids.add(self.face_texture(face["texture"], resolved["textures"]))
        textures, missing = {}, []
        for texture in sorted(texture_ids):
            path = entry_path(texture, "textures", "png")
            if path not in self.names:
                missing.append(path)
                continue
            row = {"sha256": steve.digest(self.archive.read(path))}
            if path + ".mcmeta" in self.names:
                meta = self.read_json(path + ".mcmeta")
                row["mcmetaSha256"] = steve.digest(self.archive.read(path + ".mcmeta"))
                row["animation"] = meta.get("animation")
            textures[path] = row
        return {"modelFiles": dict(sorted(resolved["modelFiles"].items())), "textures": textures,
                "builtins": resolved["builtins"], "missing": missing,
                "tintedFaces": sum("tintindex" in face for element in resolved.get("elements", []) for face in element.get("faces", {}).values()),
                "elementCount": len(resolved.get("elements", []))}

    @classmethod
    def face_texture(cls, value: str, mapping: dict) -> str:
        # JsonUnbakedModel.resolveSprite removes an optional leading '#', then
        # looks up the KEY. Vanilla heavy_core faces use "all", without '#'.
        key = value[1:] if value.startswith("#") else value
        if key not in mapping:
            raise ValueError("Missing face texture key: " + key)
        return cls.texture(mapping[key], mapping)

    def coverage(self) -> dict:
        entries = []
        for path in sorted(name for name in self.names if name.startswith("assets/minecraft/blockstates/") and name.endswith(".json")):
            state = self.read_json(path)
            row = {"id": "minecraft:" + path[len("assets/minecraft/blockstates/"):-5], "file": path,
                   "sha256": steve.digest(self.archive.read(path)), "selectorKind": "multipart" if "multipart" in state else "variants", "choices": []}
            for choice in choices(state):
                item = dict(choice)
                try:
                    item.update(self.dependencies(choice["model"]))
                    item["dependencyStatus"] = "missing" if item["missing"] else "resolved"
                except (ValueError, KeyError) as error:
                    item.update({"dependencyStatus": "missing", "error": str(error)})
                row["choices"].append(item)
            row["nativeIntegrated"] = False
            entries.append(row)
        return {"schemaVersion": 1, "minecraftVersion": "1.21.1", "scope": "client blockstate resource files; not a registry or legal-state enumeration",
                "registryComplete": False, "nativeIntegrated": False, "resourceFileCount": len(entries),
                "modelChoiceCount": sum(len(row["choices"]) for row in entries),
                "missingChoiceCount": sum(choice["dependencyStatus"] == "missing" for row in entries for choice in row["choices"]),
                "builtinChoiceCount": sum(bool(choice.get("builtins")) for row in entries for choice in row["choices"]),
                "emptyGeometryChoiceCount": sum(choice.get("elementCount") == 0 for row in entries for choice in row["choices"]),
                "entries": entries}

    def baseline_quads(self) -> tuple[list[dict], list[dict]]:
        assets, quads = [], []
        for block in BASELINE:
            state = self.read_json(f"assets/minecraft/blockstates/{block}.json")
            if "multipart" in state:
                raise ValueError("Baseline multipart geometry is not supported")
            for choice in choices(state):
                if type(choice["x"]) is not int or type(choice["y"]) is not int or choice["x"] not in (0, 90, 180, 270) or choice["y"] not in (0, 90, 180, 270):
                    raise ValueError("Unsupported blockstate rotation")
                if type(choice["uvlock"]) is not bool or type(choice["weight"]) is not int or choice["weight"] < 1:
                    raise ValueError("Invalid variant metadata")
                model = self.model(choice["model"])
                dep = self.dependencies(choice["model"])
                if dep["missing"] or dep["builtins"] or not model.get("elements"):
                    raise ValueError("Baseline requires complete cuboid geometry: " + choice["model"])
                token = choice["selector"].replace("=", "_") or "default"
                filename = f"{block}__{token}__choice_{choice['choice']}"
                asset = {"id": "minecraft:" + block, **choice, "file": f"meshes/{filename}.gltf", "quadIds": [], "dependencies": dep}
                for element in model["elements"]:
                    if "rotation" in element:
                        raise ValueError("Element rotation is not supported by this baseline slice")
                    for bound in ("from", "to"):
                        if len(element.get(bound, [])) != 3 or any(type(n) not in (int, float) or not math.isfinite(n) for n in element[bound]):
                            raise ValueError("Invalid cuboid bounds")
                    if any(element["from"][i] >= element["to"][i] for i in range(3)):
                        raise ValueError("Degenerate cuboid")
                    for face, data in element["faces"].items():
                        if face not in FACES or data.get("tintindex", -1) != -1:
                            raise ValueError("Unsupported face or biome tint")
                        if data.get("rotation", 0) not in (0, 90, 180, 270):
                            raise ValueError("Unsupported face UV rotation")
                        if "uv" in data and (len(data["uv"]) != 4 or any(type(n) not in (int, float) or not math.isfinite(n) for n in data["uv"])):
                            raise ValueError("Invalid face UV")
                        texture = self.face_texture(data["texture"], model["textures"])
                        texture_path = entry_path(texture, "textures", "png")
                        png_info(self.archive.read(texture_path), require_opaque=True)
                        if texture_path + ".mcmeta" in self.names and "animation" in self.read_json(texture_path + ".mcmeta"):
                            raise ValueError("Animated baseline textures are not supported")
                        q = {"quadId": len(quads), "from": element["from"], "to": element["to"], "face": face,
                             "texture": texture, "cullface": data.get("cullface"), "shade": element.get("shade", True),
                             "uvRotation": data.get("rotation", 0), "x": choice["x"], "y": choice["y"], "uvlock": choice["uvlock"]}
                        if "uv" in data:
                            q["uv"] = data["uv"]
                        asset["quadIds"].append(q["quadId"])
                        quads.append(q)
                assets.append(asset)
        return assets, quads


def png_info(data: bytes, require_opaque: bool = False) -> dict:
    """Validate PNG framing/CRC, scanline length/filters, and conservative opacity."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Invalid PNG signature")
    pos, info, compressed, transparency = 8, None, bytearray(), False
    ended = False
    while pos < len(data):
        if pos + 12 > len(data):
            raise ValueError("Truncated PNG")
        length = struct.unpack_from(">I", data, pos)[0]
        kind, end = data[pos + 4:pos + 8], pos + 8 + length
        if end + 4 > len(data) or zlib.crc32(data[pos + 4:end]) != struct.unpack_from(">I", data, end)[0]:
            raise ValueError("PNG length/CRC mismatch")
        body = data[pos + 8:end]
        if kind == b"IHDR":
            if pos != 8 or info or length != 13:
                raise ValueError("Invalid PNG header")
            w, h, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
            if not (0 < w <= 4096 and 0 < h <= 4096 and compression == filtering == interlace == 0):
                raise ValueError("Unsupported PNG dimensions/encoding")
            channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)
            allowed_depths = (1, 2, 4, 8) if color == 3 else (1, 2, 4, 8, 16) if color == 0 else (8, 16)
            if channels is None or depth not in allowed_depths:
                raise ValueError("Unsupported PNG color encoding")
            info = {"width": w, "height": h, "bitDepth": depth, "colorType": color}
        elif kind == b"tRNS":
            transparency = True
        elif kind == b"IDAT":
            compressed.extend(body)
        elif kind == b"IEND":
            if length or end + 4 != len(data):
                raise ValueError("Invalid PNG end")
            ended = True
        pos = end + 4
    if not info or not ended:
        raise ValueError("Incomplete PNG")
    stride = (info["width"] * channels * info["bitDepth"] + 7) // 8 + 1
    expected = info["height"] * stride
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(compressed, expected + 1)
    if len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or any(pixels[i] > 4 for i in range(0, expected, stride)):
        raise ValueError("Invalid PNG scanlines")
    if require_opaque and (transparency or info["colorType"] in (4, 6)):
        raise ValueError("Baseline texture opacity is not proven")
    return info


def checked_target(output: Path, relative: str) -> Path:
    path = output / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(output.resolve()):
        raise ValueError("Output file leaves asset directory")
    current = path
    while current != output:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("Asset output cannot follow symlinks/junctions")
        current = current.parent
    return path


def write_file(output: Path, name: str, data: bytes) -> None:
    path = checked_target(output, name)
    temporary = checked_target(output, name + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(data)
    temporary.replace(path)


def engine_geometry(output: Path, client: Path, jars: list[Path], quads: list[dict], java_home: Path | None) -> list[dict]:
    write_file(output, "BlockQuadDump.java", JAVA_READER.encode("utf-8"))
    write_file(output, "quad-input.json", json_bytes(quads))
    classes = checked_target(output, "helper-classes")
    checked_target(output, "helper-classes/local/crimsonmc/assets/BlockQuadDump.class")
    classes.mkdir(exist_ok=True)
    java, javac = steve.java_tools(java_home)
    classpath = steve.os.pathsep.join(str(p) for p in [client, *jars])
    subprocess.run([str(javac), "--release", "21", "-cp", classpath, "-d", str(classes), str(output / "BlockQuadDump.java")],
                   check=True, capture_output=True, text=True)
    target = checked_target(output, "engine-quads.json")
    subprocess.run([str(java), "-Djava.awt.headless=true", "-cp", str(classes) + steve.os.pathsep + classpath,
                    "local.crimsonmc.assets.BlockQuadDump", str(output / "quad-input.json"), str(target)], check=True, capture_output=True, text=True)
    result = json.loads(target.read_text(encoding="utf-8"))
    if [row.get("quadId") for row in result] != list(range(len(quads))):
        raise ValueError("Engine output quad IDs disagree with input")
    return result


def normal(points: list[list[float]]) -> list[float]:
    a = [points[1][i] - points[0][i] for i in range(3)]
    b = [points[2][i] - points[0][i] for i in range(3)]
    n = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    length = math.sqrt(sum(x * x for x in n))
    if length < 1e-8:
        raise ValueError("Degenerate engine quad")
    return [x / length for x in n]


def export_gltf(asset: dict, quads: list[dict], geometry: list[dict]) -> tuple[dict, bytes]:
    texture_ids = sorted({quads[i]["texture"] for i in asset["quadIds"]})
    data = bytearray()
    gltf = {"asset": {"version": "2.0", "generator": "CrimsonMC original-class baseline block exporter"},
            "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": asset["id"]}],
            "meshes": [{"primitives": []}], "buffers": [{"uri": Path(asset["file"]).with_suffix(".bin").name}],
            "bufferViews": [], "accessors": [], "images": [], "textures": [], "materials": [],
            "samplers": [{"magFilter": 9728, "minFilter": 9728, "wrapS": 33071, "wrapT": 33071}],
            "extras": {"minecraftVersion": "1.21.1", "nativeIntegrated": False,
                       "coordinateSystem": "Minecraft: X east, Y up, Z south; one unit is one block; minimum corner at 0,0,0",
                       "selector": asset["selector"], "choice": asset["choice"], "weight": asset["weight"],
                       "model": asset["model"], "x": asset["x"], "y": asset["y"], "uvlock": asset["uvlock"],
                       "atlasUvShrinkApplied": False, "randomChoiceApplied": False}}
    for index, texture in enumerate(texture_ids):
        namespace, path = texture.split(":", 1)
        gltf["images"].append({"uri": f"../textures/{namespace}/{path}.png"})
        gltf["textures"].append({"source": index, "sampler": 0})
        gltf["materials"].append({"name": texture, "pbrMetallicRoughness": {"baseColorTexture": {"index": index}, "metallicFactor": 0, "roughnessFactor": 1}})

    def accessor(rows: list, components: int, code: str, kind: str, target: int) -> int:
        while len(data) % 4:
            data.append(0)
        offset = len(data)
        flat = [n for row in rows for n in row] if components > 1 else rows
        if not all(math.isfinite(n) for n in flat):
            raise ValueError("Nonfinite engine attribute")
        data.extend(struct.pack("<" + code * len(flat), *flat))
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": offset, "byteLength": len(data) - offset, "target": target})
        acc = {"bufferView": len(gltf["bufferViews"]) - 1, "componentType": 5126 if code == "f" else 5123, "count": len(rows), "type": kind}
        if kind == "VEC3":
            acc.update({"min": [min(row[i] for row in rows) for i in range(3)], "max": [max(row[i] for row in rows) for i in range(3)]})
        gltf["accessors"].append(acc)
        return len(gltf["accessors"]) - 1

    for index in asset["quadIds"]:
        quad, source = geometry[index], quads[index]
        points, uvs = quad["positions"], quad["uvs"]
        if len(points) != 4 or len(uvs) != 4 or any(len(p) != 3 for p in points) or any(len(uv) != 2 for uv in uvs):
            raise ValueError("Invalid engine quad shape")
        attributes = {"POSITION": accessor(points, 3, "f", "VEC3", 34962),
                      "NORMAL": accessor([normal(points)] * 4, 3, "f", "VEC3", 34962),
                      "TEXCOORD_0": accessor(uvs, 2, "f", "VEC2", 34962)}
        gltf["meshes"][0]["primitives"].append({"attributes": attributes, "indices": accessor([0, 1, 2, 0, 2, 3], 1, "H", "SCALAR", 34963),
                                             "material": texture_ids.index(source["texture"]), "mode": 4,
                                             "extras": {"sourceQuadId": index, "modelFace": source["face"], "modelCullface": source["cullface"], "minecraftShade": source["shade"]}})
    gltf["buffers"][0]["byteLength"] = len(data)
    return gltf, bytes(data)


def build(output: Path = DEFAULT_OUTPUT, client: Path | None = None, download: bool = False, java_home: Path | None = None) -> dict:
    output = steve.output_directory(output)
    config = steve.read_config()
    client, jars = steve.dependencies(config, client, download)
    steve.verify_client(client, config)
    with zipfile.ZipFile(client) as archive:
        for path, expected in ENGINE_CLASSES.items():
            if steve.digest(archive.read(path)) != expected:
                raise ValueError("Block engine class hash mismatch: " + path)
        resources = Resources(archive)
        coverage = resources.coverage()
        assets, quads = resources.baseline_quads()
        files = {"coverage.json": json_bytes(coverage)}
        for texture in sorted({q["texture"] for q in quads}):
            namespace, name = texture.split(":", 1)
            files[f"textures/{namespace}/{name}.png"] = archive.read(entry_path(texture, "textures", "png"))
    output.mkdir(parents=True, exist_ok=True)
    geometry = engine_geometry(output, client, jars, quads, java_home)
    for asset in assets:
        gltf, binary = export_gltf(asset, quads, geometry)
        files[asset["file"]] = json_bytes(gltf)
        files[str(Path(asset["file"]).with_suffix(".bin")).replace("\\", "/")] = binary
    # Validate the entire output plan before publishing the files/manifest.
    for name in files:
        checked_target(output, name)
        checked_target(output, name + ".tmp")
    for name, data in files.items():
        write_file(output, name, data)
    files.update({name: (output / name).read_bytes() for name in ("BlockQuadDump.java", "quad-input.json", "engine-quads.json")})
    manifest = {"schemaVersion": 1, "minecraftVersion": "1.21.1", "clientSha256": config["client"]["sha256"],
                "sourceConfigSha256": steve.digest(steve.CONFIG.read_bytes()), "exporterSha256": steve.digest(Path(__file__).read_bytes()),
                "engineClassSha256": ENGINE_CLASSES, "readerSha256": steve.digest(JAVA_READER.encode("utf-8")),
                "nativeIntegrated": False, "registryComplete": False, "assets": assets,
                "coverage": {key: coverage[key] for key in ("resourceFileCount", "modelChoiceCount", "missingChoiceCount", "builtinChoiceCount", "emptyGeometryChoiceCount")},
                "files": {name: steve.digest(data) for name, data in sorted(files.items())},
                "limitations": ["Resource-file coverage is not Registries.BLOCK or an enumeration of all legal states.",
                                "Only six baseline opaque cuboid block types are exported; every listed variant/weight is retained, no random choice is executed.",
                                "Element rotations, multipart geometry, biome tint, fluids, builtin/block-entity renderers, transparency and texture animation are not exported.",
                                "Original Java classes provide model corners, default/rotated UVs and blockstate transforms; atlas-specific UV shrink is omitted for standalone textures.",
                                "glTF has no Crimson Desert PAC/material/prefab binding, collision, lighting/ambient occlusion, neighbor culling or in-game evidence.",
                                "Official resources and derived assets remain local/ignored; no game assets may be bundled in the plugin or repository."]}
    write_file(output, "manifest.json", json_bytes(manifest))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--client", type=Path)
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    try:
        result = build(args.output, args.client, args.download, args.java_home)
    except subprocess.CalledProcessError as error:
        raise SystemExit("Offline block reader failed: " + (error.stderr or error.stdout)) from error
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps({"output": str(steve.output_directory(args.output)), "assets": len(result["assets"]),
                      "coverage": result["coverage"], "nativeIntegrated": False, "registryComplete": False}, indent=2))


if __name__ == "__main__":
    main()
