"""Durable, conservative reconciliation of the six blue block proxies.

Registry confirmation is not proof of rendered geometry or engine collision.
There is no server idempotency key for spawn: an unknown admission is deliberately
not retried or guessed from similar objects. This module never writes Minecraft.
"""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import time
import uuid

from bridge.native_block_models import BLUE_PREFAB, state_key
from bridge.native_identity import EXE_SHA256, IdentityError, session_token
from bridge.red_side import GameAPIError

PROJECT = "CrimsonMCPrototype"
GAME_VERSION = "1.0.0.2976"
TRANSFORM = ("x", "y", "z", "yaw", "pitch", "roll", "scale")
MAX_OBJECTS = 50000


def fail(message):
    raise GameAPIError(message)


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def number(value, bound=1000000):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= bound


def targets(state, origin):
    """Keep complete authoritative properties; stateId is deliberately transient."""
    if (not isinstance(state, dict) or not integer(state.get("revision"), 0, 2**63-1)
            or not isinstance(state.get("blocks"), list) or len(state["blocks"]) > 128):
        fail("Invalid Minecraft block snapshot (maximum 128 blocks)")
    if not isinstance(origin, dict) or set(origin) != set("xyz") or not all(number(v) for v in origin.values()):
        fail("Invalid bridge anchor")
    result, cells = [], set()
    for block in state["blocks"]:
        if not isinstance(block, dict) or not all(integer(block.get(a), 64 if a == "y" else -16,
                                                         95 if a == "y" else 16) for a in "xyz"):
            fail("Invalid Minecraft cell in block snapshot")
        try:
            key = state_key(block.get("block"), block.get("properties"))
        except (TypeError, ValueError) as error:
            raise GameAPIError("Incomplete or unsupported Minecraft block properties: " + str(error)) from error
        cell = tuple(block[a] for a in "xyz")
        if cell in cells:
            fail("Duplicate Minecraft cell")
        cells.add(cell)
        result.append({"block": key[0], "properties": dict(key[1]), "cell": list(cell),
                       "prefab": BLUE_PREFAB, "x": origin["x"] + cell[0],
                       "y": origin["y"] + cell[1] - 64, "z": origin["z"] + cell[2],
                       "yaw": 0, "pitch": 0, "roll": 0, "scale": 1})
    return sorted(result, key=lambda row: row["cell"])


def valid_identity(identity):
    try:
        session_token(identity)
        return True
    except IdentityError:
        return False


def object_row(row):
    if (not isinstance(row, dict) or not integer(row.get("uid"), 1, 2147483646)
            or not isinstance(row.get("prefab"), str) or not 1 <= len(row["prefab"]) <= 600
            or type(row.get("hidden")) is not bool
            or not isinstance(row.get("project"), str) or len(row["project"]) > 600
            or any(ord(c) < 32 for c in row["project"])
            or not all(number(row.get(a)) for a in TRANSFORM)):
        fail("Malformed native object identity/transform")
    return {key: row[key] for key in ("uid", "prefab", "hidden", "project", *TRANSFORM)}


def matches(row, expected, *, hidden=False):
    return (row["prefab"] == expected["prefab"] and (hidden or row["hidden"] is False)
            and all(abs(row[a] - expected[a]) < (0.015 if a in "xyz" else 0.001) for a in TRANSFORM))


def object_precondition(row):
    """Use the last GET values, including native float rounding, not target doubles."""
    return {"expected" + key[0].upper() + key[1:]: row[key]
            for key in ("project", "prefab", *TRANSFORM, "hidden")}


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail("Duplicate journal JSON key")
        result[key] = value
    return result


def _session_rejected(error, identity):
    details = getattr(error, "details", None)
    if (getattr(error, "status", None) != 409 or not isinstance(details, dict)
            or details.get("sessionMismatch") is not True or not isinstance(details.get("instanceId"), str)):
        return False
    token = details["instanceId"]
    parts = token.split(":")
    if (len(parts) != 2 or any(not p.isascii() or not p.isdigit() or len(p) > 20 for p in parts)
            or not 1 <= int(parts[0]) <= 2**32-1 or not 1 <= int(parts[1]) <= 2**64-1
            or token != f"{int(parts[0])}:{int(parts[1])}"):
        return False
    return token != session_token(identity)


class NativeReconciler:
    def __init__(self, red, path, *, timeout=2.0, poll_interval=0.04):
        self.red, self.path = red, Path(path)
        self.timeout, self.poll_interval = timeout, poll_interval

    def _load(self):
        if not self.path.exists():
            return {"schemaVersion": 1, "project": PROJECT, "plan": None, "mcPending": None}
        if self.path.stat().st_size > 4 * 1024 * 1024:
            fail("Native operation journal exceeds its size limit")
        try:
            journal = json.loads(self.path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs)
            if (journal["schemaVersion"] != 1 or journal["project"] != PROJECT
                    or set(journal) != {"schemaVersion", "project", "plan", "mcPending"}):
                fail("Unsupported native operation journal")
            pending = journal["mcPending"]
            if pending is not None and (not isinstance(pending, dict)
                    or pending.get("phase") != "submitted" or not isinstance(pending.get("operationId"), str)):
                fail("Invalid pending Minecraft intent")
            plan = journal["plan"]
            if plan is not None:
                if (not valid_identity(plan["session"]) or str(uuid.UUID(plan["id"])) != plan["id"]
                        or type(plan["complete"]) is not bool or not isinstance(plan["operations"], list)
                        or len(plan["operations"]) > 384):
                    fail("Invalid native operation plan")
                # Reconstruct, rather than trust, persisted prefab/transform targets.
                blocks = [{"block": r["block"], "properties": r["properties"],
                           **dict(zip("xyz", r["cell"]))} for r in plan["desired"]]
                if targets({"revision": plan["revision"], "blocks": blocks}, plan["origin"]) != plan["desired"]:
                    fail("Native journal target has been altered")
                for op in plan["operations"]:
                    if op["kind"] == "create":
                        if (op["target"] not in plan["desired"] or op["phase"] not in
                                {"submitted", "admitted", "assigning", "confirmed", "rejected", "conflict"}
                                or not integer(op["beforeUidMax"], 0, 2147483646)):
                            fail("Invalid recorded create operation")
                        if op["phase"] not in {"submitted", "rejected"} and (not integer(op.get("uid"), 1, 2147483646)
                                                           or op["uid"] <= op["beforeUidMax"]):
                            fail("Invalid recorded spawn admission")
                        if "initialProject" in op and (not isinstance(op["initialProject"], str)
                                                       or len(op["initialProject"]) > 600):
                            fail("Invalid recorded initial ownership")
                    elif op["kind"] == "delete":
                        self._managed(object_row(op["object"]))
                        if op["phase"] not in {"submitted", "confirmed", "cancelled", "rejected", "conflict"}:
                            fail("Invalid recorded delete operation")
                    else:
                        fail("Unknown recorded native operation")
            return journal
        except (KeyError, TypeError, ValueError) as error:
            raise GameAPIError("Corrupt native operation journal; preserved without writes") from error

    def _write(self, journal, path=None):
        path = self.path if path is None else path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(journal, stream, sort_keys=True, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _archive(self, journal):
        plan = journal["plan"]
        if plan is not None:
            # The immutable history identifies this native plan. A later MC
            # intent belongs to the current journal, even if a disk failure left
            # the previous completed plan current after its archive was written.
            archived = {**journal, "mcPending": None}
            path = self.path.parent / (self.path.stem + "-history") / (plan["id"] + ".json")
            if path.exists():
                if json.loads(path.read_text(encoding="utf-8")) != archived:
                    fail("Native journal history conflict")
            else:
                self._write(archived, path)

    def ensure_build_allowed(self):
        journal = self._load()
        if journal["mcPending"] is not None or (journal["plan"] is not None and not journal["plan"]["complete"]):
            fail("Previous building action is unresolved. Use Restore blocks; do not repeat placement or consume materials.")

    def begin_mc(self, state, origin, path, mutation):
        self.ensure_build_allowed()
        identity = self._identity()
        self._ready(identity)
        self._same(identity)
        journal = self._load()
        journal["mcPending"] = {"phase": "submitted", "operationId": mutation["operationId"],
                                "path": path, "body": deepcopy(mutation), "revision": state["revision"],
                                "desiredBefore": targets(state, origin)}
        self._write(journal)

    def _identity(self):
        result = self.red.session_identity()
        if not valid_identity(result):
            fail("Unverified native process identity")
        return result

    def _same(self, identity):
        if self._identity() != identity:
            fail("Game process changed; old native UIDs cannot be used. Restore blocks to re-evaluate the new session.")

    def _ready(self, identity):
        code, status = self.red.request("/api/status")
        if (code != 200 or not isinstance(status, dict) or type(status.get("apiVersion")) is not int
                or status.get("apiVersion") != 1 or status.get("gameVersion") != GAME_VERSION
                or status.get("sessionPreconditions") is not True
                or status.get("objectPreconditions") is not True
                or status.get("instanceId") != session_token(identity)
                or status.get("ready") is not True or status.get("buildOk") is not True):
            fail("Unsupported or unavailable native building API")

    def _get(self, uid):
        try:
            code, row = self.red.request(f"/api/objects/{uid}")
        except GameAPIError as error:
            if getattr(error, "status", None) == 404:
                return None
            raise
        if code == 404:
            return None
        if code != 200:
            fail("Native object query was not confirmed")
        row = object_row(row)
        if row["uid"] != uid:
            fail("Native query returned a different UID")
        return row

    def _objects(self):
        result, offset, total = [], 0, None
        while True:
            code, page = self.red.request(f"/api/objects?offset={offset}&limit=500")
            if (code != 200 or not isinstance(page, dict) or not integer(page.get("offset"), 0, MAX_OBJECTS)
                    or page.get("offset") != offset or type(page.get("limit")) is not int or page.get("limit") != 500
                    or not integer(page.get("total"), 0, MAX_OBJECTS) or not isinstance(page.get("items"), list)):
                fail("Invalid native registry pagination")
            if total is None:
                total = page["total"]
            if total != page["total"] or len(page["items"]) != min(500, total-offset):
                fail("Native registry changed during pagination")
            result.extend(object_row(row) for row in page["items"])
            offset += len(page["items"])
            if page.get("nextOffset") != (offset if offset < total else None):
                fail("Invalid native registry continuation")
            if offset == total:
                if len({row["uid"] for row in result}) != total:
                    fail("Duplicate UID in native registry")
                return result

    @staticmethod
    def _managed(row):
        if (row["project"] != PROJECT or row["prefab"] != BLUE_PREFAB or abs(row["scale"]-1) >= 0.001
                or any(abs(row[a]) >= 0.001 for a in ("yaw", "pitch", "roll"))):
            fail("Project contains an unrecognized native object; it will not be changed")
        return row

    def _owned(self, uid, expected, *, hidden=False):
        row = self._get(uid)
        if row is not None and (row["project"] != PROJECT or not matches(row, expected, hidden=hidden)):
            fail("Native ownership/prefab/transform changed; operation stopped")
        return row

    def _mutate(self, journal, op, path, method, body=None):
        identity = journal["plan"]["session"]
        try:
            return self.red.request(path, method, body, expected_session=identity)
        except Exception as error:
            if _session_rejected(error, identity):
                op["sessionRejection"] = {"path": path, "instanceId": error.details["instanceId"]}
                # A rejected assignment does not erase the successful creation
                # that preceded it in the old process. Its ownership is unresolved.
                if op["kind"] == "delete" or op["phase"] == "submitted":
                    op["phase"] = "rejected"
                self._write(journal)
            elif (getattr(error, "status", None) == 409 and isinstance(getattr(error, "details", None), dict)
                    and error.details.get("mutationApplied") is False
                    and (op["kind"] == "delete" or op["phase"] == "assigning")):
                reason = error.details.get("reason")
                changed = reason == "object_changed" and error.details.get("objectMismatch") is True
                busy = (isinstance(reason, str) and reason in {"busy", "unsupported"}
                        and error.details.get("objectMismatch") is False)
                if changed or busy:
                    op["objectRejection"] = {"path": path, "mutationApplied": False, "reason": reason}
                    # A busy engine has not changed ownership. Only the explicit
                    # changed-fields contract permanently stops automatic recovery.
                    if changed:
                        op["phase"] = "conflict"
                    self._write(journal)
            raise

    def _confirm_create(self, journal, op):
        identity = journal["plan"]["session"]
        if op["phase"] == "submitted":
            fail("Native spawn result unknown: no valid admission was recorded. No spawn or Minecraft action will be retried.")
        deadline = time.monotonic() + self.timeout
        while True:
            self._same(identity)
            row = self._get(op["uid"])
            self._same(identity)
            if row is not None:
                if not matches(row, op["target"]):
                    fail("Admitted native UID has a different prefab/transform or is hidden")
                if "initialProject" not in op:
                    op["initialProject"] = row["project"]
                    self._write(journal)
                allowed = {op["initialProject"]}
                if op["phase"] == "assigning":
                    allowed.add(PROJECT)
                if row["project"] not in allowed:
                    fail("Admitted native object changed project ownership")
                if row["project"] != PROJECT:
                    op["phase"] = "assigning"
                    op["objectPrecondition"] = object_precondition(row)
                    self._write(journal)
                    self._same(identity)
                    code, response = self._mutate(journal, op, f"/api/objects/{op['uid']}/project", "POST",
                                                  {"name": PROJECT, **op["objectPrecondition"]})
                    self._same(identity)
                    if (code != 200 or response.get("uid") != op["uid"] or response.get("project") != PROJECT
                            or response.get("conditional") is not True):
                        fail("Native project assignment response is unknown; Restore blocks to inspect it")
                    row = self._owned(op["uid"], op["target"])
                    self._same(identity)
                    if row is None:
                        fail("Assigned native object disappeared")
                op["phase"] = "confirmed"
                self._write(journal)
                return row
            if time.monotonic() >= deadline:
                fail("Native spawn was admitted but registry confirmation timed out; Restore blocks without placing again")
            time.sleep(self.poll_interval)

    def _checkpoint(self, identity, desired, origin, read_state):
        self._same(identity)
        self._ready(identity)
        # Independent inventory actions may advance revision without changing the
        # block target. Actual block/property changes stop the stale plan.
        if targets(read_state(), origin) != desired:
            fail("Minecraft blocks changed during native sync; Restore blocks to use the current authoritative state")
        self._same(identity)

    def reconcile(self, state, origin, read_state):
        desired = targets(state, origin)
        identity = self._identity()
        self._checkpoint(identity, desired, origin, read_state)
        journal = self._load()
        previous = journal["plan"]
        if previous is not None:
            for op in previous["operations"]:
                if op["phase"] in {"confirmed", "cancelled", "rejected"}:
                    continue
                if op["phase"] == "conflict":
                    fail("Native object precondition conflict is unresolved; no ownership or deletion will be retried. Inspect the preserved journal.")
                if op["kind"] == "create":
                    if previous["session"] != identity:
                        fail("Game restarted with an unresolved spawn. Old UID ownership cannot be transferred; journal retained for inspection.")
                    self._confirm_create(journal, op)
                elif previous["session"] == identity:
                    self._same(identity)
                    # A still-present deletion is reconsidered against current MC,
                    # never replayed merely because its previous response was lost.
                    row = self._owned(op["object"]["uid"], op["object"], hidden=True)
                    self._same(identity)
                    op["phase"] = "confirmed" if row is None else "cancelled"
                    self._write(journal)
            self._archive(journal)
        self._checkpoint(identity, desired, origin, read_state)
        objects = self._objects()
        self._same(identity)
        existing = [self._managed(row) for row in objects if row["project"] == PROJECT]
        if len(existing) > 256:
            fail("Native project exceeds the bounded recovery limit of 256 objects; no objects changed")
        journal["plan"] = {"id": str(uuid.uuid4()), "session": identity, "revision": state["revision"],
                           "origin": deepcopy(origin), "desired": desired, "operations": [], "complete": False}
        self._write(journal)
        plan, used = journal["plan"], {}
        for target in desired:
            row = next((row for row in existing if row["uid"] not in used and matches(row, target)), None)
            if row is None:
                self._checkpoint(identity, desired, origin, read_state)
                before = self._objects()
                self._same(identity)
                # The pinned API allocates monotonically increasing UIDs. A UID
                # above the observed maximum proves it was not already present,
                # without copying a potentially large registry into every entry.
                op = {"kind": "create", "phase": "submitted", "target": target,
                      "beforeUidMax": max((r["uid"] for r in before), default=0)}
                plan["operations"].append(op)
                self._write(journal)  # Must succeed before submitting any native write.
                self._same(identity)
                try:
                    code, admission = self._mutate(journal, op, "/api/objects", "POST",
                                                   {key: target[key] for key in ("prefab", *TRANSFORM)})
                    self._same(identity)
                    uid = admission.get("uid")
                    if code != 202 or admission.get("queued") is not True or not integer(uid, 1, 2147483646) or uid <= op["beforeUidMax"]:
                        fail("Invalid native spawn admission")
                    op.update({"uid": uid, "phase": "admitted"})
                    self._write(journal)
                except Exception as error:
                    if op["phase"] == "rejected":
                        raise GameAPIError("Native spawn rejected before enqueue because the game session changed. Restore blocks to inspect the new session.") from error
                    raise GameAPIError("Native spawn result unknown; journal retained. Do not repeat placement. " + str(error)) from error
                row = self._confirm_create(journal, op)
            used[row["uid"]] = target
        self._checkpoint(identity, desired, origin, read_state)
        for uid, target in used.items():
            if self._owned(uid, target) is None:
                fail("A replacement disappeared before old-object cleanup")
        # Only after the complete desired set has been read back with our project.
        for row in existing:
            if row["uid"] in used:
                continue
            self._checkpoint(identity, desired, origin, read_state)
            current = self._owned(row["uid"], row, hidden=True)
            if current is None:
                continue
            op = {"kind": "delete", "phase": "submitted", "object": current,
                  "objectPrecondition": object_precondition(current)}
            plan["operations"].append(op)
            self._write(journal)
            self._same(identity)
            code, response = self._mutate(journal, op, f"/api/objects/{row['uid']}", "DELETE", op["objectPrecondition"])
            self._same(identity)
            if (code != 202 or response.get("queued") is not True or response.get("uid") != row["uid"]
                    or response.get("conditional") is not True):
                fail("Native deletion response is unknown; Restore blocks to inspect it")
            deadline = time.monotonic() + self.timeout
            while self._owned(row["uid"], row, hidden=True) is not None:
                self._same(identity)
                if time.monotonic() >= deadline:
                    fail("Native deletion not confirmed; journal retained for Restore blocks")
                time.sleep(self.poll_interval)
            self._same(identity)
            op["phase"] = "confirmed"
            self._write(journal)
        self._checkpoint(identity, desired, origin, read_state)
        plan["complete"], journal["mcPending"] = True, None
        self._write(journal)
        return state
