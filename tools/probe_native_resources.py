"""Read a fixed native resource slice and compare local, hash-checked assets.

Only the loopback resource-probe API and MC GET state are used. No installation,
spawn, inventory write, arbitrary path request or visual acceptance is provided.
Evidence stays in ignored runtime; licensed payload bytes are never in reports.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler
import uuid

import prepare_native_block as block
import prepare_native_steve as native
from probe_native_block import game_instance, NoRedirect, VERSION

ROOT = native.ROOT
NATIVE_BASE = "http://127.0.0.1:8765"
MC_BASE = "http://127.0.0.1:8766"
PROJECT = "CrimsonMCNativeResourceProbe"
MAX_RESPONSE = 2 * 1024 * 1024
MAX_BYTES = 16384
INDEX_SHA = "63a9286ed8712e72bd5d022a96e808bc4a10a2ed29b16bd942ce869e1a82d939"
HASH_ALGORITHM = "fnv1a64-noncryptographic"
PROBE_VARIANTS = ("static-oak-log", "blue-template-alias", "blue-material-alias", "oak-pami-no-declaration")
NO_DECLARATION_PAMI_SHA256 = "13594ac365e4dcb4f52f652c4a892c845bf9524b700d1fe521a88cf9e22fa07d"
KINDS = {"prefab": "prefab", "meshinfo": "meshInfo", "pam": "staticMesh",
         "pamlod": "staticMeshLod", "pami": "material", "hkx": "collision"}


def resource_paths() -> dict[str, str]:
    result = {}
    for group in ("blue", "oak_x", "oak_y", "oak_z"):
        stem = "cd_testfield_grid_box_1m" if group == "blue" else "crimsonmc_oak_log_" + group[-1]
        for suffix in KINDS:
            folder = "object/bin__/00_common/system" if suffix in ("prefab", "meshinfo") else "object/00_common/system"
            result[group + "_" + suffix] = folder + "/" + stem + "." + suffix
    for suffix in ("", "_n", "_sp"):
        result["oak_atlas" + suffix] = block.TEXTURE_TARGET + suffix + ".dds"
    return result


RESOURCES = resource_paths()
BLUE = tuple(name for name in RESOURCES if name.startswith("blue_"))
ATLAS = ("oak_atlas", "oak_atlas_n", "oak_atlas_sp")
GROUPS = {"default": BLUE + tuple("oak_y_" + suffix for suffix in KINDS) + ATLAS,
          "blue": BLUE, "oak": tuple("oak_y_" + suffix for suffix in KINDS) + ATLAS,
          "all": tuple(RESOURCES)}
TERMINAL = {"read", "notFound", "emptyBuffer", "readFailed", "tooLarge", "unavailable", "expired"}


class ProbeError(RuntimeError):
    pass


class RequestFailure(ProbeError):
    """A POST may already be accepted; never automatically submit it again."""


def strict_json(data: bytes) -> dict:
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError, UnicodeError) as error:
        raise ProbeError("Expected strict UTF-8 JSON without duplicate keys or nonfinite numbers") from error
    if not isinstance(result, dict):
        raise ProbeError("Expected a JSON object")
    return result


def bounded_number(value, name, low, high) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise ProbeError(f"Invalid bounded {name}")
    return float(value)


def integer(value, name, low=0, high=2147483646) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ProbeError(f"Invalid integer {name}")
    return value


def fnv1a64(data: bytes) -> str:
    value = 0xcbf29ce484222325
    for byte in data:
        value = ((value ^ byte) * 0x100000001b3) & 0xffffffffffffffff
    return f"{value:016x}"


def summary(data: bytes) -> dict:
    return {"length": len(data), "head16hex": data[:16].hex(), "fnv1a64": fnv1a64(data)}


def build_path(path: Path) -> Path:
    lexical = Path(os.path.abspath(path))
    if not lexical.is_relative_to(ROOT / "build") or lexical == ROOT / "build":
        raise ProbeError("Resource inputs must stay in ignored build")
    native.check_links(lexical)
    return lexical


def read_file(path: Path, maximum: int) -> bytes:
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise ProbeError("Resource input is missing, empty or exceeds its bounded size: " + str(path))
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if not 0 < len(data) <= maximum:
        raise ProbeError("Resource input changed size while reading")
    return data


def load_assets(report_path: Path) -> dict:
    """Prove exact paths/template pins and every reported local file before HTTP."""
    report_path = build_path(report_path)
    if report_path.name != "native-block-report.json":
        raise ProbeError("Expected a native-block-report.json input")
    raw = read_file(report_path, MAX_RESPONSE)
    report = strict_json(raw)
    variant = report.get("probeVariant", "static-oak-log")
    if variant not in PROBE_VARIANTS:
        raise ProbeError("Unknown native asset probe variant")
    if variant == "static-oak-log" and "control" in report:
        raise ProbeError("A control report cannot claim the ordinary oak variant")
    if (type(report.get("schemaVersion")) is not int or report["schemaVersion"] != 1
            or report.get("supportedExeSha256") != native.EXE_SHA256
            or report.get("archiveIndex") != "0000/0.pamt" or report.get("archiveIndexSha256") != INDEX_SHA):
        raise ProbeError("Native block report version, EXE or source index pin differs")
    cdmw = report.get("cdmw", {})
    if (not isinstance(cdmw, dict) or cdmw.get("commit") != native.CDMW_COMMIT
            or cdmw.get("pythonSourceTreeSha256") != native.CDMW_SOURCE_SHA256):
        raise ProbeError("Native block report CDMW source pin differs")
    if report.get("integration") != {"nativeRenderable": False, "installed": False, "collisionVerified": False,
                                     "bridgeMapped": False, "minecraftSamplerVerified": False, "nativeLightingVerified": False}:
        raise ProbeError("Offline block report has unexpected integration claims")
    candidates = report.get("candidateResources")
    if not isinstance(candidates, list) or len(candidates) != 21:
        raise ProbeError("Expected exactly 21 oak candidate resources")
    expected = {}
    for name, path in RESOURCES.items():
        if name in BLUE:
            continue
        if name in ATLAS:
            suffix = name.removeprefix("oak_atlas")
            template, kind = block.TEX + suffix + ".dds", "texture"
        else:
            suffix = name.rsplit("_", 1)[-1]
            template, kind = RESOURCES["blue_" + suffix], KINDS[suffix]
        expected[path] = {"localFile": "candidate/" + path, "kind": kind,
                          "templatePath": template, "templateSha256": block.TEMPLATE_HASHES[template]}
    rows = {}
    for row in candidates:
        if not isinstance(row, dict) or set(row) != {"virtualPath", "localFile", "sha256", "kind", "templatePath", "templateSha256"}:
            raise ProbeError("Candidate resource fields differ from the reviewed schema")
        path = row["virtualPath"]
        if not isinstance(path, str) or path not in expected or path in rows:
            raise ProbeError("Candidate resource path is unrecognized or duplicated")
        if any(row[key] != value for key, value in expected[path].items()):
            raise ProbeError("Candidate local path, kind or template provenance differs")
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ProbeError("Candidate SHA256 is invalid")
        rows[path] = row
    if set(rows) != set(expected):
        raise ProbeError("Candidate resources are incomplete")
    files = report.get("files")
    expected_files = {"template/" + path: digest for path, digest in block.TEMPLATE_HASHES.items()}
    expected_files.update({row["localFile"]: row["sha256"] for row in rows.values()})
    if not isinstance(files, dict) or files != expected_files:
        raise ProbeError("Native block file map is incomplete or polluted")
    payloads = {}
    for path, digest in expected_files.items():
        local = build_path(report_path.parent / path)
        data = read_file(local, 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ProbeError("Local resource SHA256 differs: " + path)
        payloads[path] = data
    resources = {}
    for name, path in RESOURCES.items():
        local = "template/" + path if name in BLUE else rows[path]["localFile"]
        data = payloads[local]
        if len(data) > MAX_BYTES:
            raise ProbeError("A whitelisted diagnostic asset exceeds the native 16KiB bound")
        resources[name] = {"resource": name, "path": path, "localFile": local,
                           "sha256": expected_files[local], **summary(data)}
    if variant != "static-oak-log":
        from prepare_native_block_control import validate_control
        validate_control(report_path, report)
    elif any(resources["oak_y_" + suffix]["sha256"] == resources["blue_" + suffix]["sha256"]
             for suffix in ("prefab", "pami")):
        raise ProbeError("An original blue prefab/material alias must be explicitly labelled as a control")
    elif resources["oak_y_pami"]["sha256"] == NO_DECLARATION_PAMI_SHA256:
        raise ProbeError("A PAMI declaration control must be explicitly labelled as a control")
    return {"reportPath": str(report_path), "reportSha256": hashlib.sha256(raw).hexdigest(),
            "probeVariant": variant, "resources": resources}


class LoopbackAPI:
    def __init__(self, role: str = "native", timeout: float = 4):
        if role not in ("native", "mc"):
            raise ProbeError("Invalid fixed API role")
        self.role = role
        self.base = NATIVE_BASE if role == "native" else MC_BASE
        self.timeout = bounded_number(timeout, "request timeout", 0.05, 4)
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
        allowed = self.role == "mc" and (method, path, body) == ("GET", "/api/state", None)
        if self.role == "native":
            allowed = (method, path, body) == ("GET", "/api/status", None)
            if method == "POST" and path == "/api/prototype/resource-probe":
                allowed = isinstance(body, dict) and set(body) == {"resource"} and isinstance(body["resource"], str) and body["resource"] in RESOURCES
            if method == "GET" and re.fullmatch(r"/api/prototype/resource-result\?ticket=[1-9][0-9]{0,9}", path) and body is None:
                allowed = int(path.split("=")[1]) <= 2147483646
        if not allowed:
            raise ProbeError("Request is outside the fixed resource diagnostic allowlist")
        data = None if body is None else json.dumps(body, allow_nan=False).encode("utf-8")
        request = Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            try:
                response = self.opener.open(request, timeout=self.timeout)
            except HTTPError as error:
                response = error
            with response:
                payload = response.read(MAX_RESPONSE + 1)
                if len(payload) > MAX_RESPONSE:
                    raise RequestFailure("API response exceeds the bounded size; do not resubmit")
                try:
                    return response.code, strict_json(payload)
                except ProbeError as error:
                    raise RequestFailure("Invalid API response; do not resubmit") from error
        except (OSError, URLError, TimeoutError, HTTPException) as error:
            raise RequestFailure(f"No complete response for {method} {path}; do not resubmit") from error


def report_location(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    if not path.is_relative_to(ROOT / "runtime") or path == ROOT / "runtime" or path.suffix != ".json":
        raise ProbeError("Resource probe evidence must be JSON inside ignored runtime")
    native.check_links(path)
    if path.exists():
        raise ProbeError("Evidence already exists; choose a new output to preserve previous tickets")
    return path


class Evidence:
    """Exclusive evidence reservation, then owned atomic updates before POST."""
    def __init__(self, path: Path):
        self.path = report_location(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        native.check_links(self.path)
        self.last = None

    def write(self, report: dict) -> None:
        native.check_links(self.path)
        data = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(data) > MAX_RESPONSE:
            raise ProbeError("Evidence exceeds its bounded size")
        if self.last is None:
            with self.path.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        else:
            if not self.path.is_file() or self.path.read_bytes() != self.last:
                raise ProbeError("Evidence ownership changed during the diagnostic")
            temporary = self.path.with_name(self.path.name + "." + uuid.uuid4().hex + ".tmp")
            native.check_links(temporary)
            owned = False
            try:
                with temporary.open("xb") as stream:
                    owned = True
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                native.check_links(self.path)
                if self.path.read_bytes() != self.last:
                    raise ProbeError("Evidence ownership changed before atomic update")
                os.replace(temporary, self.path)
            finally:
                if owned and temporary.exists():
                    temporary.unlink()
        self.last = data


class ResourceProbe:
    def __init__(self, api: LoopbackAPI, mc: LoopbackAPI, evidence: Evidence, *, identity=game_instance,
                 timeout: float = 12, interval: float = 0.1):
        if api.role != "native" or mc.role != "mc":
            raise ProbeError("Incompatible API roles")
        self.api, self.mc, self.evidence, self.identity = api, mc, evidence, identity
        self.timeout = bounded_number(timeout, "poll timeout", 0.05, 25)
        self.interval = bounded_number(interval, "poll interval", 0.005, 0.5)

    def instance(self) -> dict:
        value = self.identity()
        if (not isinstance(value, dict) or type(value.get("pid")) is not int or not 0 < value["pid"] <= 0xffffffff
                or not isinstance(value.get("creationTime100ns"), str) or not re.fullmatch(r"[0-9]{1,20}", value["creationTime100ns"])
                or not isinstance(value.get("imagePath"), str) or not value["imagePath"]
                or value.get("imageSha256") != native.EXE_SHA256 or value.get("access") != "PROCESS_QUERY_LIMITED_INFORMATION"):
            raise ProbeError("Game process identity does not match the fixed EXE")
        return value

    def ready(self, report: dict, key: str) -> dict:
        code, value = self.api.request("/api/status")
        # Keep the actual failed readiness response too: an unloaded scene,
        # unsupported build and HTTP failure require different next actions.
        report[key] = value
        report[key + "HttpStatus"] = code
        if (code != 200 or type(value.get("apiVersion")) is not int or value["apiVersion"] != 1
                or value.get("gameVersion") != VERSION or value.get("ready") is not True or value.get("buildOk") is not True):
            raise ProbeError("Expected ready/buildOk API 1 on Crimson Desert " + VERSION)
        integer(value.get("pending"), "native pending count", 0, 5000)
        return value

    def mc_snapshot(self) -> dict:
        code, value = self.mc.request("/api/state")
        if code != 200:
            raise ProbeError("MC read-only state is unavailable")
        integer(value.get("revision"), "MC revision", 0, 2**63 - 1)
        if not isinstance(value.get("inventory"), dict) or not isinstance(value.get("blocks"), list):
            raise ProbeError("MC read-only state is missing inventory/blocks")
        data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return {"state": value, "sha256": hashlib.sha256(data).hexdigest()}

    def validate_result(self, code: int, value: dict, ticket: int, expected: dict) -> str:
        if value.get("ticket") != ticket or type(value.get("ticket")) is not int or value.get("resource") != expected["resource"]:
            raise ProbeError("Ticket result does not match its requested resource")
        state = value.get("state")
        if state == "pending":
            if code != 202:
                raise ProbeError("Pending resource result has invalid HTTP status")
            return state
        if code != 200 or state not in TERMINAL or value.get("path") != expected["path"]:
            raise ProbeError("Resource result state, HTTP status or physical path differs")
        integer(value.get("attempts"), "native read attempts", 0 if state == "expired" else 1, 3)
        length = integer(value.get("length"), "resource length", 0, 0xffffffff)
        integer(value.get("storedSize"), "stored size", 0, 0xffffffff)
        integer(value.get("decodedSize"), "decoded size", 0, 0xffffffff)
        integer(value.get("storageFlags"), "storage flags", 0, 0xffffffff)
        if type(value.get("handlerPresent")) is not bool or type(value.get("handlerReleased")) is not bool or value.get("maxBytes") != MAX_BYTES or type(value.get("maxBytes")) is not int or value.get("hashAlgorithm") != HASH_ALGORITHM:
            raise ProbeError("Resource handler or hash metadata differs")
        head, digest = value.get("head16hex"), value.get("fnv1a64")
        if not isinstance(head, str) or not re.fullmatch(r"(?:[0-9a-f]{2}){0,16}", head) or not isinstance(digest, str) or not re.fullmatch(r"(?:[0-9a-f]{16})?", digest):
            raise ProbeError("Resource digest encoding is invalid")
        native_length = value["storedSize"] if value["storageFlags"] & 15 == 1 else value["decodedSize"]
        if state == "read" and (not 0 < length <= MAX_BYTES or length != native_length
                                or value["storedSize"] > MAX_BYTES or value["decodedSize"] > MAX_BYTES
                                or len(head) != 2 * min(16, length) or not digest
                                or value["handlerPresent"] is not True or value["handlerReleased"] is not True):
            raise ProbeError("Read result lacks bounded bytes or released handler evidence")
        return state

    def run(self, assets: dict, group: str = "default") -> dict:
        if group not in GROUPS:
            raise ProbeError("Unknown fixed resource group")
        names = GROUPS[group]
        if set(assets.get("resources", {})) != set(RESOURCES):
            raise ProbeError("Input assets do not cover the exact fixed resource set")
        if assets.get("probeVariant") not in PROBE_VARIANTS:
            raise ProbeError("Input assets lack a verified probe variant")
        report = {"schemaVersion": 1, "project": PROJECT, "runId": uuid.uuid4().hex,
                  "probeVariant": assets["probeVariant"],
                  "startedUtc": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": "preflight", "group": group,
                  "nativeBase": self.api.base, "mcBase": self.mc.base, "sourceReport": assets["reportPath"],
                  "sourceReportSha256": assets["reportSha256"], "requestedResources": list(names), "results": [],
                  "allReadAndMatched": False, "gameInstanceUnchanged": False, "mcStateUnchanged": False,
                  "success": False, "visualAcceptance": False, "collisionAcceptance": False,
                  "limitations": ["FNV1a64 is noncryptographic; SHA256 checks only local asset provenance.",
                                  "A resource read does not prove visible geometry, texture, animation or collision.",
                                  "No install, spawn, inventory write or visual verification was performed."]}
        self.evidence.write(report)
        try:
            report["gameBefore"] = self.instance()
            self.ready(report, "statusBefore")
            report["mcBefore"] = self.mc_snapshot()
            if self.instance() != report["gameBefore"]:
                raise ProbeError("Game instance changed during preflight")
            report["phase"] = "reading"
            self.evidence.write(report)
            tickets = set()
            for name in names:
                if self.instance() != report["gameBefore"]:
                    raise ProbeError("Game instance changed; no further resource submissions")
                expected = assets["resources"][name]
                row = {"expected": expected, "state": "submissionUnknown", "matched": False, "postAttempts": 1}
                report["results"].append(row)
                self.evidence.write(report)  # Durable intent before any enqueue.
                code, accepted = self.api.request("/api/prototype/resource-probe", "POST", {"resource": name})
                row["accepted"] = accepted
                if code != 202 or set(accepted) != {"ticket", "resource", "state"} or accepted.get("resource") != name or accepted.get("state") != "pending":
                    raise ProbeError("Resource POST was not a matching 202 ticket; do not resubmit")
                ticket = integer(accepted.get("ticket"), "resource ticket", 1)
                if ticket in tickets:
                    raise ProbeError("Resource POST reused a ticket; do not resubmit")
                tickets.add(ticket)
                row.update(ticket=ticket, state="pending", polls=0)
                self.evidence.write(report)
                deadline = time.monotonic() + self.timeout
                while True:
                    if self.instance() != report["gameBefore"]:
                        raise ProbeError("Game instance changed while polling; do not resubmit")
                    code, result = self.api.request(f"/api/prototype/resource-result?ticket={ticket}")
                    row["polls"] += 1
                    row["nativeResult"] = result
                    state = self.validate_result(code, result, ticket, expected)
                    if state != "pending":
                        row["state"] = state
                        row["matched"] = state == "read" and all(result[key] == expected[key] for key in ("length", "head16hex", "fnv1a64"))
                        break
                    if time.monotonic() >= deadline:
                        row["state"] = "timeout"
                        row["error"] = "Ticket remained pending; original request was not resubmitted"
                        break
                    time.sleep(min(self.interval, max(0, deadline - time.monotonic())))
                self.evidence.write(report)
                if row["state"] == "timeout":
                    raise ProbeError("Pending ticket timed out; no further submissions")
        except Exception as error:
            report["error"] = str(error)
        finally:
            try:
                report["gameAfter"] = self.instance()
                report["gameInstanceUnchanged"] = report.get("gameBefore") == report["gameAfter"]
                self.ready(report, "statusAfter")
            except Exception as error:
                report["gameAfterError"] = str(error)
            try:
                report["mcAfter"] = self.mc_snapshot()
                report["mcStateUnchanged"] = report.get("mcBefore", {}).get("sha256") == report["mcAfter"]["sha256"]
            except Exception as error:
                report["mcAfterError"] = str(error)
            report["allReadAndMatched"] = len(report["results"]) == len(names) and all(row["matched"] for row in report["results"])
            report["success"] = (report["allReadAndMatched"] and report["gameInstanceUnchanged"] and report["mcStateUnchanged"]
                                 and "error" not in report and "gameAfterError" not in report and "mcAfterError" not in report)
            report["phase"] = "complete" if report["success"] else "failed"
            report["finishedUtc"] = dt.datetime.now(dt.timezone.utc).isoformat()
            self.evidence.write(report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=ROOT / "build/native-block/native-block-report.json")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/native-resource-probe.json")
    parser.add_argument("--group", choices=("blue", "oak", "all"), default="default",
                        help="blue=6 original templates; oak=Y-axis six plus atlas three; all=27; default=blue+oak")
    parser.add_argument("--timeout", type=float, default=12, help="Per-ticket polling timeout, 0.05..25 seconds")
    args = parser.parse_args()
    try:
        assets = load_assets(args.assets)
        evidence = Evidence(args.output)
        probe = ResourceProbe(LoopbackAPI(), LoopbackAPI("mc"), evidence, timeout=args.timeout)
        result = probe.run(assets, args.group)
        print(json.dumps({"success": result["success"], "allReadAndMatched": result["allReadAndMatched"],
                          "probeVariant": result["probeVariant"],
                          "resources": len(result["results"]), "report": str(evidence.path), "visualAcceptance": False}))
        return 0 if result["success"] else 1
    except (ProbeError, ValueError, OSError) as error:
        print("Resource diagnostic stopped: " + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
