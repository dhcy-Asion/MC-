"""Read only the fixed Steve head material through the native file resolver.

Requires the canonical nine-report plan and its currently installed receipt.
This diagnoses resolvable bytes, never renderer selection or texture sampling.
No install, appearance apply, inventory mutation or arbitrary resource is exposed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request
import uuid

import install_steve_probe as installer
import prepare_steve_head_basecolor_overlay as composition
import probe_native_resources as base

ROOT = base.ROOT
RESOURCE = "steve_head_pami"
VIRTUAL_PATH = "character/modelproperty/1_pc/1_phm/head/head/crimsonmc_steve_head_1_21_1.pac_xml"
PLAN_SHA256 = "29b813224b362f8d2e751a8ae31968846a55d96410f290ffd10deb00322078e5"
PAYLOAD_SHA256 = "cc86b387583430d7e2d8ef136db965dd39d3e5754501626b7c82fa606b2abf3f"
PAYLOAD_SIZE = 16134
VARIANT = composition.VARIANT
PROJECT = "CrimsonMCSteveHeadMaterialReadProbe"
ProbeError = base.ProbeError
UNTOUCHED_FILES = {
    "meta/0.papk": "e107572c2496c8f4119c5cfdadb1de151feefb7a3e30eb7b6e20c5c776d1350d",
    "meta/0.paver": "b98b041ca1d8efab73e60fa61228a516f17db1213107533161ed2569431b8543",
}


def fixed_read(path: Path, maximum: int) -> bytes:
    return base.read_file(path, maximum)


def load_assets(plan: Path = composition.DEFAULT_OUTPUT) -> dict:
    """Full production admission of the exact local plan, before any HTTP."""
    plan = base.build_path(plan)
    report_path = installer.transaction.target(plan, composition.REPORT_NAME)
    raw = fixed_read(report_path, base.MAX_RESPONSE)
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ProbeError("Expected the canonical nine-report Steve head base-color plan")
    report = base.strict_json(raw)
    names = composition.admitted_report_paths(report.get("candidateReports"), composition.COMPOSITION_REPORT_NAMES)
    rows = report.get("resources")
    if (not isinstance(rows, list) or len(rows) != 14
            or len({row.get("virtualPath") for row in rows if isinstance(row, dict)}) != 14):
        raise ProbeError("Expected fourteen unique canonical resources")
    targets = [row for row in rows if row.get("virtualPath") == VIRTUAL_PATH]
    if (len(targets) != 1 or targets[0].get("sha256") != PAYLOAD_SHA256
            or targets[0].get("kind") != "skinnedMaterial" or targets[0].get("archiveFlags") != 50):
        raise ProbeError("The canonical unique head PAMI row differs")
    composition.fixed_cdmw(ROOT / "build/cdmw-fixed-source", ROOT / "build/cdmw-deps")
    admitted = installer.load_plan(plan)
    payload = admitted["payloads"][VIRTUAL_PATH]
    if (admitted["reportSha256"] != PLAN_SHA256 or admitted["probeVariant"] != VARIANT
            or admitted["name"] != "0041" or len(payload) != PAYLOAD_SIZE
            or hashlib.sha256(payload).hexdigest() != PAYLOAD_SHA256):
        raise ProbeError("Admitted head plan identity or exact material bytes differ")
    paths = {report_path: PLAN_SHA256}
    paths.update({installer.build_path(path): digest for path, digest in report["candidateReports"].items()})
    paths.update({installer.transaction.target(plan, path): digest for path, digest in report["files"].items()})
    paths.update({installer.build_path(row["localFile"]): row["sha256"] for row in rows})
    assets = {"plan": plan, "report": report, "sourceHashes": paths,
              "resource": {"resource": RESOURCE, "path": VIRTUAL_PATH,
                           "sha256": PAYLOAD_SHA256, **base.summary(payload)}}
    verify_assets(assets)
    return assets


def verify_assets(assets: dict) -> None:
    for path, digest in assets["sourceHashes"].items():
        base.native.check_links(path)
        if not path.is_file() or base.native.file_hash(path) != digest:
            raise ProbeError("Admitted local plan or payload changed during the diagnostic")


def read_receipt(assets: dict, state_root: Path = ROOT) -> dict:
    """Read and bind current installation ownership; never restore or lock it."""
    installation_path = installer.transaction.target(state_root, "runtime/installation.json")
    receipt_path = installer.transaction.target(state_root, installer.transaction.RECEIPT)
    installation_raw = fixed_read(installation_path, base.MAX_RESPONSE)
    installation = base.strict_json(installation_raw.decode("utf-8-sig").encode("utf-8"))
    receipt_raw = fixed_read(receipt_path, base.MAX_RESPONSE)
    receipt = base.strict_json(receipt_raw)
    game = Path(installation.get("gameRoot", ""))
    base.native.check_links(game)
    if (not game.is_absolute() or not game.is_dir() or receipt.get("format") != "crimsonmc_asset_probe_v1"
            or receipt.get("owner") != installer.transaction.STEVE_OWNER or receipt.get("probeKind") != installer.KIND
            or receipt.get("status") != "installed" or receipt.get("probeVariant") != VARIANT
            or not isinstance(receipt.get("id"), str) or not re.fullmatch(r"[0-9a-f]{32}", receipt["id"])
            or Path(receipt.get("gameRoot", "")).resolve() != game.resolve()
            or Path(receipt.get("plan", "")).resolve() != assets["plan"].resolve()
            or receipt.get("planSha256") != PLAN_SHA256 or receipt.get("directoryName") != "0041"
            or receipt.get("sourceIndexes") != assets["report"]["sourceIndexes"]
            or receipt.get("untouchedGameFiles") != UNTOUCHED_FILES
            or receipt.get("absentOptionalMountedDirectories") != assets["report"]["absentOptionalMountedDirectories"]):
        raise ProbeError("Active receipt does not own this exact installed head probe")
    expected_files = {"0041/0.pamt": assets["report"]["files"]["package/0041/0.pamt"],
                      "0041/0.paz": assets["report"]["files"]["package/0041/0.paz"]}
    marker_relative = "0041/" + installer.transaction.MARKER
    marker = {"owner": installer.transaction.STEVE_OWNER, "id": receipt["id"], "planSha256": PLAN_SHA256}
    marker_path = installer.transaction.target(game, marker_relative)
    marker_raw = fixed_read(marker_path, base.MAX_RESPONSE)
    if base.strict_json(marker_raw) != marker:
        raise ProbeError("Installed overlay marker differs from the active receipt")
    expected_files[marker_relative] = hashlib.sha256(marker_raw).hexdigest()
    expected_metadata = {path: assets["report"]["files"]["metadata-after/" + Path(path).name]
                         for path in installer.transaction.METADATA}
    if receipt.get("installedFiles") != expected_files or receipt.get("metadataAfter") != expected_metadata:
        raise ProbeError("Receipt installed file or active metadata inventory differs")
    # The canonical 34 original indexes and two untouched metadata files are
    # checked on disk too; a correct receipt dictionary cannot hide an override.
    checks = {**assets["report"]["sourceIndexes"], **UNTOUCHED_FILES, **expected_files, **expected_metadata}
    for path, digest in checks.items():
        # Canonical sourceIndexes retain Windows host separators; this is a
        # filesystem identity, never an alias or user-supplied virtual path.
        file = installer.transaction.target(game, path.replace("\\", "/"))
        if not file.is_file() or base.native.file_hash(file) != digest:
            raise ProbeError("Active installed file bytes differ: " + path)
    if (game / ".cdmw").exists():
        raise ProbeError("An external resource override is active")
    return {"id": receipt["id"], "kind": installer.KIND, "variant": VARIANT,
            "planSha256": PLAN_SHA256, "gameRoot": str(game.resolve()),
            "receiptSha256": hashlib.sha256(receipt_raw).hexdigest(),
            "installationSha256": hashlib.sha256(installation_raw).hexdigest(),
            "checkedInstalledFileHashes": checks}


class HeadAPI(base.LoopbackAPI):
    """Same loopback transport and NoRedirect, with one fixed native alias."""
    def request(self, path: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
        if self.role == "mc":
            return super().request(path, method, body)
        allowed = (method, path, body) == ("GET", "/api/status", None)
        if method == "POST" and path == "/api/prototype/resource-probe":
            allowed = body == {"resource": RESOURCE} and isinstance(body, dict) and set(body) == {"resource"}
        if method == "GET" and body is None and re.fullmatch(r"/api/prototype/resource-result\?ticket=[1-9][0-9]{0,9}", path):
            allowed = int(path.split("=")[1]) <= 2147483646
        if not allowed:
            raise ProbeError("Request is outside the single fixed head-material diagnostic")
        data = None if body is None else json.dumps(body, allow_nan=False).encode("utf-8")
        request = Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            try:
                response = self.opener.open(request, timeout=self.timeout)
            except HTTPError as error:
                response = error
            with response:
                payload = response.read(base.MAX_RESPONSE + 1)
                if len(payload) > base.MAX_RESPONSE:
                    raise base.RequestFailure("API response exceeds its bound; do not resubmit")
                try:
                    return response.code, base.strict_json(payload)
                except ProbeError as error:
                    raise base.RequestFailure("Invalid API response; do not resubmit") from error
        except (OSError, URLError, TimeoutError, HTTPException) as error:
            raise base.RequestFailure("No complete response; do not resubmit") from error


class HeadProbe(base.ResourceProbe):
    def __init__(self, api, mc, evidence, *, state_root=ROOT, **kwargs):
        super().__init__(api, mc, evidence, **kwargs)
        self.state_root = state_root

    def ready(self, report: dict, key: str) -> dict:
        value = super().ready(report, key)
        identity = report["gameBefore"]
        if (value.get("instanceId") != f'{identity["pid"]}:{identity["creationTime100ns"]}'
                or value.get("sessionPreconditions") is not True or value.get("objectPreconditions") is not True):
            raise ProbeError("Native resource API belongs to another instance or lacks session conditions")
        return value

    def mc_snapshot(self) -> dict:
        snapshot = super().mc_snapshot()
        state = snapshot["state"]
        slots = state.get("slots")
        if (state.get("engine") != "Minecraft Java 1.21.1" or type(state.get("schemaVersion")) is not int
                or state["schemaVersion"] != 3 or not isinstance(slots, list) or len(slots) != 36
                or any(not isinstance(row, dict) or type(row.get("slot")) is not int for row in slots)
                or {row["slot"] for row in slots} != set(range(36))
                or not isinstance(state.get("equipment"), dict)):
            raise ProbeError("Expected the complete current MC schema3 backpack and equipment snapshot")
        base.integer(state.get("selectedSlot"), "MC selected slot", 0, 35)
        return snapshot

    def validate_result(self, code: int, value: dict, ticket: int, expected: dict) -> str:
        state = super().validate_result(code, value, ticket, expected)
        if state == "read" and value["storageFlags"] != 50:
            raise ProbeError("Resolved head PAMI does not retain its fixed flags50 storage contract")
        return state

    def run(self, assets: dict) -> dict:
        expected = assets["resource"]
        report = {"schemaVersion": 1, "project": PROJECT, "runId": uuid.uuid4().hex,
                  "startedUtc": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": "preflight",
                  "sourcePlan": str(assets["plan"]), "sourcePlanSha256": PLAN_SHA256, "probeVariant": VARIANT,
                  "expectedResource": expected, "result": None, "fileResolvableReadMatched": False,
                  "gameInstanceUnchanged": False, "mcStateUnchanged": False, "installedContextUnchanged": False,
                  "success": False, "rendererMaterialSelected": False, "textureSamplingVerified": False,
                  "steveSkinVerified": False, "gameMemoryWritten": False, "appearanceApplied": False,
                  "limitations": ["File-resolver bytes do not prove renderer selection, shader inputs or DDS sampling.",
                                  "FNV1a64 is noncryptographic; local SHA256 verifies only admitted provenance.",
                                  "No installation, spawn, appearance apply or MC mutation is performed."]}
        self.evidence.write(report)
        try:
            verify_assets(assets)
            report["installedBefore"] = read_receipt(assets, self.state_root)
            report["gameBefore"] = self.instance()
            expected_exe = Path(report["installedBefore"]["gameRoot"]) / "bin64/CrimsonDesert.exe"
            if Path(report["gameBefore"]["imagePath"]).resolve() != expected_exe.resolve():
                raise ProbeError("Running EXE belongs to another game installation")
            self.ready(report, "statusBefore")
            report["mcBefore"] = self.mc_snapshot()
            if self.instance() != report["gameBefore"]:
                raise ProbeError("Game instance changed during preflight")
            if read_receipt(assets, self.state_root) != report["installedBefore"]:
                raise ProbeError("Installed probe changed during preflight")
            row = {"state": "submissionUnknown", "postAttempts": 1, "matched": False}
            report.update(phase="reading", result=row)
            self.evidence.write(report)  # Durable intent before the only POST.
            code, accepted = self.api.request("/api/prototype/resource-probe", "POST", {"resource": RESOURCE})
            row["accepted"] = accepted
            if (code != 202 or set(accepted) != {"ticket", "resource", "state"}
                    or accepted.get("resource") != RESOURCE or accepted.get("state") != "pending"):
                raise ProbeError("Head material POST did not return its matching ticket; do not resubmit")
            ticket = base.integer(accepted.get("ticket"), "resource ticket", 1)
            row.update(ticket=ticket, state="pending", polls=0)
            self.evidence.write(report)
            deadline = time.monotonic() + self.timeout
            while True:
                if self.instance() != report["gameBefore"]:
                    raise ProbeError("Game instance changed while polling; do not resubmit")
                self.ready(report, "statusPoll")
                code, value = self.api.request(f"/api/prototype/resource-result?ticket={ticket}")
                row["polls"] += 1
                row["nativeResult"] = value
                state = self.validate_result(code, value, ticket, expected)
                if state != "pending":
                    row["state"] = state
                    row["matched"] = state == "read" and all(value[key] == expected[key] for key in ("length", "head16hex", "fnv1a64"))
                    break
                if time.monotonic() >= deadline:
                    row.update(state="timeout", error="Original pending request was not resubmitted")
                    raise ProbeError("Head material ticket timed out; do not resubmit")
                time.sleep(min(self.interval, max(0, deadline - time.monotonic())))
        except Exception as error:
            report["error"] = str(error)
        finally:
            try:
                verify_assets(assets)
                report["installedAfter"] = read_receipt(assets, self.state_root)
                report["installedContextUnchanged"] = report.get("installedBefore") == report["installedAfter"]
            except Exception as error:
                report["installedAfterError"] = str(error)
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
            row = report["result"]
            report["success"] = (isinstance(row, dict) and row["matched"] and report["gameInstanceUnchanged"]
                                 and report["mcStateUnchanged"] and report["installedContextUnchanged"]
                                 and not any(key.endswith("Error") or key == "error" for key in report))
            report["fileResolvableReadMatched"] = report["success"]
            report["phase"] = "complete" if report["success"] else "failed"
            report["finishedUtc"] = dt.datetime.now(dt.timezone.utc).isoformat()
            self.evidence.write(report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=composition.DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/steve-head-material-read.json")
    parser.add_argument("--timeout", type=float, default=12)
    args = parser.parse_args()
    try:
        assets = load_assets(args.plan)
        evidence = base.Evidence(args.output)
        result = HeadProbe(HeadAPI(), HeadAPI("mc"), evidence, timeout=args.timeout).run(assets)
        print(json.dumps({"success": result["success"], "fileResolvableReadMatched": result["fileResolvableReadMatched"],
                          "rendererMaterialSelected": False, "textureSamplingVerified": False,
                          "steveSkinVerified": False, "report": str(evidence.path)}))
        return 0 if result["success"] else 1
    except (ProbeError, ValueError, OSError, KeyError, TypeError) as error:
        print("Steve head material diagnostic stopped: " + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
