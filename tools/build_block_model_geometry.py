"""Export every pinned vanilla blockstate model variant's actual faces offline.

The original Java FaceBakery component methods provide positions, rotation,
rescale, UV lock, facing and winding. Standalone sprite UVs omit atlas shrink.
This is consumable quad data, not a renderer, collision mesh or native import.
All licensed source/derived data remain in a new ignored build directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import subprocess
import tempfile
import zipfile

import build_block_assets as base

steve = base.steve
DEFAULT_OUTPUT = steve.ROOT / "build/block-model-geometry-1.21.1"
ENGINE_CLASSES = {**base.ENGINE_CLASSES,
    "gfx$a.class": "82114d80278992d4db414c67f1db7d0c93f010e1a6688bd2c8693bcea561ac84",
    "gfz.class": "f5d524fb2de352631d088d9f1a268f8b38aa11a9edbcf9ed87f92b92d1ab5322",
    "ji$a.class": "fe933a7a42a0cadffad20a1adca1fa7471b7f03705d87de448b70d6a962cdf0e",
    "jc.class": "746907d5267a32e3f69d2af160a65b667379a1d1192fb14bc03a3cce533cf3c2",
}
JAVA_READER = r'''package local.crimsonmc.assets;
import com.google.gson.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.Map;
import java.util.zip.ZipFile;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

/** No Minecraft main, registry bootstrap, world, native image, GPU or atlas. */
public final class BlockModelGeometryDump {
    static Class<?> v,d,t,rotation,transformation,baker,cube,corner,element,elementRotation;
    static Object instance,rotationDeserializer;
    static Method position,transform,defaultUv,faceFor,cornerFor,getRotation,getTransform;
    static Method elementRotate,parseRotation,calculateFacing,recalculateWinding;
    static Object vector(JsonArray a) throws Exception {
        return v.getConstructor(float.class,float.class,float.class).newInstance(
            a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());
    }
    static JsonArray numbers(float... values) {
        JsonArray a=new JsonArray();
        for(float n:values) {
            if(!Float.isFinite(n)) throw new IllegalStateException("Nonfinite engine output");
            a.add(n);
        }
        return a;
    }
    public static void main(String[] args) throws Exception {
        v=Class.forName("org.joml.Vector3f");d=Class.forName("ji");t=Class.forName("gga");
        rotation=Class.forName("gsn");transformation=Class.forName("j");baker=Class.forName("ggd");
        cube=Class.forName("geq");corner=Class.forName("geq$b");element=Class.forName("gfx");
        instance=baker.getConstructor().newInstance();elementRotation=Class.forName("gfz");
        Class<?> deserializer=Class.forName("gfx$a");
        Constructor<?> constructor=deserializer.getDeclaredConstructor();constructor.setAccessible(true);
        rotationDeserializer=constructor.newInstance();
        parseRotation=deserializer.getDeclaredMethod("a",JsonObject.class);parseRotation.setAccessible(true);
        elementRotate=baker.getDeclaredMethod("a",v,elementRotation);elementRotate.setAccessible(true);
        calculateFacing=baker.getMethod("a",int[].class);
        recalculateWinding=baker.getDeclaredMethod("a",int[].class,d);recalculateWinding.setAccessible(true);
        position=baker.getDeclaredMethod("a",v,v);position.setAccessible(true);
        transform=baker.getMethod("a",v,transformation);
        defaultUv=element.getDeclaredMethod("a",d);defaultUv.setAccessible(true);
        faceFor=cube.getMethod("a",d);cornerFor=cube.getMethod("a",int.class);
        getRotation=rotation.getMethod("a",int.class,int.class);getTransform=rotation.getMethod("b");
        JsonObject input=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        JsonArray output=new JsonArray();
        for(JsonElement value:input.getAsJsonArray("quads")) {
            JsonObject q=value.getAsJsonObject();Object from=vector(q.getAsJsonArray("from"));
            Object to=vector(q.getAsJsonArray("to"));
            Object dir=d.getMethod("a",String.class).invoke(null,q.get("face").getAsString());
            float[] pos=(float[])position.invoke(instance,from,to);
            JsonObject elementData=new JsonObject();
            if(q.has("elementRotation")) elementData.add("rotation",q.get("elementRotation"));
            // Original deserializer converts model-space origin /16 and validates angle/axis.
            Object er=parseRotation.invoke(rotationDeserializer,elementData);
            float[] uv;
            if(!q.has("uv")) {
                Object el=element.getConstructor(v,v,Map.class,elementRotation,boolean.class)
                    .newInstance(from,to,Map.of(),null,true);
                uv=(float[])defaultUv.invoke(el,dir);
            } else {
                uv=new float[4];for(int i=0;i<4;i++) uv[i]=q.getAsJsonArray("uv").get(i).getAsFloat();
            }
            Object tex=t.getConstructor(float[].class,int.class).newInstance(uv,q.get("uvRotation").getAsInt());
            Object rot=getRotation.invoke(null,q.get("x").getAsInt(),q.get("y").getAsInt());
            if(rot==null) throw new IllegalStateException("Unsupported blockstate rotation");
            Object tr=getTransform.invoke(rot);
            if(q.get("uvlock").getAsBoolean()) tex=baker.getMethod("a",t,d,transformation).invoke(null,tex,dir,tr);
            Object cf=faceFor.invoke(null,dir);int[] packed=new int[32];
            for(int i=0;i<4;i++) {
                Object c=cornerFor.invoke(cf,i);
                Object point=v.getConstructor(float.class,float.class,float.class).newInstance(
                    pos[corner.getField("a").getInt(c)],pos[corner.getField("b").getInt(c)],pos[corner.getField("c").getInt(c)]);
                elementRotate.invoke(instance,point,er);transform.invoke(instance,point,tr);
                packed[i*8]=Float.floatToRawIntBits((float)v.getMethod("x").invoke(point));
                packed[i*8+1]=Float.floatToRawIntBits((float)v.getMethod("y").invoke(point));
                packed[i*8+2]=Float.floatToRawIntBits((float)v.getMethod("z").invoke(point));
                packed[i*8+3]=-1;
                packed[i*8+4]=Float.floatToRawIntBits((float)t.getMethod("a",int.class).invoke(tex,i)/16f);
                packed[i*8+5]=Float.floatToRawIntBits((float)t.getMethod("b",int.class).invoke(tex,i)/16f);
            }
            Object computedFace=calculateFacing.invoke(null,packed);
            // This branch is identical to FaceBakery.bakeQuad, including angle=0 rotations.
            if(er==null) recalculateWinding.invoke(instance,packed,computedFace);
            JsonArray points=new JsonArray(),uvs=new JsonArray();
            for(int i=0;i<4;i++) {
                points.add(numbers(Float.intBitsToFloat(packed[i*8]),Float.intBitsToFloat(packed[i*8+1]),Float.intBitsToFloat(packed[i*8+2])));
                uvs.add(numbers(Float.intBitsToFloat(packed[i*8+4]),Float.intBitsToFloat(packed[i*8+5])));
            }
            JsonObject result=new JsonObject();result.addProperty("quadId",q.get("quadId").getAsInt());
            result.addProperty("calculatedFacing",computedFace.toString());
            result.addProperty("windingRecalculated",er==null);
            if(q.has("cullface")) {
                Object mat=transformation.getMethod("c").invoke(tr);
                Object sourceCull=d.getMethod("a",String.class).invoke(null,q.get("cullface").getAsString());
                // Vanilla scaffolding contains "bottom": Direction.byName returns null.
                if(sourceCull==null) result.add("transformedCullface",JsonNull.INSTANCE);
                else {
                    Object cull=d.getMethod("a",Class.forName("org.joml.Matrix4f"),d).invoke(null,mat,sourceCull);
                    result.addProperty("transformedCullface",cull.toString());
                }
            }
            result.add("positions",points);result.add("uvs",uvs);output.add(result);
        }
        JsonObject textures=new JsonObject();
        try(ZipFile archive=new ZipFile(args[2])) {
            for(JsonElement value:input.getAsJsonArray("textures")) {
                JsonObject source=value.getAsJsonObject();String entry=source.get("entry").getAsString();
                BufferedImage img;
                try(var stream=archive.getInputStream(archive.getEntry(entry))) {img=ImageIO.read(stream);}
                if(img==null) throw new IllegalStateException("PNG decoder failed: "+entry);
                int transparent=0,partial=0,opaque=0;
                for(int y=0;y<img.getHeight();y++) for(int x=0;x<img.getWidth();x++) {
                    int alpha=(img.getRGB(x,y)>>>24)&255;
                    if(alpha==0) transparent++;else if(alpha==255) opaque++;else partial++;
                }
                JsonObject row=new JsonObject();row.addProperty("width",img.getWidth());row.addProperty("height",img.getHeight());
                row.addProperty("transparentPixels",transparent);row.addProperty("partialAlphaPixels",partial);row.addProperty("opaquePixels",opaque);
                row.addProperty("pixelAlphaClass",partial>0?"fractional-alpha":transparent>0?"binary-alpha":"opaque");
                textures.add(source.get("id").getAsString(),row);
            }
        }
        JsonObject result=new JsonObject();result.add("quads",output);result.add("textures",textures);
        Files.writeString(Path.of(args[1]),new GsonBuilder().serializeNulls().create().toJson(result)+"\n",StandardOpenOption.CREATE_NEW);
    }
}
'''


def compact(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def variant_tuple(choice: dict) -> tuple:
    return choice["model"], choice["x"], choice["y"], choice["uvlock"]


def variant_key(choice: dict) -> str:
    return f"{choice['model']}|x={choice['x']}|y={choice['y']}|uvlock={int(choice['uvlock'])}"


def preflight(output: Path, client: Path | None = None) -> Path:
    output = steve.output_directory(output)
    if output.exists():
        raise ValueError("Geometry output already exists; no assets are overwritten")
    if client and client.resolve().is_relative_to(output):
        raise ValueError("Geometry output overlaps client input")
    return output


def finite_vector(value: object, size: int) -> bool:
    return isinstance(value, list) and len(value) == size and all(type(n) in (int, float) and math.isfinite(n) for n in value)


def source_plan(resources: base.Resources) -> tuple[list, list, list, dict]:
    """Retain source choices; share only geometrically identical variant tuples."""
    entries, variants, quads, models = [], {}, [], {}
    for path in sorted(n for n in resources.names if n.startswith("assets/minecraft/blockstates/") and n.endswith(".json")):
        document = resources.read_json(path)
        row = {"id": "minecraft:" + path.removeprefix("assets/minecraft/blockstates/")[:-5],
               "file": path, "sha256": steve.digest(resources.archive.read(path)),
               "selectorKind": "multipart" if "multipart" in document else "variants", "choices": []}
        for choice in base.choices(document):
            if any(type(choice[k]) is not int or choice[k] not in (0, 90, 180, 270) for k in ("x", "y")):
                raise ValueError("Invalid model rotation")
            if type(choice["uvlock"]) is not bool or type(choice["weight"]) is not int or choice["weight"] < 1:
                raise ValueError("Invalid model choice")
            key = variant_key(choice)
            row["choices"].append({**choice, "geometryKey": key})
            if key in variants:
                continue
            model = resources.model(choice["model"])
            if choice["model"] not in models:
                dep = resources.dependencies(choice["model"])
                if dep["missing"]:
                    raise ValueError("Unresolved model dependency: " + choice["model"])
                models[choice["model"]] = dep
            variant = {"key": key, **{k: choice[k] for k in ("model", "x", "y", "uvlock")},
                       "firstQuad": len(quads), "quadCount": 0,
                       "ambientOcclusion": model.get("ambientocclusion", True),
                       "geometryKind": "json-elements" if model.get("elements") else "builtin-or-empty",
                       "builtins": model["builtins"], "nativeIntegrated": False}
            for index, element in enumerate(model.get("elements", [])):
                if not all(finite_vector(element.get(k), 3) for k in ("from", "to")):
                    raise ValueError("Invalid element bounds")
                # Reversed/zero-width bounds are real vanilla models. Do not normalize or discard.
                rotation = element.get("rotation")
                if rotation is not None:
                    if not isinstance(rotation, dict) or not finite_vector(rotation.get("origin"), 3):
                        raise ValueError("Invalid element rotation origin")
                    if rotation.get("axis") not in ("x", "y", "z") or rotation.get("angle") not in (-45, -22.5, 0, 22.5, 45):
                        raise ValueError("Invalid element rotation")
                    if type(rotation.get("rescale", False)) is not bool:
                        raise ValueError("Invalid element rescale")
                for face, data in element.get("faces", {}).items():
                    if face not in base.FACES or data.get("rotation", 0) not in (0, 90, 180, 270):
                        raise ValueError("Invalid face")
                    if "uv" in data and not finite_vector(data["uv"], 4):
                        raise ValueError("Invalid face UV")
                    if "cullface" in data and not isinstance(data["cullface"], str):
                        raise ValueError("Invalid cullface type")
                    quad = {"quadId": len(quads), "geometryKey": key, "element": index,
                            "from": element["from"], "to": element["to"], "face": face,
                            "texture": resources.face_texture(data["texture"], model["textures"]),
                            "tintIndex": data.get("tintindex", -1), "shade": element.get("shade", True),
                            "uvRotation": data.get("rotation", 0),
                            **{k: choice[k] for k in ("x", "y", "uvlock")}}
                    for field in ("uv", "cullface"):
                        if field in data:
                            quad[field] = data[field]
                    if rotation is not None:
                        quad["elementRotation"] = rotation
                    quads.append(quad)
            variant["quadCount"] = len(quads) - variant["firstQuad"]
            variants[key] = variant
        entries.append(row)
    return entries, list(variants.values()), quads, models


def engine_geometry(output: Path, client: Path, jars: list[Path], request: dict, java_home: Path | None) -> dict:
    """Only called inside an exclusive temporary build directory."""
    source = output / "BlockModelGeometryDump.java"
    source.write_bytes(JAVA_READER.encode("utf-8"))
    (output / "quad-input.json").write_bytes(compact(request))
    classes = output / "helper-classes"
    classes.mkdir()
    java, javac = steve.java_tools(java_home)
    classpath = steve.os.pathsep.join(str(p) for p in [client, *jars])
    options = {"cwd": output, "check": True, "capture_output": True, "text": True, "timeout": 180}
    if steve.os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.run([str(javac), "--release", "21", "-cp", classpath, "-d", str(classes), str(source)], **options)
    target = output / "engine-quads.json"
    subprocess.run([str(java), "-Xmx1024m", "-Djava.awt.headless=true", "-cp", str(classes) + steve.os.pathsep + classpath,
                    "local.crimsonmc.assets.BlockModelGeometryDump", str(output / "quad-input.json"), str(target), str(client)], **options)
    return json.loads(target.read_bytes())


def triangle_normal(points: list, triangle: tuple) -> list | None:
    a, b, c = (points[i] for i in triangle)
    u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
    cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
    length = math.sqrt(sum(n*n for n in cross))
    return [n / length for n in cross] if length > 1e-12 else None


def validate_geometry(request: list, result: list) -> None:
    if len(result) != len(request):
        raise ValueError("Engine output quad count disagrees")
    for source, quad in zip(request, result):
        if quad.get("quadId") != source["quadId"] or quad.get("calculatedFacing") not in base.FACES:
            raise ValueError("Engine output identity/facing disagrees")
        if quad.get("windingRecalculated") != ("elementRotation" not in source):
            raise ValueError("Engine winding branch disagrees")
        for name, width in (("positions", 3), ("uvs", 2)):
            value = quad.get(name)
            if not isinstance(value, list) or len(value) != 4 or not all(finite_vector(v, width) for v in value):
                raise ValueError("Invalid engine geometry")
        if ("cullface" in source) != ("transformedCullface" in quad):
            raise ValueError("Engine cullface disappeared/appeared")
        if "transformedCullface" in quad and quad["transformedCullface"] not in (*base.FACES, None):
            raise ValueError("Invalid transformed cullface")


def build(output: Path = DEFAULT_OUTPUT, client: Path | None = None, java_home: Path | None = None) -> dict:
    # Java runs in a private stage; CLI-relative inputs belong to the caller's cwd.
    client = client.resolve() if client is not None else None
    java_home = java_home.resolve() if java_home is not None else None
    output = preflight(output, client)
    config = steve.read_config()
    client, jars = steve.dependencies(config, client, False)
    steve.verify_client(client, config)
    files, texture_rows = {}, {}
    with zipfile.ZipFile(client) as archive:
        for path, expected in ENGINE_CLASSES.items():
            if steve.digest(archive.read(path)) != expected:
                raise ValueError("Geometry engine class hash mismatch: " + path)
        resources = base.Resources(archive)
        entries, variants, quads, models = source_plan(resources)
        for texture in sorted({q["texture"] for q in quads}):
            entry = base.entry_path(texture, "textures", "png")
            data = archive.read(entry)
            info = base.png_info(data)
            name = "textures/" + texture.replace(":", "/") + ".png"
            files[name] = data
            row = {"entry": entry, "file": name, "sha256": steve.digest(data), **info, "animated": False}
            if entry + ".mcmeta" in resources.names:
                meta_bytes = archive.read(entry + ".mcmeta")
                row.update({"metadata": json.loads(meta_bytes), "mcmetaSha256": steve.digest(meta_bytes)})
                row["animated"] = "animation" in row["metadata"]
                files[name + ".mcmeta"] = meta_bytes
            texture_rows[texture] = row
    request = {"quads": quads, "textures": [{"id": k, "entry": v["entry"]} for k, v in texture_rows.items()]}
    (steve.ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="block-geometry-", dir=steve.ROOT / "build") as temporary:
        stage = steve.output_directory(Path(temporary))
        result = engine_geometry(stage, client, jars, request, java_home)
        files.update({name: (stage / name).read_bytes() for name in ("BlockModelGeometryDump.java", "quad-input.json", "engine-quads.json")})
    validate_geometry(quads, result["quads"])
    if set(result["textures"]) != set(texture_rows):
        raise ValueError("Texture decoder coverage disagrees")
    for texture, decoded in result["textures"].items():
        row = texture_rows[texture]
        if decoded["width"] != row["width"] or decoded["height"] != row["height"]:
            raise ValueError("Texture decoder dimensions disagree")
        if sum(decoded[k] for k in ("transparentPixels", "partialAlphaPixels", "opaquePixels")) != row["width"] * row["height"]:
            raise ValueError("Texture decoder alpha coverage disagrees")
        row.update(decoded)
    geometry = []
    for source, computed in zip(quads, result["quads"]):
        normals = [triangle_normal(computed["positions"], tri) for tri in ((0, 1, 2), (0, 2, 3))]
        geometry.append({**source, **computed, "triangleNormals": normals,
                         "degenerateTriangles": sum(n is None for n in normals)})
    for variant in variants:
        subset = geometry[variant["firstQuad"]:variant["firstQuad"] + variant["quadCount"]]
        variant["tintedFaceCount"] = sum(q["tintIndex"] != -1 for q in subset)
        variant["degenerateFaceCount"] = sum(q["degenerateTriangles"] > 0 for q in subset)
        variant["requiresTextureAnimation"] = any(texture_rows[q["texture"]]["animated"] for q in subset)
        variant["containsNonopaquePixels"] = any(texture_rows[q["texture"]]["pixelAlphaClass"] != "opaque" for q in subset)
    summary = {"resourceBlockCount": len(entries), "modelChoiceCount": sum(len(e["choices"]) for e in entries),
               "uniqueReferencedModelCount": len(models), "geometryVariantCount": len(variants),
               "nonemptyVariantCount": sum(v["quadCount"] > 0 for v in variants),
               "emptyVariantCount": sum(v["quadCount"] == 0 for v in variants),
               "quadCount": len(geometry), "elementRotatedQuadCount": sum("elementRotation" in q for q in geometry),
               "rescaledQuadCount": sum(q.get("elementRotation", {}).get("rescale", False) for q in geometry),
               "tintedQuadCount": sum(q["tintIndex"] != -1 for q in geometry),
               "degenerateQuadCount": sum(q["degenerateTriangles"] > 0 for q in geometry),
               "faceTextureCount": len(texture_rows), "animatedFaceTextureCount": sum(t["animated"] for t in texture_rows.values()),
               "textureAlphaClasses": dict(sorted(Counter(t["pixelAlphaClass"] for t in texture_rows.values()).items()))}
    files["geometry.json"] = compact({"schemaVersion": 1, "coordinateSystem": "original Minecraft block coordinates; one unit per block",
        "uvSpace": "standalone frame-local UV, no atlas placement/shrink or animation-frame sampling", "triangles": [[0, 1, 2], [0, 2, 3]],
        "variants": variants, "quads": geometry, "nativeIntegrated": False})
    files["model-dependencies.json"] = compact(models)
    files["resource-models.json"] = compact({"schemaVersion": 1, "entries": entries, "randomChoiceApplied": False, "registryComplete": False})
    files["textures.json"] = compact(texture_rows)
    report = {"schemaVersion": 1, "minecraftVersion": "1.21.1", "summary": summary,
        "clientSha256": config["client"]["sha256"], "sourceConfigSha256": steve.digest(steve.CONFIG.read_bytes()),
        "exporterSha256": steve.digest(Path(__file__).read_bytes()), "resourceResolverSha256": steve.digest(Path(base.__file__).read_bytes()),
        "readerSha256": steve.digest(JAVA_READER.encode("utf-8")), "engineClassSha256": ENGINE_CLASSES,
        "files": {name: steve.digest(data) for name, data in sorted(files.items())},
        "integration": {"nativeIntegrated": False, "collisionExported": False, "rendererImplemented": False,
                        "registryComplete": False, "randomChoiceApplied": False, "gameOrWorldStarted": False},
        "limitations": ["Covers client resource choices, including two unregistered item-frame resources; join legal states by exact (model,x,y,uvlock).",
            "Every weighted choice/multipart condition is retained; no random selection or neighbor culling is executed.",
            "Original FaceBakery component methods are used, not full client baking; standalone UV omits atlas shrink/placement.",
            "Biome tint, texture alpha, animation metadata, shade and ambient occlusion are preserved but not rendered; render layers are unimplemented.",
            "Zero-width, reversed and collapsed source faces remain; degenerate triangles have null normals, never invented cube geometry.",
            "Empty/builtin models have no invented faces: fluid, block entity and special renderer geometry remains unimplemented.",
            "No native mesh/material/prefab, collision, runtime state wiring, in-game appearance or equipment is provided."]}
    # Publishing requires a still-new output directory. A failed build never replaces a prior package.
    output = preflight(output, client)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for name, data in files.items():
        base.write_file(output, name, data)
    base.write_file(output, "manifest.json", base.json_bytes(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--client", type=Path)
    parser.add_argument("--java-home", type=Path)
    args = parser.parse_args()
    try:
        report = build(args.output, args.client, args.java_home)
    except subprocess.CalledProcessError as error:
        raise SystemExit("Offline model geometry failed: " + (error.stderr or error.stdout)) from error
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps({"output": str(args.output), **report["summary"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
