"""Map every pinned vanilla 1.21.1 state to all applicable model groups offline.

An isolated original-class Java oracle checks every predicate/state and parsed
variant. This starts registries only, never a world, client, server or service.
No random choice, default-state substitution or native geometry is produced.
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

import build_block_assets as models
import build_block_registry as registry

assets = registry.assets
ROOT = assets.ROOT
DEFAULT_OUTPUT = ROOT / "build/block-state-models-1.21.1"
REGISTRY_DIR = ROOT / "build/block-registry-1.21.1"
COVERAGE = ROOT / "build/block-assets-1.21.1/coverage.json"
MAPPINGS = ROOT / "downloads/block-state-models-1.21.1/client-mappings.txt"
MAPPINGS_SOURCE = {"url": "https://piston-data.mojang.com/v1/objects/2244b6f072256667bcd9a73df124d6c58de77992/client.txt",
                   "sha1": "2244b6f072256667bcd9a73df124d6c58de77992", "size": 9598610}
MAPPINGS_SHA256 = "140c47931cccc8fc9e4c22d7603e2d714d1a953a146f51ea7397d95c955536ec"
REGISTRY_SHA256 = "8322699afad9f8873fac2fcde539ba7bdf52d3e7b3f0a5216f6b66e5538efd04"
COVERAGE_SHA256 = "8fbe5fb4ee9f8752080d1f58861c85397faff8c964ba1749fa854989dd08504d"
CONFIG_SHA256 = "1cc61e1018feaed90ef5287b4df0e2dabb9848e78fe14c8a572d6b3c7a4ad4d7"
CLIENT_SHA256 = "499f6897d1837516680f3114072d8106e11c9adcd933fe5cf051b551089b0c99"
ENGINE_CLASSES = {
    "ggc.class": "f3896078de8c4cf8eed8e2ef3aa278ef7f0749fc9e5dbdc30c8bc5772d18437c",
    "ggc$a.class": "2085c2f58d77e7ee468fcfb2794bb85195dea64b619970324bb8054db0febb80",
    "ggc$b.class": "416df35e8174ece362c2a688f91fab90f074982fabe2c98053a7f1b7140f7f9b",
    "ggj.class": "c45216f605d2fd77fefaa4fcc795a154735b28bc745cfc1ab0adbecd22b699cd",
    "ggj$a.class": "8a5a3e0c932fe820680b8a80772eaac18189deedd113d4103ffc2643abf47349",
    "ggk.class": "1311fa349080067f338e7446eb11d532080642ba09cd85b248aa0b20af91acb1",
    "ggk$a.class": "d6eac32140e125a1700509065a1981df4692791657be1e3fdaa1d973ba87f667",
    "ggl.class": "e9dfb359015c4ca0017a5caabaf8dc7d36438a9f6695b63a20acf9518a4d4e85",
    "ggm.class": "1afca24983beaab0a7a65086def4f626f111c086f0485d9ec79414bc85a916b2",
    "ggn.class": "a76c222ffe6993a6e6c1c991afe75b9c6d7f830e3f57e74f2171c5441480634d",
    "ggo.class": "6223c30e6d82fd20c1d53fb6200ed710e03d5b5101819b67d8043503273c1811",
    "ggo$a.class": "188a19d5fd7405bdfe5bd7718dad3f11061426db0414505cf171f919e791a651",
    "ggp.class": "020e74031c898acfb73748cd94412fe18f24f929def2dd8f178d167c0ffa783f",
    "ggq.class": "fa935320ba30af5c9aad88006001b1aa4281e41f9b4199a09ce3ba213d48534c",
    "ggq$a.class": "ba39596c5d8fa03862dbc26ebd3ef08904e1a89c97f3edd180fbab265512bfca",
    "gso.class": "e07a372c235c0d702cb126046ec84676daecc9d7910fe49c28fc1ae3e6e709af",
    "gsn.class": "9a6447bcfbc76169baceebe3c15495b5cfc08da65441a659bc56170b4c6326d1",
}
MAPPING_HEADERS = {
    "net.minecraft.client.resources.model.BlockStateModelLoader": "gso",
    "net.minecraft.client.renderer.block.model.BlockModelDefinition": "ggc",
    "net.minecraft.client.renderer.block.model.BlockModelDefinition$Context": "ggc$a",
    "net.minecraft.client.renderer.block.model.multipart.Selector": "ggq",
    "net.minecraft.client.renderer.block.model.multipart.KeyValueCondition": "ggn",
    "net.minecraft.world.level.block.state.StateDefinition": "dtd",
    "net.minecraft.world.level.block.state.BlockState": "dtc",
    "net.minecraft.core.registries.BuiltInRegistries": "lt",
}

JAVA_READER = r'''package local.crimsonmc.assets;
import com.google.gson.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.function.Predicate;
import java.util.zip.ZipFile;
public final class BlockStateModelDump {
    static Class<?> def, state, block, holder, property, definition, context, selector, multi, variant, rotation;
    static Object blocks; static TreeMap<String,Object> byName = new TreeMap<>();
    static Method variantPredicate, parse, stateId, stateProperties, propertyName, valueName, render;
    static void initialize() throws Exception {
        Class.forName("ab").getMethod("a").invoke(null);
        Class.forName("akt").getMethod("a").invoke(null);
        def=Class.forName("dtd"); state=Class.forName("dtc"); block=Class.forName("dfy");
        holder=Class.forName("dte"); property=Class.forName("duf"); definition=Class.forName("ggc");
        context=Class.forName("ggc$a"); selector=Class.forName("ggq"); multi=Class.forName("ggj");
        variant=Class.forName("ggk"); rotation=Class.forName("gsn");
        blocks=Class.forName("lt").getField("e").get(null);
        Method key=Class.forName("jz").getMethod("b",Object.class);
        for(Object b:(Iterable<?>)blocks) byName.put(key.invoke(blocks,b).toString(),b);
        variantPredicate=Class.forName("gso").getDeclaredMethod("a",def,String.class);
        variantPredicate.setAccessible(true);
        parse=definition.getMethod("a",context,JsonElement.class); stateId=block.getMethod("i",state);
        stateProperties=holder.getMethod("C"); propertyName=property.getMethod("f");
        valueName=property.getMethod("a",Comparable.class); render=Class.forName("dtb$a").getMethod("l");
    }
    static Object stateDefinition(Object b) throws Exception {return block.getMethod("l").invoke(b);}
    static Object parseDefinition(Object d,JsonObject raw) throws Exception {
        Object c=context.getConstructor().newInstance();context.getMethod("a",def).invoke(c,d);
        return parse.invoke(null,c,raw);
    }
    @SuppressWarnings("unchecked") static Predicate<Object> variantPredicate(Object d,String key) throws Exception {
        return (Predicate<Object>)variantPredicate.invoke(null,d,key);
    }
    static JsonObject properties(Object s) throws Exception {
        TreeMap<String,String> sorted=new TreeMap<>();
        for(var e:((Map<?,?>)stateProperties.invoke(s)).entrySet())
            sorted.put((String)propertyName.invoke(e.getKey()),(String)valueName.invoke(e.getKey(),e.getValue()));
        JsonObject out=new JsonObject();sorted.forEach(out::addProperty);return out;
    }
    static JsonArray parsedChoices(Object mv,JsonElement source) throws Exception {
        List<?> values=(List<?>)multi.getMethod("a").invoke(mv);
        JsonArray raw=source.isJsonArray()?source.getAsJsonArray():new JsonArray();
        if(!source.isJsonArray())raw.add(source);
        if(values.size()!=raw.size())throw new IllegalStateException("Original variant list changed size");
        JsonArray out=new JsonArray();
        for(int i=0;i<values.size();i++) {
            Object v=values.get(i);JsonObject input=raw.get(i).getAsJsonObject();
            int x=input.has("x")?input.get("x").getAsInt():0,y=input.has("y")?input.get("y").getAsInt():0;
            Object r=rotation.getMethod("a",int.class,int.class).invoke(null,x,y);
            if(r==null||!variant.getMethod("b").invoke(v).equals(rotation.getMethod("b").invoke(r)))
                throw new IllegalStateException("Original variant rotation differs from raw x/y");
            JsonObject q=new JsonObject();q.addProperty("choice",i);
            q.addProperty("model",variant.getMethod("a").invoke(v).toString());q.addProperty("x",x);q.addProperty("y",y);
            q.addProperty("uvlock",(Boolean)variant.getMethod("c").invoke(v));
            q.addProperty("weight",(Integer)variant.getMethod("d").invoke(v));out.add(q);
        }return out;
    }
    @SuppressWarnings("unchecked") static JsonObject blockResult(String id,JsonObject raw) throws Exception {
        Object b=byName.get(id);if(b==null)throw new IllegalStateException("Unknown registry block");
        Object d=stateDefinition(b),parsed=parseDefinition(d,raw);
        ArrayList<Predicate<Object>> predicates=new ArrayList<>();JsonArray groups=new JsonArray();
        if(raw.has("variants")) {
            Map<?,?> parsedMap=(Map<?,?>)definition.getMethod("a").invoke(parsed);
            if(!parsedMap.keySet().equals(raw.getAsJsonObject("variants").keySet()))throw new IllegalStateException("Variant key mismatch");
            for(var e:raw.getAsJsonObject("variants").entrySet()) {
                predicates.add(variantPredicate(d,e.getKey()));
                groups.add(parsedChoices(parsedMap.get(e.getKey()),e.getValue()));
            }
        } else {
            Object multipart=definition.getMethod("d").invoke(parsed);
            List<?> parts=(List<?>)Class.forName("ggo").getMethod("a").invoke(multipart);
            if(parts.size()!=raw.getAsJsonArray("multipart").size())throw new IllegalStateException("Multipart group mismatch");
            for(int i=0;i<parts.size();i++) {
                predicates.add((Predicate<Object>)selector.getMethod("a",def).invoke(parts.get(i),d));
                groups.add(parsedChoices(selector.getMethod("a").invoke(parts.get(i)),raw.getAsJsonArray("multipart").get(i).getAsJsonObject().get("apply")));
            }
        }
        TreeMap<Integer,JsonObject> states=new TreeMap<>();
        for(Object s:(Iterable<?>)def.getMethod("a").invoke(d)) {
            JsonObject q=new JsonObject();int sid=(Integer)stateId.invoke(null,s);q.addProperty("id",sid);q.add("properties",properties(s));
            int shape=((Enum<?>)render.invoke(s)).ordinal();
            if(shape<0||shape>2)throw new IllegalStateException("Unknown original RenderShape");
            q.addProperty("renderShape",new String[]{"INVISIBLE","ENTITYBLOCK_ANIMATED","MODEL"}[shape]);
            JsonArray selected=new JsonArray();for(int i=0;i<predicates.size();i++)if(predicates.get(i).test(s))selected.add(i);
            q.add("groups",selected);if(states.put(sid,q)!=null)throw new IllegalStateException("Duplicate state ID");
        }
        JsonObject out=new JsonObject();out.addProperty("id",id);out.addProperty("registryId",(Integer)Class.forName("jz").getMethod("a",Object.class).invoke(blocks,b));
        out.add("choices",groups);JsonArray list=new JsonArray();states.values().forEach(list::add);out.add("states",list);return out;
    }
    @SuppressWarnings("unchecked") static JsonObject fixture(JsonObject input) throws Exception {
        JsonObject out=new JsonObject();out.addProperty("name",input.get("name").getAsString());
        try {
            Object d=stateDefinition(byName.get("minecraft:oak_log"));Predicate<Object> p;
            if(input.get("kind").getAsString().equals("variants"))p=variantPredicate(d,input.get("selector").getAsString());
            else {
                JsonObject raw=new JsonObject(),part=new JsonObject(),apply=new JsonObject();apply.addProperty("model","block/stone");
                part.add("apply",apply);if(input.has("when"))part.add("when",input.get("when"));
                JsonArray parts=new JsonArray();parts.add(part);raw.add("multipart",parts);
                Object parsed=parseDefinition(d,raw),mp=definition.getMethod("d").invoke(parsed);
                Object sel=((List<?>)Class.forName("ggo").getMethod("a").invoke(mp)).getFirst();
                p=(Predicate<Object>)selector.getMethod("a",def).invoke(sel,d);
            }
            JsonArray ids=new JsonArray();for(Object s:(Iterable<?>)def.getMethod("a").invoke(d))if(p.test(s))ids.add((Integer)stateId.invoke(null,s));
            out.addProperty("error",false);out.add("states",ids);
        }catch(InvocationTargetException e) {out.addProperty("error",true);}
        return out;
    }
    public static void main(String[] args) throws Exception {
        initialize();JsonObject input=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        JsonObject output=new JsonObject();JsonArray blocksOut=new JsonArray(),casesOut=new JsonArray();
        try(ZipFile archive=new ZipFile(args[1])) {
            for(JsonElement id:input.getAsJsonArray("blocks")) {
                String name=id.getAsString(),entry="assets/minecraft/blockstates/"+name.substring("minecraft:".length())+".json";
                JsonObject raw=JsonParser.parseString(new String(archive.getInputStream(archive.getEntry(entry)).readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
                blocksOut.add(blockResult(name,raw));
            }
        }
        for(JsonElement q:input.getAsJsonArray("cases"))casesOut.add(fixture(q.getAsJsonObject()));
        output.addProperty("registeredBlockCount",byName.size());output.add("blocks",blocksOut);output.add("cases",casesOut);
        Files.writeString(Path.of(args[2]),new GsonBuilder().create().toJson(output)+"\n",StandardOpenOption.CREATE_NEW);
    }
}
'''

CONTRACT_CASES = [
    {"name": "blank_variant", "kind": "variants", "selector": ""},
    {"name": "empty_variant_tokens", "kind": "variants", "selector": ",,"},
    {"name": "variant_literal", "kind": "variants", "selector": "axis=x"},
    {"name": "variant_last_duplicate", "kind": "variants", "selector": "axis=x,axis=y"},
    {"name": "variant_unknown", "kind": "variants", "selector": "absent=x"},
    {"name": "variant_pipe_invalid", "kind": "variants", "selector": "axis=x|y"},
    {"name": "variant_negation_invalid", "kind": "variants", "selector": "axis=!x"},
    {"name": "variant_no_equal", "kind": "variants", "selector": "axis"},
    {"name": "variant_no_trim", "kind": "variants", "selector": " axis=x"},
    {"name": "unconditional_part", "kind": "multipart"},
    {"name": "empty_when_invalid", "kind": "multipart", "when": {}},
    {"name": "empty_and_true", "kind": "multipart", "when": {"AND": []}},
    {"name": "empty_or_false", "kind": "multipart", "when": {"OR": []}},
    {"name": "part_pipe", "kind": "multipart", "when": {"axis": "x|y"}},
    {"name": "part_negated_union", "kind": "multipart", "when": {"axis": "!x|y"}},
    {"name": "part_empty_pipe_single_invalid", "kind": "multipart", "when": {"axis": "x|"}},
    {"name": "part_omit_empty_multi", "kind": "multipart", "when": {"axis": "x||y"}},
    {"name": "part_nested", "kind": "multipart", "when": {"AND": [{"OR": [{"axis": "x"}, {"axis": "z"}]}, {"axis": "!z"}]}},
    {"name": "part_unknown", "kind": "multipart", "when": {"unknown": "x"}},
    {"name": "part_no_trim", "kind": "multipart", "when": {"axis": " x"}},
    {"name": "part_invalid_empty_value", "kind": "multipart", "when": {"axis": "!"}},
]


def strict_json(data: bytes) -> dict:
    if not data or len(data) > 128 * 1024 * 1024:
        raise ValueError("State-model JSON exceeds size bound")
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Duplicate state-model JSON key")
            result[key] = value
        return result
    result = json.loads(data, object_pairs_hook=pairs,
                        parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
    if not isinstance(result, dict):
        raise ValueError("State-model JSON must be an object")
    return result


def property_values(key, value, domains):
    if key not in domains or value not in domains[key]:
        raise ValueError("Selection uses an unknown property/value")


def variant_predicate(selector, domains):
    if not isinstance(selector, str):
        raise ValueError("Variant selector must be text")
    values = {}
    for token in selector.split(","):
        key, _, value = token.partition("=")
        if not key:
            continue
        property_values(key, value, domains)
        values[key] = value  # Exact original HashMap semantics, no implicit OR.
    return lambda state: all(state[k] == v for k, v in values.items())


def multipart_predicate(when, domains, *, absent=False, depth=0):
    if absent:
        return lambda state: True
    if depth > 64 or not isinstance(when, dict) or not when:
        raise ValueError("Invalid multipart condition")
    if len(when) == 1 and ("OR" in when or "AND" in when):
        operator = next(iter(when))
        clauses = when[operator]
        if not isinstance(clauses, list):
            raise ValueError("Multipart operator needs an array")
        tests = [multipart_predicate(c, domains, depth=depth + 1) for c in clauses]
        return (lambda state: any(t(state) for t in tests)) if operator == "OR" else (lambda state: all(t(state) for t in tests))
    tests = []
    for key, expression in when.items():
        if not isinstance(expression, str) or key not in domains:
            raise ValueError("Invalid multipart property/value")
        negated = expression.startswith("!")
        value = expression[1:] if negated else expression
        tokens = [v for v in value.split("|") if v]
        if not tokens:
            raise ValueError("Empty multipart value list")
        # Original uses the entire expression when omitEmptyStrings yields one.
        values = tokens if len(tokens) > 1 else [value]
        for v in values:
            property_values(key, v, domains)
        tests.append(lambda state, k=key, vs=tuple(values), neg=negated: (state[k] in vs) != neg)
    return lambda state: all(test(state) for test in tests)


def model_choices(raw):
    values = raw if isinstance(raw, list) else [raw]
    if not values or len(values) > 65536:
        raise ValueError("Model choices must be nonempty and bounded")
    result = []
    for index, value in enumerate(values):
        if not isinstance(value, dict) or "model" not in value:
            raise ValueError("Model choice must have a model")
        row = {"choice": index, "model": models.resource_id(value["model"]),
               "x": value.get("x", 0), "y": value.get("y", 0),
               "uvlock": value.get("uvlock", False), "weight": value.get("weight", 1)}
        if (any(type(row[k]) is not int or row[k] not in (0, 90, 180, 270) for k in ("x", "y"))
                or type(row["uvlock"]) is not bool or type(row["weight"]) is not int or not 1 <= row["weight"] <= 2147483647):
            raise ValueError("Invalid model rotation, uvlock or weight")
        result.append(row)
    return result


def select_block(block, resource):
    if ("variants" in resource) == ("multipart" in resource):
        raise ValueError("Expected exactly one variants/multipart selection kind")
    domains = block["properties"]
    groups, predicates = [], []
    if "variants" in resource:
        if not isinstance(resource["variants"], dict) or not resource["variants"]:
            raise ValueError("Variants must be a nonempty object")
        for selector, raw in resource["variants"].items():
            groups.append({"group": len(groups), "selector": selector, "choices": model_choices(raw)})
            predicates.append(variant_predicate(selector, domains))
    else:
        parts = resource["multipart"]
        if not isinstance(parts, list) or not parts:
            raise ValueError("Multipart must be a nonempty list")
        for part in parts:
            if not isinstance(part, dict) or "apply" not in part:
                raise ValueError("Multipart part lacks apply")
            groups.append({"group": len(groups), "whenPresent": "when" in part,
                           "when": copy.deepcopy(part.get("when")), "choices": model_choices(part["apply"])})
            predicates.append(multipart_predicate(part.get("when"), domains, absent="when" not in part))
    states = []
    for source in sorted(block["states"], key=lambda s: s["id"]):
        values = source.get("properties", {})
        if set(values) != set(domains) or any(values[k] not in domains[k] for k in domains):
            raise ValueError("State is not legal for its block")
        selected = [i for i, test in enumerate(predicates) if test(values)]
        if "variants" in resource and len(selected) != 1:
            raise ValueError("Variant selections overlap or leave a legal state uncovered")
        states.append({**copy.deepcopy(source), "properties": dict(sorted(values.items())), "groups": selected})
    return {"id": block["id"], "registryId": block["registryId"], "defaultStateId": block["defaultStateId"],
            "properties": copy.deepcopy(domains), "blockstateResource": block["blockstateResource"],
            "blockstateResourceSha256": block["blockstateResourceSha256"],
            "selectorKind": "variants" if "variants" in resource else "multipart", "groups": groups, "states": states}


def case_results(cases, oak):
    result = []
    for case in cases:
        row = {"name": case["name"]}
        try:
            test = variant_predicate(case["selector"], oak["properties"]) if case["kind"] == "variants" else multipart_predicate(case.get("when"), oak["properties"], absent="when" not in case)
            row.update(error=False, states=[s["id"] for s in oak["states"] if test(s.get("properties", {}))])
        except ValueError:
            row["error"] = True
        result.append(row)
    return result


def verify_oracle(rows, oracle, cases):
    if oracle.get("registeredBlockCount") != 1060 or len(oracle.get("blocks", [])) != len(rows):
        raise ValueError("Original Java registry coverage differs")
    by_id = {b["id"]: b for b in oracle["blocks"]}
    if len(by_id) != len(rows) or set(by_id) != {r["id"] for r in rows}:
        raise ValueError("Original Java block identities differ")
    for row in rows:
        original = by_id[row["id"]]
        if original["registryId"] != row["registryId"] or original["choices"] != [g["choices"] for g in row["groups"]]:
            raise ValueError("Original Java variant metadata differs")
        states = original["states"]
        if len(states) != len(row["states"]):
            raise ValueError("Original Java state coverage differs")
        for output, java in zip(row["states"], states):
            if any(output[k] != java[k] for k in ("id", "properties", "groups")):
                raise ValueError("Original Java state predicate matrix differs")
            if java["renderShape"] not in ("INVISIBLE", "ENTITYBLOCK_ANIMATED", "MODEL"):
                raise ValueError("Unknown original render shape")
            output["renderShape"] = java["renderShape"]
    if oracle.get("cases") != cases:
        raise ValueError("Original Java edge selection semantics differ")


def check_links(path):
    current = Path(os.path.abspath(path))
    while current != current.parent:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("State-model paths cannot contain symlinks or junctions")
        current = current.parent


def preflight(output, inputs=()):
    output = assets.output_directory(output)
    for path in inputs:
        check_links(path)
        path = path.resolve()
        # Exclude full input trees, not just direct file aliases.
        directory = path if path.is_dir() else path.parent
        if output == directory or output.is_relative_to(directory) or directory.is_relative_to(output):
            raise ValueError("State-model output overlaps an input directory")
    if output.exists():
        raise ValueError("State-model output already exists; no assets are overwritten")
    return output


def fixed_read(path, digest, snapshots):
    check_links(path)
    data = assets.checked_bytes(path, digest, "sha256")
    snapshots[path.resolve()] = assets.digest(data)
    return data


def verify_snapshots(snapshots):
    for path, digest in snapshots.items():
        check_links(path)
        if assets.digest(path.read_bytes()) != digest:
            raise ValueError("State-model input changed during export")


def run_java(stage, client, jars, java_home, block_ids, cases):
    java, javac = assets.java_tools(java_home)
    java, javac = java.resolve(), javac.resolve()
    helper = stage / "BlockStateModelDump.java"
    helper.write_text(JAVA_READER, encoding="utf-8")
    classes = stage / "classes"
    classes.mkdir()
    classpath = os.pathsep.join(str(p) for p in (client, *jars))
    commands = [([str(javac), "--release", "21", "-cp", classpath, "-d", str(classes), str(helper)], 60)]
    request = stage / "request.json"
    request.write_bytes(models.json_bytes({"blocks": block_ids, "cases": cases}))
    result_path = stage / "oracle.json"
    commands.append(([str(java), "-Djava.awt.headless=true", "-cp", os.pathsep.join((str(classes), classpath)),
                      "local.crimsonmc.assets.BlockStateModelDump", str(request), str(client), str(result_path)], 180))
    for command, timeout in commands:
        result = subprocess.run(command, cwd=stage, capture_output=True, text=True, timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise ValueError("Original Java selection reader failed: " + (result.stdout + result.stderr)[-5000:])
    return result_path.read_bytes()


def build(output=DEFAULT_OUTPUT, client=None, java_home=None, download=False):
    snapshots = {}
    output = preflight(output, (REGISTRY_DIR, COVERAGE, assets.CONFIG, MAPPINGS))
    fixed_read(assets.CONFIG, CONFIG_SHA256, snapshots)
    config = assets.read_config()
    client, jars = assets.dependencies(config, client, download)
    client, jars = client.resolve(), [j.resolve() for j in jars]
    inputs = (REGISTRY_DIR, COVERAGE, assets.CONFIG, client, *jars, MAPPINGS)
    output = preflight(output, inputs)
    fixed_read(client, CLIENT_SHA256, snapshots)
    check_links(MAPPINGS)
    assets.obtain(MAPPINGS, MAPPINGS_SOURCE, [], download)
    mappings_raw = fixed_read(MAPPINGS, MAPPINGS_SHA256, snapshots)
    if len(mappings_raw) != MAPPINGS_SOURCE["size"] or assets.digest(mappings_raw, "sha1") != MAPPINGS_SOURCE["sha1"]:
        raise ValueError("Official client mappings fingerprint mismatch")
    for named, obfuscated in MAPPING_HEADERS.items():
        if (named + " -> " + obfuscated + ":\n").encode() not in mappings_raw:
            raise ValueError("Official selection class mapping differs")
    source_raw = fixed_read(REGISTRY_DIR / "block-registry.json", REGISTRY_SHA256, snapshots)
    source = strict_json(source_raw)
    if source["clientSha256"] != CLIENT_SHA256:
        raise ValueError("Registry client differs from model client")
    reports = {name: fixed_read(REGISTRY_DIR / "reports" / name, digest, snapshots) for name, digest in source["sourceReports"].items()}
    if assets.digest(reports["blocks.json"]) != registry.BLOCKS_SHA256:
        raise ValueError("Registry raw blocks differ")
    coverage_raw = fixed_read(COVERAGE, COVERAGE_SHA256, snapshots)
    coverage = strict_json(coverage_raw)
    for jar in jars:
        check_links(jar)
        digest = assets.digest(jar.read_bytes())
        if source["libraries"].get(jar.name) != digest:
            raise ValueError("Original Java library differs from fixed registry provenance")
        snapshots[jar] = digest
    rows, dependency_map = [], {}
    with zipfile.ZipFile(client) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError("Duplicate official client archive entry")
        class_hashes = {name: assets.digest(archive.read(name)) for name in ENGINE_CLASSES}
        if class_hashes != ENGINE_CLASSES:
            raise ValueError("Original selection class fingerprints differ")
        audited = registry.audit_registry(strict_json(reports["blocks.json"]), strict_json(reports["registries.json"]), archive)
        if audited["blocks"] != source["blocks"] or audited["registeredBlockCount"] != 1060 or audited["legalStateCount"] != 26684:
            raise ValueError("Actual vanilla registry coverage differs")
        resources = models.Resources(archive)
        coverage_by_id = {b["id"]: b for b in coverage["entries"]}
        for block in audited["blocks"]:
            resource = strict_json(archive.read(block["blockstateResource"]))
            row = select_block(block, resource)
            reference = coverage_by_id[block["id"]]
            flattened = [{**choice, "selector": group.get("selector", "part:" + str(group["group"])), "when": group.get("when")}
                         for group in row["groups"] for choice in group["choices"]]
            expected = [{key: c[key] for key in ("choice", "model", "x", "y", "uvlock", "weight", "selector", "when")} for c in reference["choices"]]
            if reference["sha256"] != row["blockstateResourceSha256"] or flattened != expected:
                raise ValueError("Pinned resource coverage does not match selection choices")
            rows.append(row)
            for group in row["groups"]:
                for choice in group["choices"]:
                    name = choice["model"]
                    if name not in dependency_map:
                        dependency = resources.dependencies(name)
                        if dependency["missing"]:
                            raise ValueError("Selected model has missing dependency")
                        dependency_map[name] = {**dependency, "geometryKind": "builtin" if dependency["builtins"] else "empty" if dependency["elementCount"] == 0 else "json_elements",
                                                "nativeIntegrated": False}
    oak = next(r for r in source["blocks"] if r["id"] == "minecraft:oak_log")
    expected_cases = case_results(CONTRACT_CASES, oak)
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="block-state-oracle-", dir=ROOT / "build") as temporary:
        oracle_raw = run_java(assets.output_directory(Path(temporary)), client, jars, java_home,
                              [row["id"] for row in rows], CONTRACT_CASES)
    oracle = strict_json(oracle_raw)
    verify_oracle(rows, oracle, expected_cases)
    shapes = collections.Counter(s["renderShape"] for r in rows for s in r["states"])
    selection = {"schemaVersion": 1, "minecraftVersion": "1.21.1", "scope": "all legal vanilla states; complete applicable groups and weighted choices",
                 "registeredBlockCount": len(rows), "legalStateCount": sum(len(r["states"]) for r in rows),
                 "groupCount": sum(len(r["groups"]) for r in rows),
                 "modelChoiceCount": sum(len(g["choices"]) for r in rows for g in r["groups"]),
                 "uniqueModelCount": len(dependency_map), "renderShapeStateCounts": dict(sorted(shapes.items())),
                 "blocks": rows, "integration": {"nativeModelsMapped": False, "nativeRenderingVerified": False,
                    "nativeCollisionVerified": False, "specialRenderersImplemented": False, "allItemUsesImplemented": False},
                 "limitations": ["Weighted alternatives remain a per-group list; no random model is selected.",
                    "Multipart groups combine simultaneously, with independent alternatives inside each group.",
                    "RenderShape comes from original states; builtins, empty models, invisible and entity-rendered blocks are not replaced by cubes.",
                    "Selection and dependency coverage do not implement tint, fluids, block entities, animation, rendering or collision.",
                    "Vanilla offline registry only, not the running Fabric authority registry; no world or service was accessed."]}
    files = {"block-state-models.json": models.json_bytes(selection),
             "model-dependencies.json": models.json_bytes({"schemaVersion": 1, "models": dict(sorted(dependency_map.items()))}),
             "selection-oracle.json": oracle_raw,
             "contract-cases.json": models.json_bytes({"cases": CONTRACT_CASES, "results": expected_cases})}
    report = {"schemaVersion": 1, "minecraftVersion": "1.21.1", "sourcePins": {
        "clientSha256": CLIENT_SHA256, "configSha256": CONFIG_SHA256, "registryReportSha256": REGISTRY_SHA256,
        "resourceCoverageSha256": COVERAGE_SHA256, "sourceReports": source["sourceReports"], "libraries": source["libraries"],
        "versionMetadata": config["versionMetadata"], "officialMappings": {**MAPPINGS_SOURCE, "sha256": MAPPINGS_SHA256},
        "selectionClasses": class_hashes, "officialClassMappings": MAPPING_HEADERS, "javaReaderSourceSha256": assets.digest(JAVA_READER.encode())},
        "oracle": {"implementation": "Original BlockModelDefinition/Variant parsers and BlockStateModelLoader/Selector predicates",
                   "allStatesCompared": 26684, "mismatchedStates": 0, "parsedChoicesCompared": selection["modelChoiceCount"],
                   "contractCasesCompared": len(CONTRACT_CASES), "originalRenderShapesRead": True, "worldStarted": False},
        "summary": {k: selection[k] for k in ("registeredBlockCount", "legalStateCount", "groupCount", "modelChoiceCount", "uniqueModelCount", "renderShapeStateCounts")},
        "files": {name: assets.digest(data) for name, data in files.items()}, "integration": selection["integration"],
        "limitations": selection["limitations"]}
    files["block-state-models-report.json"] = models.json_bytes(report)
    verify_snapshots(snapshots)
    output = preflight(output, inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    check_links(output)
    output.mkdir()
    for name, data in files.items():
        target = assets.output_directory(output / name)
        with target.open("xb") as stream:
            stream.write(data)
    verify_snapshots(snapshots)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--client", type=Path)
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--download", action="store_true", help="Fetch missing hash-pinned official dependencies")
    args = parser.parse_args()
    try:
        report = build(args.output, args.client, args.java_home, args.download)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"Block state model export stopped: {error}") from error
    print(json.dumps({"output": str(args.output), **report["summary"], "oracle": report["oracle"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
