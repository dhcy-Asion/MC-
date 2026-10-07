"""Rehearse a native asset overlay in ignored build, without writing the game.

Consumes candidateResources from the offline asset tools. This is a packaging
check, not an installer or proof that an engine can render the candidate assets.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import tempfile
from pathlib import Path, PurePosixPath
from unittest.mock import patch

import prepare_native_steve as native

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_LIMIT = 128
FILE_LIMIT = 16 * 1024 * 1024


def virtual_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Resource paths must be relative POSIX virtual paths")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", value):
        raise ValueError("Resource paths contain unsupported characters")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError("Resource path escapes its virtual namespace")
    if len(parsed.parts) < 2 or len(value.encode("utf-8")) > 512:
        raise ValueError("Resource path must be folder-qualified and bounded")
    return value


def load_resources(reports: list[Path]) -> tuple[list[dict], dict[str, bytes], dict[str, str]]:
    resources: list[dict] = []
    payloads: dict[str, bytes] = {}
    inputs: dict[str, str] = {}
    for report_path in reports:
        # Candidate assets and their provenance reports may only come from build.
        report_path = native.output_directory(report_path)
        report_data = report_path.read_bytes()
        inputs[str(report_path.relative_to(ROOT))] = native.sha256(report_data)
        report = json.loads(report_data)
        rows = report.get("candidateResources")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"No candidateResources in {report_path.name}")
        for row in rows:
            target = virtual_path(row["virtualPath"])
            if not target.isascii() or target != target.casefold():
                raise ValueError("Candidate virtual paths must use canonical lowercase ASCII")
            local = virtual_path("asset/" + row["localFile"])[6:]
            path = native.output_directory(report_path.parent / local)
            if not path.is_relative_to(report_path.parent):
                raise ValueError("Candidate resource escapes its report directory")
            if target.casefold() in {value.casefold() for value in payloads}:
                raise ValueError(f"Duplicate overlay resource: {target}")
            # Never overwrite an original asset under a deceptively familiar name.
            if not PurePosixPath(target).name.startswith("crimsonmc_"):
                raise ValueError("Candidate overlay files need a crimsonmc_ basename")
            if path.stat().st_size > FILE_LIMIT:
                raise ValueError("Candidate resource exceeds the rehearsal size limit")
            data = path.read_bytes()
            if not data or native.sha256(data) != row["sha256"]:
                raise ValueError(f"Candidate resource checksum mismatch: {target}")
            template = virtual_path(row["templatePath"])
            resource = {"virtualPath": target, "localFile": str(path.relative_to(ROOT)),
                        "sha256": native.sha256(data), "kind": row["kind"],
                        "templatePath": template, "templateSha256": row["templateSha256"]}
            if not re.fullmatch(r"[0-9a-f]{64}", resource["templateSha256"]):
                raise ValueError("Resource needs a pinned template fingerprint")
            resources.append(resource)
            payloads[target] = data
        if len(resources) > RESOURCE_LIMIT:
            raise ValueError("Too many candidate overlay resources")
    return resources, payloads, inputs


def audit_mounts(before: bytes, after: bytes, name: str, pamt: bytes) -> dict:
    from cdmw.core.papgt_format import parse_papgt, serialize_papgt, PAPGT_DEFAULT_FLAGS
    from cdmw.core.archive_format import calculate_pa_checksum
    original = parse_papgt(before)
    updated = parse_papgt(after)
    if serialize_papgt(original, header=before[:12]) != before:
        raise ValueError("Native mount list no-edit rebuild changed bytes")
    if len({item.name for item in original}) != len(original) or name in {item.name for item in original}:
        raise ValueError("Overlay directory collides with a mounted archive")
    checksum = struct.unpack_from("<I", pamt)[0]
    if checksum != calculate_pa_checksum(pamt[12:]):
        raise ValueError("Overlay PAMT checksum mismatch")
    if (updated[1:] != original or updated[0].name != name or
            updated[0].pamt_checksum != checksum or updated[0].flags != PAPGT_DEFAULT_FLAGS):
        raise ValueError("Overlay mount rehearsal changed original records")
    if before[:4] != after[:4] or before[9:12] != after[9:12] or after[8] != len(updated):
        raise ValueError("Overlay mount rehearsal changed unknown header metadata")
    return {"beforeDirectoryCount": len(original), "afterDirectoryCount": len(updated),
            "originalRecordsUnchanged": True, "originalNoEditRebuildByteIdentical": True}


def audit_registry(before: bytes, after: bytes, textures: dict[str, bytes]) -> dict:
    from cdmw.core.pathc_format import parse_pathc, encode_pathc, dds_shape, block_infos_for
    original, updated = parse_pathc(before), parse_pathc(after)
    if encode_pathc(original) != before:
        raise ValueError("Native texture registry no-edit rebuild changed bytes")
    original_rows = {row.checksum: row for row in original.entries}
    updated_rows = {row.checksum: row for row in updated.entries}
    if any(updated_rows.get(key) != row for key, row in original_rows.items()):
        raise ValueError("Overlay registry changed an original texture row")
    if (updated.headers[:len(original.headers)] != original.headers or
            updated.collisions != original.collisions or updated.filenames != original.filenames or
            updated.header_size != original.header_size or updated.reserved != original.reserved):
        raise ValueError("Overlay registry changed original headers or collision metadata")
    if len(updated.entries) != len(original.entries) + len(textures):
        raise ValueError("Overlay registry added an unexpected texture count")
    for path, dds in textures.items():
        validate_candidate_dds(dds)
        row = updated.find(path)
        if row is None or not row.is_direct or original.find(path) is not None:
            raise ValueError(f"Missing or colliding texture registration: {path}")
        if dds_shape(updated.dds_header_for(row)) != dds_shape(dds[:128]):
            raise ValueError(f"Wrong registered DDS shape: {path}")
        if row.block_infos != block_infos_for(dds):
            raise ValueError(f"Wrong registered mip block sizes: {path}")
    return {"beforeEntries": len(original.entries), "afterEntries": len(updated.entries),
            "newTextures": len(textures), "originalRowsHeadersCollisionsUnchanged": True,
            "originalNoEditRebuildByteIdentical": True}


def validate_candidate_dds(data: bytes) -> dict:
    """Strictly bound the three legacy DDS formats used by these candidates.

    Registry construction alone does not check that every mip exists. Unknown
    formats and DX10 headers remain unsupported rather than falling through.
    """
    if len(data) < 128 or data[:4] != b"DDS " or struct.unpack_from("<I", data, 4)[0] != 124:
        raise ValueError("Candidate DDS has an invalid legacy header")
    flags, height, width, pitch, depth, mips = struct.unpack_from("<6I", data, 8)
    if (flags & 0x1007) != 0x1007 or depth != 1:
        raise ValueError("Candidate DDS lacks required fields or native depth=1")
    if not 1 <= width <= 1024 or not 1 <= height <= 1024 or width & (width - 1) or height & (height - 1):
        raise ValueError("Candidate DDS dimensions must be bounded powers of two")
    if mips != max(width, height).bit_length() or (mips > 1 and not flags & 0x20000):
        raise ValueError("Candidate DDS must contain a complete mip chain")
    pf_size, pf_flags = struct.unpack_from("<2I", data, 76)
    fourcc = data[84:88]
    if pf_size != 32 or pf_flags != 4 or fourcc not in (b"DXT1", b"DXT5", b"BC5U"):
        raise ValueError("Candidate DDS uses an unsupported pixel format")
    block_bytes = 8 if fourcc == b"DXT1" else 16
    sizes = [max(1, (max(1, width >> level) + 3) // 4) *
             max(1, (max(1, height >> level) + 3) // 4) * block_bytes for level in range(mips)]
    if pitch != sizes[0] or len(data) != 128 + sum(sizes):
        raise ValueError("Candidate DDS has incorrect mip payload sizes")
    return {"width": width, "height": height, "mips": mips,
            "fourcc": fourcc.decode("ascii"), "payloadBytes": sum(sizes)}


def audit_package(output: Path, resources: list[dict], payloads: dict[str, bytes]) -> dict:
    from cdmw.core.archive_format import parse_archive_pamt, calculate_pa_checksum
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    from cdmw.core.archive_entry_addition import parse_pamt_document
    pamt = output / "0.pamt"
    data, paz = pamt.read_bytes(), (output / "0.paz").read_bytes()
    document = parse_pamt_document(data)
    if document.serialize() != data:
        raise ValueError("Overlay PAMT no-edit rebuild changed bytes")
    if document.paz_records != [(0, calculate_pa_checksum(paz), len(paz))] or len(paz) % 16:
        raise ValueError("Overlay PAZ checksum, length or alignment mismatch")
    entries = parse_archive_pamt(pamt)
    if len(entries) != len(resources) or {entry.path for entry in entries} != set(payloads):
        raise ValueError("Overlay archive does not contain exactly the candidate resources")
    for entry in entries:
        if entry.offset % 16 or entry.offset + entry.comp_size > len(paz):
            raise ValueError("Overlay resource has an invalid payload boundary")
        data = _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
        if data != payloads[entry.path]:
            raise ValueError(f"Overlay decode differs from candidate: {entry.path}")
    return {"entries": len(entries), "pazBytes": len(paz), "allPayloadsDecodeByteIdentically": True,
            "pamtNoEditRebuildByteIdentical": True, "payloadBoundariesAndChecksumsValid": True}


def preflight_outputs(output: Path, names: list[str]) -> None:
    output = native.output_directory(output)
    # Validate every eventual file AND temporary file before publishing any.
    for name in names:
        target = output / virtual_path(name)
        native.check_links(target)
        temporary = target.with_name(target.name + ".tmp")
        native.check_links(temporary)
        if target.exists() and not target.is_file():
            raise ValueError("Overlay output collides with an existing directory")
        if temporary.exists() and not temporary.is_file():
            raise ValueError("Overlay temporary output collides with an existing directory")


def publish(output: Path, files: dict[str, bytes]) -> None:
    output = native.output_directory(output)
    preflight_outputs(output, list(files))
    for name, data in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(target)


def prepare(game: Path, reports: list[Path], output: Path, source: Path, deps: Path,
            *, replacement_report: Path | None = None, initial_appearance_report: Path | None = None,
            part_table_report: Path | None = None) -> dict:
    if (initial_appearance_report is not None or part_table_report is not None) and replacement_report is None:
        raise ValueError("Steve registration/appearance control requires its fixed mesh-parameter candidate")
    if initial_appearance_report is not None and part_table_report is None:
        raise ValueError("Initial Steve appearance control requires private part registration")
    output = native.output_directory(output)
    provenance = native.load_cdmw(source, deps)
    native.check_links(game)
    if native.file_hash(game / "bin64" / "CrimsonDesert.exe") != native.EXE_SHA256:
        raise ValueError("Unsupported Crimson Desert EXE SHA; overlay rehearsal stopped")
    resources, payloads, inputs = load_resources(reports)
    # The general loader/CLI remains new-name-only. A separate reviewed Steve
    # probe may shadow its fixed Kliff mesh-parameter template, optionally with
    # the fixed part table and one initial app. No arbitrary replacement paths.
    replacement_paths, replacement_snapshot = set(), {}
    if replacement_report is not None:
        import prepare_steve_appearance as appearance
        replacement_report = native.output_directory(replacement_report)
        replacement, replacement_payloads, replacement_snapshot = appearance.load_candidate(replacement_report)
        rows = replacement["targetReplacements"]
        if len(rows) != 1 or set(replacement_payloads) != {appearance.TARGET_PATH}:
            raise ValueError("Only the reviewed single Steve mesh-parameter replacement is permitted")
        for row in rows:
            path = virtual_path(row["virtualPath"])
            if path != row["templatePath"] or path in payloads or row["kind"] != "appearanceMeshParams":
                raise ValueError("Unexpected Steve replacement identity or duplicate resource")
            resource = dict(row, localFile=str((replacement_report.parent / row["localFile"]).relative_to(ROOT)))
            resources.append(resource)
            payloads[path] = replacement_payloads[path]
            replacement_paths.add(path)
        inputs[str(replacement_report.relative_to(ROOT))] = native.file_hash(replacement_report)
        if len(resources) > RESOURCE_LIMIT:
            raise ValueError("Too many candidate overlay resources")
    if part_table_report is not None:
        import prepare_steve_part_table as parts
        part_table_report = native.output_directory(part_table_report)
        candidate, table_payloads, table_snapshot = parts.load_candidate(part_table_report)
        rows = candidate["targetReplacements"]
        table_path = "character/bin__/partprefabtable.pappt"
        if len(rows) != 1 or set(table_payloads) != {table_path}:
            raise ValueError("Steve registration must replace exactly the reviewed part table")
        row = rows[0]
        if (row["virtualPath"] != table_path or row["templatePath"] != table_path
                or table_path in payloads or row["kind"] != "partPrefabTable"):
            raise ValueError("Unexpected Steve part table identity or duplicate resource")
        resources.append(dict(row, localFile=str((part_table_report.parent / row["localFile"]).relative_to(ROOT))))
        payloads[table_path] = table_payloads[table_path]
        replacement_paths.add(table_path)
        replacement_snapshot.update(table_snapshot)
        inputs[str(part_table_report.relative_to(ROOT))] = native.file_hash(part_table_report)
        if len(resources) > RESOURCE_LIMIT:
            raise ValueError("Too many candidate overlay resources")
    if initial_appearance_report is not None:
        import prepare_steve_app as app
        initial_appearance_report = native.output_directory(initial_appearance_report)
        candidate, app_payloads, app_snapshot = app.load_candidate(initial_appearance_report)
        rows = candidate["targetReplacements"]
        if len(rows) != 1 or len(app_payloads) != 1:
            raise ValueError("Initial Steve appearance control must replace exactly one fixed app")
        row = rows[0]
        path = virtual_path(row["virtualPath"])
        if (path != row["templatePath"] or path in payloads or row["kind"] != "appearanceDefinition"
                or path not in appearance.APPEARANCES or set(app_payloads) != {path}):
            raise ValueError("Unexpected initial Steve appearance identity or duplicate resource")
        resources.append(dict(row, localFile=str((initial_appearance_report.parent / row["localFile"]).relative_to(ROOT))))
        payloads[path] = app_payloads[path]
        replacement_paths.add(path)
        replacement_snapshot.update(app_snapshot)
        inputs[str(initial_appearance_report.relative_to(ROOT))] = native.file_hash(initial_appearance_report)
        if len(resources) > RESOURCE_LIMIT:
            raise ValueError("Too many candidate overlay resources")
    if any(output.is_relative_to((ROOT / relative).parent) or
           (ROOT / relative).is_relative_to(output) for relative in inputs):
        raise ValueError("Overlay output must be separate from its candidate inputs")
    from cdmw.core.archive_format import parse_archive_pamt, calculate_pa_checksum
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    from cdmw.core.papgt_format import parse_papgt
    from cdmw.core.pathc_format import parse_pathc, encode_pathc, register_dds
    from cdmw.domain.archives.mutation import ArchiveAddRequest, ArchivePatchRequest
    from cdmw.services.archive_overlay_install import prepare_overlay_install, overlay_directory_name
    papgt_path, pathc_path = game / "meta/0.papgt", game / "meta/0.pathc"
    for path in (papgt_path, pathc_path):
        native.check_links(path)
    papgt_before, pathc_before = papgt_path.read_bytes(), pathc_path.read_bytes()
    records = parse_papgt(papgt_before)
    # This first vertical slice requires a clean namespace; it never merges other mods.
    if (game / ".cdmw").exists():
        raise ValueError("Existing CDMW management state requires a separate compatibility review")
    wanted = {resource["templatePath"] for resource in resources}
    targets = {path.casefold() for path in payloads}
    templates, index_hashes, missing_optional = {}, {}, []
    for record in records:
        if not re.fullmatch(r"[0-9]{4}", record.name):
            raise ValueError("Unexpected mounted archive directory layout")
        index = game / record.name / "0.pamt"
        native.check_links(index)
        if not index.exists():
            # Low-byte 1 is the fixed format's optional-package flag. Preserve
            # these mounted reservations even when their payload isn't installed.
            if record.flags & 0xFF != 1:
                raise ValueError("A required mounted archive index is missing")
            missing_optional.append(record.name)
            continue
        index_hashes[str(index.relative_to(game))] = native.file_hash(index)
        index_bytes = index.read_bytes()
        stored_checksum = struct.unpack_from("<I", index_bytes)[0]
        if (stored_checksum != record.pamt_checksum or
                stored_checksum != calculate_pa_checksum(index_bytes[12:])):
            raise ValueError("Mounted PAMT does not match PAPGT record")
        entries = parse_archive_pamt(index)
        if any(entry.path.casefold() in targets - replacement_paths for entry in entries):
            raise ValueError("Candidate virtual path already exists in a mounted archive")
        for entry in entries:
            # First mounted occurrence has the same priority as the game loader.
            if entry.path in wanted and entry.path not in templates:
                templates[entry.path] = entry
    if set(templates) != wanted:
        raise ValueError(f"Missing native packaging templates: {sorted(wanted - set(templates))}")
    table = parse_pathc(pathc_before)
    textures = {}
    template_payloads = {}
    additions, requests = [], []
    for resource in resources:
        path, template_path = resource["virtualPath"], resource["templatePath"]
        template = templates[template_path]
        native.check_links(template.paz_file)
        original = _decode_archive_entry_data(template, read_archive_entry_raw_data(template))[0]
        if native.sha256(original) != resource["templateSha256"]:
            raise ValueError(f"Native packaging template checksum mismatch: {template_path}")
        template_payloads[template_path] = original
        if (int(template.compression_type) not in (0, 1, 2) or
                int(template.flags) >> 4 not in (0, 3)):
            raise ValueError("Candidate template uses unreviewed storage flags")
        if PurePosixPath(path).suffix.casefold() != PurePosixPath(template_path).suffix.casefold():
            raise ValueError("Candidate and template resource types differ")
        if resource["kind"] == "texture":
            if not path.endswith(".dds"):
                raise ValueError("Texture resource must be a DDS")
            validate_candidate_dds(payloads[path])
            textures[path] = payloads[path]
            table = register_dds(table, path, payloads[path])
        elif path.endswith(".dds"):
            raise ValueError("DDS resources must be marked texture for registry publication")
        resource["templateArchiveFlags"] = int(template.flags)
        if path in replacement_paths:
            if path != template_path or path.endswith(".dds"):
                raise ValueError("Replacement must shadow its exact nontexture template")
            requests.append(ArchivePatchRequest(template, payloads[path]))
            resource["archiveFlags"] = int(template.flags)
            continue
        addition = ArchiveAddRequest.from_template(template, path, payloads[path])
        if resource["kind"] == "texture":
            # These are complete DDS files, not the template's PartialDDS
            # chunks. Store them raw (the OverlayFile default) and register their
            # full header/mips as documented by CDMW register_dds. Engine loading
            # remains unverified; do not copy storage flag 1 from partial DDS.
            addition.flags = 0
            resource["storagePolicy"] = "Complete DDS, raw unencrypted storage; no PartialDDS flag inherited"
        resource["archiveFlags"] = int(addition.flags)
        additions.append(addition)
    pathc_after = encode_pathc(table)
    name = overlay_directory_name(game)
    if (game / name).exists() or name in {record.name for record in records}:
        raise ValueError("Allocated overlay directory is already occupied")
    # The pinned writer delegates >64KiB PAZ checksums to a separately bundled
    # native helper. Use its own reviewed Python checksum algorithm in process;
    # no helper download, game call or change to the fixed source tree is needed.
    def reference_checksum(data: bytearray, *, stop_event: object = None) -> int:
        if len(data) > RESOURCE_LIMIT * FILE_LIMIT:
            raise ValueError("Overlay payload exceeds the rehearsal size limit")
        return calculate_pa_checksum(bytes(data))

    with patch("cdmw.core.archive_overlay._payload_checksum", reference_checksum):
        preparation = prepare_overlay_install(requests, additions, package_root=game,
                                             meta_files=(("meta/0.pathc", pathc_after),), directory_name=name)
    if preparation.carried_forward_paths or set(preparation.all_paths) != set(payloads):
        raise ValueError("Unexpected carried-forward overlay resources")
    mounts = audit_mounts(papgt_before, preparation.papgt_after, name, preparation.pamt_bytes)
    registry = audit_registry(pathc_before, pathc_after, textures)
    # Stop before publication if an installed resource/index or candidate changed.
    if papgt_path.read_bytes() != papgt_before or pathc_path.read_bytes() != pathc_before:
        raise ValueError("Native metadata changed during overlay rehearsal")
    for relative, expected in index_hashes.items():
        if native.file_hash(game / relative) != expected:
            raise ValueError("Native archive index changed during overlay rehearsal")
    if any((game / name / "0.pamt").exists() for name in missing_optional):
        raise ValueError("Optional archive installation changed during overlay rehearsal")
    for template_path, expected in template_payloads.items():
        template = templates[template_path]
        actual = _decode_archive_entry_data(template, read_archive_entry_raw_data(template))[0]
        if actual != expected:
            raise ValueError("Native template payload changed during overlay rehearsal")
    for resource in resources:
        if native.file_hash(ROOT / resource["localFile"]) != resource["sha256"]:
            raise ValueError("Candidate changed during overlay rehearsal")
    for relative, expected in inputs.items():
        if native.file_hash(ROOT / relative) != expected:
            raise ValueError("Candidate report changed during overlay rehearsal")
    if replacement_snapshot:
        from prepare_steve_orientation import verify_snapshot
        verify_snapshot(replacement_snapshot)
    files = {f"package/{name}/0.pamt": preparation.pamt_bytes,
             f"package/{name}/0.paz": preparation.paz_bytes,
             "metadata-before/0.papgt": papgt_before, "metadata-before/0.pathc": pathc_before,
             "metadata-after/0.papgt": preparation.papgt_after, "metadata-after/0.pathc": pathc_after}
    report_file = "reports/overlay-report.json"
    preflight_outputs(output, [*files, report_file])
    # Audit an owned build-only staging directory before replacing any published
    # file. A bad package or report path cannot leave an old report with a new PAZ.
    with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="overlay-stage-") as temporary:
        stage = native.output_directory(Path(temporary))
        publish(stage, files)
        package = audit_package(stage / "package" / name, resources, payloads)
    report = {"schemaVersion": 1, "supportedExeSha256": native.EXE_SHA256,
              "cdmw": provenance, "directoryName": name, "resources": resources,
              "candidateReports": inputs, "sourceIndexes": index_hashes,
              "absentOptionalMountedDirectories": missing_optional,
              "checksumImplementation": "Fixed CDMW calculate_pa_checksum, in-process Python",
              "mountAudit": mounts, "registryAudit": registry, "packageAudit": package,
              "files": {relative: native.sha256(data) for relative, data in files.items()},
              "integration": {"installed": False, "nativeRenderable": False,
                              "prefabLoadVerified": False, "collisionVerified": False},
              "limitations": ["Only a local archive/registry rehearsal; no game files were written.",
                              "Resource decoding and registry consistency do not prove engine rendering or companion compatibility.",
                              "Installation needs a fresh preflight, exact metadata backups, ownership receipt and tested restoration.",
                              "Derived game resources must remain local and must not be uploaded."]}
    if replacement_paths:
        report["replacementPaths"] = sorted(replacement_paths)
        report["replacementScope"] = "Temporary shadow of the fixed Kliff mesh-parameter file; all consumers may observe it, not an actor-local override"
        if part_table_report is not None:
            report["replacementScope"] = (
                "Temporary shadow of exactly replacementPaths: the fixed Kliff mesh parameters, "
                "the global part-prefab table with two private body/head registrations"
                + (", and one explicitly selected shared Macduff appearance" if initial_appearance_report is not None else "")
                + "; all consumers may observe these resources, not an actor-local override")
    files[report_file] = json.dumps(report, ensure_ascii=False, indent=2).encode()
    publish(output, files)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/native-asset-overlay")
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    game = args.game_root
    if game is None:
        game = Path(json.loads((ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
    try:
        result = prepare(game, args.report, args.output, args.cdmw_source, args.deps)
    except (OSError, ValueError, ImportError, KeyError, TypeError, struct.error) as error:
        raise SystemExit(f"Asset overlay rehearsal stopped: {error}") from error
    print(json.dumps({key: result[key] for key in ("directoryName", "mountAudit", "registryAudit", "packageAudit", "integration")}, indent=2))


if __name__ == "__main__":
    main()
