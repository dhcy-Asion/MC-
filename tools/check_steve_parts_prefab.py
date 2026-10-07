"""Check fixed private component clones with raw parsing and real reconstruction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import prepare_steve_parts_prefab as parts


# These positions/bytes are from the SHA-pinned originals, not the new writer.
LAYOUT = {
    "body": (1591, 1604, 1782, 1677, 1758, "0200000800000000", "00020000000000000000000000", "0300280c00010000"),
    "head": (1689, 1702, 1916, 1775, 1869, "0200001000000000", "00080000000000000000000000", "0300285800010000"),
}


def independent_single(data, kind):
    """Read the exact single-component grammar without CDMW or writer helpers."""
    blob, _, _, _, _, root, reference, header = LAYOUT[kind]
    if struct.unpack_from("<I", data, blob-24)[0] != len(data):
        raise ValueError("file size")
    if struct.unpack_from("<II", data, blob-8) != (blob, len(data)-blob):
        raise ValueError("blob extent")
    pos = blob
    def take(size):
        nonlocal pos
        result = data[pos:pos+size]
        pos += size
        if len(result) != size:
            raise ValueError("truncated")
        return result
    def expect(value):
        if take(len(value)) != value:
            raise ValueError("fixed grammar bytes")
    def u32():
        return struct.unpack("<I", take(4))[0]
    def text():
        n = u32()
        if not 0 < n <= 256:
            raise ValueError("string extent")
        return take(n).decode("ascii")
    def pointer(owner=None):
        raw_owner = take(8)
        if owner is not None and raw_owner != owner:
            raise ValueError("pointer owner")
        target = u32()
        if target != pos:
            raise ValueError("pointer self position")
        return target, raw_owner
    expect(bytes.fromhex(root))
    expect(b"\0"+struct.pack("<I", 1))
    expect(bytes.fromhex(reference))
    expect(bytes.fromhex(header))
    name_target, owner = pointer()
    expect(b"\0\0\1\0\0\0")
    name = text()
    expect(bytes.fromhex("01010001030000"))
    mesh_target, _ = pointer(b"\xff"*8)
    expect(b"\0"*4)
    mesh = text()
    at = pos
    if u32() != at-mesh_target:
        raise ValueError("mesh footer")
    expect(bytes.fromhex("01010000020000"))
    pointer(b"\xff"*8)
    expect(struct.pack("<II", 0, 4))
    expect(bytes.fromhex("cdcc4c3d"))
    tag = text()
    script = text() if kind == "head" else None
    at = pos
    if u32() != at-name_target:
        raise ValueError("name footer")
    expect(b"\1")
    if pos != len(data):
        raise ValueError("extra component or trailer")
    return {"name": name, "mesh": mesh, "tag": tag, "script": script, "owner": owner.hex()}


class PrivatePrefabChecks(unittest.TestCase):
    output = parts.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        parts.native.load_cdmw(parts.ROOT / "build/cdmw-fixed-source", parts.ROOT / "build/cdmw-deps")
        cls.output = parts.native.output_directory(cls.output)
        cls.report_raw = (cls.output / parts.REPORT_NAME).read_bytes()
        cls.report = json.loads(cls.report_raw)
        cls.source, cls.candidates = {}, {}
        cls.snapshot = {}
        for kind, spec in parts.PARTS.items():
            cls.source[kind] = parts.read_fixed(cls.output / ("template/"+spec["template"]), spec["sha256"], cls.snapshot)
            cls.candidates[kind] = (cls.output / ("resources/"+spec["target"])).read_bytes()
        cls.descriptor = parts.read_fixed(cls.output / ("template/"+parts.DESCRIPTOR_TEMPLATE), parts.DESCRIPTOR_SHA256, cls.snapshot)

    def test_01_fixed_source_and_manifest_inventory_do_not_claim_runtime(self):
        self.assertEqual(len(self.report["candidateResources"]), 3)
        self.assertEqual(len(self.report["files"]), 6)
        self.assertEqual(self.report["requiredExternalMeshes"], [s["targetMesh"] for s in parts.PARTS.values()])
        for relative, digest in self.report["files"].items():
            self.assertEqual(parts.native.file_hash(self.output / relative), digest)
        for row in self.report["candidateResources"]:
            self.assertEqual(row["sha256"], self.report["files"][row["localFile"]])
        self.assertTrue(self.report["integration"])
        self.assertTrue(all(x is False for x in self.report["integration"].values()))
        self.assertEqual(self.report["supportedExeSha256"], parts.native.EXE_SHA256)
        self.assertTrue(any("runtime uniqueness" in text and "unverified" in text for text in self.report["limitations"]))

    def test_02_independent_raw_grammar_preserves_names_shrink_and_empty_skeleton(self):
        for kind, spec in parts.PARTS.items():
            got = independent_single(self.candidates[kind], kind)
            self.assertEqual(got["name"], spec["names"][0])
            self.assertEqual(got["mesh"], spec["targetMesh"])
            self.assertEqual(got["tag"], "Nude")
            self.assertEqual(got["script"], "breath_effect_basic" if kind == "head" else None)
            self.assertEqual(len(self.candidates[kind]), 1792 if kind == "body" else 1918)
            for discarded in spec["names"][1:]:
                self.assertNotIn(discarded.encode(), self.candidates[kind])

    def test_03_all_original_name_footers_are_verified_before_tail_extraction(self):
        for kind, data in self.source.items():
            d, rows = parts.strict_layout(data)
            self.assertEqual(len(rows), len(parts.PARTS[kind]["names"]))
            for row, obj in zip(rows, d.objects):
                self.assertEqual(row["name"], obj.name)
                self.assertEqual(struct.unpack_from("<I", data, row["fieldOffset"])[0], row["length"])
            self.assertEqual(rows[0]["length"], 145 if kind == "body" else 181)

    def test_04_independent_byte_reconstruction_changes_only_proven_fields(self):
        # Direct bounded byte construction is independent of CDMW resize/path
        # writers. In particular, retain FIRST footer, not the old final footer.
        for kind, spec in parts.PARTS.items():
            source = self.source[kind]
            blob, first, end, mesh, skeleton, *_ = LAYOUT[kind]
            old, new = spec["sourceMesh"].encode(), spec["targetMesh"].encode()
            delta = len(new)-len(old)
            self.assertEqual(source[mesh+4:mesh+4+len(old)], old)
            expected = bytearray(source[:mesh]+struct.pack("<I", len(new))+new+source[mesh+4+len(old):end+4]+source[-1:])
            for offset, value in ((blob-24, len(expected)), (blob-4, len(expected)-blob),
                                  (first-4, 1), (mesh+4+len(new), len(new)+8),
                                  (skeleton+delta, skeleton+delta+4), (len(expected)-5, end-(first+33)+delta)):
                struct.pack_into("<I", expected, offset, value)
            self.assertEqual(bytes(expected), self.candidates[kind])

    def test_05_cdmw_no_edit_and_variable_length_path_inverse_are_exact(self):
        from cdmw.core.prefab_binary_edit import rewrite_prefab_paths
        for kind, spec in parts.PARTS.items():
            candidate = self.candidates[kind]
            self.assertEqual(rewrite_prefab_paths(candidate, {}).data, candidate)
            reverted = rewrite_prefab_paths(candidate, {spec["targetMesh"]: spec["sourceMesh"]})
            original = self.source[kind]
            blob, first, end, *_ = LAYOUT[kind]
            restored = bytearray(reverted.data[:-1]+original[end+4:-1]+reverted.data[-1:])
            for at in (blob-24, blob-4, first-4):
                restored[at:at+4] = original[at:at+4]
            self.assertEqual(bytes(restored), original)
            self.assertEqual(parts.build_part(original, kind)[0], candidate)

    def test_06_cdmw_naive_tail_removal_is_rejected_despite_complete_walk(self):
        from cdmw.core.prefab_array_edit import remove_prefab_element
        from cdmw.core.prefab_binary import decode_prefab_binary
        for kind, raw in self.source.items():
            for index in reversed(range(1, len(parts.PARTS[kind]["names"]))):
                raw = remove_prefab_element(raw, 0, index).data
            self.assertTrue(decode_prefab_binary(raw).walk_complete)
            with self.assertRaisesRegex(ValueError, "name-pointee footer"):
                parts.strict_layout(raw)
            with self.assertRaisesRegex(ValueError, "name footer"):
                independent_single(raw, kind)

    def test_07_corrupt_footer_pointer_count_and_header_fail_independently(self):
        for kind, good in self.candidates.items():
            blob, first, *_ = LAYOUT[kind]
            for at in (len(good)-5, first+29, first-4, blob-24, blob-4):
                with self.subTest(kind=kind, offset=at):
                    bad = bytearray(good)
                    bad[at] ^= 1
                    with self.assertRaises(ValueError):
                        parts.strict_layout(bytes(bad))
                    with self.assertRaises(ValueError):
                        independent_single(bytes(bad), kind)

    def test_08_source_mutation_or_wrong_component_template_is_rejected(self):
        for kind, data in self.source.items():
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                parts.build_part(data+b"\0", kind)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            parts.build_part(self.source["body"], "head")
        with self.assertRaisesRegex(ValueError, "Only fixed"):
            parts.build_part(self.source["body"], "hair")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            parts.descriptor_audit(self.descriptor.replace(b"1.02571", b"1.00000"))

    def test_09_current_descriptor_is_byte_identical_without_fit_claims(self):
        candidate = (self.output / ("resources/"+parts.DESCRIPTOR_PATH)).read_bytes()
        self.assertEqual(candidate, self.descriptor)
        self.assertIn(b"cd_phm_00_nude_01_0002.pabc", candidate)
        self.assertIn(b"macduff.hkt", candidate)
        audit = self.report["audits"]["bodyDescriptor"]
        self.assertTrue(audit["byteIdenticalCopy"])
        self.assertFalse(audit["candidateMeshFitVerified"])
        self.assertFalse(audit["currentVariationDeformationVerified"])
        self.assertFalse(any("head" in r["virtualPath"] and r["kind"] == "prefabDescriptor" for r in self.report["candidateResources"]))

    def test_10_output_does_not_overwrite_original_or_existing_files(self):
        with tempfile.TemporaryDirectory(prefix="parts-prefab-check-", dir=parts.ROOT / "build") as temporary:
            out = Path(temporary)
            sentinel = out / "keep.txt"
            sentinel.write_bytes(b"keep")
            with self.assertRaisesRegex(ValueError, "already exists"):
                parts.prepare(parts.DEFAULT_INPUT, parts.DEFAULT_DESCRIPTOR, out, parts.ROOT / "build/cdmw-fixed-source", parts.ROOT / "build/cdmw-deps")
            self.assertEqual(sentinel.read_bytes(), b"keep")
            with self.assertRaisesRegex(ValueError, "overlaps"):
                parts.orientation.preflight(out / "nested", [out])
        with self.assertRaises(ValueError):
            parts.orientation.preflight(parts.ROOT / "artifacts/private-prefab", [])
        parts.orientation.verify_snapshot(self.snapshot)

    def test_11_failed_input_fingerprint_leaves_no_output_directory(self):
        with tempfile.TemporaryDirectory(prefix="parts-prefab-input-", dir=parts.ROOT / "build") as temporary:
            folder = Path(temporary)
            inputs = folder / "input"
            inputs.mkdir()
            (inputs / parts.PARTS["body"]["local"]).write_bytes(self.source["body"]+b"changed")
            output = folder / "output"
            # Already-loaded CDMW is protected by the production import guard;
            # bypass only re-import here so this check reaches the input gate.
            with mock.patch.object(parts.native, "load_cdmw", return_value=self.report["cdmw"]):
                with self.assertRaisesRegex(ValueError, "fingerprint"):
                    parts.prepare(inputs, parts.DEFAULT_DESCRIPTOR, output, parts.ROOT / "build/cdmw-fixed-source", parts.ROOT / "build/cdmw-deps")
            self.assertFalse(output.exists())

    def test_12_real_fresh_rebuild_matches_every_byte_and_preserves_sources(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for independent reconstruction")
        with tempfile.TemporaryDirectory(prefix="parts-prefab-rebuild-", dir=parts.ROOT / "build") as temporary:
            output = Path(temporary) / "fresh"
            result = subprocess.run([sys.executable, "-B", str(parts.ROOT / "tools/prepare_steve_parts_prefab.py"), "--output", str(output)],
                                    cwd=parts.ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / parts.REPORT_NAME).read_bytes(), self.report_raw)
            for relative in self.report["files"]:
                self.assertEqual((output / relative).read_bytes(), (self.output / relative).read_bytes())
        parts.orientation.verify_snapshot(self.snapshot)

    def test_13_real_fixed_archive_extraction_matches_all_three_saved_templates(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild to check the installed game's fixed source index")
        extracted = parts.read_native_templates(parts.installed_game())
        self.assertEqual(extracted, {**{s["template"]: self.source[k] for k, s in parts.PARTS.items()},
                                     parts.DESCRIPTOR_TEMPLATE: self.descriptor})

    def test_14_bad_exe_or_index_stops_before_archive_parsing(self):
        from cdmw.core import archive_format
        for values in (("0"*64,), (parts.native.EXE_SHA256, "0"*64)):
            with mock.patch.object(parts.native, "file_hash", side_effect=values), mock.patch.object(archive_format, "parse_archive_pamt") as parser:
                with self.assertRaisesRegex(ValueError, "Unsupported EXE or source archive index"):
                    parts.read_native_templates(parts.ROOT / "build/not-a-mounted-game")
                parser.assert_not_called()

    def test_15_decoded_archive_payload_has_its_own_exact_fingerprint_gate(self):
        from cdmw.core import archive_format, archive_extraction
        spec = parts.PARTS["body"]
        entry = SimpleNamespace(paz_file=str(self.output / "template" / spec["template"]))
        with mock.patch.object(parts.native, "file_hash", side_effect=(parts.native.EXE_SHA256, parts.INDEX_SHA256)), \
                mock.patch.object(archive_format, "parse_archive_pamt", return_value=[]), \
                mock.patch.object(parts.native, "select_unique_entries", return_value={spec["template"]: entry}), \
                mock.patch.object(archive_extraction, "read_archive_entry_raw_data", return_value=b"wrong"), \
                mock.patch.object(archive_extraction, "_decode_archive_entry_data", return_value=(b"wrong", "", False)):
            with self.assertRaisesRegex(ValueError, "payload fingerprint"):
                parts.read_native_templates(parts.ROOT / "build/not-a-mounted-game")

    def test_16_source_index_change_after_extraction_is_rejected(self):
        from cdmw.core import archive_format, archive_extraction
        payloads = {**{s["template"]: self.source[k] for k, s in parts.PARTS.items()}, parts.DESCRIPTOR_TEMPLATE: self.descriptor}
        entries = {p: SimpleNamespace(path=p, paz_file=str(self.output / "template" / p)) for p in payloads}
        with mock.patch.object(parts.native, "file_hash", side_effect=(parts.native.EXE_SHA256, parts.INDEX_SHA256, parts.native.EXE_SHA256, "0"*64)), \
                mock.patch.object(archive_format, "parse_archive_pamt", return_value=[]), \
                mock.patch.object(parts.native, "select_unique_entries", return_value=entries), \
                mock.patch.object(archive_extraction, "read_archive_entry_raw_data", side_effect=lambda entry: payloads[entry.path]), \
                mock.patch.object(archive_extraction, "_decode_archive_entry_data", side_effect=lambda entry, data: (data, "", False)):
            with self.assertRaisesRegex(ValueError, "Unsupported EXE or source archive index"):
                parts.read_native_templates(parts.ROOT / "build/not-a-mounted-game")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=parts.DEFAULT_OUTPUT)
    p.add_argument("--rebuild", action="store_true")
    a = p.parse_args()
    PrivatePrefabChecks.output, PrivatePrefabChecks.rebuild = a.output, a.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PrivatePrefabChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
