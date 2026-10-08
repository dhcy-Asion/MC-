"""Append two private Steve stems to the fixed native part-prefab table offline.

The original part/head rows stay in their original order and retain every byte.
Only the two counts and four appended rows differ. The new part rows declare
only the components retained in the private prefabs; descriptor rows keep the
donor metadata. This does not establish that the engine loaded Steve.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import struct

import prepare_native_steve as native
import prepare_steve_orientation as orientation
from prepare_steve_prefab import strict_json

ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT/"build/steve-part-table-v2"
REPORT_NAME = "steve-part-table-report.json"
VARIANT = "steve-private-body-head-part-prefab-table-probe-v2"
TABLE_PATH = "character/bin__/partprefabtable.pappt"
SOURCE_SHA256 = "d6947dcb57d32e0503704da28edf4645baaa8faad8fbd47d09a8a8832686abed"
SOURCE_SIZE = 2130295
INDEX_SHA256 = "c561ae348ba6dea65b0460686dec089b65291bbbeec439643d42bc5f4ead05b9"
ARCHIVE_FLAGS = 50
SOURCE_PART_COUNT, SOURCE_HEAD_COUNT = 15566, 2630
FORMAT_SOURCE = "cdmw/core/pappt_format.py"
FORMAT_SOURCE_SHA256 = "50585868bace762cccb294ec8ef9db3fc59da848c43cbd68610387f0ae47d52c"
CLONES = (
    {"original": "cd_phm_00_nude_01_0002_macduff", "private": "crimsonmc_steve_body_1_21_1", "folder": "1_pc/01_phm/nude",
     "parts": ["CD_Nude", "CD_Underwear"], "privateParts": ["CD_Nude"]},
    {"original": "cd_phm_00_head_00_0001_macduff", "private": "crimsonmc_steve_head_1_21_1", "folder": "1_pc/01_phm/head/head",
     "parts": ["CD_Head", "CD_EyeLeft", "CD_EyeRight", "CD_Eyebrows", "CD_Eyelashes", "CD_Tooth", "CD_Nude_Hair"],
     "privateParts": ["CD_Head"]},
)
INTEGRATION = {key: False for key in ("installed", "runtimePartTableLoaded", "privatePrefabsResolved", "appearanceApplied",
    "steveVisible", "actorLocal", "animationVerified", "equipmentVerified", "restorationVerified")}


class Reader:
    def __init__(self, data):
        if not isinstance(data, bytes) or not 16 <= len(data) <= SOURCE_SIZE+4096:
            raise ValueError("PAPPT buffer exceeds the bounded native table size")
        self.data, self.pos = data, 0

    def take(self, count):
        if not 0 <= count <= len(self.data)-self.pos:
            raise ValueError("PAPPT field runs past the bounded table")
        start = self.pos
        self.pos += count
        return self.data[start:self.pos]

    def u8(self):
        return self.take(1)[0]

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def string(self):
        length = self.u8()
        if not length:
            raise ValueError("PAPPT string length must include its NUL")
        raw = self.take(length)
        if raw[-1:] != b"\0" or b"\0" in raw[:-1]:
            raise ValueError("PAPPT string has invalid NUL termination")
        try:
            return raw[:-1].decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("PAPPT string is not UTF-8") from error


def parse_table(data):
    """Independent bounded parser for only this fixed tag-01 native layout."""
    reader = Reader(data)
    reserved = reader.take(8)
    if reserved != b"\0"*8:
        raise ValueError("PAPPT reserved header differs")
    count = reader.u32()
    if not 1 <= count <= 20000:
        raise ValueError("PAPPT part count exceeds bounds")
    records = []
    for _ in range(count):
        start = reader.pos
        stem = reader.string()
        stem_end = reader.pos
        folder, sockets = reader.string(), reader.string()
        if reader.u8() != 1:
            raise ValueError("PAPPT per-record tag is not the fixed 01 layout")
        extra, flag, part_count = reader.string(), reader.u8(), reader.u8()
        parts = [{"name": reader.string(), "flag": reader.u8()} for _ in range(part_count)]
        records.append({"start": start, "end": reader.pos, "stemEnd": stem_end, "stem": stem, "folder": folder,
                        "sockets_path": sockets, "extra": extra, "flag": flag, "parts": parts})
    head_count_offset = reader.pos
    head_count = reader.u32()
    if not 1 <= head_count <= 4096:
        raise ValueError("PAPPT head count exceeds bounds")
    heads = []
    for _ in range(head_count):
        start = reader.pos
        stem = reader.string()
        stem_end = reader.pos
        folder = reader.string()
        heads.append({"start": start, "end": reader.pos, "stemEnd": stem_end, "stem": stem, "folder": folder})
    if reader.pos != len(data):
        raise ValueError("PAPPT has unconsumed trailing bytes")
    return {"records": records, "headRecords": heads, "headCountOffset": head_count_offset}


def semantic(row):
    return {key: value for key, value in row.items() if key not in ("start", "end", "stemEnd")}


def unique_row(rows, stem):
    matches = [row for row in rows if row["stem"] == stem]
    if len(matches) != 1:
        raise ValueError("PAPPT original stem is missing or ambiguous")
    return matches[0]


def validate_source(source):
    if len(source) != SOURCE_SIZE or native.sha256(source) != SOURCE_SHA256:
        raise ValueError("PAPPT source fingerprint differs")
    parsed = parse_table(source)
    if (len(parsed["records"]), len(parsed["headRecords"])) != (SOURCE_PART_COUNT, SOURCE_HEAD_COUNT):
        raise ValueError("PAPPT source counts differ")
    for clone in CLONES:
        if any(row["stem"].casefold() == clone["private"].casefold() for section in ("records", "headRecords") for row in parsed[section]):
            raise ValueError("PAPPT private stem already exists")
        part, head = (unique_row(parsed[section], clone["original"]) for section in ("records", "headRecords"))
        expected = {"stem": clone["original"], "folder": clone["folder"], "sockets_path": "", "extra": "", "flag": 0,
                    "parts": [{"name": name, "flag": 1} for name in clone["parts"]]}
        if semantic(part) != expected or semantic(head) != {"stem": clone["original"], "folder": clone["folder"]}:
            raise ValueError("PAPPT original body/head metadata contract differs")
    return parsed


def clone_row(source, row, stem, part_names=None):
    encoded = stem.encode("utf-8")+b"\0"
    if not 1 < len(encoded) <= 255 or b"\0" in encoded[:-1] or "/" in stem or "\\" in stem:
        raise ValueError("PAPPT private stem is not a bounded bare name")
    prefix = bytes([len(encoded)])+encoded
    if part_names is None:
        return prefix+source[row["stemEnd"]:row["end"]]
    if not part_names or len(set(part_names)) != len(part_names):
        raise ValueError("PAPPT private parts must be nonempty and unique")
    reader = Reader(source)
    reader.pos = row["stemEnd"]
    reader.string(), reader.string()  # Folder and sockets stay byte-identical.
    reader.u8(), reader.string(), reader.u8()  # Tag, extra and record flag.
    prefix += source[row["stemEnd"]:reader.pos]
    count = reader.u8()
    slots = {}
    for _ in range(count):
        start = reader.pos
        name = reader.string()
        reader.u8()
        if name in slots:
            raise ValueError("PAPPT source has duplicate part slots")
        slots[name] = source[start:reader.pos]
    if reader.pos != row["end"] or any(name not in slots for name in part_names):
        raise ValueError("PAPPT private parts differ from the donor slots")
    return prefix+bytes([len(part_names)])+b"".join(slots[name] for name in part_names)


def private_part_record(row, clone):
    parts = {part["name"]: part for part in row["parts"]}
    return dict(semantic(row), stem=clone["private"],
                parts=[dict(parts[name]) for name in clone["privateParts"]])


def build_table(source):
    parsed = validate_source(source)
    part_rows = [clone_row(source, unique_row(parsed["records"], clone["original"]), clone["private"], clone["privateParts"]) for clone in CLONES]
    head_rows = [clone_row(source, unique_row(parsed["headRecords"], clone["original"]), clone["private"]) for clone in CLONES]
    offset = parsed["headCountOffset"]
    candidate = (source[:8]+struct.pack("<I", SOURCE_PART_COUNT+2)+source[12:offset]+b"".join(part_rows)
                 +struct.pack("<I", SOURCE_HEAD_COUNT+2)+source[offset+4:]+b"".join(head_rows))
    actual = parse_table(candidate)
    for section in ("records", "headRecords"):
        old, new = parsed[section], actual[section]
        if len(new) != len(old)+2 or any(source[a["start"]:a["end"]] != candidate[b["start"]:b["end"]] for a, b in zip(old, new)):
            raise ValueError("PAPPT rewrite altered original row bytes or order")
        for row, clone in zip(new[-2:], CLONES):
            expected = dict(semantic(unique_row(old, clone["original"])), stem=clone["private"])
            if section == "records":
                expected = private_part_record(unique_row(old, clone["original"]), clone)
            if semantic(row) != expected or sum(r["stem"]==clone["private"] for r in new) != 1:
                raise ValueError("PAPPT appended row changed metadata or shadowed a stem")
    restored = (candidate[:8]+struct.pack("<I", SOURCE_PART_COUNT)+candidate[12:actual["records"][-2]["start"]]
                +struct.pack("<I", SOURCE_HEAD_COUNT)+candidate[actual["headCountOffset"]+4:actual["headRecords"][-2]["start"]])
    if restored != source:
        raise ValueError("PAPPT inverse append is not byte-identical")
    return candidate


def verify_cdmw(source, candidate):
    """Cross-check the full independent parse and appended output with fixed CDMW."""
    from cdmw.core.pappt_format import parse_pappt, encode_pappt
    original = parse_pappt(source)
    if original.reserved != b"\0"*8 or original.tag_prefix != b"\x01" or encode_pappt(original) != source:
        raise ValueError("CDMW PAPPT original round trip differs")
    records = []
    for clone in CLONES:
        donor = next(row for row in original.records if row.stem==clone["original"])
        records.append(replace(donor, stem=clone["private"],
                               parts=tuple(next(slot for slot in donor.parts if slot.name==name) for name in clone["privateParts"])))
    heads = tuple(replace(next(row for row in original.head_records if row.stem==clone["original"]), stem=clone["private"]) for clone in CLONES)
    expected = replace(original, records=original.records+tuple(records), head_records=original.head_records+heads)
    if encode_pappt(expected) != candidate or parse_pappt(candidate) != expected:
        raise ValueError("CDMW PAPPT appended candidate differs")
    for raw, table in ((source, original), (candidate, expected)):
        own = parse_table(raw)
        for section, rows in (("records", table.records), ("headRecords", table.head_records)):
            # JSON normalizes CDMW tuples without discarding any fields.
            independent = [semantic(row) for row in own[section]]
            if independent != json.loads(json.dumps([asdict(row) for row in rows])):
                raise ValueError("Independent/CDMW full PAPPT decode differs")


def read_source(game):
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    exe, index = game/"bin64/CrimsonDesert.exe", game/"0009/0.pamt"
    def gate():
        for path in (game, exe, index):
            native.check_links(path)
        if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != INDEX_SHA256:
            raise ValueError("Unsupported EXE or original 0009 index")
    gate()
    entry = native.select_unique_entries(parse_archive_pamt(index), (TABLE_PATH,))[TABLE_PATH]
    if entry.flags != ARCHIVE_FLAGS:
        raise ValueError("PAPPT native archive storage flags differ")
    native.check_links(Path(entry.paz_file))
    source = _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
    validate_source(source)
    gate()
    return source


def make_report(source):
    parsed, candidate = validate_source(source), build_table(source)
    added = []
    for clone in CLONES:
        part, head = (unique_row(parsed[section], clone["original"]) for section in ("records", "headRecords"))
        added.append({"templateStem": clone["original"], "privateStem": clone["private"],
                      "partRecord": private_part_record(part, clone),
                      "omittedDonorParts": [name for name in clone["parts"] if name not in clone["privateParts"]],
                      "headRecord": dict(semantic(head), stem=clone["private"]),
                      "prefabPath": "character/bin__/prefab/"+clone["folder"]+"/"+clone["private"]+".prefab"})
    row = {"virtualPath": TABLE_PATH, "localFile": "replacements/"+TABLE_PATH, "sha256": native.sha256(candidate),
           "kind": "partPrefabTable", "templatePath": TABLE_PATH, "templateSha256": SOURCE_SHA256,
           "templateArchiveFlags": ARCHIVE_FLAGS, "archiveFlags": ARCHIVE_FLAGS}
    return {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256, "archiveIndexSha256": INDEX_SHA256,
            "candidateResources": [], "targetReplacements": [row], "sourceHashes": {TABLE_PATH: SOURCE_SHA256},
            "files": {"template/"+TABLE_PATH: SOURCE_SHA256, row["localFile"]: row["sha256"]},
            "audit": {"sourceBytes": len(source), "candidateBytes": len(candidate),
                      "partCounts": {"before": SOURCE_PART_COUNT, "after": SOURCE_PART_COUNT+2},
                      "headCounts": {"before": SOURCE_HEAD_COUNT, "after": SOURCE_HEAD_COUNT+2},
                      "reservedHex": "0000000000000000", "tagPrefixHex": "01", "originalRowsAndOrderByteIdentical": True,
                      "inverseByteIdentical": True, "onlyCountFieldsAndAppendedRowsChanged": True,
                      "addedRegistrations": added,
                      "crossCheck": {"cdmwCommit": native.CDMW_COMMIT, "formatSource": FORMAT_SOURCE,
                                     "formatSourceSha256": FORMAT_SOURCE_SHA256,
                                     "originalReencodeByteIdentical": True, "candidateReencodeByteIdentical": True,
                                     "independentFullDecodeMatches": True}},
            "integration": dict(INTEGRATION),
            "limitations": [
                "Offline v2 single-table candidate. New part rows declare only CD_Nude/CD_Head, matching the retained private prefab components; descriptor rows only rename their donor stems.",
                "All original rows, order, folder/socket/extra/flags/part slots and reserved/tag bytes remain intact; original stems are not overwritten.",
                "The two private prefab paths and their descriptors, meshes and materials are separate reviewed resources, not bundled here.",
                "This global table registration does not select an appearance app, refresh a controlled actor, or prove private prefab resolution/display in game.",
                "Skeleton merge, head scale, animation, equipment fit, hair/armor occlusion and restoration remain unverified by this candidate.",
                "No game files, process, native functions, save or inventory state are touched. Licensed payloads remain in ignored local build."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False)+"\n").encode()


def bounded_read(path, limit):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("PAPPT input is absent or exceeds its bounded size")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("PAPPT input changed beyond its bounded size")
    return raw


def load_candidate(report_path):
    """Pure admission -> (report, {virtualPath: payload}, snapshot), without CDMW."""
    path = native.output_directory(report_path)
    raw_report = bounded_read(path, 131072)
    report = strict_json(raw_report)
    template = native.output_directory(path.parent/("template/"+TABLE_PATH))
    source = bounded_read(template, SOURCE_SIZE)
    expected = make_report(source)
    if report != expected or raw_report != report_bytes(expected):
        raise ValueError("PAPPT report differs from the exact additive single-table contract")
    payload_path = native.output_directory(path.parent/expected["targetReplacements"][0]["localFile"])
    candidate = bounded_read(payload_path, SOURCE_SIZE+4096)
    if candidate != build_table(source):
        raise ValueError("PAPPT candidate differs from the exact four appended rows")
    snapshot = {path: raw_report, template: source, payload_path: candidate}
    orientation.verify_snapshot(snapshot)
    return report, {TABLE_PATH: candidate}, snapshot


def prepare(game, output, source, deps):
    protected = [game, source, deps, *(ROOT/("build/"+name) for name in (
        "steve-part-table", "steve-assembly", "steve-appearance", "steve-head-descriptor", "steve-app-macduff-00000", "steve-app-macduff-00002"))]
    output = orientation.preflight(output, protected)
    native.load_cdmw(source, deps)
    if native.file_hash(source/FORMAT_SOURCE) != FORMAT_SOURCE_SHA256:
        raise ValueError("Fixed CDMW PAPPT implementation differs")
    original = read_source(game)
    candidate = build_table(original)
    verify_cdmw(original, candidate)
    report = make_report(original)
    native.verify_source(source)
    if read_source(game) != original:
        raise ValueError("Original PAPPT changed before publication")
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for relative, payload in {"template/"+TABLE_PATH: original, "replacements/"+TABLE_PATH: candidate, REPORT_NAME: report_bytes(report)}.items():
        path = output/relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(payload)
    load_candidate(output/REPORT_NAME)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT/"build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT/"build/cdmw-deps")
    args = parser.parse_args()
    installation = ROOT/"runtime/installation.json"
    native.check_links(installation)
    game = args.game_root or Path(json.loads(installation.read_text(encoding="utf-8-sig"))["gameRoot"])
    report = prepare(game, args.output, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "targetReplacements": report["targetReplacements"],
                      "counts": {key: report["audit"][key] for key in ("partCounts", "headCounts")}, "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
