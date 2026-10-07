"""Pure selection of explicitly admitted native models; not wired into the bridge.

These records are inputs from a future verification adapter, NOT raw report
parsers or proof that an asset has been verified. That adapter must first check
actual files/receipts, visual and collision evidence, game identity/readiness,
and native resource read results. This module only checks their explicit scope
and exact identity agreement. A config flag or self-declared `verified: true`
is never an input. No I/O, installation, game calls or persistence is performed.

An enabled profile can persist asset/evidence hashes. SessionVerification is
ephemeral and must be rebuilt after a process change; its token is supplied by
the adapter and compared with the caller's freshly observed current token.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

GAME_VERSION = "1.0.0.2976"
EXE_SHA256 = "57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7"
BLUE_PREFAB = "/object/00_common/system/cd_testfield_grid_box_1m.prefab"
BASELINE_BLOCKS = frozenset({"minecraft:oak_log", "minecraft:oak_planks", "minecraft:cobblestone",
                             "minecraft:dirt", "minecraft:stone", "minecraft:crafting_table"})
OAK_PREFABS = {axis: f"/object/00_common/system/crimsonmc_oak_log_{axis}.prefab" for axis in "xyz"}
StateKey = tuple[str, tuple[tuple[str, str], ...]]


class ModelSelectionError(ValueError):
    """Unsupported state, missing admission, or incompatible current evidence."""


def _sha(value: object, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ModelSelectionError(label + " must be a lowercase SHA256")


def _session_token(value: object) -> None:
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ModelSelectionError("A nonempty current process-session token is required")


def state_key(block: str, properties: Mapping[str, str]) -> StateKey:
    """Require the complete MC properties for the existing six-block slice.

    This is a rendering allowlist, not Minecraft placement/property authority.
    It deliberately does not default a missing oak axis or use runtime stateId.
    """
    if not isinstance(block, str) or block not in BASELINE_BLOCKS:
        raise ModelSelectionError("Block is outside the six supported baseline types")
    if not isinstance(properties, Mapping):
        raise ModelSelectionError("Complete Minecraft properties must be supplied as a mapping")
    values = dict(properties)
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in values.items()):
        raise ModelSelectionError("Minecraft property names and values must be strings")
    if block == "minecraft:oak_log":
        if set(values) != {"axis"} or values["axis"] not in OAK_PREFABS:
            raise ModelSelectionError("Oak log requires exactly axis=x, axis=y, or axis=z")
    elif values:
        raise ModelSelectionError("This baseline block requires an empty complete properties mapping")
    return block, tuple(sorted(values.items()))


def _native_prefab(key: StateKey) -> str:
    if key[0] != "minecraft:oak_log":
        raise ModelSelectionError("No native asset is implemented for this baseline block; use explicit blue mode")
    return OAK_PREFABS[dict(key[1])["axis"]]


@dataclass(frozen=True)
class AssetIdentity:
    candidate_report_sha256: str
    # SHA256 of verified overlay-report.json, which binds package file hashes,
    # metadata and candidate report. A PAZ hash alone is not this identity.
    package_report_sha256: str
    exe_sha256: str = EXE_SHA256
    game_version: str = GAME_VERSION

    def __post_init__(self) -> None:
        _sha(self.candidate_report_sha256, "Candidate report")
        _sha(self.package_report_sha256, "Package report")
        if self.exe_sha256 != EXE_SHA256 or self.game_version != GAME_VERSION:
            raise ModelSelectionError("Native model selection requires the supported game version and EXE")


@dataclass(frozen=True)
class ModelAdmission:
    """One exact state's prior visual/collision acceptance and observed identity.

    Evidence hashes reference separately checked actual observations. Merely
    constructing this object does not authenticate or inspect those observations.
    """
    identity: AssetIdentity
    state: StateKey
    prefab: str
    visual_evidence_sha256: str
    collision_evidence_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.identity, AssetIdentity):
            raise ModelSelectionError("Admission requires the actual observed asset identity")
        if (not isinstance(self.state, tuple) or len(self.state) != 2 or not isinstance(self.state[1], tuple)
                or any(not isinstance(pair, tuple) or len(pair) != 2 for pair in self.state[1])):
            raise ModelSelectionError("Admission state must be an immutable canonical state key")
        try:
            key = state_key(self.state[0], dict(self.state[1]))
        except (TypeError, ValueError) as error:
            raise ModelSelectionError("Admission state is invalid") from error
        if key != self.state:
            raise ModelSelectionError("Admission state is duplicated or not canonical")
        if self.prefab != _native_prefab(key):
            raise ModelSelectionError("Admission prefab differs from the fixed native asset for its exact state")
        _sha(self.visual_evidence_sha256, "Visual evidence")
        _sha(self.collision_evidence_sha256, "Collision evidence")


@dataclass(frozen=True)
class NativeProfile:
    identity: AssetIdentity
    admissions: tuple[ModelAdmission, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.identity, AssetIdentity):
            raise ModelSelectionError("Profile requires an explicit AssetIdentity, not a raw report")
        if (not isinstance(self.admissions, tuple) or not 1 <= len(self.admissions) <= 3
                or any(not isinstance(a, ModelAdmission) for a in self.admissions)):
            raise ModelSelectionError("Profile requires one to three explicit native state admissions")
        if len({a.state for a in self.admissions}) != len(self.admissions):
            raise ModelSelectionError("Profile contains duplicate state admissions")
        if any(a.identity != self.identity for a in self.admissions):
            raise ModelSelectionError("State admission belongs to a different candidate/package identity")


@dataclass(frozen=True)
class SessionVerification:
    """Ephemeral adapter result after installed-file and native-read checks.

    Before every call the adapter must still observe ready/buildOk/version and
    this same process-session. No PID, UID or previous ready flag is persisted
    by this module. The record is not a substitute for those external checks.
    """
    identity: AssetIdentity
    session_token: str
    resource_evidence_sha256: str
    resource_verified_prefabs: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.identity, AssetIdentity):
            raise ModelSelectionError("Session requires an explicit AssetIdentity, not a raw report")
        _session_token(self.session_token)
        _sha(self.resource_evidence_sha256, "Current-session native resource evidence")
        if (not isinstance(self.resource_verified_prefabs, frozenset) or not self.resource_verified_prefabs
                or not self.resource_verified_prefabs <= frozenset(OAK_PREFABS.values())):
            raise ModelSelectionError("Session resource results must name only fixed oak native prefabs")


@dataclass(frozen=True)
class ModelChoice:
    state: StateKey
    mode: str
    prefab: str
    # None in explicit blue mode. Native choices retain asset identity so a
    # future reconciler cannot treat a same-path asset from another package as
    # interchangeable. This result is a plan, never a spawn confirmation.
    identity: AssetIdentity | None


def select_model(block: str, properties: Mapping[str, str], *, mode: str = "blue",
                 profile: NativeProfile | None = None, session: SessionVerification | None = None,
                 current_session_token: str | None = None) -> ModelChoice:
    """Select a plan, or refuse native mode without an exact admitted state.

    Blue mode is explicit/default and supports all six existing baseline types.
    Native mode never silently downgrades: missing evidence or an unsupported
    state raises before any caller should spend materials or mutate objects.
    Raw diagnostic JSON, generic truthy flags, arbitrary paths and stale process
    sessions are not accepted. No production profile is shipped in this module.
    """
    key = state_key(block, properties)
    if mode not in ("blue", "native"):
        raise ModelSelectionError("Mode must explicitly be blue or native")
    if profile is not None and not isinstance(profile, NativeProfile):
        raise ModelSelectionError("Expected NativeProfile; raw asset reports are not verified inputs")
    if session is not None and not isinstance(session, SessionVerification):
        raise ModelSelectionError("Expected SessionVerification; raw resource reports are not verified inputs")
    if mode == "blue":
        return ModelChoice(key, "blue", BLUE_PREFAB, None)
    prefab = _native_prefab(key)
    if profile is None or session is None:
        raise ModelSelectionError("Native mode requires state acceptance and current-session asset verification")
    _session_token(current_session_token)
    if session.session_token != current_session_token:
        raise ModelSelectionError("Game process-session changed; verify native assets again")
    if profile.identity != session.identity:
        raise ModelSelectionError("Candidate/package identity differs from the current installed verification")
    if not any(a.state == key and a.prefab == prefab for a in profile.admissions):
        raise ModelSelectionError("This exact block state has no visual and collision admission in the selected profile")
    if prefab not in session.resource_verified_prefabs:
        raise ModelSelectionError("This prefab's resources were not verified in the current process-session")
    return ModelChoice(key, "native", prefab, profile.identity)
